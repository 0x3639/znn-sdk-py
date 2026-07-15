---
sidebar_position: 8
title: Stable SDK conformance
description: Understand the stable specification coverage, offline vectors, manifest, and CI gates.
---

# Stable SDK conformance

PyZNN targets the stable `zenon-sdk-spec` 1.0 surface plus its canonical-node
corrections. Verification is deterministic and does not require a live Zenon
node.

## Implemented surface

| Surface | Current result |
| --- | ---: |
| Stable portable vectors | 764 / 764 |
| ABI boundary profile | 491 / 491 |
| All ABI cases | 512 / 512 |
| Canonical JSON-RPC methods | 76 / 76 |
| Field-aware models | 72 / 72 |
| Enums | 6 / 6 |
| Embedded ABI functions | 84 / 84 |
| Embedded builders | 68 / 68 |
| Capability manifest | `full`, 309 mappings |
| Offline pytest suite | 77 passing |
| Branch-enabled combined coverage | 95.46% |

The portable result document is emitted as `znn-sdk-results/1` with
`complete: true`. All capability-manifest symbols resolve to concrete Python
implementations.

## Run the offline test suite

Clone the stable specification and check out the revision pinned by CI:

```bash
git clone https://github.com/0x3639/zenon-sdk-spec.git ../zenon-sdk-spec
git -C ../zenon-sdk-spec checkout 69f2ecf955bafa4037c73f4b858619ef834e738b
```

Run tests with the specification vectors and localhost transport fixture:

```bash
ZNN_SPEC_ROOT=../zenon-sdk-spec \
  python3.12 -m coverage run -m pytest -q
python3.12 -m coverage report
```

CI enables branch coverage across the complete `znn` package and requires a
95.00% combined floor at two-decimal precision. The current audited result is
97.10% statement coverage, 91.70% branch coverage, and 95.46% combined.

## Run and validate all vectors

```bash
python3.12 -m znn.conformance \
  ../zenon-sdk-spec/conformance/vectors \
  --output znn-sdk-results.json

python3.12 ../zenon-sdk-spec/tools/znn_spec.py \
  check-results znn-sdk-results.json

python3.12 ../zenon-sdk-spec/tools/znn_spec.py \
  check-manifest conformance/manifest.json
```

The three stateful transport cases run the real `HttpClient`, `LedgerApi`, and
`WsClient` against the specification's localhost HTTP/WebSocket fixture. They
cover successful-null publication, pagination errors, subscription
normalization, disconnect, reconnect, resubscribe, and post-reconnect updates.
The fixture is not a Zenon node and never reaches an external network.

## What the regression suite protects

The expanded offline tests cover:

- every RPC facade and typed response route;
- all removable required model fields and nested response parsing;
- canonical account-block hashing, signing, nonce, and base64 boundaries;
- ABI integers, booleans, fixed bytes, custom arrays, and registry isolation;
- key-file round trips, configurable KDF parameters, upgrades, and malformed
  document classes;
- transaction preparation, fused plasma, PoW providers, receive validation,
  publication, and provider failures;
- HTTP protocol and correlation failures;
- WebSocket send/connect failures, bounded orphan buffers, reconnect races,
  full-set resubscription retries, terminal recovery errors, and clean shutdown;
- high-level SDK lifecycle and compatibility aliases.

No known stable conformance failures remain.

## Generated inventories

The model runtime and RPC response routing are generated from the pinned
specification inventory:

```bash
python3.12 tools/generate_models.py \
  ../zenon-sdk-spec/spec/models.json

python3.12 tools/generate_rpc_responses.py \
  ../zenon-sdk-spec/spec/rpc.json
```

Generation must reproduce the committed files byte for byte. When the stable
specification changes, update the pinned revision, regenerate, run the complete
offline suite, validate the manifest, and document the resulting surface change
in the same pull request.
