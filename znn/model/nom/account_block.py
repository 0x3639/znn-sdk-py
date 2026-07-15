import base64

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
        self.__dict__.update(kwargs)

    @staticmethod
    def from_json(json_data):
        known_keys = {
            "version", "blockType", "chainIdentifier", "fromBlockHash", "hash",
            "previousHash", "height", "momentumAcknowledged", "address",
            "toAddress", "amount", "tokenStandard", "fusedPlasma", "data",
            "difficulty", "nonce", "publicKey", "signature",
        }
        nonce_text = json_data.get("nonce", "0000000000000000")
        try:
            nonce = bytes.fromhex(nonce_text)
        except ValueError:
            nonce = nonce_text
        kwargs = {
            "version": int(json_data.get("version", 1)),
            "block_type": int(json_data.get("blockType", 0)),
            "chain_identifier": int(json_data.get("chainIdentifier", 1)),
            "from_block_hash": Hash.parse(json_data.get("fromBlockHash", str(EMPTY_HASH))),
            "hash": Hash.parse(json_data.get("hash", str(EMPTY_HASH))),
            "previous_hash": Hash.parse(json_data.get("previousHash", str(EMPTY_HASH))),
            "height": int(json_data.get("height", 0)),
            "momentum_acknowledged": HashHeight.from_json(
                json_data.get("momentumAcknowledged")
            ),
            "address": Address.parse(json_data.get("address", str(EMPTY_ADDRESS))),
            "to_address": Address.parse(json_data.get("toAddress", str(EMPTY_ADDRESS))),
            "amount": int(json_data.get("amount", 0)),
            "token_standard": TokenStandard.parse(json_data.get("tokenStandard", str(EMPTY_ZTS))),
            "fused_plasma": int(json_data.get("fusedPlasma", 0)),
            "data": base64.b64decode(json_data.get("data", "")),
            "difficulty": int(json_data.get("difficulty", 0)),
            "nonce": nonce,
            "public_key": base64.b64decode(json_data.get("publicKey", "")),
            "signature": base64.b64decode(json_data.get("signature", "")),
            "_momentum_was_empty": not bool(json_data.get("momentumAcknowledged")),
            "_extra_fields": {
                key: value for key, value in json_data.items() if key not in known_keys
            },
        }
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
        response_fields = {
            "token": self._extra_fields.get("token"),
            "descendantBlocks": self._extra_fields.get("descendantBlocks"),
            "basePlasma": self._extra_fields.get("basePlasma"),
            "usedPlasma": self._extra_fields.get("usedPlasma"),
            "changesHash": self._extra_fields.get("changesHash"),
            "confirmationDetail": self._extra_fields.get("confirmationDetail"),
            "pairedAccountBlock": self._extra_fields.get("pairedAccountBlock"),
        }
        result.update(
            {key: value for key, value in response_fields.items() if key in self._extra_fields}
        )
        result.update(self._extra_fields)
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
