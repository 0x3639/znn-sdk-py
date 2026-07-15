# JSON-RPC clients

PyZNN provides HTTP and WebSocket JSON-RPC 2.0 transports. Both correlate
integer request IDs, validate the protocol envelope, normalize transport
failures, and raise structured node errors.

## HTTP

Use `HttpClient` for request/response calls when subscriptions are not needed.
Its blocking standard-library HTTP work is moved off the event loop.

```python
from znn.api.ledger import LedgerApi
from znn.client.http import HttpClient

client = HttpClient("https://your-node.example:35997", timeout=15)
ledger = LedgerApi(client)

momentum = await ledger.get_frontier_momentum()
print(momentum.height)

await client.disconnect()
```

## Persistent WebSocket

`WsClient` keeps one socket open, supports concurrent correlated requests, and
runs a listener task for responses and subscription notifications.

```python
from znn.api.stats import StatsApi
from znn.client.websocket import WsClient

client = WsClient(
    "wss://your-node.example:35998",
    reconnect=True,
    reconnect_interval=1,
    maximum_attempts=10,
    connect_timeout=15,
)

await client.connect()
try:
    sync = await StatsApi(client).sync_info()
    print(sync.state)
finally:
    await client.disconnect()
```

`maximum_attempts=0` means unlimited reconnect attempts. During recovery, all
active subscriptions are restored as one set. Pending requests fail explicitly
instead of hanging, and permanent recovery failure is delivered to subscription
consumers as `TransportError`.

## Raw requests

Most applications should use an API facade because it applies canonical method
names, positional parameters, and typed result parsing. Raw calls remain
available when necessary:

```python
result = await client.send_request("ledger.getFrontierMomentum", [])
```

## Subscriptions

Subscriptions require WebSocket and return an async iterator. Each iteration
produces one normalized update object rather than the outer JSON-RPC
notification envelope.

```python
from znn.api.subscribe import SubscribeApi

subscription = await SubscribeApi(client).to_all_account_blocks()

async for account_block in subscription:
    print(account_block["hash"])
```

Available convenience subscriptions are:

- `to_momentums()`;
- `to_all_account_blocks()`;
- `to_account_blocks_by_address(address)`;
- `to_unreceived_account_blocks_by_address(address)`.

`subscribe_to(topic, address=None)` is also available, but only the canonical
topic and arity combinations are accepted.

## Errors

```python
from znn.client.errors import JsonRpcError, TransportError

try:
    await LedgerApi(client).get_momentum_by_hash("0" * 64)
except JsonRpcError as error:
    print(error.code, error.message, error.data)
except TransportError as error:
    print(f"connection or protocol failure: {error}")
```

`JsonRpcError` preserves the node's code, message, optional data, method, and
parameters. `TransportError` covers connection failures, invalid JSON,
malformed JSON-RPC envelopes, response-ID mismatches, send failures, and
exhausted WebSocket recovery.

## No implicit endpoint

`get_default_client()` remains as a compatibility helper, but its client is
intentionally unconfigured. Calling it without first configuring a trusted URL
raises `TransportError`; new code should construct `WsClient(url)` directly.
No public node is selected for you.

For complete runnable connection, concurrency, subscription, fake-transport,
and error-handling examples, continue to the [example cookbook](./cookbook.md).
