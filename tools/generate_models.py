#!/usr/bin/env python3
"""Generate field-aware Python wire models from the stable SDK model inventory."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SPECIAL_MODELS = {"AccountBlock", "Address", "Hash", "HashHeight", "TokenStandard"}


RUNTIME = r'''"""Field-aware JSON wire models generated from the stable SDK specification."""

from __future__ import annotations

import base64
import re
from collections.abc import Mapping
from copy import deepcopy
from enum import IntEnum

from znn.model._base64 import decode_model_base64
from znn.model.primitives.address import Address
from znn.model.primitives.hash import Hash
from znn.model.primitives.hash_height import HashHeight
from znn.model.primitives.token_standard import TokenStandard


_DECIMAL = re.compile(r"^-?(?:0|[1-9][0-9]*)$")
_MISSING = object()


def _get_path(value, path):
    current = value
    if path == "":
        return value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return _MISSING
        current = current[part]
    return current


def _set_path(value, path, item):
    if path == "":
        return item
    current = value
    parts = path.split(".")
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = item
    return value


def _default_value(text):
    if text is None:
        return _MISSING
    if text == "0":
        return 0
    if text == "{}":
        return {}
    if text == "[]":
        return []
    if text == "false":
        return False
    if text == "true":
        return True
    if re.fullmatch(r"-?[0-9]+n", text):
        return int(text[:-1])
    return _MISSING


def _decode_target(target, value, strict):
    if not strict and value in ({}, []):
        return deepcopy(value)
    if target == "Address":
        return Address.parse(value) if isinstance(value, str) else Address.from_json(value)
    if target == "Hash":
        return Hash.parse(value.removeprefix("0x")) if isinstance(value, str) else Hash.from_json(value)
    if target == "HashHeight":
        return HashHeight.from_json(value, strict=strict)
    if target == "TokenStandard":
        return TokenStandard.parse(value) if isinstance(value, str) else TokenStandard.from_json(value)
    if target == "AccountBlock":
        from znn.model.nom.account_block import AccountBlock
        return AccountBlock.from_json(
            value, strict=strict, require_response=strict
        )
    cls = MODEL_TYPES.get(target)
    if cls is None:
        raise ValueError(f"Unknown nested model {target!r}")
    if isinstance(cls, type) and issubclass(cls, IntEnum):
        return cls(value)
    return cls.from_json(value, strict=strict)


def _decode_field(field, value, strict):
    name, _key, wire_type, encoding, target, _required, _default, object_item = field
    if value is None:
        raise ValueError(f"{name} cannot be null")
    if wire_type == "decimal-string":
        if not isinstance(value, str) or not _DECIMAL.fullmatch(value):
            raise ValueError(f"{name} must be a canonical base-10 integer string")
        return int(value)
    if wire_type == "number":
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"{name} must be an integer")
        return value
    if wire_type == "boolean":
        if not isinstance(value, bool):
            raise TypeError(f"{name} must be a boolean")
        return value
    if wire_type == "string":
        if not isinstance(value, str):
            raise TypeError(f"{name} must be a string")
        if encoding == "hex-32":
            return Hash.parse(value.removeprefix("0x"))
        if encoding == "bech32-address":
            return Address.parse(value)
        if encoding == "bech32-token-standard":
            return TokenStandard.parse(value)
        if encoding == "base64":
            return decode_model_base64(value, name)
        return value
    if wire_type == "model":
        return _decode_target(target, value, strict)
    if wire_type == "array":
        if not isinstance(value, list):
            raise TypeError(f"{name} must be an array")
        return [_decode_target(target, item, strict) for item in value]
    if wire_type == "object":
        if not isinstance(value, dict):
            raise TypeError(f"{name} must be an object")
        if object_item:
            return {key: _decode_target(object_item, item, strict) for key, item in value.items()}
        return deepcopy(value)
    raise ValueError(f"Unsupported wire type {wire_type!r}")


def _encode_target(value):
    if isinstance(value, (Address, Hash, TokenStandard)):
        return str(value)
    if isinstance(value, HashHeight):
        return value.to_json()
    if isinstance(value, IntEnum):
        return int(value)
    if hasattr(value, "to_json"):
        return value.to_json()
    return deepcopy(value)


def _encode_field(field, value):
    _name, _key, wire_type, encoding, _target, _required, _default, _object_item = field
    if wire_type == "decimal-string":
        return str(value)
    if wire_type == "string":
        if encoding in {"hex-32", "bech32-address", "bech32-token-standard"}:
            return str(value)
        if encoding == "base64":
            return base64.b64encode(bytes(value)).decode()
        return value
    if wire_type == "model":
        return _encode_target(value)
    if wire_type == "array":
        return [_encode_target(item) for item in value]
    if wire_type == "object":
        return {key: _encode_target(item) for key, item in value.items()}
    return int(value) if isinstance(value, IntEnum) else value


class Model(Mapping):
    _fields = ()

    def __init__(self, **values):
        object.__setattr__(self, "_wire", {})
        object.__setattr__(self, "_values", {})
        names = {field[0] for field in self._fields}
        unknown = set(values) - names
        if unknown:
            raise TypeError(f"Unknown {type(self).__name__} fields: {sorted(unknown)}")
        self._values.update(values)

    @classmethod
    def from_json(cls, value, *, strict=True, nested_strict=None):
        root = len(cls._fields) == 1 and cls._fields[0][1] == ""
        if root:
            if not isinstance(value, list):
                raise TypeError(f"{cls.__name__} JSON must be an array")
        elif not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} JSON must be an object")
        instance = cls()
        object.__setattr__(instance, "_wire", deepcopy(value))
        for field in cls._fields:
            raw = _get_path(value, field[1])
            if raw is _MISSING:
                default = _default_value(field[6])
                if default is not _MISSING:
                    instance._values[field[0]] = default
                elif field[5] and strict:
                    raise ValueError(f"Missing required {cls.__name__}.{field[1]}")
                continue
            decode_strict = strict if nested_strict is None else nested_strict
            instance._values[field[0]] = _decode_field(field, raw, decode_strict)
        return instance

    def to_json(self):
        root = len(self._fields) == 1 and self._fields[0][1] == ""
        if root:
            field = self._fields[0]
            return _encode_field(field, self._values.get(field[0], []))
        result = deepcopy(self._wire) if isinstance(self._wire, dict) else {}
        for field in self._fields:
            if field[0] in self._values:
                _set_path(result, field[1], _encode_field(field, self._values[field[0]]))
        return result

    def __getattr__(self, name):
        values = object.__getattribute__(self, "_values")
        if name in values:
            return values[name]
        raise AttributeError(name)

    def __setattr__(self, name, value):
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        if name not in {field[0] for field in self._fields}:
            raise AttributeError(f"Unknown {type(self).__name__} field {name!r}")
        self._values[name] = value

    def __getitem__(self, key):
        if key in self._values:
            return self._values[key]
        for field in self._fields:
            if field[1] == key and field[0] in self._values:
                return self._values[field[0]]
        raise KeyError(key)

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __repr__(self):
        return f"{type(self).__name__}({self._values!r})"

    def __eq__(self, other):
        return type(self) is type(other) and self.to_json() == other.to_json()
'''


def field_tuple(field: dict) -> tuple:
    wire = field["wire"]
    target = wire.get("model") or wire.get("items")
    object_item = None
    if wire["type"] == "object":
        matches = re.findall(r":\s*([A-Za-z][A-Za-z0-9_]*)", field.get("sourceType", ""))
        object_item = matches[-1] if matches else None
    return (
        field["name"], wire.get("key", field["name"]), wire["type"],
        wire.get("encoding"), target, bool(field.get("required")),
        field.get("sourceDefault"), object_item,
    )


def generate(spec: Path) -> str:
    document = json.loads(spec.read_text())
    sections = [RUNTIME]
    for enum in document["enums"]:
        body = "\n".join(f"    {name} = {value}" for name, value in enum["values"].items())
        sections.append(f"\n\nclass {enum['name']}(IntEnum):\n{body}\n")
    schemas = {}
    for model in document["models"]:
        fields = tuple(field_tuple(field) for field in model.get("fields", []))
        schemas[model["name"]] = fields
        if model["name"] in SPECIAL_MODELS or model["name"] == "Model":
            continue
        sections.append(f"\n\nclass {model['name']}(Model):\n    _fields = {fields!r}\n")
    sections.append("\n\nfrom znn.model.nom.account_block import AccountBlock\n")
    model_names = [model["name"] for model in document["models"]]
    sections.append("\nMODEL_TYPES = {\n")
    for name in model_names:
        sections.append(f"    {name!r}: {name},\n")
    for enum in document["enums"]:
        sections.append(f"    {enum['name']!r}: {enum['name']},\n")
    sections.append("}\n")
    sections.append(f"\nWIRE_SCHEMAS = {schemas!r}\n")
    sections.append(r'''

def wire_model_round_trip(name, value):
    """Validate a spec wire fixture without weakening strict runtime primitives.

    The corpus uses placeholder strings for model-specific binary fields and for
    AccountBlock nonce, so those schema-only fixtures cannot be constructed as
    valid runtime primitives. All declared keys and wire types are still checked.
    """
    fields = WIRE_SCHEMAS.get(name)
    if fields is None:
        raise ValueError(f"Unknown wire model {name!r}")
    if name == "AccountBlock":
        fields = WIRE_SCHEMAS["AccountBlockTemplate"] + fields
    if name in SPECIAL_MODEL_NAMES:
        wire_type = type(f"_{name}Wire", (Model,), {"_fields": fields})
        return wire_type.from_json(value, strict=True, nested_strict=False).to_json()
    return MODEL_TYPES[name].from_json(value, strict=True, nested_strict=False).to_json()


SPECIAL_MODEL_NAMES = frozenset({"AccountBlock", "Address", "Hash", "HashHeight", "TokenStandard"})
''')
    return "".join(sections)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    parser.add_argument("--output", type=Path, default=Path("znn/model/models.py"))
    args = parser.parse_args()
    args.output.write_text(generate(args.spec))


if __name__ == "__main__":
    main()
