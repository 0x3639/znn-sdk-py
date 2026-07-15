---
sidebar_position: 7
title: Errors and troubleshooting
description: Exception taxonomy, retry guidance, validation failures, and remedies for HTTP, WebSocket, model, ABI, key-file, PoW, and transaction problems.
---

# Errors and troubleshooting

PyZNN rejects malformed local values and malformed node responses as early as
possible. Catch the narrowest exception that your application can handle.

## Exception taxonomy

| Exception | Module | Meaning |
| --- | --- | --- |
| `TypeError` | Python/runtime validators | A value has the wrong Python type or an unsupported coercion was attempted |
| `ValueError` | Primitives, models, amounts, PoW | A value has the right general type but an invalid format, range, checksum, length, or schema |
| `JsonRpcError` | `znn.client.errors` | The node returned a JSON-RPC `error` object |
| `TransportError` | `znn.client.errors` | Connection, JSON, envelope, correlation, send, reconnect, or shutdown failure |
| `ABIError` | `znn.abi.abi` | Invalid ABI declaration, parameter, selector, encoding, or decoding |
| `KeyFileError` | `znn.wallet.keyfile` | Malformed key-file document, unsupported crypto, bad password, or corrupted ciphertext |
| `TransactionError` | `znn.wallet.transact` | Invalid preparation inputs, node PoW response, provider nonce, or publication result |
| `ReceiveValidationError` | `znn.wallet.transact` | A receive template or its source block does not match the signer |
| `NotImplementedError` | Removed compatibility surface | A historical method is not present in the canonical node API |

## Handle node and transport failures separately

```python
from znn.client.errors import JsonRpcError, TransportError

try:
    momentum = await ledger.get_frontier_momentum()
except JsonRpcError as error:
    # The node processed the request and returned a protocol error.
    print(error.code, error.message, error.data, error.method, error.parameters)
except TransportError as error:
    # Delivery or response validity is uncertain.
    print(f"transport failure: {error}")
```

`JsonRpcError.to_json()` returns a serializable record containing the preserved
error context.

## Retry guidance

| Operation | Automatic retry guidance |
| --- | --- |
| Idempotent read RPC | Retry with bounded backoff when appropriate |
| WebSocket subscription | Let `WsClient` reconnect and resubscribe |
| Local builder, model parse, amount conversion | Do not retry; correct the input |
| Transaction preparation before publication | Usually safe to restart from fresh frontiers |
| Publication with a definite JSON-RPC error | Correct the rejected block before retrying |
| Publication with an ambiguous transport failure | Query by prepared hash before any retry |

The library does not silently replay in-flight JSON-RPC requests after a socket
loss. Pending requests fail explicitly. This prevents an application from
assuming that a non-idempotent operation was never received.

## “No default Zenon endpoint is configured”

Cause: `get_default_client()` or an API facade with no explicit transport tried
to perform I/O.

Fix:

```python
from znn.api.ledger import LedgerApi
from znn.client.websocket import WsClient

client = WsClient("wss://your-node.example:35998")
await client.connect()
ledger = LedgerApi(client)
```

There is intentionally no fallback public node.

## Invalid endpoint scheme

- `HttpClient` accepts only `http` and `https`.
- `WsClient` accepts only `ws` and `wss`.
- `Zenon.initialize()` accepts all four and selects the corresponding client.

Bare hostnames and unsupported schemes raise `ValueError` before connection.

## HTTP response ID does not match the request

The HTTP client requires a JSON-RPC 2.0 object whose integer `id` exactly equals
the request ID. A proxy, cache, or nonconforming endpoint may return another
request's response. Treat this as a protocol failure; do not use the result.

## WebSocket request never returns successfully

Pending requests do not survive a connection loss. They receive
`TransportError`, while the client separately recovers the socket and active
subscriptions. Callers may retry idempotent reads after recovery.

If `maximum_attempts` is nonzero and all attempts fail, subscription iterators
also raise terminal `TransportError` instead of waiting forever.

## Invalid subscription topic or arity

Use the convenience methods whenever possible:

```python
await subscribe.to_momentums()
await subscribe.to_all_account_blocks()
await subscribe.to_account_blocks_by_address(address)
await subscribe.to_unreceived_account_blocks_by_address(address)
```

