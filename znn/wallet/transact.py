"""Offline-testable account-block preparation and publication."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Awaitable, Callable

from znn.api.embedded.plasma import PlasmaApi
from znn.api.ledger import LedgerApi
from znn.model.nom.account_block import AccountBlock
from znn.model.primitives.address import Address
from znn.model.primitives.hash import EMPTY_HASH, Hash
from znn.model.primitives.hash_height import HashHeight
from znn.model.primitives.token_standard import TokenStandard
from znn.pow import (
    MAX_POW_DIFFICULTY, PowCancelledError, account_block_data_hash, generate, verify,
)
from znn.wallet.keypair import KeyPair


class TransactionError(Exception):
    """Base error for transaction preparation and publication."""


class ReceiveValidationError(TransactionError):
    """A receive template does not match its source block."""


PowProvider = Callable[[str, int], str | Awaitable[str]]

# At most this many built-in PoW searches run concurrently, no matter how many
# transactions or event loops are active; a threading semaphore is used because
# asyncio primitives cannot be shared across loops.
MAX_CONCURRENT_POW_WORKERS = 8

_POW_SEMAPHORE = threading.BoundedSemaphore(MAX_CONCURRENT_POW_WORKERS)


class Transact:
    def __init__(
        self,
        private_key: str | KeyPair,
        ledger_api: LedgerApi | None = None,
        plasma_api: PlasmaApi | None = None,
        pow_provider: PowProvider | None = None,
    ) -> None:
        self.keypair = private_key if isinstance(private_key, KeyPair) else KeyPair(private_key)
        self.ledger_api = ledger_api
        self.plasma_api = plasma_api
        self.pow_provider = pow_provider

    def _ledger(self) -> LedgerApi:
        return self.ledger_api if self.ledger_api is not None else LedgerApi()

    def _plasma(self) -> PlasmaApi:
        return self.plasma_api if self.plasma_api is not None else PlasmaApi()

    async def _validate_receive(self, block: AccountBlock, ledger: LedgerApi) -> None:
        if block.from_block_hash == EMPTY_HASH:
            raise ReceiveValidationError("Receive blocks require a non-empty source hash")
        if block.data:
            raise ReceiveValidationError("Receive blocks must contain empty data")
        source = await ledger.get_account_block_by_hash(str(block.from_block_hash))
        if source is None:
            raise ReceiveValidationError("Receive source block does not exist")
        destination = source.to_address if isinstance(source, AccountBlock) else source.get("toAddress")
        if str(destination) != str(self.keypair.address):
            raise ReceiveValidationError("Receive source destination does not match signer")

    async def _generate_nonce(self, data_hash: str, difficulty: int) -> str:
        if self.pow_provider is None:
            cancelled = threading.Event()

            def worker():
                while not _POW_SEMAPHORE.acquire(timeout=0.05):
                    if cancelled.is_set():
                        return None
                try:
                    return generate(data_hash, difficulty, None, cancelled.is_set)
                except PowCancelledError:
                    return None
                finally:
                    _POW_SEMAPHORE.release()

            try:
                return await asyncio.to_thread(worker)
            except asyncio.CancelledError:
                cancelled.set()
                raise
        result = self.pow_provider(data_hash, difficulty)
        if hasattr(result, "__await__"):
            return await result  # type: ignore[misc]
        return result

    async def prepare_block(self, account_block: AccountBlock) -> AccountBlock:
        """Populate, PoW, hash, and sign a block without publishing it."""
        ledger = self._ledger()
        if (
            not isinstance(account_block.difficulty, int)
            or isinstance(account_block.difficulty, bool)
            or not 0 <= account_block.difficulty <= (1 << 64) - 1
        ):
            raise TransactionError("Difficulty must fit an unsigned 64-bit integer")
        supplied_difficulty = account_block.difficulty > 0
        if supplied_difficulty and (
            not isinstance(account_block.nonce, bytes) or len(account_block.nonce) != 8
        ):
            raise TransactionError("A preselected difficulty requires an 8-byte nonce")
        account_block.address = self.keypair.address
        account_block.public_key = bytes.fromhex(self.keypair.public_key)

        frontier = await ledger.get_frontier_account_block(str(self.keypair.address))
        if frontier is None:
            account_block.height = 1
            account_block.previous_hash = EMPTY_HASH
        else:
            frontier_height = frontier.height if isinstance(frontier, AccountBlock) else frontier["height"]
            frontier_hash = frontier.hash if isinstance(frontier, AccountBlock) else Hash.parse(frontier["hash"])
            account_block.height = int(frontier_height) + 1
            account_block.previous_hash = frontier_hash

        momentum = await ledger.get_frontier_momentum()
        momentum_hash = momentum.hash if hasattr(momentum, "hash") else Hash.parse(momentum["hash"])
        momentum_height = momentum.height if hasattr(momentum, "height") else int(momentum["height"])
        account_block.momentum_acknowledged = HashHeight(momentum_hash, momentum_height)

        if account_block.block_type in {1, 3, 5}:
            await self._validate_receive(account_block, ledger)

        required = await self._plasma().get_internal_required_pow_for_account_block(account_block)
        required_difficulty = required.get("requiredDifficulty", 0)
        if (
            not isinstance(required_difficulty, int)
            or isinstance(required_difficulty, bool)
            or not 0 <= required_difficulty <= (1 << 64) - 1
        ):
            raise TransactionError("Node returned an invalid required PoW difficulty")
        if required_difficulty > MAX_POW_DIFFICULTY:
            raise TransactionError(
                "Node returned a required PoW difficulty above the protocol maximum"
            )
        if required_difficulty == 0:
            account_block.difficulty = 0
            account_block.nonce = bytes(8)
            account_block.fused_plasma = int(required["basePlasma"])
        else:
            difficulty = account_block.difficulty or required_difficulty
            if difficulty < required_difficulty:
                raise TransactionError(
                    "Preselected difficulty is below the node-required difficulty"
                )
            data_hash = account_block_data_hash(
                bytes(account_block.address), account_block.previous_hash.core
            )
            nonce_hex = (
                account_block.nonce.hex()
                if supplied_difficulty
                else await self._generate_nonce(data_hash, difficulty)
            )
            account_block.difficulty = difficulty
            try:
                account_block.nonce = bytes.fromhex(nonce_hex)
            except (TypeError, ValueError) as error:
                raise TransactionError("PoW provider returned a non-hexadecimal nonce") from error
            if len(account_block.nonce) != 8:
                raise TransactionError("PoW provider returned a nonce with invalid length")
            try:
                valid_nonce = verify(data_hash, difficulty, nonce_hex)
            except ValueError as error:
                raise TransactionError("PoW provider returned an invalid nonce") from error
            if not valid_nonce:
                raise TransactionError("PoW provider returned an invalid nonce")
            account_block.fused_plasma = int(required.get("availablePlasma", 0))

        account_block.hash = account_block.get_hash()
        account_block.signature = self.keypair.sign_hash(account_block.hash)
        return account_block

    async def publish_block(self, account_block: AccountBlock) -> AccountBlock:
        """Publish an already prepared block and return that block on null success."""
        result = await self._ledger().publish_raw_transaction(account_block)
        if result is not None:
            raise TransactionError("publishRawTransaction must return null on success")
        return account_block

    async def fast_forward_block(self, account_block: AccountBlock) -> AccountBlock:
        prepared = await self.prepare_block(account_block)
        return await self.publish_block(prepared)

    async def send(
        self, to_address: Address, zts: TokenStandard, amount: int
    ) -> AccountBlock:
        account_block = AccountBlock(
            to_address=to_address,
            token_standard=zts,
            amount=amount,
            block_type=2,
        )
        return await self.fast_forward_block(account_block)

    async def receive(self, from_block_hash: Hash) -> AccountBlock:
        account_block = AccountBlock(from_block_hash=from_block_hash, block_type=3)
        return await self.fast_forward_block(account_block)

    async def call_contract(
        self,
        contract_address: Address,
        zts: TokenStandard,
        amount: int,
        data: bytes,
    ) -> AccountBlock:
        return await self.fast_forward_block(
            AccountBlock.contract_call(contract_address, zts, amount, data)
        )
