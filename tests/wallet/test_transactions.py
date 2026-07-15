import asyncio
import pytest

from znn.model.nom.account_block import AccountBlock
from znn.model.primitives.address import Address
from znn.model.primitives.hash import Hash
from znn.model.primitives.token_standard import ZNN_ZTS
from znn.pow import account_block_data_hash, generate, verify
from znn.wallet.transact import (
    ReceiveValidationError, Transact, TransactionError,
)


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


def test_transaction_validation_and_provider_failure_matrix(monkeypatch):
    async def scenario():
        ledger = FakeLedger()
        tx = Transact(PRIVATE_KEY, ledger, FakePlasma())
        source_hash = Hash(bytes([9]) * 32)

        with pytest.raises(ReceiveValidationError, match="non-empty"):
            await tx.prepare_block(AccountBlock.receive(Hash(bytes(32))))

        with_data = AccountBlock.receive(source_hash)
        with_data.data = b"unexpected"
        with pytest.raises(ReceiveValidationError, match="empty data"):
            await tx.prepare_block(with_data)

        with pytest.raises(ReceiveValidationError, match="does not exist"):
            await tx.prepare_block(AccountBlock.receive(source_hash))

        ledger.source = {"toAddress": str(EMPTY_DESTINATION)}
        with pytest.raises(ReceiveValidationError, match="does not match"):
            await tx.prepare_block(AccountBlock.receive(source_hash))

        ledger.source = AccountBlock(to_address=tx.keypair.address)
        assert (await tx.prepare_block(AccountBlock.receive(source_hash))).block_type == 3

        class FrontierLedger(FakeLedger):
            async def get_frontier_account_block(self, _address):
                return AccountBlock(height=4, hash=Hash(bytes([7]) * 32))

        frontier_tx = Transact(PRIVATE_KEY, FrontierLedger(), FakePlasma())
        frontier = await frontier_tx.prepare_block(
            AccountBlock.send(EMPTY_DESTINATION, ZNN_ZTS, 1)
        )
        assert frontier.height == 5 and frontier.previous_hash == Hash(bytes([7]) * 32)

        invalid_difficulty = AccountBlock.send(EMPTY_DESTINATION, ZNN_ZTS, 1)
        invalid_difficulty.difficulty = True
        with pytest.raises(TransactionError, match="Difficulty"):
            await tx.prepare_block(invalid_difficulty)

        class InvalidPlasma:
            async def get_internal_required_pow_for_account_block(self, _block):
                return {"requiredDifficulty": True, "basePlasma": 0}

        with pytest.raises(TransactionError, match="invalid required"):
            await Transact(PRIVATE_KEY, FakeLedger(), InvalidPlasma()).prepare_block(
                AccountBlock.send(EMPTY_DESTINATION, ZNN_ZTS, 1)
            )

        async def async_provider(_hash, _difficulty):
            return "00" * 8

        async_tx = Transact(PRIVATE_KEY, FakeLedger(), FakePlasma(1), async_provider)
        assert (await async_tx.prepare_block(
            AccountBlock.send(EMPTY_DESTINATION, ZNN_ZTS, 1)
        )).nonce == bytes(8)

        short_tx = Transact(
            PRIVATE_KEY, FakeLedger(), FakePlasma(2), lambda *_args: "00"
        )
        with pytest.raises(TransactionError, match="invalid length"):
            await short_tx.prepare_block(
                AccountBlock.send(EMPTY_DESTINATION, ZNN_ZTS, 1)
            )

        original_verify = verify
        monkeypatch.setattr("znn.wallet.transact.verify", lambda *_args: False)
        rejected_tx = Transact(
            PRIVATE_KEY, FakeLedger(), FakePlasma(2), lambda *_args: "00" * 8
        )
        with pytest.raises(TransactionError, match="invalid nonce"):
            await rejected_tx.prepare_block(
                AccountBlock.send(EMPTY_DESTINATION, ZNN_ZTS, 1)
            )

        def invalid_verify(*_args):
            raise ValueError("bad nonce")

        monkeypatch.setattr("znn.wallet.transact.verify", invalid_verify)
        with pytest.raises(TransactionError, match="invalid nonce"):
            await rejected_tx.prepare_block(
                AccountBlock.send(EMPTY_DESTINATION, ZNN_ZTS, 1)
            )
        monkeypatch.setattr("znn.wallet.transact.verify", original_verify)

        class RejectingLedger(FakeLedger):
            async def publish_raw_transaction(self, _block):
                return {"unexpected": True}

        with pytest.raises(TransactionError, match="must return null"):
            await Transact(PRIVATE_KEY, RejectingLedger(), FakePlasma()).publish_block(
                AccountBlock()
            )

        helper_tx = Transact(PRIVATE_KEY, FakeLedger(), FakePlasma())
        assert (await helper_tx.send(EMPTY_DESTINATION, ZNN_ZTS, 3)).amount == 3
        assert (
            await helper_tx.call_contract(EMPTY_DESTINATION, ZNN_ZTS, 0, b"call")
        ).data == b"call"
        assert helper_tx._ledger() is helper_tx.ledger_api
        assert helper_tx._plasma() is helper_tx.plasma_api
        assert Transact(PRIVATE_KEY)._ledger() is not None
        assert Transact(PRIVATE_KEY)._plasma() is not None

    asyncio.run(scenario())


EMPTY_DESTINATION = Address.from_core(bytes([8]) * 20)
