from znn.model.primitives.hash import EMPTY_HASH
from znn.model.primitives.hash import Hash


class HashHeight:
    def __init__(self, hash_instance: Hash, height: int):
        if not isinstance(hash_instance, Hash):
            raise TypeError("hash_instance must be a Hash")
        if not isinstance(height, int) or isinstance(height, bool):
            raise TypeError("height must be an integer")
        if not 0 <= height <= (1 << 64) - 1:
            raise ValueError("height must fit an unsigned 64-bit integer")
        self.height = height
        self.hash = hash_instance

    def __str__(self):
        return self.to_bytes().hex()

    def to_bytes(self) -> bytes:
        return self.hash.core + self.height.to_bytes(8, "big")

    def __bytes__(self) -> bytes:
        return self.to_bytes()

    @staticmethod
    def from_json(json_data):
        if not json_data:
            return EMPTY_HASH_HEIGHT
        return HashHeight(Hash.parse(json_data["hash"]), int(json_data["height"]))

    def to_json(self):
        return {"hash": str(self.hash), "height": self.height}


EMPTY_HASH_HEIGHT = HashHeight(EMPTY_HASH, 0)
