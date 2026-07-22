from nacl.encoding import Base64Encoder
from nacl.encoding import HexEncoder
from nacl.encoding import RawEncoder
from nacl.signing import SigningKey
from nacl.signing import VerifyKey

from znn.model.primitives.address import Address
from znn.model.primitives.hash import Hash
from znn.wallet.utils import from_ascii


def verify_signature(
    public_key_hex: str,
    signature: str,
    unsigned_message: str,
    encoding=Base64Encoder,
):
    verifying_key = VerifyKey(public_key_hex.encode(), encoder=HexEncoder)
    verifying_key.verify(
        Base64Encoder.encode(unsigned_message.encode()),
        from_ascii(signature.encode(), "", "base64"),
        encoder=encoding,
    )


class KeyPair:
    """Ed25519 signing key pair.

    CPython cannot guarantee erasure of key material: the private key is held
    in immutable ``str``/``bytes`` objects (including inside PyNaCl), and
    copies may persist in interpreter memory until garbage collection, or in
    allocator arenas afterwards. :meth:`clear` drops references on a
    best-effort basis only. Use an external signer or PoW/signing hardware if
    guaranteed zeroization is required.
    """

    def __init__(self, private_key: str | bytes):
        private_key_hex = private_key.hex() if isinstance(private_key, bytes) else private_key
        if len(bytes.fromhex(private_key_hex)) != 32:
            raise ValueError("Ed25519 private key must be exactly 32 bytes")
        self.private_key = private_key_hex
        self.signing_key = SigningKey(private_key_hex.encode(), encoder=HexEncoder)
        self.public_key = self.signing_key.verify_key.encode(
            encoder=HexEncoder
        ).decode()
        self.address = Address.from_public_key_hex(self.public_key)

    @property
    def public_key_bytes(self) -> bytes:
        return bytes.fromhex(self.public_key)

    def sign(self, message: str | bytes | Hash, encoding=None) -> bytes:
        """Sign a message while preserving the legacy text-signing API.

        Text input remains base64-encoded for backward compatibility. Bytes and
        Hash values return the protocol's raw 64-byte Ed25519 signature.
        """
        if isinstance(message, Hash):
            payload = message.core
            selected_encoder = RawEncoder if encoding is None else encoding
        elif isinstance(message, bytes):
            payload = message
            selected_encoder = RawEncoder if encoding is None else encoding
        elif isinstance(message, str):
            payload = message.encode()
            selected_encoder = Base64Encoder if encoding is None else encoding
        else:
            raise TypeError("message must be str, bytes, or Hash")
        return self.signing_key.sign(payload, encoder=selected_encoder).signature

    def sign_hash(self, block_hash: Hash | bytes) -> bytes:
        payload = block_hash.core if isinstance(block_hash, Hash) else bytes(block_hash)
        if len(payload) != Hash.LENGTH:
            raise ValueError("An account-block hash must be exactly 32 bytes")
        signature = self.signing_key.sign(payload).signature
        if len(signature) != 64:
            raise RuntimeError("Ed25519 produced an invalid signature length")
        return signature

    def clear(self) -> None:
        """Drop key references. Best-effort only; see the class docstring."""
        self.private_key = ""
        self.signing_key = None
        self.public_key = ""
