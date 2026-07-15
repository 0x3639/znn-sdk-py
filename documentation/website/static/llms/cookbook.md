# Example cookbook

These examples favor explicit inputs and cleanup. Online examples read trusted
endpoint and account values from environment variables; PyZNN does not provide
or select a public node.

## Choose the right entry point

| Goal | Recommended entry point |
| --- | --- |
| Read RPC data over HTTP | `HttpClient` plus an API facade |
| Read RPC data and subscribe | `WsClient` plus API facades |
| Manage connection and submit a block | `Zenon` |
| Prepare and publish in separate policy steps | `Transact` |
| Build an embedded contract call without I/O | An embedded API builder |
| Test application code without a node | A fake transport passed to an API facade |

## Read the frontier momentum over HTTP

Required environment variable: `ZNN_HTTP_URL`, containing an `http://` or
`https://` endpoint you operate or trust.

```python
import asyncio
import os

from znn.api.ledger import LedgerApi
from znn.client.http import HttpClient


async def main() -> None:
    client = HttpClient(os.environ["ZNN_HTTP_URL"], timeout=15)
    try:
        momentum = await LedgerApi(client).get_frontier_momentum()
        print(
            {
                "height": momentum.height,
                "hash": str(momentum.hash),
                "timestamp": momentum.timestamp,
            }
        )
    finally:
        await client.disconnect()


asyncio.run(main())
```

Result type: `znn.model.models.Momentum`. A non-nullable `null`, missing field,
wrong field type, malformed primitive, or non-canonical decimal string is
rejected during response parsing.

## Run concurrent typed RPC calls over WebSocket

Required environment variable: `ZNN_WS_URL`, containing a `ws://` or `wss://`
endpoint.

```python
import asyncio
import os

from znn.api.ledger import LedgerApi
from znn.api.stats import StatsApi
from znn.client.websocket import WsClient


async def main() -> None:
    client = WsClient(
        os.environ["ZNN_WS_URL"],
        connect_timeout=15,
        reconnect=True,
        reconnect_interval=1,
        maximum_attempts=10,
    )
    await client.connect()
    try:
        momentum, sync = await asyncio.gather(
            LedgerApi(client).get_frontier_momentum(),
            StatsApi(client).sync_info(),
        )
        print(momentum.height)
        print(sync.state, sync.currentHeight, sync.targetHeight)
    finally:
        await client.disconnect()


asyncio.run(main())
```

The persistent client correlates response IDs, so concurrent requests can
complete in a different order from the order in which they were sent.

## Read an optional RPC result

Required environment variables: `ZNN_HTTP_URL` and `ZNN_BLOCK_HASH`.

```python
import asyncio
import os

from znn.api.ledger import LedgerApi
from znn.client.http import HttpClient
from znn.model.nom.account_block import AccountBlock


async def main() -> None:
    client = HttpClient(os.environ["ZNN_HTTP_URL"])
    try:
        block = await LedgerApi(client).get_account_block_by_hash(
            os.environ["ZNN_BLOCK_HASH"]
        )
        if block is None:
            print("block not found")
            return
        assert isinstance(block, AccountBlock)
        print(block.height, block.hash, block.address)
    finally:
        await client.disconnect()


asyncio.run(main())
```

`get_account_block_by_hash()` is nullable. By contrast,
`get_frontier_momentum()` is not nullable and rejects `null`.

## Consume a subscription

Required environment variable: `ZNN_WS_URL`.

```python
import asyncio
import os

from znn.api.subscribe import SubscribeApi
from znn.client.websocket import WsClient


async def main() -> None:
    client = WsClient(os.environ["ZNN_WS_URL"], maximum_attempts=10)
    await client.connect()
    try:
        subscription = await SubscribeApi(client).to_momentums()
        async for update in subscription:
            print(update)
    finally:
        await client.disconnect()


asyncio.run(main())
```

Each yielded value is one item from the notification's `result` array. The
JSON-RPC envelope and subscription identifier are normalized away. On reconnect,
the client restores the complete active subscription set before delivery
continues.

## Subscribe for one account

Required environment variables: `ZNN_WS_URL` and `ZNN_ADDRESS`.

