import bech32

HRP = "zts"


class TokenStandard:
    LENGTH = 10

    def __init__(self, hrp: str, core: bytes):
        if not isinstance(core, (bytes, bytearray, memoryview)):
            raise TypeError("Token-standard core must be bytes-like")
        core = bytes(core)
        if hrp != HRP:
            raise ValueError(f"Token-standard HRP must be {HRP!r}")
        if len(core) != self.LENGTH:
            raise ValueError(f"Token-standard core must be exactly {self.LENGTH} bytes")
        self.hrp = hrp
        self.core = core

    def __str__(self):
        return bech32.bech32_encode(self.hrp, bech32.convertbits(self.core, 8, 5, True))

    @staticmethod
    def parse(token_standard: str):
        """Get Address instance from bech32 encoded address string.

        Parameters
        ----------
        address : str
            For example, z1qqjnwjjpnue8xmmpanz6csze6tcmtzzdtfsww7

        Returns
        -------
        Address instance

        Example
        -------
        In [0]: a = Address.parse("z1qqjnwjjpnue8xmmpanz6csze6tcmtzzdtfsww7")

        In [1]: str(a) # Also, check a.__dict__
        Out[1]: 'z1qqjnwjjpnue8xmmpanz6csze6tcmtzzdtfsww7'
        """
        hrp, bcore = bech32.bech32_decode(token_standard)
        if hrp != HRP or bcore is None:
            raise ValueError("Invalid Zenon token standard or HRP")
        core = bech32.convertbits(bcore, 5, 8, False)
        if core is None:
            raise ValueError("Invalid Zenon token-standard encoding")
        result = TokenStandard(hrp, bytes(core))
        if str(result) != token_standard:
            raise ValueError("Non-canonical Zenon token-standard encoding")
        return result

    @staticmethod
    def from_hex(ts_hex: str):
        return TokenStandard.from_core(bytes.fromhex(ts_hex.removeprefix("0x")))

    @staticmethod
    def from_core(core: bytes) -> "TokenStandard":
        return TokenStandard(HRP, core)

    @staticmethod
    def from_json(value: dict) -> "TokenStandard":
        if not isinstance(value, dict):
            raise TypeError("Token-standard JSON must be an object")
        core = value.get("core")
        if not isinstance(core, str) or len(core) != TokenStandard.LENGTH * 2:
            raise ValueError(
                "Token-standard JSON core must be exactly 20 hexadecimal characters"
            )
        if core != core.lower():
            raise ValueError("Token-standard JSON core must use lowercase hexadecimal characters")
        try:
            decoded = bytes.fromhex(core)
        except ValueError as error:
            raise ValueError(
                "Token-standard JSON core must contain only hexadecimal characters"
            ) from error
        return TokenStandard(value.get("hrp", HRP), decoded)

    def to_json(self) -> dict:
        return {"core": self.core_to_hex.removeprefix("0x")}

    def to_bytes(self) -> bytes:
        return bytes(self.core)

    def __bytes__(self) -> bytes:
        return self.to_bytes()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, TokenStandard) and self.core == other.core

    def __hash__(self) -> int:
        return hash(self.core)

    @property
    def core_to_hex(self):
        return f"0x{bytes(self.core).hex()}"


EMPTY_ZTS = TokenStandard.parse("zts1qqqqqqqqqqqqqqqqtq587y")
ZNN_ZTS = TokenStandard.parse("zts1znnxxxxxxxxxxxxx9z4ulx")
QSR_ZTS = TokenStandard.parse("zts1qsrxxxxxxxxxxxxxmrhjll")
