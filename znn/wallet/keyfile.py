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
DEFAULT_KDF_CONFIG = {
    "timeCost": DEFAULT_TIME_COST,
    "memoryCost": DEFAULT_MEMORY_COST,
    "hashLength": DEFAULT_HASH_LENGTH,
    "parallelism": DEFAULT_PARALLELISM,
}


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


def _kdf_config(config: dict[str, Any] | None = None) -> dict[str, int]:
    values = dict(DEFAULT_KDF_CONFIG)
    if config is not None:
        if not isinstance(config, dict):
            raise KeyFileError("KDF configuration must be an object")
        unknown = set(config) - set(values)
        if unknown:
            raise KeyFileError(f"Unknown KDF configuration fields: {sorted(unknown)}")
        values.update(config)
    if any(
        not isinstance(value, int) or isinstance(value, bool)
        for value in values.values()
    ):
        raise KeyFileError("KDF configuration values must be integers")
    if any(value <= 0 for value in values.values()):
        raise KeyFileError("KDF configuration values must be positive")
    if values["hashLength"] != 32:
        raise KeyFileError("AES-256-GCM key files require a 32-byte Argon2 output")
    return values


def needs_upgrade(
    document: dict[str, Any], target_config: dict[str, Any] | None = None
) -> bool:
    if not isinstance(document, dict):
        raise KeyFileError("Key file must be a JSON object")
    crypto = document.get("crypto", {})
    if not isinstance(crypto, dict):
        raise KeyFileError("Key file crypto must be an object")
    params = crypto.get("argon2Params", {})
    if not isinstance(params, dict):
        raise KeyFileError("Key file argon2Params must be an object")
    target = _kdf_config(target_config)
    try:
        return any(int(params[key]) != value for key, value in target.items())
    except (KeyError, TypeError, ValueError):
        return True


def decrypt(document: dict[str, Any], password: str) -> KeyStore:
    if not isinstance(password, str):
        raise KeyFileError("Key-file password must be a string")
    if not isinstance(document, dict):
        raise KeyFileError("Key file must be a JSON object")
    required = {"baseAddress", "crypto", "timestamp", "version"}
    missing = required - set(document)
    if missing:
        raise KeyFileError(f"Missing required key-file fields: {sorted(missing)}")
    if document.get("version") != 1:
        raise KeyFileError("Unsupported key-file version")
    if not isinstance(document["baseAddress"], str):
        raise KeyFileError("Key file baseAddress must be a string")
    if (
        not isinstance(document["timestamp"], int)
        or isinstance(document["timestamp"], bool)
        or document["timestamp"] < 0
    ):
        raise KeyFileError("Key file timestamp must be a non-negative integer")
    crypto = document.get("crypto", {})
    if not isinstance(crypto, dict):
        raise KeyFileError("Key file crypto must be an object")
    crypto_required = {"argon2Params", "cipherData", "cipherName", "kdf", "nonce"}
    crypto_missing = crypto_required - set(crypto)
    if crypto_missing:
        raise KeyFileError(
            f"Missing required key-file crypto fields: {sorted(crypto_missing)}"
        )
    if crypto.get("cipherName") != "aes-256-gcm":
        raise KeyFileError("Unsupported key-file cipher")
    if crypto.get("kdf") != "argon2.IDKey":
        raise KeyFileError("Unsupported key-file KDF")
    params = crypto.get("argon2Params", {})
    if not isinstance(params, dict):
        raise KeyFileError("Key file argon2Params must be an object")

    def decode_hex(value, name):
        if (
            not isinstance(value, str)
            or not value.startswith("0x")
            or value != value.lower()
            or len(value[2:]) % 2
        ):
            raise KeyFileError(f"Key file {name} must be 0x-prefixed lowercase hex")
        try:
            return bytes.fromhex(value[2:])
        except ValueError as error:
            raise KeyFileError(f"Key file {name} must contain hexadecimal data") from error

    try:
        salt_text = params["salt"]
        nonce_text = crypto["nonce"]
        payload_text = crypto["cipherData"]
        if not all(isinstance(value, str) for value in (salt_text, nonce_text, payload_text)):
            raise TypeError("cryptographic fields must be strings")
        salt = decode_hex(salt_text, "salt")
        nonce = decode_hex(nonce_text, "nonce")
        payload = decode_hex(payload_text, "cipherData")
    except KeyFileError:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise KeyFileError("Invalid or missing key-file cryptographic field") from error
    if len(salt) != 16 or len(nonce) != 12 or len(payload) < 16:
        raise KeyFileError("Invalid key-file cryptographic field length")
    effective_params = dict(DEFAULT_KDF_CONFIG)
    for key in effective_params:
        if key not in params:
            continue
        value = params[key]
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise KeyFileError(f"Key file Argon2 {key} must be a positive integer")
        effective_params[key] = value
    if effective_params["hashLength"] != 32:
        raise KeyFileError("AES-256-GCM key files require a 32-byte Argon2 output")
    try:
        key = _argon2(password, salt, effective_params)
    except (TypeError, ValueError, OverflowError) as error:
        raise KeyFileError("Invalid Argon2 key-file parameters") from error
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


def encrypt(
    store: KeyStore,
    password: str,
    *,
    timestamp: int | None = None,
    kdf_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(store, KeyStore):
        raise KeyFileError("Key-file encryption requires a KeyStore")
    if not isinstance(password, str):
        raise KeyFileError("Key-file password must be a string")
    if timestamp is not None and (
        not isinstance(timestamp, int) or isinstance(timestamp, bool) or timestamp < 0
    ):
        raise KeyFileError("Key file timestamp must be a non-negative integer")
    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
    params = {"salt": f"0x{salt.hex()}", **_kdf_config(kdf_config)}
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
        "timestamp": int(time.time()) if timestamp is None else timestamp,
        "version": 1,
    }


class KeyFile:
    """Password-bound compatibility facade around key-file functions."""

    def __init__(self, password: str):
        self.password = password

    @classmethod
    def set_password(cls, password: str) -> "KeyFile":
        return cls(password)

    def encrypt(
        self,
        store: KeyStore,
        *,
        timestamp: int | None = None,
        kdf_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return encrypt(
            store, self.password, timestamp=timestamp, kdf_config=kdf_config
        )

    def decrypt(self, document: dict[str, Any]) -> KeyStore:
        return decrypt(document, self.password)

    @staticmethod
    def needs_upgrade(
        document: dict[str, Any], target_config: dict[str, Any] | None = None
    ) -> bool:
        return needs_upgrade(document, target_config)
