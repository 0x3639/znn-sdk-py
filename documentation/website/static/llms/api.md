# API facades and embedded contracts

API facade methods map Python names to the stable SDK's canonical positional
JSON-RPC calls. Read methods return validated model instances, enums, integers,
booleans, lists, or `None` according to the declared result type.

## Core APIs

Pass either `HttpClient` or `WsClient` to a facade:

```python
from znn.api.ledger import LedgerApi
from znn.api.stats import StatsApi
from znn.client.http import HttpClient

client = HttpClient("https://your-node.example:35997")

ledger = LedgerApi(client)
stats = StatsApi(client)

account = await ledger.get_account_info_by_address(
    "z1qpa4flg6m7r27rvpyturavecmemkxh7ms8vrp7"
)
if account is not None:
    print(account.address, account.blockCount)

sync = await stats.sync_info()
print(sync.state, sync.currentHeight, sync.targetHeight)
```

| Facade | Purpose |
| --- | --- |
| `LedgerApi` | Account blocks, momentums, balances, and publication |
| `StatsApi` | OS, process, network, and synchronization information |
| `SubscribeApi` | Four canonical subscription topics over WebSocket |

Generated result parsing is strict: required wire keys cannot be omitted,
decimal strings must be canonical, nested models are constructed recursively,
and nullable results are accepted only where the specification permits them.

## Embedded APIs

The complete stable embedded surface is available, including the recently
added Bridge, HTLC, Liquidity, and Spork modules.

| Facade | Read and builder surface |
| --- | --- |
| `AcceleratorApi` | Projects, phases, votes, donations, and project updates |
| `BridgeApi` | Networks, wrap/unwrap requests, security, administration, and bridge operations |
| `HtlcApi` | HTLC lookup, proxy-unlock status, creation, reclaim, and unlock |
| `LiquidityApi` | Liquidity state, rewards, stakes, security, and administration |
| `PillarApi` | Pillars, delegation, rewards, registration, and QSR management |
| `PlasmaApi` | Plasma state, fusion entries, PoW requirements, fuse, and cancel |
| `SentinelApi` | Sentinel state, registration, rewards, and QSR management |
| `SporkApi` | Spork listing, creation, and activation |
| `StakeApi` | Stake entries, rewards, stake, cancel, and collection |
| `SwapApi` | Swap assets, legacy pillars, and asset retrieval |
| `TokenApi` | Token lookup, issuance, mint, burn, and update |

Read methods call the node. Builder methods are synchronous and create an
unsigned `AccountBlock` locally. They do not publish anything.

```python
from znn.api.embedded.stake import StakeApi
from znn.model.primitives.address import Address

stake_api = StakeApi(client)

address = Address.parse("z1qpa4flg6m7r27rvpyturavecmemkxh7ms8vrp7")
entries = await stake_api.get_entries_by_address(address)
unsigned_block = stake_api.stake(
    duration_in_sec=30 * 24 * 60 * 60,
    amount=100_000_000,
)
```

Prepare, inspect, and publish the returned block with `Transact` or the
high-level `Zenon` service. See [Wallets and transactions](./wallet.md).

## ABI behavior

The embedded builders use the complete set of 84 ABI functions and enforce the
stable ABI boundary rules:

- integers and booleans are not silently coerced;
- fixed-size byte values must have the exact declared length;
- addresses, hashes, and token standards use their canonical binary cores;
- custom arrays preserve their specified element types and layout;
- decoding rejects malformed payloads with normalized `ValueError` failures.

The ABI compatibility registry is isolated from `eth_abi`'s process-global
default registry, so importing `znn.abi.registry` cannot change unrelated ABI
code in the same process.

## Compatibility aliases

Canonical names are preferred. A small number of legacy Python names remain as
aliases, including token lookup by owner address and accelerator project
listing. The removed node method
`embedded.plasma.getRequiredFusionAmount` remains only as a deprecated stub and
raises `NotImplementedError` rather than sending a non-canonical RPC call.

See the [complete API reference](./api-reference.md) for every exact signature,
wire method, method kind, and declared result. The [example cookbook](./cookbook.md)
contains complete online and offline usage patterns.
