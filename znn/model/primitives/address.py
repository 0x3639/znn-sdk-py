import hashlib
from copy import deepcopy

import bech32

HRP = "z"


class Address:
    LENGTH = 20

    def __init__(self, hrp: str, core: bytes):
        core = bytes(core)
        if hrp != HRP:
            raise ValueError(f"Address HRP must be {HRP!r}")
        if len(core) != self.LENGTH:
            raise ValueError(f"Address core must be exactly {self.LENGTH} bytes")
        self.hrp = hrp
        # Keep the historical list-valued ``core`` API while validating via bytes.
        self.core = list(core)

    def __str__(self):
        return bech32.bech32_encode(self.hrp, bech32.convertbits(self.core, 8, 5, True))

    @staticmethod
    def from_public_key_hex(public_key_hex: str):
        """Get Address instance from public key hex string.

        Parameters
        ----------
        public_key_hex : str
            Without the leading 0x

        Example
        -------
        In [0]: pubkey_hex = "3e13d7238d0e768a567dce84b54915f2323f2dcd0ef9a716d9c61abed631ba10"
        In [0]: a = Address.from_public_key_hex(pubkey_hex)

        In [1]: str(a) # Also, check a.__dict__
        Out[1]: 'z1qqjnwjjpnue8xmmpanz6csze6tcmtzzdtfsww7'
        """
        public_key = bytes.fromhex(public_key_hex)
        if len(public_key) != 32:
            raise ValueError("Ed25519 public key must be exactly 32 bytes")
        core = bytes([0]) + hashlib.sha3_256(public_key).digest()[:19]
        return Address(HRP, core)

    @staticmethod
    def from_public_key(public_key: bytes) -> "Address":
        return Address.from_public_key_hex(bytes(public_key).hex())

    @staticmethod
    def parse(address: str):
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
        hrp, bcore = bech32.bech32_decode(address)
        if hrp != HRP or bcore is None:
            raise ValueError("Invalid Zenon address or address HRP")
        core = bech32.convertbits(bcore, 5, 8, False)
        if core is None:
            raise ValueError("Invalid Zenon address encoding")
        result = Address(hrp, bytes(core))
        if str(result) != address:
            raise ValueError("Non-canonical Zenon address encoding")
        return result

    @staticmethod
    def from_hex(address_hex: str):
        return Address.from_core(bytes.fromhex(address_hex.removeprefix("0x")))

    @staticmethod
    def from_core(core: bytes) -> "Address":
        return Address(HRP, core)

    @staticmethod
    def from_json(value: dict) -> "Address":
        instance = Address.__new__(Address)
        instance.hrp = value["hrp"]
        instance.core = deepcopy(value["core"])
        instance._wire_json = deepcopy(value)
        return instance

    def to_json(self) -> dict:
        if hasattr(self, "_wire_json"):
            return deepcopy(self._wire_json)
        return {"hrp": self.hrp, "core": self.core_to_hex.removeprefix("0x")}

    def to_bytes(self) -> bytes:
        return bytes(self.core)

    def __bytes__(self) -> bytes:
        return self.to_bytes()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Address) and self.core == other.core

    def __hash__(self) -> int:
        return hash(self.core)

    @property
    def core_to_hex(self):
        return f"0x{bytes(self.core).hex()}"


EMPTY_ADDRESS = Address.parse("z1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqsggv2f")
PLASMA_ADDRESS = Address.parse("z1qxemdeddedxplasmaxxxxxxxxxxxxxxxxsctrp")
PILLAR_ADDRESS = Address.parse("z1qxemdeddedxpyllarxxxxxxxxxxxxxxxsy3fmg")
TOKEN_ADDRESS = Address.parse("z1qxemdeddedxt0kenxxxxxxxxxxxxxxxxh9amk0")
SENTINEL_ADDRESS = Address.parse("z1qxemdeddedxsentynelxxxxxxxxxxxxxwy0r2r")
STAKE_ADDRESS = Address.parse("z1qxemdeddedxstakexxxxxxxxxxxxxxxxjv8v62")
SWAP_ADDRESS = Address.parse("z1qxemdeddedxswapxxxxxxxxxxxxxxxxxxl4yww")
SPORK_ADDRESS = Address.parse("z1qxemdeddedxsp0rkxxxxxxxxxxxxxxxx956u48")
ACCELERATOR_ADDRESS = Address.parse("z1qxemdeddedxaccelerat0rxxxxxxxxxxp4tk22")
LIQUIDITY_ADDRESS = Address.parse("z1qxemdeddedxlyquydytyxxxxxxxxxxxxflaaae")
BRIDGE_ADDRESS = Address.parse("z1qxemdeddedxdrydgexxxxxxxxxxxxxxxmqgr0d")
HTLC_ADDRESS = Address.parse("z1qxemdeddedxhtlcxxxxxxxxxxxxxxxxxygecvw")
