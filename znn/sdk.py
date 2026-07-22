"""High-level Zenon SDK lifecycle service."""

from urllib.parse import urlparse

from znn.api.embedded.plasma import PlasmaApi
from znn.api.ledger import LedgerApi
from znn.client.http import HttpClient
from znn.client.websocket import WsClient
from znn.wallet.transact import Transact
from znn.wallet.keypair import KeyPair


class Zenon:
    def __init__(self):
        self.client = None
        self.network_id = 1
        self.chain_id = 1
        self.pow_provider = None

    async def initialize(self, server_url: str, timeout: float = 30.0, **websocket_options):
        if (
            not isinstance(timeout, (int, float))
            or isinstance(timeout, bool)
            or timeout <= 0
        ):
            raise ValueError("timeout must be a positive number")
        scheme = urlparse(server_url).scheme
        if scheme in {"http", "https"}:
            self.client = HttpClient(server_url, timeout)
        elif scheme in {"ws", "wss"}:
            websocket_options.setdefault("request_timeout", timeout)
            self.client = WsClient(
                server_url, connect_timeout=timeout, **websocket_options
            )
            await self.client.connect()
        else:
            raise ValueError("Zenon endpoint must use http, https, ws, or wss")

    async def disconnect(self):
        if self.client is not None:
            await self.client.disconnect()
        self.client = None

    def set_network_id(self, network_id: int):
        self.network_id = self._validate_identifier(network_id, "network_id")

    def get_network_id(self):
        return self.network_id

    def set_chain_id(self, chain_id: int):
        self.chain_id = self._validate_identifier(chain_id, "chain_id")

    def get_chain_id(self):
        return self.chain_id

    def set_pow_provider(self, provider):
        if not callable(provider):
            raise TypeError("PoW provider must be callable")
        self.pow_provider = provider

    def clear_pow_provider(self):
        self.pow_provider = None

    @staticmethod
    def _validate_identifier(value, name):
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or not 0 <= value <= (1 << 64) - 1
        ):
            raise ValueError(f"{name} must fit an unsigned 64-bit integer")
        return value

    def _transact(self, private_key: str | KeyPair):
        if self.client is None:
            raise RuntimeError("SDK is not initialized")
        return Transact(private_key, LedgerApi(self.client), PlasmaApi(self.client), self.pow_provider)

    async def prepare_block(self, block, private_key: str | KeyPair):
        block.chain_identifier = self.chain_id
        return await self._transact(private_key).prepare_block(block)

    async def send(self, block, private_key: str | KeyPair):
        block.chain_identifier = self.chain_id
        return await self._transact(private_key).fast_forward_block(block)


zenon = Zenon()