The two address-scoped topics require an address. The two global topics reject
one. Unknown topics, empty subscription IDs, and malformed notification
envelopes are rejected.

## Required model field is missing

Generated models distinguish absent fields from false-like values such as `0`,
`false`, an empty list, or an empty map. Supply every field marked `Required`
in the [complete model reference](./model-reference.md).

```python
from znn.model.models import SyncInfo

# Raises because targetHeight is absent.
SyncInfo.from_json({"state": 1, "currentHeight": 10})
```

Do not work around this with `strict=False` for node responses. RPC parsing uses
strict runtime models so malformed node data cannot silently enter application
state.

## Invalid address, hash, or token standard

- Address and token-standard strings require their canonical human-readable
  prefix, payload size, and checksum.
- Hash strings contain exactly 64 hexadecimal characters; `Hash.parse()` accepts
  the core without `0x`.
- Primitive `from_json()` methods apply the same validation as direct parsing.

Validate user input before making an RPC request or building a transaction.

## Invalid base64

Model bytes accept standard base64 in valid padded or unpadded form. URL-safe
characters, impossible lengths, misplaced padding, or excess padding raise
`ValueError`. Account-block nonces must decode to exactly eight bytes.

## Decimal-string response rejected

The wire representation must be a canonical base-10 integer string:

- accepted: `"0"`, `"123"`, `"-1"` where the declared domain permits negatives;
- rejected: `"01"`, `"+1"`, `"1.0"`, whitespace, exponent notation, booleans,
  and JSON numbers when the specification declares a decimal string.

The parsed Python value is an arbitrary-precision `int`.

## Amount conversion gives an unexpected value

`to_base_units()` truncates excess fractional digits toward zero. It never
rounds to nearest.

```python
from znn.amount import to_base_units

assert to_base_units("1.239", decimals=2) == 123
```

Use a decimal string or `Decimal`, not `float`. Confirm the token's declared
decimal count before conversion.

## ABI encoding fails

The ABI codec intentionally rejects convenient but ambiguous coercions:

- boolean is not an integer;
- integer fields require integers in their valid signed/unsigned range;
- `bytesN` requires exactly `N` bytes;
- fixed arrays require the declared number of elements;
- address, hash, and token-standard inputs must parse canonically;
- function parameter count must match exactly.

Catch `ABIError` and correct the local builder input. Do not submit partially
encoded data.

## Key-file decryption fails

`KeyFileError` intentionally does not distinguish a bad password from corrupted
ciphertext. Check that:

1. `version` is `1`;
2. `cipherName` is `aes-256-gcm`;
3. `kdf` is `argon2.IDKey`;
4. all Argon2 parameters are positive integers and `hashLength` is `32`;
5. salt, nonce, and cipher data are lowercase `0x`-prefixed hex;
6. the decrypted entropy derives the declared `baseAddress`.

Use `needs_upgrade()` to compare a valid document's KDF work factors with the
current target configuration.

## PoW provider returned an invalid nonce

A provider must return a lowercase 16-character hexadecimal string. PyZNN then
checks that the decoded nonce is eight bytes and satisfies the exact data hash
and difficulty. A preselected difficulty must be at least the node-required
difficulty.

Do not disable local verification for remote PoW workers.

## Receive validation fails

Receive preparation requires:

- a non-empty source block hash;
- empty receive-block data;
- an existing source block; and
- a source `toAddress` equal to the signing account.

Any mismatch raises `ReceiveValidationError` before publication.

## Publication returned a non-null result

Canonical `ledger.publishRawTransaction` success is JSON `null`. Any non-null
success-shaped result raises `TransactionError`, because accepting a different
shape would hide node incompatibility.

## Removed plasma method raises NotImplementedError

`PlasmaApi.get_required_fusion_amount()` exists only so older applications fail
clearly. The canonical node removed
`embedded.plasma.getRequiredFusionAmount`; PyZNN does not send that stale call.
Use the current plasma and PoW APIs instead.

## Search is empty during local development

The local search index is produced by the static build. Test search with:

```bash
cd documentation/website
npm run build
npm run serve
```

The development server may not have a complete search index. Production builds
index documentation and site pages without sending queries to an external
search service.
