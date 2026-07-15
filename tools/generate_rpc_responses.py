#!/usr/bin/env python3
"""Generate RPC result-model routing from the stable SDK RPC inventory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


HEADER = '''"""RPC result routing generated from the stable SDK specification."""

from __future__ import annotations

import re

from znn.model.models import MODEL_TYPES


_DECIMAL = re.compile(r"^-?(?:0|[1-9][0-9]*)$")
'''


PARSER = '''

def parse_rpc_response(method, value):
    result = RPC_RESULTS.get(method)
    if result is None:
        return value
    result_type, nullable = result
    if value is None:
        if nullable or result_type == "null":
            return None
        raise ValueError(f"{method} returned null for a non-nullable result")
    if result_type == "AccountBlock":
        return MODEL_TYPES[result_type].from_json(value, require_response=True)
    if result_type in MODEL_TYPES:
        return MODEL_TYPES[result_type].from_json(value)
    if result_type == "decimal-string":
        if not isinstance(value, str) or not _DECIMAL.fullmatch(value):
            raise ValueError(f"{method} returned a non-canonical decimal string")
        return int(value)
    if result_type == "boolean" and not isinstance(value, bool):
        raise TypeError(f"{method} returned a non-boolean result")
    if result_type == "array" and not isinstance(value, list):
        raise TypeError(f"{method} returned a non-array result")
    if result_type == "subscription-id" and (
        not isinstance(value, str) or not value
    ):
        raise TypeError(f"{method} returned an invalid subscription ID")
    if result_type == "null":
        raise TypeError(f"{method} must return null")
    return value
'''


def generate(path: Path) -> str:
    document = json.loads(path.read_text())
    mapping = {
        method["wireMethod"]: (
            method["result"]["type"], bool(method["result"].get("nullable"))
        )
        for method in document["methods"]
    }
    return HEADER + f"\nRPC_RESULTS = {mapping!r}\n" + PARSER


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    parser.add_argument("--output", type=Path, default=Path("znn/api/_response.py"))
    args = parser.parse_args()
    args.output.write_text(generate(args.spec))


if __name__ == "__main__":
    main()
