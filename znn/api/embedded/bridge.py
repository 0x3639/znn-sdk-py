from znn.client.websocket import get_default_client
from znn.constants import RPC_MAX_PAGE_SIZE, MEMORY_POOL_PAGE_SIZE
from znn.embedded.definitions import BRIDGE_ABI
from znn.embedded.definitions import COMMON_ABI
from znn.model.nom.account_block import AccountBlock
from znn.model.primitives.address import Address, BRIDGE_ADDRESS
from znn.model.primitives.hash import Hash
from znn.model.primitives.token_standard import TokenStandard, ZNN_ZTS

def _address(value): return value if isinstance(value, Address) else Address.parse(value)
def _hash(value): return value if isinstance(value, Hash) else Hash.parse(value.removeprefix("0x"))
def _zts(value): return value if isinstance(value, TokenStandard) else TokenStandard.parse(value)
def _data(value): return value if value is None or isinstance(value, bytes) else bytes.fromhex(value.removeprefix("0x"))

class BridgeApi:
    def __init__(self, ws_client=None):
        self.ws_client = ws_client if ws_client is not None else get_default_client()

    async def get_all_networks(self, page_index=0, page_size=RPC_MAX_PAGE_SIZE):
        return await self.ws_client.send_request("embedded.bridge.getAllNetworks", [page_index, page_size])

    async def get_all_unsigned_wrap_token_requests(self, page_index=0, page_size=RPC_MAX_PAGE_SIZE):
        return await self.ws_client.send_request("embedded.bridge.getAllUnsignedWrapTokenRequests", [page_index, page_size])

    async def get_all_unwrap_token_requests(self, page_index=0, page_size=RPC_MAX_PAGE_SIZE):
        return await self.ws_client.send_request("embedded.bridge.getAllUnwrapTokenRequests", [page_index, page_size])

    async def get_all_unwrap_token_requests_by_to_address(self, to_address: str, page_index=0, page_size=RPC_MAX_PAGE_SIZE):
        return await self.ws_client.send_request("embedded.bridge.getAllUnwrapTokenRequestsByToAddress", [to_address, page_index, page_size])

    async def get_all_wrap_token_requests(self, page_index=0, page_size=RPC_MAX_PAGE_SIZE):
        return await self.ws_client.send_request("embedded.bridge.getAllWrapTokenRequests", [page_index, page_size])

    async def get_all_wrap_token_requests_by_to_address(self, to_address: str, page_index=0, page_size=RPC_MAX_PAGE_SIZE):
        return await self.ws_client.send_request("embedded.bridge.getAllWrapTokenRequestsByToAddress", [to_address, page_index, page_size])

    async def get_all_wrap_token_requests_by_to_address_network_class_and_chain_id(self, to_address: str, network_class: int, chain_id: int, page_index=0, page_size=RPC_MAX_PAGE_SIZE):
        return await self.ws_client.send_request("embedded.bridge.getAllWrapTokenRequestsByToAddressNetworkClassAndChainId", [to_address, network_class, chain_id, page_index, page_size])

    async def get_bridge_info(self):
        return await self.ws_client.send_request("embedded.bridge.getBridgeInfo", [])

    async def get_fee_token_pair(self, zts: TokenStandard):
        return await self.ws_client.send_request("embedded.bridge.getFeeTokenPair", [str(zts)])

    async def get_network_info(self, network_class: int, chain_id: int):
        return await self.ws_client.send_request("embedded.bridge.getNetworkInfo", [network_class, chain_id])

    async def get_orchestrator_info(self):
        return await self.ws_client.send_request("embedded.bridge.getOrchestratorInfo", [])

    async def get_security_info(self):
        return await self.ws_client.send_request("embedded.bridge.getSecurityInfo", [])

    async def get_time_challenges_info(self):
        return await self.ws_client.send_request("embedded.bridge.getTimeChallengesInfo", [])

    async def get_unwrap_token_request_by_hash_and_log(self, tx_hash: Hash, log_index: int):
        return await self.ws_client.send_request("embedded.bridge.getUnwrapTokenRequestByHashAndLog", [str(tx_hash), log_index])

    async def get_wrap_token_request_by_id(self, id: Hash):
        return await self.ws_client.send_request("embedded.bridge.getWrapTokenRequestById", [str(id)])

    def change_administrator(self, administrator: Address):
        administrator = _address(administrator)
        return AccountBlock.contract_call(
            BRIDGE_ADDRESS, ZNN_ZTS, int(0),
            BRIDGE_ABI.encode("ChangeAdministrator", [administrator]),
        )

    def change_tss_e_c_d_s_a_pub_key(self, pub_key: str, old_pub_key_signature: str, new_pub_key_signature: str):
        return AccountBlock.contract_call(
            BRIDGE_ADDRESS, ZNN_ZTS, int(0),
            BRIDGE_ABI.encode("ChangeTssECDSAPubKey", [pub_key, old_pub_key_signature, new_pub_key_signature]),
        )

    def emergency(self):
        return AccountBlock.contract_call(
            BRIDGE_ADDRESS, ZNN_ZTS, int(0),
            BRIDGE_ABI.encode("Emergency", []),
        )

    def halt(self, signature: str):
        return AccountBlock.contract_call(
            BRIDGE_ADDRESS, ZNN_ZTS, int(0),
            BRIDGE_ABI.encode("Halt", [signature]),
        )

    def nominate_guardians(self, guardians: list):
        guardians = [_address(item) for item in guardians]
        return AccountBlock.contract_call(
            BRIDGE_ADDRESS, ZNN_ZTS, int(0),
            BRIDGE_ABI.encode("NominateGuardians", [guardians]),
        )

    def propose_administrator(self, address: Address):
        address = _address(address)
        return AccountBlock.contract_call(
            BRIDGE_ADDRESS, ZNN_ZTS, int(0),
            BRIDGE_ABI.encode("ProposeAdministrator", [address]),
        )

    def redeem(self, transaction_hash: Hash, log_index: int):
        transaction_hash = _hash(transaction_hash)
        log_index = int(log_index)
        return AccountBlock.contract_call(
            BRIDGE_ADDRESS, ZNN_ZTS, int(0),
            BRIDGE_ABI.encode("Redeem", [transaction_hash, log_index]),
        )

    def remove_network(self, network_class: int, chain_id: int):
        network_class = int(network_class)
        chain_id = int(chain_id)
        return AccountBlock.contract_call(
            BRIDGE_ADDRESS, ZNN_ZTS, int(0),
            BRIDGE_ABI.encode("RemoveNetwork", [network_class, chain_id]),
        )

    def remove_token_pair(self, network_class: int, chain_id: int, token_standard: TokenStandard, token_address: str):
        network_class = int(network_class)
        chain_id = int(chain_id)
        token_standard = _zts(token_standard)
        return AccountBlock.contract_call(
            BRIDGE_ADDRESS, ZNN_ZTS, int(0),
            BRIDGE_ABI.encode("RemoveTokenPair", [network_class, chain_id, token_standard, token_address]),
        )

    def revoke_unwrap_request(self, transaction_hash: Hash, log_index: int):
        transaction_hash = _hash(transaction_hash)
        log_index = int(log_index)
        return AccountBlock.contract_call(
            BRIDGE_ADDRESS, ZNN_ZTS, int(0),
            BRIDGE_ABI.encode("RevokeUnwrapRequest", [transaction_hash, log_index]),
        )

    def set_allow_key_gen(self, allow_key_gen: bool):
        return AccountBlock.contract_call(
            BRIDGE_ADDRESS, ZNN_ZTS, int(0),
            BRIDGE_ABI.encode("SetAllowKeyGen", [allow_key_gen]),
        )

    def set_bridge_metadata(self, metadata: str):
        return AccountBlock.contract_call(
            BRIDGE_ADDRESS, ZNN_ZTS, int(0),
            BRIDGE_ABI.encode("SetBridgeMetadata", [metadata]),
        )

    def set_network(self, network_class: int, chain_id: int, name: str, contract_address: str, metadata: str):
        network_class = int(network_class)
        chain_id = int(chain_id)
        return AccountBlock.contract_call(
            BRIDGE_ADDRESS, ZNN_ZTS, int(0),
            BRIDGE_ABI.encode("SetNetwork", [network_class, chain_id, name, contract_address, metadata]),
        )

    def set_network_metadata(self, network_class: int, chain_id: int, metadata: str):
        network_class = int(network_class)
        chain_id = int(chain_id)
        return AccountBlock.contract_call(
            BRIDGE_ADDRESS, ZNN_ZTS, int(0),
            BRIDGE_ABI.encode("SetNetworkMetadata", [network_class, chain_id, metadata]),
        )

    def set_orchestrator_info(self, window_size: int, key_gen_threshold: int, confirmations_to_finality: int, estimated_momentum_time: int):
        window_size = int(window_size)
        key_gen_threshold = int(key_gen_threshold)
        confirmations_to_finality = int(confirmations_to_finality)
        estimated_momentum_time = int(estimated_momentum_time)
        return AccountBlock.contract_call(
            BRIDGE_ADDRESS, ZNN_ZTS, int(0),
            BRIDGE_ABI.encode("SetOrchestratorInfo", [window_size, key_gen_threshold, confirmations_to_finality, estimated_momentum_time]),
        )

    def set_token_pair(self, network_class: int, chain_id: int, token_standard: TokenStandard, token_address: str, bridgeable: bool, redeemable: bool, owned: bool, min_amount: int, fee_percentage: int, redeem_delay: int, metadata: str):
        network_class = int(network_class)
        chain_id = int(chain_id)
        token_standard = _zts(token_standard)
        min_amount = int(min_amount)
        fee_percentage = int(fee_percentage)
        redeem_delay = int(redeem_delay)
        return AccountBlock.contract_call(
            BRIDGE_ADDRESS, ZNN_ZTS, int(0),
            BRIDGE_ABI.encode("SetTokenPair", [network_class, chain_id, token_standard, token_address, bridgeable, redeemable, owned, min_amount, fee_percentage, redeem_delay, metadata]),
        )

    def unhalt(self):
        return AccountBlock.contract_call(
            BRIDGE_ADDRESS, ZNN_ZTS, int(0),
            BRIDGE_ABI.encode("Unhalt", []),
        )

    def unwrap_token(self, network_class: int, chain_id: int, transaction_hash: Hash, log_index: int, to_address: Address, token_address: str, amount: int, signature: str):
        network_class = int(network_class)
        chain_id = int(chain_id)
        transaction_hash = _hash(transaction_hash)
        log_index = int(log_index)
        to_address = _address(to_address)
        amount = int(amount)
        return AccountBlock.contract_call(
            BRIDGE_ADDRESS, ZNN_ZTS, int(0),
            BRIDGE_ABI.encode("UnwrapToken", [network_class, chain_id, transaction_hash, log_index, to_address, token_address, amount, signature]),
        )

    def update_wrap_request(self, id: Hash, signature: str):
        id = _hash(id)
        return AccountBlock.contract_call(
            BRIDGE_ADDRESS, ZNN_ZTS, int(0),
            BRIDGE_ABI.encode("UpdateWrapRequest", [id, signature]),
        )

    def wrap_token(self, network_class: int, chain_id: int, to_address: str, amount: int, token_standard: TokenStandard):
        network_class = int(network_class)
        chain_id = int(chain_id)
        amount = int(amount)
        token_standard = _zts(token_standard)
        return AccountBlock.contract_call(
            BRIDGE_ADDRESS, token_standard, int(amount),
            BRIDGE_ABI.encode("WrapToken", [network_class, chain_id, to_address]),
        )
