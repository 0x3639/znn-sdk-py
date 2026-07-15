---
sidebar_position: 4
title: Models, primitives, amounts, and PoW
description: Work with strict wire models, protocol primitives, exact amounts, and Zenon proof of work.
---

# Models, primitives, amounts, and PoW

The stable SDK surface includes 72 field-aware models and six `IntEnum` types.
RPC facades construct these types automatically, but they are also available for
local parsing and serialization.

## Protocol primitives

`Address`, `Hash`, `TokenStandard`, and `HashHeight` validate their complete
wire encodings. Invalid prefixes, checksums, lengths, ranges, or hexadecimal
forms are rejected at the parse boundary.

```python
from znn.model.primitives.address import Address
from znn.model.primitives.hash import Hash
from znn.model.primitives.token_standard import ZNN_ZTS

address = Address.parse("z1qpa4flg6m7r27rvpyturavecmemkxh7ms8vrp7")
block_hash = Hash.parse("00" * 32)
token_standard = ZNN_ZTS

assert Address.from_json(address.to_json()) == address
assert Hash.from_json(block_hash.to_json()) == block_hash
```

Primitive objects are hashable and can be used as dictionary keys or set
members. Bytes-like constructor inputs are accepted only when their lengths are
correct.

## Generated models

```python
from znn.model.models import AccountInfo

account = AccountInfo.from_json(wire_document)
print(account.blockCount)       # wire key: accountHeight
print(account.balanceInfoMap)

assert account.to_json() == wire_document
```

Model parsing is field-aware rather than a generic dictionary wrapper:

- required fields must be present and cannot be shadowed by model methods;
- wire keys are mapped to their declared Python attributes;
- decimal-string values become arbitrary-precision Python integers;
- nested models, primitives, arrays, maps, and enums are constructed recursively;
- standard base64 accepts valid padded or unpadded input and rejects malformed
  alphabets or padding.

The generated enums are `AcceleratorProjectStatus`, `AcceleratorProjectVote`,
`BlockTypeEnum`, `ReceiveBlockTypeEnum`, `SendBlockTypeEnum`, and `SyncState`.

## Account blocks

`AccountBlock` has strict template and response parsing, canonical hashing, and
local builders for send, receive, and contract-call blocks.

```python
from znn.model.nom.account_block import AccountBlock
from znn.model.primitives.address import Address
from znn.model.primitives.hash import Hash
from znn.model.primitives.token_standard import ZNN_ZTS

send = AccountBlock.send(
    Address.parse("z1qzpcwr6lk0zhejzpt04j2jcqqadtu046ffr8nr"),
    ZNN_ZTS,
    100_000_000,
)
receive = AccountBlock.receive(Hash.parse("00" * 32))

wire = send.to_json()
parsed = AccountBlock.from_json(wire)
```

Response-only fields are required when RPC results are parsed. Nonces are
validated immediately as eight-byte standard-base64 values, and the canonical
hash preimage uses the exact protocol field order and encodings.

## Exact amount conversion

Use the amount helpers instead of binary floating point:

```python
from znn.amount import from_base_units, to_base_units

base_units = to_base_units("1.23456789", decimals=8)
assert base_units == 123_456_789
assert from_base_units(base_units, decimals=8) == "1.23456789"
```

Inputs are decimal strings, integers, or `Decimal` values. Fractional digits
beyond the requested precision are truncated toward zero.

## Proof of work

```python
from znn.pow import generate, verify

data_hash = "00" * 32
nonce = generate(data_hash, difficulty=100)
assert verify(data_hash, difficulty=100, nonce_hex=nonce)
```

PoW hashes are 32-byte lowercase hex, nonces are eight-byte lowercase hex, and
difficulty must fit an unsigned 64-bit integer. Difficulty zero has the
canonical all-zero nonce. Transaction preparation normally handles this for you
and can use a custom synchronous or asynchronous PoW provider.

See the [complete model reference](./model-reference.md) for every Python
attribute, wire key, wire type, nested target, required flag, default, and enum
value.
