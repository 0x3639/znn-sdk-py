#!/usr/bin/env python3
"""Generate deterministic Docusaurus references and LLM-readable artifacts."""

from __future__ import annotations

import argparse
import ast
import importlib
import inspect
import re
from enum import IntEnum
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEBSITE = ROOT / "documentation" / "website"
DOCS = WEBSITE / "docs"
STATIC = WEBSITE / "static"
LLMS_DIR = STATIC / "llms"
SITE_ROOT = "https://pyznn.0x3639.com"

API_MODULES = (
    "znn.api.ledger",
    "znn.api.stats",
    "znn.api.subscribe",
    "znn.api.embedded.accelerator",
    "znn.api.embedded.bridge",
    "znn.api.embedded.htlc",
    "znn.api.embedded.liquidity",
    "znn.api.embedded.pillar",
    "znn.api.embedded.plasma",
    "znn.api.embedded.sentinel",
    "znn.api.embedded.spork",
    "znn.api.embedded.stake",
    "znn.api.embedded.swap",
    "znn.api.embedded.token",
)

API_SUMMARIES = {
    "LedgerApi": "Account blocks, momentums, balances, and transaction publication.",
    "StatsApi": "Node operating-system, process, network, and synchronization state.",
    "SubscribeApi": "Canonical WebSocket subscription topics and normalized async iterators.",
    "AcceleratorApi": "Accelerator projects, phases, votes, donations, and updates.",
    "BridgeApi": "Bridge networks, wrap/unwrap requests, security, and administration.",
    "HtlcApi": "HTLC lookup, proxy-unlock policy, creation, reclaim, and unlock.",
    "LiquidityApi": "Liquidity state, rewards, stakes, security, and administration.",
    "PillarApi": "Pillar discovery, registration, delegation, rewards, and QSR management.",
    "PlasmaApi": "Plasma state, fusion entries, PoW requirements, fuse, and cancel.",
    "SentinelApi": "Sentinel discovery, registration, rewards, and QSR management.",
    "SporkApi": "Spork discovery, creation, and activation.",
    "StakeApi": "Stake entries, rewards, staking, cancellation, and collection.",
    "SwapApi": "Swap assets, legacy pillars, and asset retrieval.",
    "TokenApi": "Token discovery, issuance, minting, burning, and updates.",
}

LLMS_SECTIONS = {
    "Start here": (
        "installation",
        "json-rpc-client",
        "api",
        "models-and-primitives",
        "wallet",
    ),
    "Examples and troubleshooting": (
        "cookbook",
        "errors-and-troubleshooting",
    ),
    "Complete reference": (
        "api-reference",
        "model-reference",
        "conformance",
    ),
    "Optional": (
        "contributing",
        "llm-access",
    ),
}


def frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    marker = text.find("\n---\n", 4)
    if marker < 0:
        raise ValueError("unterminated Markdown front matter")
    values = {}
    for line in text[4:marker].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip().strip('"')
    return values, text[marker + 5 :]


def write_or_check(path: Path, content: str, check: bool) -> None:
    normalized = content.rstrip() + "\n"
    if check:
        if not path.exists() or path.read_text() != normalized:
            raise SystemExit(f"generated documentation is stale: {path.relative_to(ROOT)}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(normalized)


def format_signature(cls, name: str) -> str:
    method = getattr(cls, name)
    signature = inspect.signature(method)
    parameters = list(signature.parameters.values())
    if parameters and parameters[0].name in {"self", "cls"}:
        signature = signature.replace(parameters=parameters[1:])
    prefix = "async " if inspect.iscoroutinefunction(method) else ""
    return f"{prefix}{name}{signature}"


def class_source_metadata(cls) -> dict[str, dict[str, str]]:
    path = Path(inspect.getsourcefile(cls))
    tree = ast.parse(path.read_text())
    class_node = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == cls.__name__
    )
    metadata = {}
    for node in class_node.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        wire = ""
        for child in ast.walk(node):
            if (
                isinstance(child, ast.Constant)
                and isinstance(child.value, str)
                and child.value.startswith(("ledger.", "stats.", "embedded."))
            ):
                wire = child.value
                break
        doc = ast.get_docstring(node) or ""
        metadata[node.name] = {"wire": wire, "doc": doc.splitlines()[0] if doc else ""}
    return metadata


def method_kind(name: str, method, wire: str, doc: str) -> str:
    if name in {
        "subscribe_to",
        "to_momentums",
        "to_all_account_blocks",
        "to_account_blocks_by_address",
        "to_unreceived_account_blocks_by_address",
    }:
        return "Subscription helper"
    if name == "get_required_fusion_amount":
        return "Removed compatibility stub"
    if wire:
        return "RPC"
    if "alias" in doc.lower() or name in {"get_by_owner_address", "get_account_blocks_by_page"}:
        return "Compatibility alias"
    if inspect.iscoroutinefunction(method):
        return "Subscription helper"
    if name == "get_plasma_by_qsr":
        return "Local calculation"
    return "AccountBlock builder"


