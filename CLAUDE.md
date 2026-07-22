# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Python 3.12+ SDK for the Zenon Network of Momentum protocol. Published on PyPI as `znn-sdk`; the import name is `znn`. Version lives in `znn/__init__.py` (`__version__`), read dynamically by `pyproject.toml`.

The implementation tracks the stable language-neutral `zenon-sdk-spec` (GitHub `0x3639/zenon-sdk-spec`) and canonical `go-zenon` wire behavior. Everything is verified deterministically and offline — no live node is required for any test.

## The spec checkout dependency

Several tests and the conformance run need a local checkout of `zenon-sdk-spec`. Discovery order: the `ZNN_SPEC_ROOT` env var, else a sibling directory `../zenon-sdk-spec`. CI pins the spec at commit `69f2ecf9`. Tests that need the spec skip gracefully when it is absent, but coverage and conformance numbers are only meaningful with it present.

## Commands

```bash
python3.12 -m pip install -e '.[dev]'      # install with dev deps

python3.12 -m pytest -q                     # unit suite
python3.12 -m pytest tests/wallet/test_keypair.py -q        # one file
python3.12 -m pytest -q -k "name_substring"                 # one test

ruff check --select E9,F63,F7,F82 znn tests                 # lint (what CI runs)

# Coverage — CI enforces >= 95% branch-enabled combined coverage of znn/
ZNN_SPEC_ROOT=/path/to/zenon-sdk-spec python3.12 -m coverage run -m pytest -q
python3.12 -m coverage report

# Full conformance: run all stable vectors, then validate the result document
python3.12 -m znn.conformance /path/to/zenon-sdk-spec/conformance/vectors --output znn-sdk-results.json
python3 /path/to/zenon-sdk-spec/tools/znn_spec.py check-results znn-sdk-results.json
python3 /path/to/zenon-sdk-spec/tools/znn_spec.py check-manifest conformance/manifest.json

python3 tools/generate_documentation.py --check   # CI fails if generated docs are stale
```

The Docusaurus site lives in `documentation/website` (`npm ci && npm run build`); CI builds it and deploys on pushes to master.

## Generated code — do not hand-edit

These files are generated from the spec inventories by scripts in `tools/`; regenerate instead of editing:

- `znn/model/models.py` — all 72 field-aware wire models and 6 enums (`tools/generate_models.py`)
- `znn/api/_response.py` — the `RPC_RESULTS` method→model routing table (`tools/generate_rpc_responses.py`)
- `documentation/website/docs` reference pages (`tools/generate_documentation.py`; CI runs it with `--check`, so regenerate whenever the public API changes)
- `conformance/manifest.json` symbol mappings are maintained with `tools/update_manifest_symbols.py` and validated by the spec's `check-manifest`

Hand-written strict parsers for `Address`, `Hash`, `HashHeight`, `TokenStandard`, and `AccountBlock` live in `znn/model/primitives/` and `znn/model/nom/` and intentionally override the generated schema treatment.

## Architecture

Layered, bottom to top:

- **`znn/client/`** — transports. `protocol.py` builds positional JSON-RPC 2.0 requests and normalizes subscription notifications; `http.py` and `websocket.py` are the real clients (the WebSocket client handles reconnect and resubscription); `errors.py` defines `JsonRpcError` and friends.
- **`znn/api/`** — public RPC surface (`ledger.py`, `stats.py`, `subscribe.py`, and one class per embedded contract under `api/embedded/`). Every API class talks through `ApiClient` (`api/client.py`), which wraps a transport and routes each raw JSON result through `parse_rpc_response` in `_response.py` so callers get typed models, not dicts. Strictness is deliberate: non-nullable nulls, non-canonical decimal strings, and missing required keys raise.
- **`znn/abi/` + `znn/embedded/`** — Ethereum-style ABI encoding with Zenon-specific behavior (custom `hash`/`address`/`tokenStandard` types, strict integer/boolean/fixed-byte handling). `embedded/definitions.py` holds each contract's ABI JSON plus the canonical encode-call builders used to construct `AccountBlock` data.
- **`znn/wallet/`** — BIP39/SLIP-0010 key derivation, Ed25519 `KeyPair`, Argon2id/AES-256-GCM key files, and `transact.py`: `Transact.prepare_block` (reads frontiers, applies fused plasma or PoW, hashes the canonical preimage, signs) is intentionally separate from `publish_block`; `send`/`receive`/`call_contract` are convenience combinations.
- **`znn/sdk.py`** — the `Zenon` facade: picks `HttpClient` or `WsClient` from the URL scheme, holds network/chain IDs and an optional PoW provider.
- **`znn/conformance.py`** — the adapter that runs the spec's portable vector corpus and emits a `znn-sdk-results/1` document. Amounts (`amount.py`, decimal-string wire format), PoW (`pow.py`), and constants round it out.

## Constraints worth knowing

- JSON-RPC params are always positional lists; there are exactly 76 canonical RPC methods — adding or removing one must be reflected in the manifest and conformance results.
- Amounts cross the wire as arbitrary-precision decimal strings, never floats or ints.
- `embedded.plasma.getRequiredFusionAmount` is a deprecated stub that raises `NotImplementedError`; keep it that way.
- The spec repo's `tools/audit_python_sdk.py` hardcodes its transport/transaction/wallet/apiSurface sections (stale snapshots); only its rpc/ABI/builders/models inventories are actually computed.
