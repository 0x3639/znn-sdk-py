---
sidebar_position: 1
title: Installation and quick start
description: Install znn-sdk and connect the high-level SDK to an explicit Zenon endpoint.
---

# Installation and quick start

PyZNN is a Python 3.12+ SDK for the Zenon Network of Momentum protocol. The
current release follows the stable language-neutral SDK specification and the
canonical `go-zenon` wire behavior.

## Install

Install the published package:

The package is published on PyPI as `znn-sdk`; the import name stays `znn`.

```bash
python3.12 -m pip install znn-sdk
```

For development, clone the repository and install the package with its test
dependencies:

```bash
python3.12 -m pip install -e ".[dev]"
```

## Connect the SDK

PyZNN never selects a public third-party node automatically. Always pass an
endpoint you operate or trust.

```python
import asyncio

from znn import Zenon
from znn.api.ledger import LedgerApi


async def main():
    sdk = Zenon()
    await sdk.initialize("wss://your-node.example:35998")
    try:
        ledger = LedgerApi(sdk.client)
        momentum = await ledger.get_frontier_momentum()
        print(momentum.height, momentum.hash)
    finally:
        await sdk.disconnect()


asyncio.run(main())
```

`Zenon.initialize()` accepts `http`, `https`, `ws`, and `wss` URLs. HTTP is a
request/response transport. WebSocket maintains a persistent connection and is
required for subscriptions.

| Endpoint | Client | Best for |
| --- | --- | --- |
| `http://` or `https://` | `HttpClient` | RPC calls without subscriptions |
| `ws://` or `wss://` | `WsClient` | RPC calls, subscriptions, and reconnect/resubscribe |

The optional `timeout` argument must be positive and defaults to 30 seconds.
WebSocket-specific options such as `reconnect`, `reconnect_interval`, and
`maximum_attempts` can be passed to `initialize()` as keyword arguments.

```python
await sdk.initialize(
    "wss://your-node.example:35998",
    timeout=15,
    reconnect=True,
    reconnect_interval=1,
    maximum_attempts=10,
)
```

## What is included

- strict address, hash, token-standard, hash-height, and account-block types;
- 72 generated wire models and six enums;
- all 76 canonical positional JSON-RPC methods with typed results;
- all 84 embedded ABI functions and 68 corrected transaction builders;
- HTTP and persistent WebSocket transports with structured errors;
- BIP39/SLIP-0010 wallets, Ed25519 signing, and encrypted key files;
- transaction preparation, fused plasma, PoW, signing, and publication;
- exact amount conversion and a complete offline conformance runner.

Continue with [JSON-RPC clients](./json-rpc-client.md), [API facades](./api.md),
or [wallets and transactions](./wallet.md).
