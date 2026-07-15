"""Interoperable version-one Zenon key-file encryption."""

from __future__ import annotations

import secrets
import time
from copy import deepcopy
from typing import Any

from Crypto.Cipher import AES

from znn.wallet.keystore import KeyStore


DEFAULT_TIME_COST = 1
DEFAULT_MEMORY_COST = 65536
DEFAULT_HASH_LENGTH = 32
DEFAULT_PARALLELISM = 4


class KeyFileError(ValueError):
    pass


def _argon2(password: str, salt: bytes, params: dict[str, Any]) -> bytes:
    try:
        from argon2.low_level import Type, hash_secret_raw
    except ImportError as error:
        raise RuntimeError("argon2-cffi is required for key-file support") from error
    return hash_secret_raw(
        password.encode(), salt,
        time_cost=int(params.get("timeCost", DEFAULT_TIME_COST)),
        memory_cost=int(params.get("memoryCost", DEFAULT_MEMORY_COST)),
        parallelism=int(params.get("parallelism", DEFAULT_PARALLELISM)),
        hash_len=int(params.get("hashLength", DEFAULT_HASH_LENGTH)),
        type=Type.ID,
        version=19,
    )


def needs_upgrade(document: dict[str, Any]) -> bool:
    params = document.get("crypto", {}).get("argon2Params", {})
    return not all(key in params for key in ("timeCost", "memoryCost", "hashLength", "parallelism"))


def decrypt(document: dict[str, Any], password: str) -> KeyStore:
    if document.get("version") != 1:
        raise KeyFileError("Unsupported key-file version")
    crypto = document.get("crypto", {})
    if crypto.get("cipherName") != "aes-256-gcm":
        raise KeyFileError("Unsupported key-file cipher")
    params = crypto.get("argon2Params", {})
    salt = bytes.fromhex(params["salt"].removeprefix("0x"))
    nonce = bytes.fromhex(crypto["nonce"].removeprefix("0x"))
    payload = bytes.fromhex(crypto["cipherData"].removeprefix("0x"))
    if len(salt) != 16 or len(nonce) != 12 or len(payload) < 16:
        raise KeyFileError("Invalid key-file cryptographic field length")
    key = _argon2(password, salt, params)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    cipher.update(b"zenon")
    try:
        entropy = cipher.decrypt_and_verify(payload[:-16], payload[-16:])
    except ValueError as error:
        raise KeyFileError("Invalid password or corrupted key file") from error
    store = KeyStore.from_entropy(entropy)
    if str(store.get_key_pair(0).address) != document.get("baseAddress"):
        raise KeyFileError("Decrypted entropy does not match baseAddress")
    return store


def encrypt(store: KeyStore, password: str, *, timestamp: int | None = None) -> dict[str, Any]:
    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
    params = {
        "salt": f"0x{salt.hex()}", "timeCost": DEFAULT_TIME_COST,
        "memoryCost": DEFAULT_MEMORY_COST, "hashLength": DEFAULT_HASH_LENGTH,
        "parallelism": DEFAULT_PARALLELISM,
    }
    key = _argon2(password, salt, params)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    cipher.update(b"zenon")
    ciphertext, tag = cipher.encrypt_and_digest(bytes.fromhex(store.entropy))
    return {
        "baseAddress": str(store.get_key_pair(0).address),
        "crypto": {
            "argon2Params": deepcopy(params),
            "cipherData": f"0x{(ciphertext + tag).hex()}",
            "cipherName": "aes-256-gcm", "kdf": "argon2.IDKey",
            "nonce": f"0x{nonce.hex()}",
        },
        "timestamp": int(time.time()) if timestamp is None else int(timestamp),
        "version": 1,
    }


class KeyFile:
    """Password-bound compatibility facade around key-file functions."""

    def __init__(self, password: str):
        self.password = password

    @classmethod
    def set_password(cls, password: str) -> "KeyFile":
        return cls(password)

    def encrypt(self, store: KeyStore, *, timestamp: int | None = None) -> dict[str, Any]:
        return encrypt(store, self.password, timestamp=timestamp)

    def decrypt(self, document: dict[str, Any]) -> KeyStore:
        return decrypt(document, self.password)

    @staticmethod
    def needs_upgrade(document: dict[str, Any]) -> bool:
        return needs_upgrade(document)
