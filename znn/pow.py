"""Zenon account-block proof-of-work generation and verification."""

from __future__ import annotations

import hashlib
import secrets


def _validate(hash_hex: str, difficulty: int, nonce_hex: str | None = None) -> bytes:
    try:
        data_hash = bytes.fromhex(hash_hex)
    except ValueError as error:
        raise ValueError("PoW hash must be hexadecimal") from error
    if len(data_hash) != 32:
        raise ValueError("PoW hash must be exactly 32 bytes")
    if not isinstance(difficulty, int) or isinstance(difficulty, bool) or difficulty < 0:
        raise ValueError("PoW difficulty must be a non-negative integer")
    if nonce_hex is not None:
        try:
            nonce = bytes.fromhex(nonce_hex)
        except ValueError as error:
            raise ValueError("PoW nonce must be hexadecimal") from error
        if len(nonce) != 8:
            raise ValueError("PoW nonce must be exactly 8 bytes")
    return data_hash


def verify(hash_hex: str, difficulty: int, nonce_hex: str) -> bool:
    data_hash = _validate(hash_hex, difficulty, nonce_hex)
    nonce = bytes.fromhex(nonce_hex)
    if difficulty == 0:
        return nonce == bytes(8)
    threshold = (1 << 64) - ((1 << 64) // difficulty)
    digest = hashlib.sha3_256(nonce + data_hash).digest()
    return int.from_bytes(digest[:8], "little") >= threshold


def generate(hash_hex: str, difficulty: int, start_nonce: bytes | None = None) -> str:
    _validate(hash_hex, difficulty)
    if difficulty == 0:
        return "0000000000000000"
    nonce = secrets.token_bytes(8) if start_nonce is None else bytes(start_nonce)
    if len(nonce) != 8:
        raise ValueError("PoW starting nonce must be exactly 8 bytes")
    value = int.from_bytes(nonce, "little")
    while True:
        candidate = value.to_bytes(8, "little").hex()
        if verify(hash_hex, difficulty, candidate):
            return candidate
        value = (value + 1) & ((1 << 64) - 1)


def account_block_data_hash(address: bytes, previous_hash: bytes) -> str:
    if len(address) != 20 or len(previous_hash) != 32:
        raise ValueError("PoW data requires a 20-byte address and 32-byte previous hash")
    return hashlib.sha3_256(address + previous_hash).hexdigest()