def method_result(kind: str, wire: str) -> str:
    if kind == "Subscription helper":
        return "Subscription"
    if kind == "Removed compatibility stub":
        return "Raises NotImplementedError"
    if wire:
        from znn.api._response import RPC_RESULTS

        declared = RPC_RESULTS.get(wire)
        if declared is None:
            return "Transport result"
        name, nullable = declared
        return f"{name}{' or null' if nullable and name != 'null' else ''}"
    if kind == "AccountBlock builder":
        return "AccountBlock"
    if kind == "Local calculation":
        return "int"
    return "Same as canonical method"


def generate_api_reference() -> str:
    lines = [
        "---",
        "sidebar_position: 9",
        "title: Complete API reference",
        "description: Exact constructors, method signatures, wire calls, and result types for every API facade.",
        "---",
        "",
        "# Complete API reference",
        "",
        "> Generated by `tools/generate_documentation.py`. Do not edit this page by hand.",
        "",
        "This reference is generated from the installed Python classes and the stable RPC result registry. "
        "Parameters are positional on the wire even when Python callers use keyword arguments.",
        "",
        "## Conventions",
        "",
        "- **RPC** methods perform I/O and return a validated typed result.",
        "- **AccountBlock builder** methods are synchronous, perform no I/O, and return an unsigned block.",
        "- **Subscription helper** methods require `WsClient` and return an async iterator.",
        "- Page indices are zero-based unless a method explicitly accepts a block height.",
        "- Decimal-string RPC results are converted to arbitrary-precision Python `int` values.",
        "",
    ]
    for module_name in API_MODULES:
        module = importlib.import_module(module_name)
        classes = [
            value
            for value in vars(module).values()
            if inspect.isclass(value)
            and value.__module__ == module_name
            and value.__name__.endswith("Api")
        ]
        for cls in classes:
            metadata = class_source_metadata(cls)
            public = [
                name
                for name, value in cls.__dict__.items()
                if callable(value) and not name.startswith("_")
            ]
            lines.extend(
                [
                    f"## {cls.__name__}",
                    "",
                    API_SUMMARIES[cls.__name__],
                    "",
                    f"Import: `{module_name}.{cls.__name__}`",
                    "",
                    f"Constructor: `{cls.__name__}{inspect.signature(cls)}`",
                    "",
                    "| Python signature | Kind | Wire method | Declared result |",
                    "| --- | --- | --- | --- |",
                ]
            )
            for name in public:
                info = metadata.get(name, {"wire": "", "doc": ""})
                method = getattr(cls, name)
                kind = method_kind(name, method, info["wire"], info["doc"])
                result = method_result(kind, info["wire"])
                signature = format_signature(cls, name).replace("|", "\\|")
                wire = f"`{info['wire']}`" if info["wire"] else "—"
                lines.append(f"| `{signature}` | {kind} | {wire} | `{result}` |")
            lines.append("")
    return "\n".join(lines)


def field_rows(name: str, cls) -> list[tuple]:
    from znn.model.models import WIRE_SCHEMAS

    if name == "AccountBlock":
        return list(WIRE_SCHEMAS["AccountBlockTemplate"] + WIRE_SCHEMAS["AccountBlock"])
    return list(getattr(cls, "_fields", WIRE_SCHEMAS.get(name, ())))


def decoded_type(
    wire_type: str,
    encoding: str | None,
    target: str | None,
    object_item: str | None,
) -> str:
    if wire_type == "array":
        return f"list[{target or 'object'}]"
    if wire_type == "model" and target:
        return target
    if object_item:
        return f"dict[str, {object_item}]"
    if encoding == "hex-32":
        return "Hash"
    if encoding == "bech32-address":
        return "Address"
    if encoding == "bech32-token-standard":
        return "TokenStandard"
    if encoding == "base64":
        return "bytes"
    return {
        "decimal-string": "int",
        "number": "int",
        "boolean": "bool",
        "string": "str",
        "array": "list",
        "object": "dict",
    }.get(wire_type, wire_type)


