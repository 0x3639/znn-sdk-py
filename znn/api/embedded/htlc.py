from znn.api.client import get_api_client
from znn.constants import RPC_MAX_PAGE_SIZE, MEMORY_POOL_PAGE_SIZE
from znn.embedded.definitions import HTLC_ABI
from znn.embedded.definitions import COMMON_ABI
from znn.model.nom.account_block import AccountBlock
from znn.model.primitives.address import Address, HTLC_ADDRESS
from znn.model.primitives.hash import Hash
from znn.model.primitives.token_standard import TokenStandard, ZNN_ZTS

def _address(value): return value if isinstance(value, Address) else Address.parse(value)
def _hash(value): return value if isinstance(value, Hash) else Hash.parse(value.removeprefix("0x"))
def _zts(value): return value if isinstance(value, TokenStandard) else TokenStandard.parse(value)
def _data(value): return value if value is None or isinstance(value, bytes) else bytes.fromhex(value.removeprefix("0x"))

class HtlcApi:
    def __init__(self, ws_client=None):
        self.ws_client = get_api_client(ws_client)

    async def get_by_id(self, id: Hash):
        return await self.ws_client.send_request("embedded.htlc.getById", [str(id)])

    async def get_proxy_unlock_status(self, address: Address):
        return await self.ws_client.send_request("embedded.htlc.getProxyUnlockStatus", [str(address)])

    def allow_proxy_unlock(self):
        return AccountBlock.contract_call(
            HTLC_ADDRESS, ZNN_ZTS, int(0),
            HTLC_ABI.encode("AllowProxyUnlock", []),
        )

    def create(self, token: TokenStandard, amount: int, hash_locked: Address, expiration_time: int, hash_type: int, key_max_size: int, hash_lock: bytes | None):
        token = _zts(token)
        amount = int(amount)
        hash_locked = _address(hash_locked)
        expiration_time = int(expiration_time)
        hash_type = int(hash_type)
        key_max_size = int(key_max_size)
        hash_lock = _data(hash_lock)
        return AccountBlock.contract_call(
            HTLC_ADDRESS, token, int(amount),
            HTLC_ABI.encode("Create", [hash_locked, expiration_time, hash_type, key_max_size, hash_lock]),
        )

    def deny_proxy_unlock(self):
        return AccountBlock.contract_call(
            HTLC_ADDRESS, ZNN_ZTS, int(0),
            HTLC_ABI.encode("DenyProxyUnlock", []),
        )

    def reclaim(self, id: Hash):
        id = _hash(id)
        return AccountBlock.contract_call(
            HTLC_ADDRESS, ZNN_ZTS, int(0),
            HTLC_ABI.encode("Reclaim", [id]),
        )

    def unlock(self, id: Hash, preimage: bytes | None):
        id = _hash(id)
        preimage = _data(preimage)
        return AccountBlock.contract_call(
            HTLC_ADDRESS, ZNN_ZTS, int(0),
            HTLC_ABI.encode("Unlock", [id, preimage]),
        )
