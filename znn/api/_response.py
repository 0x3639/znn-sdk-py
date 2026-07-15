"""RPC result routing generated from the stable SDK specification."""

from __future__ import annotations

import re

from znn.model.models import MODEL_TYPES


_DECIMAL = re.compile(r"^-?(?:0|[1-9][0-9]*)$")

RPC_RESULTS = {'embedded.accelerator.getAll': ('ProjectList', False), 'embedded.accelerator.getPhaseById': ('Phase', False), 'embedded.accelerator.getPillarVotes': ('array', False), 'embedded.accelerator.getProjectById': ('Project', False), 'embedded.accelerator.getVoteBreakdown': ('VoteBreakdown', False), 'embedded.bridge.getAllNetworks': ('BridgeNetworkInfoList', False), 'embedded.bridge.getAllUnsignedWrapTokenRequests': ('WrapTokenRequestList', False), 'embedded.bridge.getAllUnwrapTokenRequests': ('UnwrapTokenRequestList', False), 'embedded.bridge.getAllUnwrapTokenRequestsByToAddress': ('UnwrapTokenRequestList', False), 'embedded.bridge.getAllWrapTokenRequests': ('WrapTokenRequestList', False), 'embedded.bridge.getAllWrapTokenRequestsByToAddress': ('WrapTokenRequestList', False), 'embedded.bridge.getAllWrapTokenRequestsByToAddressNetworkClassAndChainId': ('WrapTokenRequestList', False), 'embedded.bridge.getBridgeInfo': ('BridgeInfo', False), 'embedded.bridge.getFeeTokenPair': ('ZtsFeesInfo', False), 'embedded.bridge.getNetworkInfo': ('BridgeNetworkInfo', False), 'embedded.bridge.getOrchestratorInfo': ('OrchestratorInfo', False), 'embedded.bridge.getSecurityInfo': ('SecurityInfo', False), 'embedded.bridge.getTimeChallengesInfo': ('TimeChallengesList', False), 'embedded.bridge.getUnwrapTokenRequestByHashAndLog': ('UnwrapTokenRequest', False), 'embedded.bridge.getWrapTokenRequestById': ('WrapTokenRequest', False), 'embedded.htlc.getById': ('HtlcInfo', False), 'embedded.htlc.getProxyUnlockStatus': ('boolean', False), 'embedded.liquidity.getFrontierRewardByPage': ('RewardHistoryList', False), 'embedded.liquidity.getLiquidityInfo': ('LiquidityInfo', False), 'embedded.liquidity.getLiquidityStakeEntriesByAddress': ('LiquidityStakeList', False), 'embedded.liquidity.getSecurityInfo': ('SecurityInfo', False), 'embedded.liquidity.getTimeChallengesInfo': ('TimeChallengesList', False), 'embedded.liquidity.getUncollectedReward': ('RewardDeposit', False), 'embedded.pillar.checkNameAvailability': ('boolean', False), 'embedded.pillar.getAll': ('PillarInfoList', False), 'embedded.pillar.getByName': ('PillarInfo', True), 'embedded.pillar.getByOwner': ('array', False), 'embedded.pillar.getDelegatedPillar': ('DelegationInfo', True), 'embedded.pillar.getDepositedQsr': ('decimal-string', False), 'embedded.pillar.getFrontierRewardByPage': ('RewardHistoryList', False), 'embedded.pillar.getPillarEpochHistory': ('PillarEpochHistoryList', False), 'embedded.pillar.getPillarsHistoryByEpoch': ('PillarEpochHistoryList', False), 'embedded.pillar.getQsrRegistrationCost': ('decimal-string', False), 'embedded.pillar.getUncollectedReward': ('UncollectedReward', False), 'embedded.plasma.get': ('PlasmaInfo', False), 'embedded.plasma.getEntriesByAddress': ('FusionEntryList', False), 'embedded.plasma.getRequiredPoWForAccountBlock': ('GetRequiredPowResponse', False), 'embedded.sentinel.getAllActive': ('SentinelInfoList', False), 'embedded.sentinel.getByOwner': ('SentinelInfo', True), 'embedded.sentinel.getDepositedQsr': ('decimal-string', False), 'embedded.sentinel.getFrontierRewardByPage': ('RewardHistoryList', False), 'embedded.sentinel.getUncollectedReward': ('UncollectedReward', False), 'embedded.spork.getAll': ('SporkList', False), 'embedded.stake.getEntriesByAddress': ('StakeList', False), 'embedded.stake.getFrontierRewardByPage': ('RewardHistoryList', False), 'embedded.stake.getUncollectedReward': ('UncollectedReward', False), 'embedded.swap.getAssets': ('SwapAssetList', False), 'embedded.swap.getAssetsByKeyIdHash': ('SwapAssetEntry', True), 'embedded.swap.getLegacyPillars': ('SwapLegacyPillarList', False), 'embedded.token.getAll': ('TokenList', False), 'embedded.token.getByOwner': ('TokenList', False), 'embedded.token.getByZts': ('Token', True), 'ledger.getAccountBlockByHash': ('AccountBlock', True), 'ledger.getAccountBlocksByHeight': ('AccountBlockList', False), 'ledger.getAccountBlocksByPage': ('AccountBlockList', False), 'ledger.getAccountInfoByAddress': ('AccountInfo', True), 'ledger.getDetailedMomentumsByHeight': ('DetailedMomentumList', True), 'ledger.getFrontierAccountBlock': ('AccountBlock', True), 'ledger.getFrontierMomentum': ('Momentum', False), 'ledger.getMomentumBeforeTime': ('Momentum', True), 'ledger.getMomentumByHash': ('Momentum', True), 'ledger.getMomentumsByHeight': ('MomentumList', False), 'ledger.getMomentumsByPage': ('MomentumList', False), 'ledger.getUnconfirmedBlocksByAddress': ('AccountBlockList', False), 'ledger.getUnreceivedBlocksByAddress': ('AccountBlockList', False), 'ledger.publishRawTransaction': ('null', True), 'ledger.subscribe': ('subscription-id', False), 'stats.networkInfo': ('NetworkInfo', False), 'stats.osInfo': ('OsInfo', False), 'stats.processInfo': ('ProcessInfo', False), 'stats.syncInfo': ('SyncInfo', False)}


def parse_rpc_response(method, value):
    result = RPC_RESULTS.get(method)
    if result is None:
        return value
    result_type, nullable = result
    if value is None:
        if nullable or result_type == "null":
            return None
        raise ValueError(f"{method} returned null for a non-nullable result")
    if result_type == "AccountBlock":
        return MODEL_TYPES[result_type].from_json(value, require_response=True)
    if result_type in MODEL_TYPES:
        return MODEL_TYPES[result_type].from_json(value)
    if result_type == "decimal-string":
        if not isinstance(value, str) or not _DECIMAL.fullmatch(value):
            raise ValueError(f"{method} returned a non-canonical decimal string")
        return int(value)
    if result_type == "boolean" and not isinstance(value, bool):
        raise TypeError(f"{method} returned a non-boolean result")
    if result_type == "array" and not isinstance(value, list):
        raise TypeError(f"{method} returned a non-array result")
    if result_type == "subscription-id" and (
        not isinstance(value, str) or not value
    ):
        raise TypeError(f"{method} returned an invalid subscription ID")
    if result_type == "null":
        raise TypeError(f"{method} must return null")
    return value
