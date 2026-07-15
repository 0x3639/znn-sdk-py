"""Portable znn-sdk-results/1 adapter for the stable conformance corpus."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import inspect
import json
import re
from pathlib import Path
from typing import Any

from znn.abi import ABI, ABIError
from znn.amount import from_base_units, to_base_units
from znn.api.ledger import LedgerApi
from znn.api.embedded.accelerator import AcceleratorApi
from znn.api.embedded.bridge import BridgeApi
from znn.api.embedded.htlc import HtlcApi
from znn.api.embedded.liquidity import LiquidityApi
from znn.api.embedded.pillar import PillarApi
from znn.api.embedded.plasma import PlasmaApi
from znn.api.embedded.sentinel import SentinelApi
from znn.api.embedded.spork import SporkApi
from znn.api.embedded.stake import StakeApi
from znn.api.embedded.swap import SwapApi
from znn.api.embedded.token import TokenApi
from znn.client.errors import JsonRpcError
from znn.client.http import HttpClient
from znn.client.protocol import build_request, normalize_notification, rpc_error, subscription_params
from znn.client.websocket import WsClient
from znn.embedded.definitions import (
    ACCELERATOR_ABI, BRIDGE_ABI, COMMON_ABI, HTLC_ABI, LIQUIDITY_ABI,
    PILLAR_ABI, PLASMA_ABI, SENTINEL_ABI, SPORK_ABI, STAKE_ABI,
    SWAP_ABI, TOKEN_ABI,
)
from znn.model.models import wire_model_round_trip
from znn.model.nom.account_block import AccountBlock
from znn.model.primitives.address import Address
from znn.model.primitives.hash import Hash
from znn.model.primitives.hash_height import HashHeight
from znn.model.primitives.token_standard import TokenStandard
from znn.pow import verify as verify_pow
from znn.wallet.keyfile import decrypt as decrypt_keyfile, needs_upgrade
from znn.wallet.keypair import KeyPair
from znn.wallet.keystore import KeyStore


CATALOGS = {
    "Accelerator": ACCELERATOR_ABI, "Bridge": BRIDGE_ABI, "Common": COMMON_ABI,
    "Htlc": HTLC_ABI, "Liquidity": LIQUIDITY_ABI, "Pillar": PILLAR_ABI,
    "Plasma": PLASMA_ABI, "Sentinel": SENTINEL_ABI, "Spork": SPORK_ABI,
    "Stake": STAKE_ABI, "Swap": SWAP_ABI, "Token": TOKEN_ABI,
}
API_CLASSES = {
    "accelerator": AcceleratorApi, "bridge": BridgeApi, "htlc": HtlcApi,
    "liquidity": LiquidityApi, "pillar": PillarApi, "plasma": PlasmaApi,
    "sentinel": SentinelApi, "spork": SporkApi, "stake": StakeApi,
    "swap": SwapApi, "token": TokenApi,
}


def _array_type(type_name: str):
    match = re.fullmatch(r"(.+)\[([0-9]*)\]", type_name)
    return (match.group(1), int(match.group(2)) if match.group(2) else None) if match else None


def _input(type_name: str, value: Any):
    array = _array_type(type_name)
    if array:
        return [_input(array[0], item) for item in value]
    if type_name == "bytes" or re.fullmatch(r"bytes[0-9]+", type_name):
        return bytes.fromhex(value.removeprefix("0x"))
    if type_name.startswith(("int", "uint")):
        return int(value)
    return value


def _output(type_name: str, value: Any):
    array = _array_type(type_name)
    if array:
        return [_output(array[0], item) for item in value]
    if isinstance(value, bytes):
        return f"0x{value.hex()}"
    if type_name.startswith(("int", "uint")):
        return str(value)
    return value


def _abi_case(case):
    operation, inputs = case["operation"], case["input"]
    if operation == "abi.selector":
        return Hash.digest(inputs["signature"].encode()).core[:4].hex()
    types = inputs.get("types") or [inputs["type"]]
    abi = ABI([{"type": "function", "name": "Probe", "inputs": [
        {"name": f"value{i}", "type": item} for i, item in enumerate(types)
    ]}])
    if operation in {"abi.encode", "abi.reject"}:
        values = [_input(types[i], value) if i < len(types) else value
                  for i, value in enumerate(inputs["values"])]
        if operation == "abi.reject":
            try:
                abi.encode("Probe", values)
                return False
            except ABIError:
                return True
        return f"0x{abi.encode('Probe', values)[4:].hex()}"
    data = bytes.fromhex(inputs["data"].removeprefix("0x"))
    if operation == "abi.decode-reject":
        try:
            abi.decode("Probe", bytes(4) + data)
            return False
        except ABIError:
            return True
    decoded = abi.decode("Probe", bytes(4) + data)
    values = [_output(t, decoded[f"value{i}"]) for i, t in enumerate(types)]
    return values[0] if len(values) == 1 else values


def _camel(name):
    head, *tail = name.split("_")
    return head + "".join(item.title() for item in tail)


def _builders():
    result = {}
    aliases = {
        ("pillar", "collectReward"): "collectRewards",
        ("sentinel", "collectReward"): "collectRewards",
        ("token", "mintToken"): "mint",
    }
    for namespace, cls in API_CLASSES.items():
        instance = cls()
        for name, method in inspect.getmembers(instance, inspect.ismethod):
            canonical = aliases.get((namespace, _camel(name)), _camel(name))
            result[f"builder.{namespace}.{canonical}"] = method
    return result


BUILDERS = _builders()


def _argument(parameter, value):
    annotation = parameter.annotation
    if annotation is Address:
        return Address.parse(value)
    if annotation is Hash:
        return Hash.parse(value.removeprefix("0x"))
    if annotation is TokenStandard:
        return TokenStandard.parse(value)
    if annotation is int:
        return int(value)
    return value


def _builder_case(case):
    method = BUILDERS[case["input"]["builder"]]
    parameters = list(inspect.signature(method).parameters.values())
    arguments = [_argument(p, v) for p, v in zip(parameters, case["input"]["arguments"], strict=True)]
    block = method(*arguments)
    return {"blockType": block.block_type, "toAddress": str(block.to_address),
            "amount": str(block.amount), "tokenStandard": str(block.token_standard),
            "dataHex": block.data.hex()}


def dispatch(case, transport_results=None):
    op, value = case["operation"], case["input"]
    if op.startswith("abi."):
        return _abi_case(case)
    if op == "hash.sha3-256":
        raw = value.get("utf8", "").encode() if "utf8" in value else bytes.fromhex(value["hex"])
        return str(Hash.digest(raw))
    if op == "address.from-core":
        return str(Address.from_core(bytes.fromhex(value["coreHex"])))
    if op == "address.from-public-key":
        return str(Address.from_public_key_hex(value["publicKeyHex"]))
    if op == "token-standard.from-core":
        return str(TokenStandard.from_core(bytes.fromhex(value["coreHex"])))
    if op == "hash-height.to-bytes":
        return HashHeight(Hash.parse(value["hash"]), int(value["height"])).to_bytes().hex()
    if op == "amount.to-base-units":
        return str(to_base_units(value["amount"], value["decimals"]))
    if op == "amount.from-base-units":
        return from_base_units(value["amount"], value["decimals"])
    if op == "wallet.from-private-key":
        pair = KeyPair(value["privateKeyHex"])
        return {"publicKeyHex": pair.public_key, "address": str(pair.address)}
    if op == "wallet.from-entropy":
        store = KeyStore.from_entropy(value["entropyHex"])
        return {"mnemonic": store.mnemonic,
                "addresses": [str(store.get_key_pair(index).address) for index in value["indices"]]}
    if op == "model.wire":
        return wire_model_round_trip(value["model"], value["json"])
    if op == "embedded.encode":
        name, raw_types = value["function"].split("(", 1)
        types = [] if not raw_types[:-1] else raw_types[:-1].split(",")
        params = [_input(t, v) for t, v in zip(types, value["values"], strict=True)]
        return f"0x{CATALOGS[value['contract']].encode(name, params).hex()}"
    if op == "embedded.build":
        return _builder_case(case)
    if op == "account-block.hash":
        return str(AccountBlock.from_json(value).get_hash())
    if op == "account-block.sign-hash":
        return KeyPair(value["privateKeyHex"]).sign_hash(Hash.parse(value["hash"])).hex()
    if op == "pow.verify":
        return verify_pow(value["hash"], value["difficulty"], value["nonce"])
    if op == "keyfile.decrypt":
        store = decrypt_keyfile(value["keyFile"], value["password"])
        return {"entropyHex": store.entropy, "baseAddress": str(store.get_key_pair().address),
                "needsUpgrade": needs_upgrade(value["keyFile"])}
    if op == "transport.request":
        return build_request(value["id"], value["method"], value["params"])
    if op == "transport.subscription-params":
        return subscription_params(value["topic"], value.get("address"))
    if op == "transport.subscription-notification":
        return normalize_notification(value)
    if op == "transport.error":
        return rpc_error(value["error"], value["method"], value["params"]).to_json()
    if op in {"transport.publish-null", "transport.pagination-error", "transport.reconnect"}:
        if transport_results is None or op not in transport_results:
            raise RuntimeError("live transport conformance fixture was not executed")
        result = transport_results[op]
        if isinstance(result, Exception):
            raise result
        return result
    raise NotImplementedError(op)


def _load_transport_fixture(vectors: Path):
    path = vectors.parent.parent / "tools" / "transport_fixture.py"
    if not path.is_file():
        raise FileNotFoundError(f"transport fixture not found at {path}")
    module_spec = importlib.util.spec_from_file_location("znn_spec_transport_fixture", path)
    if module_spec is None or module_spec.loader is None:
        raise ImportError(f"cannot load transport fixture from {path}")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


async def _exercise_transport(vectors: Path):
    fixture_module = _load_transport_fixture(vectors)
    fixture = fixture_module.TransportFixture()
    fixture.start()
    websocket = None
    try:
        http = HttpClient(fixture.http_url)
        ledger = LedgerApi(http)
        publish_result = await ledger.publish_raw_transaction(AccountBlock())
        try:
            await ledger.get_account_blocks_by_page(fixture_module.ADDRESS, 0, 1025)
        except JsonRpcError as error:
            pagination_result = {"code": error.code, "message": error.message}
        else:
            raise RuntimeError("oversized pagination request unexpectedly succeeded")

        websocket = WsClient(
            fixture.websocket_url, reconnect_interval=0.01, maximum_attempts=3
        )
        subscription = await websocket.subscribe(
            "accountBlocksByAddress", fixture_module.ADDRESS
        )
        await asyncio.wait_for(subscription.__anext__(), 2)
        update = await asyncio.wait_for(subscription.__anext__(), 2)
        reconnect_result = {
            "subscription": subscription.id,
            "updateHeight": update["height"],
        }
        return {
            "transport.publish-null": publish_result,
            "transport.pagination-error": pagination_result,
            "transport.reconnect": reconnect_result,
        }
    finally:
        if websocket is not None:
            await websocket.disconnect()
        fixture.close()


def run(vectors: Path):
    cases = []
    for path in sorted(vectors.glob("*.json")):
        cases.extend(json.loads(path.read_text())["cases"])
    transport_operations = {
        "transport.publish-null", "transport.pagination-error", "transport.reconnect"
    }
    transport_results = None
    if any(case["operation"] in transport_operations for case in cases):
        try:
            transport_results = asyncio.run(_exercise_transport(vectors))
        except Exception as error:
            transport_results = {operation: error for operation in transport_operations}
    results = []
    for case in cases:
        try:
            results.append({
                "id": case["id"],
                "actual": dispatch(case, transport_results=transport_results),
            })
        except Exception as error:
            results.append({"id": case["id"], "error": f"{type(error).__name__}: {error}"})
    from znn import __version__

    return {"format": "znn-sdk-results/1",
            "implementation": {"name": "znn-sdk", "version": __version__},
            "complete": len(results) == len(cases), "results": results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("vectors", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run(args.vectors)
    text = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(text + "\n")
    else:
        print(text)


if __name__ == "__main__":
    main()
