from znn.api.client import get_api_client
from znn.constants import RPC_MAX_PAGE_SIZE, MEMORY_POOL_PAGE_SIZE
from znn.embedded.definitions import SPORK_ABI
from znn.embedded.definitions import COMMON_ABI
from znn.model.nom.account_block import AccountBlock
from znn.model.primitives.address import Address, SPORK_ADDRESS
from znn.model.primitives.hash import Hash
from znn.model.primitives.token_standard import TokenStandard, ZNN_ZTS

def _address(value): return value if isinstance(value, Address) else Address.parse(value)
def _hash(value): return value if isinstance(value, Hash) else Hash.parse(value.removeprefix("0x"))
def _zts(value): return value if isinstance(value, TokenStandard) else TokenStandard.parse(value)
def _data(value): return value if value is None or isinstance(value, bytes) else bytes.fromhex(value.removeprefix("0x"))

class SporkApi:
    def __init__(self, ws_client=None):
        self.ws_client = get_api_client(ws_client)

    async def get_all(self, page_index=0, page_size=RPC_MAX_PAGE_SIZE):
        return await self.ws_client.send_request("embedded.spork.getAll", [page_index, page_size])

    def activate_spork(self, id: Hash):
        id = _hash(id)
        return AccountBlock.contract_call(
            SPORK_ADDRESS, ZNN_ZTS, int(0),
            SPORK_ABI.encode("ActivateSpork", [id]),
        )

    def create_spork(self, name: str, description: str):
        return AccountBlock.contract_call(
            SPORK_ADDRESS, ZNN_ZTS, int(0),
            SPORK_ABI.encode("CreateSpork", [name, description]),
        )
