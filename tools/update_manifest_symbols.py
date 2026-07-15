#!/usr/bin/env python3
"""Replace broad manifest RPC symbols with concrete implementation methods."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path


def rpc_implementations(root: Path) -> dict[str, str]:
    implementations = {}
    for path in (root / "znn" / "api").rglob("*.py"):
        if path.name.startswith("_"):
            continue
        module = ".".join(path.relative_to(root).with_suffix("").parts)
        tree = ast.parse(path.read_text())
        for cls in (node for node in tree.body if isinstance(node, ast.ClassDef)):
            for method in (
                node for node in cls.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            ):
                for constant in ast.walk(method):
                    if isinstance(constant, ast.Constant) and isinstance(constant.value, str):
                        if constant.value.startswith(("ledger.", "stats.", "embedded.")):
                            implementations.setdefault(
                                constant.value, f"{module}.{cls.name}.{method.name}"
                            )
    implementations["ledger.subscribe"] = "znn.client.websocket.WsClient.subscribe"
    return implementations


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("rpc_spec", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    document = json.loads(args.manifest.read_text())
    rpc = json.loads(args.rpc_spec.read_text())
    implementations = rpc_implementations(root)
    for method in rpc["methods"]:
        document["capabilities"][method["id"]]["symbol"] = implementations[method["wireMethod"]]
    capabilities = document["capabilities"]
    capabilities["model.AccountBlock"]["symbol"] = (
        "znn.model.nom.account_block.AccountBlock"
    )
    capabilities["transaction.hashing"]["symbol"] = (
        "znn.model.nom.account_block.AccountBlock.get_hash"
    )
    capabilities["transaction.signing"]["symbol"] = (
        "znn.wallet.keypair.KeyPair.sign_hash"
    )
    args.manifest.write_text(json.dumps(document, indent=2) + "\n")


if __name__ == "__main__":
    main()
