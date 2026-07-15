# znn-sdk

Python 3.12+ SDK for the Zenon Network of Momentum protocol. Version 0.1 follows
the stable language-neutral SDK specification and canonical `go-zenon` wire
behavior. Distributed on PyPI as `znn-sdk`; the import name is `znn`.

## Install

```bash
python3.12 -m pip install znn-sdk
```

No public third-party node is selected automatically. Pass an explicit HTTP(S)
or WebSocket endpoint when initializing the high-level SDK:

```python
from znn import Zenon

sdk = Zenon()
await sdk.initialize("wss://your-node.example:35998")
await sdk.disconnect()
```

## Transactions

Block preparation is separate from publication. Preparation reads the account
and momentum frontiers, applies fused plasma or PoW, hashes the canonical
preimage, and signs the raw 32-byte hash with Ed25519.

```python
from znn.model.nom.account_block import AccountBlock
from znn.model.primitives.address import Address
from znn.model.primitives.token_standard import ZNN_ZTS
from znn.wallet.transact import Transact

block = AccountBlock.send(Address.parse("z1..."), ZNN_ZTS, 100_000_000)
tx = Transact(private_key_hex, ledger_api, plasma_api)
prepared = await tx.prepare_block(block)
published = await tx.publish_block(prepared)
```

`Transact.send`, `receive`, and `call_contract` provide combined convenience
flows. The lower-level split is recommended for signing review, hardware-wallet
integration, and deterministic offline tests.

## Capabilities

- strict Address, Hash, TokenStandard, and HashHeight primitives;
- arbitrary-precision decimal-string wire amounts;
- all 72 field-aware wire models and 6 enums, with typed RPC results;
- all 76 canonical positional JSON-RPC calls;
- all 84 embedded ABI functions and 68 corrected builders;
- strict ABI integer, boolean, fixed-byte, and custom-array behavior;
- persistent WebSocket and HTTP JSON-RPC transports with structured errors;
- normalized subscriptions with reconnect/resubscribe support;
- BIP39/SLIP-0010 wallets and Ed25519 signing;
- Argon2id/AES-256-GCM key files;
- exact amount conversion and Zenon PoW generation/verification.

The removed `embedded.plasma.getRequiredFusionAmount` method remains only as a
deprecated compatibility stub and raises `NotImplementedError`.

## Conformance and tests

Run the unit suite:

```bash
python3.12 -m pytest -q
```

Measure the enforced offline branch coverage (the stable spec checkout supplies
vectors and a localhost fixture, not a Zenon node):

```bash
ZNN_SPEC_ROOT=/path/to/zenon-sdk-spec \
  python3.12 -m coverage run -m pytest -q
python3.12 -m coverage report
```

CI requires at least 95% branch-enabled combined coverage across the complete
`znn` package.

Run all 764 stable vectors and validate the portable result document:

```bash
python3.12 -m znn.conformance \
  /path/to/znn-ts-sdk-spec/conformance/vectors \
  --output znn-sdk-results.json
python3 /path/to/znn-ts-sdk-spec/tools/znn_spec.py \
  check-results znn-sdk-results.json
```

All conformance tests are deterministic and offline; no live node is required.
The transport cases use the specification's localhost fixture and exercise the
real HTTP/WebSocket clients, including reconnect and resubscription.
