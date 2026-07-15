import hashlib
from copy import deepcopy


class Hash:
    LENGTH = 32

    def __init__(self, core: bytes):
        core = bytes(core)
        if len(core) != self.LENGTH:
            raise ValueError(f"Hash core must be exactly {self.LENGTH} bytes")
        self.core = core

    def __str__(self):
        return self.core.hex()

    @staticmethod
    def parse(hex_str: str) -> "Hash":
        if not isinstance(hex_str, str) or len(hex_str) != Hash.LENGTH * 2:
            raise ValueError("Hash text must be exactly 64 hexadecimal characters")
        try:
            core = bytes.fromhex(hex_str)
        except ValueError as error:
            raise ValueError("Hash text must contain only hexadecimal characters") from error
        if hex_str != hex_str.lower():
            raise ValueError("Hash text must use lowercase hexadecimal characters")
        return Hash(core)

    @staticmethod
    def digest(data_bytes: bytes) -> "Hash":
        core = hashlib.sha3_256(data_bytes).digest()
        return Hash(core)

    @staticmethod
    def id(text: str) -> str:
        return f"0x{Hash.digest(text.encode())}"

    def to_bytes(self) -> bytes:
        return self.core

    @staticmethod
    def from_json(value: dict) -> "Hash":
        instance = Hash.__new__(Hash)
        instance.core = deepcopy(value["core"])
        instance._wire_json = deepcopy(value)
        return instance

    def to_json(self) -> dict:
        if hasattr(self, "_wire_json"):
            return deepcopy(self._wire_json)
        return {"core": self.core.hex()}

    def __bytes__(self) -> bytes:
        return self.core

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Hash) and self.core == other.core

    def __hash__(self) -> int:
        return hash(self.core)


EMPTY_HASH = Hash.parse(
    "0000000000000000000000000000000000000000000000000000000000000000"
)
