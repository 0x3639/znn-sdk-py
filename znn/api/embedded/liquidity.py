from znn.api.client import get_api_client
from znn.constants import RPC_MAX_PAGE_SIZE, MEMORY_POOL_PAGE_SIZE
from znn.embedded.definitions import LIQUIDITY_ABI
from znn.embedded.definitions import COMMON_ABI
from znn.model.nom.account_block import AccountBlock
from znn.model.primitives.address import Address, LIQUIDITY_ADDRESS
from znn.model.primitives.hash import Hash
from znn.model.primitives.token_standard import TokenStandard, ZNN_ZTS

def _address(value): return value if isinstance(value, Address) else Address.parse(value)
def _hash(value): return value if isinstance(value, Hash) else Hash.parse(value.removeprefix("0x"))
def _zts(value): return value if isinstance(value, TokenStandard) else TokenStandard.parse(value)
def _data(value): return value if value is None or isinstance(value, bytes) else bytes.fromhex(value.removeprefix("0x"))

class LiquidityApi:
    def __init__(self, ws_client=None):
        self.ws_client = get_api_client(ws_client)

    async def get_frontier_reward_by_page(self, address: Address, page_index=0, page_size=RPC_MAX_PAGE_SIZE):
        return await self.ws_client.send_request("embedded.liquidity.getFrontierRewardByPage", [str(address), page_index, page_size])

    async def get_liquidity_info(self):
        return await self.ws_client.send_request("embedded.liquidity.getLiquidityInfo", [])

    async def get_liquidity_stake_entries_by_address(self, address: Address, page_index=0, page_size=MEMORY_POOL_PAGE_SIZE):
        return await self.ws_client.send_request("embedded.liquidity.getLiquidityStakeEntriesByAddress", [str(address), page_index, page_size])

    async def get_security_info(self):
        return await self.ws_client.send_request("embedded.liquidity.getSecurityInfo", [])

    async def get_time_challenges_info(self):
        return await self.ws_client.send_request("embedded.liquidity.getTimeChallengesInfo", [])

    async def get_uncollected_reward(self, address: Address):
        return await self.ws_client.send_request("embedded.liquidity.getUncollectedReward", [str(address)])

    def cancel_liquidity_stake(self, id: Hash):
        id = _hash(id)
        return AccountBlock.contract_call(
            LIQUIDITY_ADDRESS, ZNN_ZTS, int(0),
            LIQUIDITY_ABI.encode("CancelLiquidityStake", [id]),
        )

    def change_administrator(self, administrator: Address):
        administrator = _address(administrator)
        return AccountBlock.contract_call(
            LIQUIDITY_ADDRESS, ZNN_ZTS, int(0),
            LIQUIDITY_ABI.encode("ChangeAdministrator", [administrator]),
        )

    def collect_reward(self):
        return AccountBlock.contract_call(
            LIQUIDITY_ADDRESS, ZNN_ZTS, int(0),
            COMMON_ABI.encode("CollectReward", []),
        )

    def emergency(self):
        return AccountBlock.contract_call(
            LIQUIDITY_ADDRESS, ZNN_ZTS, int(0),
            LIQUIDITY_ABI.encode("Emergency", []),
        )

    def liquidity_stake(self, duration_in_sec: int, amount: int, zts: TokenStandard):
        duration_in_sec = int(duration_in_sec)
        amount = int(amount)
        zts = _zts(zts)
        return AccountBlock.contract_call(
            LIQUIDITY_ADDRESS, zts, int(amount),
            LIQUIDITY_ABI.encode("LiquidityStake", [duration_in_sec]),
        )

    def nominate_guardians(self, guardians: list):
        guardians = [_address(item) for item in guardians]
        return AccountBlock.contract_call(
            LIQUIDITY_ADDRESS, ZNN_ZTS, int(0),
            LIQUIDITY_ABI.encode("NominateGuardians", [guardians]),
        )

    def propose_administrator(self, address: Address):
        address = _address(address)
        return AccountBlock.contract_call(
            LIQUIDITY_ADDRESS, ZNN_ZTS, int(0),
            LIQUIDITY_ABI.encode("ProposeAdministrator", [address]),
        )

    def set_additional_reward(self, znn_reward: int, qsr_reward: int):
        znn_reward = int(znn_reward)
        qsr_reward = int(qsr_reward)
        return AccountBlock.contract_call(
            LIQUIDITY_ADDRESS, ZNN_ZTS, int(0),
            LIQUIDITY_ABI.encode("SetAdditionalReward", [znn_reward, qsr_reward]),
        )

    def set_is_halted(self, is_halted: bool):
        return AccountBlock.contract_call(
            LIQUIDITY_ADDRESS, ZNN_ZTS, int(0),
            LIQUIDITY_ABI.encode("SetIsHalted", [is_halted]),
        )

    def set_token_tuple(self, token_standards: list, znn_percentages: list, qsr_percentages: list, min_amounts: list):
        znn_percentages = [int(item) for item in znn_percentages]
        qsr_percentages = [int(item) for item in qsr_percentages]
        min_amounts = [int(item) for item in min_amounts]
        return AccountBlock.contract_call(
            LIQUIDITY_ADDRESS, ZNN_ZTS, int(0),
            LIQUIDITY_ABI.encode("SetTokenTuple", [token_standards, znn_percentages, qsr_percentages, min_amounts]),
        )

    def unlock_liquidity_stake_entries(self, zts: TokenStandard):
        zts = _zts(zts)
        return AccountBlock.contract_call(
            LIQUIDITY_ADDRESS, zts, int(0),
            LIQUIDITY_ABI.encode("UnlockLiquidityStakeEntries", []),
        )
