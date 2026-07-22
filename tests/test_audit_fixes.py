"""Regression tests for the 2026-07 security/robustness audit fixes."""

import asyncio

import pytest

from znn.client.errors import TransportError
from znn.client.websocket import Subscription, WsClient, _SUBSCRIPTION_TERMINATED
from znn.model.nom.account_block import AccountBlock
from znn.model.primitives.address import Address
from znn.model.primitives.token_standard import ZNN_ZTS
from znn.pow import MAX_POW_DIFFICULTY, PowCancelledError, generate
from znn.wallet.transact import Transact, TransactionError
from znn.wallet.utils import remove_prefix, to_ascii


PRIVATE_KEY = "f58cb2e1add0382c2004fa8e04895a65a3c755553e60187d697c2e5ab9df67ea"


class FakeLedger:
    async def get_frontier_account_block(self, address):
        return None

    async def get_frontier_momentum(self):
        return {"height": 7, "hash": "11" * 32}


class FakePlasma:
    def __init__(self, difficulty):
        self.difficulty = difficulty

    async def get_internal_required_pow_for_account_block(self, block):
        return {"requiredDifficulty": self.difficulty, "basePlasma": 21,
                "availablePlasma": 8}


def test_pow_difficulty_cap_matches_protocol_maximum():
    assert MAX_POW_DIFFICULTY == 141_750_000


def test_generate_rejects_difficulty_above_protocol_cap():
    with pytest.raises(ValueError, match="difficulty"):
        generate("aa" * 32, MAX_POW_DIFFICULTY + 1)


def test_prepare_block_rejects_node_difficulty_above_cap():
    async def scenario():
        tx = Transact(PRIVATE_KEY, FakeLedger(), FakePlasma(MAX_POW_DIFFICULTY + 1))
        block = AccountBlock.send(Address.from_core(bytes([1]) * 20), ZNN_ZTS, 1)
        with pytest.raises(TransactionError, match="difficulty"):
            await tx.prepare_block(block)

    asyncio.run(scenario())


def test_generate_supports_cooperative_cancellation():
    with pytest.raises(PowCancelledError):
        generate("aa" * 32, 1_000_000, bytes(8), cancel=lambda: True)


def test_generate_rejects_non_callable_cancel():
    with pytest.raises(TypeError):
        generate("aa" * 32, 1, bytes(8), cancel=object())


def test_generate_nonce_cancellation_reaches_worker_thread(monkeypatch):
    observed = {"cancelled": False}

    def fake_generate(data_hash, difficulty, start_nonce=None, cancel=None):
        while cancel is None or not cancel():
            pass
        observed["cancelled"] = True
        raise PowCancelledError("cancelled")

    monkeypatch.setattr("znn.wallet.transact.generate", fake_generate)

    async def scenario():
        tx = Transact(PRIVATE_KEY)
        task = asyncio.ensure_future(tx._generate_nonce("aa" * 32, 5))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        for _ in range(100):
            if observed["cancelled"]:
                break
            await asyncio.sleep(0.05)
        assert observed["cancelled"]

    asyncio.run(asyncio.wait_for(scenario(), timeout=15))


def test_wallet_utils_validate_types_without_assert():
    with pytest.raises(TypeError):
        to_ascii("not-bytes")
    with pytest.raises(TypeError):
        remove_prefix(b"bytes-not-str", "prefix")


def test_account_block_rejects_unknown_keyword_arguments():
    with pytest.raises(TypeError, match="unexpected"):
        AccountBlock(shadow_method=lambda: None)


def test_account_block_still_accepts_known_fields():
    block = AccountBlock(block_type=2, amount=5)
    assert block.block_type == 2
    assert block.amount == 5


def test_subscription_termination_without_recorded_error():
    async def scenario():
        subscription = Subscription("sub-1", ["momentums"])
        subscription.queue.put_nowait(_SUBSCRIPTION_TERMINATED)
        with pytest.raises(TransportError):
            await subscription.__anext__()

    asyncio.run(scenario())


def test_ws_request_timeout_validation():
    with pytest.raises(ValueError):
        WsClient("ws://localhost:1", request_timeout=0)
    with pytest.raises(ValueError):
        WsClient("ws://localhost:1", request_timeout=True)


def test_ws_request_times_out_when_node_never_responds():
    class SilentSocket:
        async def send(self, payload):
            return None

    async def scenario():
        client = WsClient("ws://localhost:1", request_timeout=0.05)

        async def fake_connect():
            return client

        client.connect = fake_connect
        client._socket = SilentSocket()
        with pytest.raises(TransportError, match="timed out"):
            await client.send_request("ledger.getFrontierMomentum", [])
        assert client._pending == {}

    asyncio.run(asyncio.wait_for(scenario(), timeout=10))