```python
import asyncio
import os

from znn.api.subscribe import SubscribeApi
from znn.client.websocket import WsClient
from znn.model.primitives.address import Address


async def main() -> None:
    address = Address.parse(os.environ["ZNN_ADDRESS"])
    client = WsClient(os.environ["ZNN_WS_URL"])
    await client.connect()
    try:
        subscription = await SubscribeApi(client).to_account_blocks_by_address(
            str(address)
        )
        async for update in subscription:
            print(update["hash"])
    finally:
        await client.disconnect()


asyncio.run(main())
```

Parsing the address before sending catches invalid prefixes, payload lengths,
and checksums locally.

## Test typed RPC behavior without a node

API facades accept any transport with an async `send_request(method, params)`
method. This makes application tests deterministic and network-free.

```python
import asyncio

from znn.api.stats import StatsApi
from znn.model.models import SyncInfo, SyncState


class FakeTransport:
    async def send_request(self, method, params):
        assert method == "stats.syncInfo"
        assert params == []
        return {
            "state": 2,
            "currentHeight": 123,
            "targetHeight": 123,
        }


async def main() -> None:
    result = await StatsApi(FakeTransport()).sync_info()
    assert isinstance(result, SyncInfo)
    assert result.state is SyncState.SyncDone
    assert result.currentHeight == 123
    assert result.targetHeight == 123


asyncio.run(main())
```

Return raw wire data from the fake. `ApiClient` still applies the production
result parser, so tests exercise the same required fields and nested types.

## Parse and serialize a strict model

```python
from znn.model.models import SyncInfo, SyncState

wire = {
    "state": 1,
    "currentHeight": 120,
    "targetHeight": 123,
}

sync = SyncInfo.from_json(wire)
assert sync.state is SyncState.Syncing
assert sync.currentHeight == 120
assert sync.to_json() == wire
```

Unknown Python attributes are not populated from wire keys, required fields
cannot be removed, and nested models are constructed recursively.

## Convert display amounts exactly

```python
from decimal import Decimal

from znn.amount import from_base_units, to_base_units

assert to_base_units("1.23456789", 8) == 123_456_789
assert to_base_units(Decimal("0.00000001"), 8) == 1
assert from_base_units(123_456_789, 8) == "1.23456789"
```

Do not use binary `float` for token amounts. Transaction and builder amounts are
integer base units.

## Create and derive a wallet

```python
from znn.wallet.keystore import KeyStore

store = KeyStore.new_random(passphrase="optional BIP39 passphrase")
account_0 = store.get_key_pair(0)
account_1 = store.get_key_pair(1)

print(store.mnemonic)  # back up securely; do not log in production
print(account_0.address)
print(account_1.address)
```

The derivation paths are `m/44'/73404'/0'` and `m/44'/73404'/1'`.

## Import canonical entropy

Required environment variable: `ZNN_ENTROPY_HEX`, containing exactly 16 or 32
bytes of hexadecimal entropy.

```python
import os

from znn.wallet.keystore import KeyStore

store = KeyStore.from_entropy(os.environ["ZNN_ENTROPY_HEX"])
print(store.get_key_pair(0).address)
```

Other entropy sizes are outside the stable SDK profile and raise `ValueError`.

## Sign text and protocol hashes

Required environment variable: `ZNN_PRIVATE_KEY`, containing a 32-byte Ed25519
private key as hexadecimal.

```python
import os

from znn.model.primitives.hash import Hash
from znn.wallet.keypair import KeyPair, verify_signature

keypair = KeyPair(os.environ["ZNN_PRIVATE_KEY"])

text_signature = keypair.sign("Hello, aliens").decode()
verify_signature(keypair.public_key, text_signature, "Hello, aliens")

block_hash = Hash.parse("00" * 32)
raw_signature = keypair.sign_hash(block_hash)
assert len(raw_signature) == 64
```

Text signing preserves the legacy base64 behavior. Account-block signing signs
the raw 32-byte hash and returns 64 raw signature bytes.

## Encrypt and decrypt a key file

Required environment variables: `ZNN_MNEMONIC` and `ZNN_KEYFILE_PASSWORD`.

```python
import json
import os

from znn.wallet.keyfile import decrypt, encrypt, needs_upgrade
from znn.wallet.keystore import KeyStore

store = KeyStore.from_mnemonic(os.environ["ZNN_MNEMONIC"])
password = os.environ["ZNN_KEYFILE_PASSWORD"]

document = encrypt(store, password)
serialized = json.dumps(document)
restored = decrypt(json.loads(serialized), password)

assert restored.get_key_pair(0).address == store.get_key_pair(0).address
assert not needs_upgrade(document)
```

