"""Zenon ABI facade with strict canonical validation."""

from __future__ import annotations

import json
import re
from typing import Any

from eth_abi import decode as eth_decode
from eth_abi import encode as eth_encode

from znn.abi.utils import get_function_signature
from znn.model.primitives.address import Address
from znn.model.primitives.hash import Hash
from znn.model.primitives.token_standard import TokenStandard


_ARRAY = re.compile(r"^(.*)\[([0-9]*)\]$")
_FIXED_BYTES = re.compile(r"^bytes([0-9]+)$")


class ABIError(ValueError):
    """Invalid ABI declaration, input, or output."""


def _split_array(type_name: str) -> tuple[str, int | None] | None:
    match = _ARRAY.fullmatch(type_name)
    if not match:
        return None
    return match.group(1), int(match.group(2)) if match.group(2) else None


def _eth_type(type_name: str) -> str:
    array = _split_array(type_name)
    if array:
        element, length = array
        suffix = "[]" if length is None else f"[{length}]"
        return _eth_type(element) + suffix
    return {"address": "address", "hash": "bytes32", "tokenStandard": "uint80"}.get(
        type_name, type_name
    )


def _encode_value(type_name: str, value: Any) -> Any:
    array = _split_array(type_name)
    if array:
        element, length = array
        if not isinstance(value, (list, tuple)):
            raise ABIError(f"{type_name} requires an array value")
        if length is not None and len(value) != length:
            raise ABIError(f"{type_name} requires exactly {length} values")
        return [_encode_value(element, item) for item in value]

    fixed = _FIXED_BYTES.fullmatch(type_name)
    if fixed:
        required = int(fixed.group(1))
        if not 1 <= required <= 32:
            raise ABIError("bytesN width must be between 1 and 32")
        if not isinstance(value, bytes) or len(value) != required:
            raise ABIError(f"{type_name} requires exactly {required} bytes")
        return value
    if type_name == "address":
        core = bytes(value) if isinstance(value, Address) else bytes(Address.parse(value))
        return f"0x{core.hex()}"
    if type_name == "hash":
        if isinstance(value, Hash):
            return value.core
        if isinstance(value, str):
            return Hash.parse(value.removeprefix("0x")).core
        if isinstance(value, (bytes, bytearray)):
            return Hash(bytes(value)).core
        raise ABIError("hash requires a Hash, hexadecimal string, or 32-byte value")
    if type_name == "tokenStandard":
        core = bytes(value) if isinstance(value, TokenStandard) else bytes(TokenStandard.parse(value))
        return int.from_bytes(core, "big")
    return value


def _decode_value(type_name: str, value: Any) -> Any:
    array = _split_array(type_name)
    if array:
        return [_decode_value(array[0], item) for item in value]
    if type_name == "address":
        return str(Address.from_core(bytes.fromhex(value.removeprefix("0x"))))
    if type_name == "hash":
        return f"0x{bytes(value).hex()}"
    if type_name == "tokenStandard":
        return str(TokenStandard.from_core(int(value).to_bytes(10, "big")))
    return value


class ABI:
    def __init__(self, data: list[dict[str, Any]]):
        self.entries: list[dict[str, Any]] = []
        self.fn_name_map: dict[str, list[dict[str, str]]] = {}
        for entry in data:
            if entry.get("type") == "function":
                normalized = {"name": entry["name"], "inputs": entry.get("inputs", [])}
                self.entries.append(normalized)
                self.fn_name_map[entry["name"]] = normalized["inputs"]

    @staticmethod
    def from_json(json_data: str | list[dict[str, Any]]) -> "ABI":
        return ABI(json.loads(json_data) if isinstance(json_data, str) else json_data)

    def functions(self) -> list[dict[str, Any]]:
        records = []
        for entry in self.entries:
            signature = get_function_signature(entry["name"], entry["inputs"])
            records.append(
                {
                    "name": entry["name"],
                    "signature": signature,
                    "selector": f"0x{Hash.digest(signature.encode()).core[:4].hex()}",
                }
            )
        return records

    def encode(self, fn_name: str, fn_params: list[Any]) -> bytes:
        if fn_name not in self.fn_name_map:
            raise ABIError(f"Function {fn_name!r} not found in ABI")
        inputs = self.fn_name_map[fn_name]
        if len(inputs) != len(fn_params):
            raise ABIError(f"Expected {len(inputs)} parameters, received {len(fn_params)}")
        signature = get_function_signature(fn_name, inputs)
        selector = Hash.digest(signature.encode()).core[:4]
        types = [item["type"] for item in inputs]
        try:
            values = [_encode_value(t, v) for t, v in zip(types, fn_params, strict=True)]
            return selector + eth_encode([_eth_type(item) for item in types], values)
        except ABIError:
            raise
        except Exception as error:
            raise ABIError(str(error)) from error

    def decode(self, fn_name: str, data: bytes) -> dict[str, Any]:
        if fn_name not in self.fn_name_map:
            raise ABIError(f"Function {fn_name!r} not found in ABI")
        inputs = self.fn_name_map[fn_name]
        types = [item["type"] for item in inputs]
        try:
            values = eth_decode([_eth_type(item) for item in types], data[4:], strict=True)
        except Exception as error:
            raise ABIError(str(error)) from error
        try:
            return {
                item["name"]: _decode_value(item["type"], value)
                for item, value in zip(inputs, values, strict=True)
            }
        except ABIError:
            raise
        except Exception as error:
            raise ABIError(str(error)) from error

    def decode_call_data(self, data: bytes) -> tuple[str, dict[str, Any]]:
        selector = data[:4]
        for entry in self.entries:
            signature = get_function_signature(entry["name"], entry["inputs"])
            if Hash.digest(signature.encode()).core[:4] == selector:
                return entry["name"], self.decode(entry["name"], data)
        raise ABIError("Unknown function selector")