def generate_model_reference() -> str:
    from znn.model.models import MODEL_TYPES

    lines = [
        "---",
        "sidebar_position: 10",
        "title: Complete model reference",
        "description: Wire keys, Python attributes, types, required fields, defaults, and enum values for every stable model.",
        "---",
        "",
        "# Complete model reference",
        "",
        "> Generated by `tools/generate_documentation.py`. Do not edit this page by hand.",
        "",
        "Every table below is derived from the runtime model schema. `Required` describes strict runtime parsing. "
        "A dash means no declared default. RPC parsing may additionally require response-only AccountBlock fields.",
        "",
    ]
    models = [(name, cls) for name, cls in MODEL_TYPES.items() if not issubclass(cls, IntEnum)]
    enums = [(name, cls) for name, cls in MODEL_TYPES.items() if issubclass(cls, IntEnum)]
    for name, cls in models:
        rows = field_rows(name, cls)
        lines.extend(
            [
                f"## {name}",
                "",
                f"Import: `znn.model.models.{name}`"
                if cls.__module__ == "znn.model.models"
                else f"Runtime class: `{cls.__module__}.{cls.__name__}`",
                "",
            ]
        )
        if not rows:
            lines.extend(["This primitive has a custom validated wire representation.", ""])
            continue
        lines.extend(
            [
                "| Python attribute | Wire key | Wire type | Decoded Python type | Required | Default |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for attr, key, wire_type, encoding, target, required, default, object_item in rows:
            displayed_wire = f"{wire_type} ({encoding})" if encoding else wire_type
            default_value = default if default is not None else "—"
            lines.append(
                f"| `{attr}` | `{key}` | `{displayed_wire}` | "
                f"`{decoded_type(wire_type, encoding, target, object_item)}` | "
                f"{'yes' if required else 'no'} | `{default_value}` |"
            )
        lines.append("")
    lines.extend(["# Enum reference", ""])
    for name, cls in enums:
        members = ", ".join(f"`{member.name}={member.value}`" for member in cls)
        lines.extend([f"## {name}", "", members, ""])
    return "\n".join(lines)


def doc_inventory() -> list[tuple[int, str, dict[str, str], str]]:
    documents = []
    for path in DOCS.glob("*.md"):
        meta, body = frontmatter(path.read_text())
        position = int(meta.get("sidebar_position", "999"))
        documents.append((position, path.stem, meta, body.strip() + "\n"))
    return sorted(documents)


def generate_llms_files(check: bool) -> None:
    documents = doc_inventory()
    by_slug = {slug: (meta, body) for _, slug, meta, body in documents}
    for _, slug, _, body in documents:
        write_or_check(LLMS_DIR / f"{slug}.md", body, check)

    lines = [
        "# PyZNN",
        "",
        "> PyZNN is the Python 3.12+ SDK for the Zenon Network of Momentum. It implements the stable "
        "language-neutral SDK specification with strict typed models, all canonical RPC calls, embedded "
        "contract builders, wallets, transactions, and deterministic offline conformance tests.",
        "",
        "Use the Markdown links below as the authoritative documentation. No public node is configured by "
        "default. Examples using `your-node.example` require an endpoint operated or trusted by the user. "
        "All integer token amounts are base units unless explicitly converted with `znn.amount`.",
        "",
    ]
    for section, slugs in LLMS_SECTIONS.items():
        lines.extend([f"## {section}", ""])
        for slug in slugs:
            meta, _ = by_slug[slug]
            title = meta.get("title", slug.replace("-", " ").title())
            description = meta.get("description", "PyZNN documentation.")
            lines.append(f"- [{title}]({SITE_ROOT}/llms/{slug}.md): {description}")
        lines.append("")
    lines.extend(
        [
            "## Full context",
            "",
            f"- [Complete PyZNN documentation corpus]({SITE_ROOT}/llms-full.txt): All authoritative pages concatenated in reading order.",
        ]
    )
    write_or_check(STATIC / "llms.txt", "\n".join(lines), check)

    full = [
        "# PyZNN complete documentation corpus",
        "",
        "> Generated from the authoritative Docusaurus Markdown by `tools/generate_documentation.py`.",
        "",
        "Canonical project: https://github.com/0x3639/znn-sdk-py",
        f"Documentation root: {SITE_ROOT}/",
        "",
    ]
    for _, slug, meta, body in documents:
        full.extend(
            [
                "---",
                "",
                f"Source: {SITE_ROOT}/llms/{slug}.md",
                f"Title: {meta.get('title', slug)}",
                "",
                body.rstrip(),
                "",
            ]
        )
    write_or_check(STATIC / "llms-full.txt", "\n".join(full), check)


def validate_python_examples() -> None:
    """Compile every Python fence, including examples that use top-level await."""
    flags = ast.PyCF_ALLOW_TOP_LEVEL_AWAIT
    for path in sorted(DOCS.glob("*.md")):
        for number, source in enumerate(
            re.findall(r"```python\n(.*?)```", path.read_text(), re.DOTALL),
            start=1,
        ):
            compile(source, f"{path.relative_to(ROOT)}:python-block-{number}", "exec", flags=flags)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if generated files are stale")
    args = parser.parse_args()

    write_or_check(DOCS / "api-reference.md", generate_api_reference(), args.check)
    write_or_check(DOCS / "model-reference.md", generate_model_reference(), args.check)
    generate_llms_files(args.check)
    validate_python_examples()


if __name__ == "__main__":
    main()