Store the entire JSON document. Removing the version, timestamp, base address,
Argon2 parameters, nonce, cipher name, KDF name, or ciphertext makes the key file
invalid.

## Build an embedded contract call without I/O

```python
from znn.api.embedded.stake import StakeApi
from znn.model.nom.account_block import AccountBlock
from znn.model.primitives.address import STAKE_ADDRESS
from znn.model.primitives.token_standard import ZNN_ZTS

block = StakeApi().stake(
    duration_in_sec=30 * 24 * 60 * 60,
    amount=100_000_000,
)

assert isinstance(block, AccountBlock)
assert block.to_address == STAKE_ADDRESS
assert block.token_standard == ZNN_ZTS
assert block.amount == 100_000_000
assert block.data
```

The builder encodes ABI data and returns an unsigned block. It neither connects
to a node nor publishes the block.

## Inspect ABI call data

```python
from znn.embedded.definitions import STAKE_ABI

duration = 30 * 24 * 60 * 60
payload = STAKE_ABI.encode("Stake", [duration])
name, parameters = STAKE_ABI.decode_call_data(payload)

assert name == "Stake"
assert parameters == {"durationInSec": duration}
```

`decode_call_data()` identifies the function by its four-byte selector and
returns decoded custom Zenon types in their canonical string forms.

## Prepare, inspect, and publish a send block

Required environment variables: `ZNN_WS_URL`, `ZNN_PRIVATE_KEY`, and
`ZNN_TO_ADDRESS`.

```python
import asyncio
import os

from znn.api.embedded.plasma import PlasmaApi
from znn.api.ledger import LedgerApi
from znn.client.websocket import WsClient
from znn.model.nom.account_block import AccountBlock
from znn.model.primitives.address import Address
from znn.model.primitives.token_standard import ZNN_ZTS
from znn.wallet.transact import Transact


async def main() -> None:
    client = WsClient(os.environ["ZNN_WS_URL"])
    await client.connect()
    try:
        block = AccountBlock.send(
            Address.parse(os.environ["ZNN_TO_ADDRESS"]),
            ZNN_ZTS,
            100_000_000,
        )
        transaction = Transact(
            os.environ["ZNN_PRIVATE_KEY"],
            ledger_api=LedgerApi(client),
            plasma_api=PlasmaApi(client),
        )

        prepared = await transaction.prepare_block(block)
        print(prepared.to_json())  # policy or user review point
        published = await transaction.publish_block(prepared)
        print(published.hash)
    finally:
        await client.disconnect()


asyncio.run(main())
```

Do not blindly retry publication after an ambiguous transport failure. Query the
account chain by the prepared hash first so the same intent is not submitted
twice by application logic.

## Submit an embedded builder through the high-level SDK

Required environment variables: `ZNN_WS_URL` and `ZNN_PRIVATE_KEY`.

```python
import asyncio
import os

from znn import Zenon
from znn.api.embedded.stake import StakeApi


async def main() -> None:
    sdk = Zenon()
    await sdk.initialize(os.environ["ZNN_WS_URL"])
    try:
        unsigned = StakeApi().stake(
            duration_in_sec=30 * 24 * 60 * 60,
            amount=100_000_000,
        )
        published = await sdk.send(unsigned, os.environ["ZNN_PRIVATE_KEY"])
        print(published.hash)
    finally:
        await sdk.disconnect()


asyncio.run(main())
```

`Zenon.send()` applies the SDK chain identifier, prepares the block, and then
publishes it.

## Use a custom asynchronous PoW provider

```python
from znn import Zenon
from znn.pow import generate


async def local_worker(data_hash: str, difficulty: int) -> str:
    # Replace this with a trusted worker if required. The SDK verifies its result.
    return generate(data_hash, difficulty)


sdk = Zenon()
sdk.set_pow_provider(local_worker)
```

The provider must return exactly 16 lowercase hexadecimal characters. PyZNN
verifies the nonce against the data hash and required difficulty before signing.

## Generate and verify PoW directly

```python
from znn.pow import generate, verify

data_hash = "00" * 32
nonce = generate(data_hash, difficulty=100, start_nonce=bytes(8))

assert len(nonce) == 16
assert verify(data_hash, difficulty=100, nonce_hex=nonce)
```

Difficulty zero uses the canonical nonce `0000000000000000`.
