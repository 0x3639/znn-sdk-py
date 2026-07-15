import asyncio
import pytest

from znn.model.nom.account_block import AccountBlock
from znn.model.primitives.address import Address
from znn.model.primitives.hash import Hash
from znn.model.primitives.token_standard import ZNN_ZTS
from znn.pow import account_block_data_hash, generate, verify
from znn.wallet.transact import Transact, TransactionError


PRIVATE_KEY = "f58cb2e1add0382c2004fa8e04895a65a3c755553e60187d697c2e5ab9df67ea"


class FakeLedger:
    def __init__(self):
        self.published = []
        self.source = None

    async def get_frontier_account_block(self, address):
        return None

    async def get_frontier_momentum(self):
        return {"height": 7, "hash": "11" * 32}

    async def get_account_block_by_hash(self, block_hash):
        return self.source

    async def publish_raw_transaction(self, block):
        self.published.append(block)
        return None


class FakePlasma:
    def __init__(self, difficulty=0):
        self.difficulty = difficulty

    async def get_internal_required_pow_for_account_block(self, block):
        return {"requiredDifficulty": self.difficulty, "basePlasma": 21,
                "availablePlasma": 8}


def test_prepare_sign_publish_send_receive_and_contract_offline():
    async def scenario():
        ledger = FakeLedger()
        tx = Transact(PRIVATE_KEY, ledger, FakePlasma())
        template = AccountBlock.send(Address.from_core(bytes([1]) * 20), ZNN_ZTS, 5)
        prepared = await tx.prepare_block(template)
        assert ledger.published == []
        assert prepared.height == 1
        assert prepared.momentum_acknowledged.height == 7
        assert prepared.fused_plasma == 21
        assert len(prepared.hash.core) == 32
        assert len(prepared.signature) == 64
        assert await tx.publish_block(prepared) is prepared
        assert ledger.published == [prepared]

        contract = AccountBlock.contract_call(Address.from_core(bytes([2]) * 20), ZNN_ZTS, 0, b"call")
        assert (await tx.fast_forward_block(contract)).data == b"call"

        source_hash = Hash(bytes([3]) * 32)
        ledger.source = {"toAddress": str(tx.keypair.address)}
        received = await tx.receive(source_hash)
        assert received.block_type == 3
        assert received.from_block_hash == source_hash

        pow_tx = Transact(
            PRIVATE_KEY, FakeLedger(), FakePlasma(2),
            lambda data_hash, difficulty: generate(data_hash, difficulty, bytes(8)),
        )
        pow_block = await pow_tx.prepare_block(AccountBlock.send(Address.from_core(bytes([4]) * 20), ZNN_ZTS, 1))
        assert pow_block.difficulty == 2
        assert pow_block.fused_plasma == 8
        data_hash = account_block_data_hash(bytes(pow_block.address), pow_block.previous_hash.core)
        assert verify(data_hash, 2, pow_block.nonce.hex())

        invalid_preselected = AccountBlock.send(Address.from_core(bytes([5]) * 20), ZNN_ZTS, 1)
        invalid_preselected.difficulty = 2
        invalid_preselected.nonce = b""
        with pytest.raises(TransactionError, match="requires an 8-byte nonce"):
            await pow_tx.prepare_block(invalid_preselected)

        too_easy = AccountBlock.send(Address.from_core(bytes([6]) * 20), ZNN_ZTS, 1)
        too_easy.difficulty = 1
        too_easy.nonce = bytes(8)
        with pytest.raises(TransactionError, match="below the node-required"):
            await pow_tx.prepare_block(too_easy)

        malformed_provider = Transact(
            PRIVATE_KEY, FakeLedger(), FakePlasma(2), lambda _hash, _difficulty: "not-hex"
        )
        with pytest.raises(TransactionError, match="non-hexadecimal"):
            await malformed_provider.prepare_block(
                AccountBlock.send(Address.from_core(bytes([7]) * 20), ZNN_ZTS, 1)
            )

    asyncio.run(scenario())
