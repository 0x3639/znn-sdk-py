# Wallets, key files, and transactions

## Create or import a wallet

`KeyStore` uses English BIP39 mnemonics and SLIP-0010 Ed25519 derivation at
`m/44'/73404'/{account}'`.

```python
from znn.wallet.keystore import KeyStore

store = KeyStore.new_random()
first = store.get_key_pair(0)
second = store.get_key_pair(1)

print(store.mnemonic)       # back this up securely; never log it in production
print(first.address)
```

Import an existing mnemonic or the stable 16/32-byte entropy profile:

```python
store = KeyStore.from_mnemonic(mnemonic, passphrase="optional BIP39 passphrase")
store = KeyStore.from_entropy(entropy_hex)
```

Account indices must be non-negative integers. Call `clear()` on key stores and
key pairs when you no longer need their in-memory secret material.

## Keys and signatures

```python
from znn.wallet.keypair import KeyPair, verify_signature

keypair = KeyPair(private_key_hex)

# Legacy text signing returns a base64-encoded signature.
signature = keypair.sign("Hello, aliens").decode()
verify_signature(keypair.public_key, signature, "Hello, aliens")

# Protocol signing uses the raw 32-byte hash and returns 64 raw signature bytes.
block_signature = keypair.sign_hash(block_hash)
```

`KeyPair` accepts only 32-byte Ed25519 private keys. Account-block signing does
not base64-wrap or transform the canonical hash before signing.

## Encrypted key files

Version-one key files use Argon2id and AES-256-GCM with authenticated data
`zenon`.

```python
import json

from znn.wallet.keyfile import decrypt, encrypt, needs_upgrade

document = encrypt(store, password, timestamp=1_700_000_000)
serialized = json.dumps(document)

restored = decrypt(json.loads(serialized), password)
assert restored.get_key_pair(0).address == store.get_key_pair(0).address

if needs_upgrade(document):
    document = encrypt(restored, password)
```

Customize Argon2 work factors when required by your application:

```python
document = encrypt(
    store,
    password,
    kdf_config={
        "timeCost": 2,
        "memoryCost": 131072,
        "hashLength": 32,
        "parallelism": 4,
    },
)
```

Malformed documents, unsupported algorithms, invalid parameters, bad
passwords, and corrupted ciphertext raise `KeyFileError`. Keep the full
document, including `baseAddress`, `timestamp`, `version`, and every declared
crypto field.

## Prepare before publishing

Transaction preparation and publication are separate operations. Preparation:

1. reads the account and momentum frontiers;
2. validates receive blocks when applicable;
3. requests the required plasma/PoW values;
4. applies fused plasma or generates and verifies PoW;
5. hashes the canonical account-block preimage; and
6. signs the raw hash with Ed25519.

```python
from znn.api.embedded.plasma import PlasmaApi
from znn.api.ledger import LedgerApi
from znn.model.nom.account_block import AccountBlock
from znn.model.primitives.address import Address
from znn.model.primitives.token_standard import ZNN_ZTS
from znn.wallet.transact import Transact

block = AccountBlock.send(
    Address.parse("z1qzpcwr6lk0zhejzpt04j2jcqqadtu046ffr8nr"),
    ZNN_ZTS,
    100_000_000,
)

tx = Transact(
    private_key_hex,
    ledger_api=LedgerApi(client),
    plasma_api=PlasmaApi(client),
)

prepared = await tx.prepare_block(block)
# Inspect or transfer `prepared` to another policy layer here.
published = await tx.publish_block(prepared)
```

`publish_block()` requires the canonical `null` success response and returns the
prepared block. `fast_forward_block()` combines preparation and publication.
Convenience methods `send()`, `receive()`, and `call_contract()` build and
fast-forward their respective blocks.

## High-level SDK transaction flow

```python
from znn import Zenon
from znn.model.nom.account_block import AccountBlock

sdk = Zenon()
await sdk.initialize("wss://your-node.example:35998")
try:
    block = AccountBlock.send(to_address, token_standard, amount)
    published = await sdk.send(block, keypair)
finally:
    await sdk.disconnect()
```

`Zenon.prepare_block()` is also available when you need only a prepared block.
Use the explicit `Transact.prepare_block()` / `publish_block()` split when that
prepared block must later be published unchanged.

## Custom PoW providers

A provider receives `(data_hash_hex, difficulty)` and returns a 16-character
lowercase nonce hex string. It may be synchronous or asynchronous.

```python
async def remote_pow(data_hash, difficulty):
    return await trusted_pow_service(data_hash, difficulty)

sdk.set_pow_provider(remote_pow)
```

Returned nonces are length-checked and verified locally. A preselected nonce and
difficulty are also accepted when they satisfy at least the node-required
difficulty.

The [example cookbook](./cookbook.md) includes complete environment-driven
wallet, key-file, embedded builder, prepare/publish, high-level SDK, ABI, and PoW
programs.
