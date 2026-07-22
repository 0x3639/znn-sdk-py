import base64
import re

from znn.model._base64 import decode_model_base64
from znn.model.primitives.address import Address
from znn.model.primitives.address import EMPTY_ADDRESS
from znn.model.primitives.hash import EMPTY_HASH
from znn.model.primitives.hash import Hash
from znn.model.primitives.hash_height import EMPTY_HASH_HEIGHT
from znn.model.primitives.hash_height import HashHeight
from znn.model.primitives.token_standard import EMPTY_ZTS
from znn.model.primitives.token_standard import TokenStandard


class AccountBlock:
    def __init__(self, *args, **kwargs):
        self.version = 1
        self.block_type = 0
        self.chain_identifier = 1
        self.from_block_hash = EMPTY_HASH
        self.hash = EMPTY_HASH
        self.previous_hash = EMPTY_HASH
        self.height = 0
        self.momentum_acknowledged = EMPTY_HASH_HEIGHT
        self.address = EMPTY_ADDRESS
        self.to_address = EMPTY_ADDRESS
        self.amount = 0
        self.token_standard = EMPTY_ZTS
        self.fused_plasma = 0
        self.data = bytes.fromhex("")
        self.difficulty = 0
        self.nonce = bytes.fromhex("0000000000000000")
        self.public_key = b""
        self.signature = b""
        self._extra_fields = {}
        allowed = set(self.__dict__) | {"_momentum_was_empty"}
        unknown = set(kwargs) - allowed
        if unknown:
            raise TypeError(
                f"AccountBlock got unexpected keyword arguments: {sorted(unknown)}"
            )
        self.__dict__.update(kwargs)

    @staticmethod
    def from_json(json_data, *, strict=True, require_response=False):
        if not isinstance(json_data, dict):
            raise TypeError("Account-block JSON must be an object")
        known_keys = {
            "version", "blockType", "chainIdentifier", "fromBlockHash", "hash",
            "previousHash", "height", "momentumAcknowledged", "address",
            "toAddress", "amount", "tokenStandard", "fusedPlasma", "data",
            "difficulty", "nonce", "publicKey", "signature",
        }
        required = {
            "version", "blockType", "chainIdentifier", "fromBlockHash", "hash",
            "previousHash", "height", "momentumAcknowledged", "address",
            "toAddress", "amount", "tokenStandard", "fusedPlasma", "data",
            "difficulty", "nonce", "publicKey", "signature",
        }
        missing = required - set(json_data)
        if strict and missing:
            raise ValueError(f"Missing required account-block fields: {sorted(missing)}")
        response_required = {"descendantBlocks", "basePlasma", "usedPlasma", "changesHash"}
        response_missing = response_required - set(json_data)
        if strict and require_response and response_missing:
            raise ValueError(
                f"Missing required account-block response fields: {sorted(response_missing)}"
            )

        def number(key, default):
            value = json_data.get(key, default)
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"Account-block {key} must be an integer")
            if not 0 <= value <= (1 << 64) - 1:
                raise ValueError(f"Account-block {key} must fit an unsigned 64-bit integer")
            return value

        amount_text = json_data.get("amount", "0")
        if not isinstance(amount_text, str) or not re.fullmatch(
            r"0|[1-9][0-9]*", amount_text
        ):
            raise ValueError("Account-block amount must be a canonical decimal string")

        def binary(key):
            value = json_data.get(key, "")
            return decode_model_base64(value, f"Account-block {key}")

        nonce_text = json_data.get("nonce", "0000000000000000")
        if not isinstance(nonce_text, str) or len(nonce_text) != 16:
            raise ValueError("Account-block nonce must be exactly 16 hexadecimal characters")
        if nonce_text != nonce_text.lower():
            raise ValueError("Account-block nonce must use lowercase hexadecimal characters")
        try:
            nonce = bytes.fromhex(nonce_text)
        except ValueError as error:
            raise ValueError("Account-block nonce must contain only hexadecimal characters") from error
        kwargs = {
            "version": number("version", 1),
            "block_type": number("blockType", 0),
            "chain_identifier": number("chainIdentifier", 1),
            "from_block_hash": Hash.parse(json_data.get("fromBlockHash", str(EMPTY_HASH))),
            "hash": Hash.parse(json_data.get("hash", str(EMPTY_HASH))),
            "previous_hash": Hash.parse(json_data.get("previousHash", str(EMPTY_HASH))),
            "height": number("height", 0),
            "momentum_acknowledged": HashHeight.from_json(
                json_data.get("momentumAcknowledged"), strict=strict
            ),
            "address": Address.parse(json_data.get("address", str(EMPTY_ADDRESS))),
            "to_address": Address.parse(json_data.get("toAddress", str(EMPTY_ADDRESS))),
            "amount": int(amount_text),
            "token_standard": TokenStandard.parse(json_data.get("tokenStandard", str(EMPTY_ZTS))),
            "fused_plasma": number("fusedPlasma", 0),
            "data": binary("data"),
            "difficulty": number("difficulty", 0),
            "nonce": nonce,
            "public_key": binary("publicKey"),
            "signature": binary("signature"),
            "_momentum_was_empty": not bool(json_data.get("momentumAcknowledged")),
            "_extra_fields": {
                key: value for key, value in json_data.items() if key not in known_keys
            },
        }
        extras = kwargs["_extra_fields"]
        if "descendantBlocks" in extras and not isinstance(extras["descendantBlocks"], list):
            raise TypeError("Account-block descendantBlocks must be an array")
        if isinstance(extras.get("descendantBlocks"), list):
            extras["descendantBlocks"] = [
                AccountBlock.from_json(
                    item, strict=strict, require_response=require_response
                )
                for item in extras["descendantBlocks"]
            ]
        for key in ("basePlasma", "usedPlasma"):
            if key in extras and (
                not isinstance(extras[key], int)
                or isinstance(extras[key], bool)
                or not 0 <= extras[key] <= (1 << 64) - 1
            ):
                raise ValueError(
                    f"Account-block {key} must fit an unsigned 64-bit integer"
                )
        if "changesHash" in extras:
            if not isinstance(extras["changesHash"], str):
                raise TypeError("Account-block changesHash must be a hash string")
            extras["changesHash"] = Hash.parse(extras["changesHash"])
        for key in ("token", "confirmationDetail", "pairedAccountBlock"):
            if key in extras and not isinstance(extras[key], dict):
                raise TypeError(f"Account-block {key} must be an object")
        if isinstance(extras.get("pairedAccountBlock"), dict):
            extras["pairedAccountBlock"] = AccountBlock.from_json(
                extras["pairedAccountBlock"],
                strict=strict,
                require_response=require_response,
            )
        if isinstance(extras.get("token"), dict):
            from znn.model.models import Token
            extras["token"] = Token.from_json(extras["token"], strict=strict)
        if isinstance(extras.get("confirmationDetail"), dict):
            from znn.model.models import AccountBlockConfirmationDetail
            extras["confirmationDetail"] = AccountBlockConfirmationDetail.from_json(
                extras["confirmationDetail"], strict=strict
            )
        return AccountBlock(**kwargs)

    def to_json(self):
        nonce = self.nonce.hex() if isinstance(self.nonce, bytes) else self.nonce
        result = {
            "version": self.version,
            "blockType": self.block_type,
            "chainIdentifier": self.chain_identifier,
            "fromBlockHash": str(self.from_block_hash),
            "hash": str(self.hash),
            "previousHash": str(self.previous_hash),
            "height": self.height,
            "momentumAcknowledged": {} if getattr(self, "_momentum_was_empty", False) else self.momentum_acknowledged.to_json(),
            "address": str(self.address),
            "toAddress": str(self.to_address),
            "amount": str(self.amount),
            "tokenStandard": str(self.token_standard),
            "fusedPlasma": self.fused_plasma,
            "data": base64.b64encode(self.data).decode(),
            "difficulty": self.difficulty,
            "nonce": nonce,
            "publicKey": base64.b64encode(self.public_key).decode(),
            "signature": base64.b64encode(self.signature).decode(),
        }
        def wire(value):
            if isinstance(value, list):
                return [wire(item) for item in value]
            if isinstance(value, Hash):
                return str(value)
            if hasattr(value, "to_json"):
                return value.to_json()
            return value

        response_fields = {
            "token": self._extra_fields.get("token"),
            "descendantBlocks": self._extra_fields.get("descendantBlocks"),
            "basePlasma": self._extra_fields.get("basePlasma"),
            "usedPlasma": self._extra_fields.get("usedPlasma"),
            "changesHash": self._extra_fields.get("changesHash"),
            "confirmationDetail": self._extra_fields.get("confirmationDetail"),
            "pairedAccountBlock": self._extra_fields.get("pairedAccountBlock"),
        }
        result.update({
            key: wire(value)
            for key, value in response_fields.items()
            if key in self._extra_fields
        })
        result.update({key: wire(value) for key, value in self._extra_fields.items()})
        return result

    @staticmethod
    def contract_call(contract_address, zts, amount: int, data):
        ab = AccountBlock()
        ab.block_type = 2
        ab.to_address = contract_address
        ab.token_standard = zts
        ab.amount = amount
        ab.data = data
        return ab

    @staticmethod
    def send(to_address: Address, zts: TokenStandard, amount: int):
        return AccountBlock(
            block_type=2, to_address=to_address, token_standard=zts, amount=int(amount)
        )

    @staticmethod
    def receive(from_block_hash: Hash):
        return AccountBlock(block_type=3, from_block_hash=from_block_hash)

    def get_hash(self):
        if not isinstance(self.nonce, bytes) or len(self.nonce) != 8:
            raise ValueError("Account-block nonce must be exactly 8 bytes")
        if self.amount < 0 or self.amount >= 1 << 256:
            raise ValueError("Account-block amount must fit an unsigned 256-bit integer")
        unsigned_64 = {
            "version": self.version,
            "chain_identifier": self.chain_identifier,
            "block_type": self.block_type,
            "height": self.height,
            "momentum_height": self.momentum_acknowledged.height,
            "fused_plasma": self.fused_plasma,
            "difficulty": self.difficulty,
        }
        for name, value in unsigned_64.items():
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or not 0 <= value <= (1 << 64) - 1
            ):
                raise ValueError(f"Account-block {name} must fit an unsigned 64-bit integer")
        return Hash.digest(
            b"".join(
                [
                    self.version.to_bytes(8, "big"),
                    self.chain_identifier.to_bytes(8, "big"),
                    self.block_type.to_bytes(8, "big"),
                    self.previous_hash.core,
                    self.height.to_bytes(8, "big"),
                    self.momentum_acknowledged.hash.core,
                    self.momentum_acknowledged.height.to_bytes(8, "big"),
                    bytes(self.address.core),
                    bytes(self.to_address.core),
                    self.amount.to_bytes(32, "big"),
                    bytes(self.token_standard.core),
                    self.from_block_hash.core,
                    Hash.digest(b"").core,
                    Hash.digest(self.data).core,
                    self.fused_plasma.to_bytes(8, "big"),
                    self.difficulty.to_bytes(8, "big"),
                    self.nonce,
                ]
            )
        )
