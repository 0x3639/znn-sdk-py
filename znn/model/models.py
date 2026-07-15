"""Specification-complete JSON wire models and enums."""

from copy import deepcopy
from enum import IntEnum

class Model:
    _decimal_fields = ()

    def __init__(_model, **values):
        _model._wire = deepcopy(values)
        for key, value in values.items():
            setattr(_model, key, int(value) if key in _model._decimal_fields and value is not None else deepcopy(value))

    @classmethod
    def from_json(cls, value):
        if isinstance(value, dict):
            return cls(**value)
        instance = cls()
        instance._wire = deepcopy(value)
        return instance

    def to_json(self):
        result = deepcopy(self._wire)
        if not isinstance(result, dict):
            return result
        for key in self._decimal_fields:
            if hasattr(self, key) and getattr(self, key) is not None:
                result[key] = str(getattr(self, key))
        return result

class AcceleratorProjectStatus(IntEnum):
    voting = 0
    active = 1
    paid = 2
    closed = 3
    completed = 4

class AcceleratorProjectVote(IntEnum):
    yes = 0
    no = 1
    abstain = 2

class BlockTypeEnum(IntEnum):
    Unknown = 0
    GenesisReceive = 1
    UserSend = 2
    UserReceive = 3
    ContractSend = 4
    ContractReceive = 5

class ReceiveBlockTypeEnum(IntEnum):
    GenesisReceive = 1
    UserReceive = 3
    ContractReceive = 5

class SendBlockTypeEnum(IntEnum):
    UserSend = 2
    ContractSend = 4

class SyncState(IntEnum):
    Unknown = 0
    Syncing = 1
    SyncDone = 2
    NotEnoughPeers = 3

class AcceleratorProject(Model):
    _decimal_fields = ('znnFundsNeeded', 'qsrFundsNeeded')

class AccountBlockConfirmationDetail(Model):
    _decimal_fields = ()

class AccountBlockList(Model):
    _decimal_fields = ()

class AccountBlockTemplate(Model):
    _decimal_fields = ('amount',)

class AccountHeader(Model):
    _decimal_fields = ()

class AccountInfo(Model):
    _decimal_fields = ()

class BalanceInfoListItem(Model):
    _decimal_fields = ('balance',)

class BridgeInfo(Model):
    _decimal_fields = ()

class BridgeNetworkInfo(Model):
    _decimal_fields = ()

class BridgeNetworkInfoList(Model):
    _decimal_fields = ()

class DelegationInfo(Model):
    _decimal_fields = ('weight',)

class DetailedMomentum(Model):
    _decimal_fields = ()

class DetailedMomentumList(Model):
    _decimal_fields = ()

class FusionEntry(Model):
    _decimal_fields = ('qsrAmount',)

class FusionEntryList(Model):
    _decimal_fields = ('qsrAmount',)

class GetRequiredPowParam(Model):
    _decimal_fields = ()

class GetRequiredPowResponse(Model):
    _decimal_fields = ()

class HtlcInfo(Model):
    _decimal_fields = ('amount',)

class LiquidityInfo(Model):
    _decimal_fields = ('znnReward', 'qsrReward')

class LiquidityStakeEntry(Model):
    _decimal_fields = ('amount', 'weightedAmount')

class LiquidityStakeList(Model):
    _decimal_fields = ('totalAmount', 'totalWeightedAmount')

class Momentum(Model):
    _decimal_fields = ()

class MomentumList(Model):
    _decimal_fields = ()

class NetworkInfo(Model):
    _decimal_fields = ()

class OrchestratorInfo(Model):
    _decimal_fields = ()

class OsInfo(Model):
    _decimal_fields = ()

class Peer(Model):
    _decimal_fields = ()

class Phase(Model):
    _decimal_fields = ()

class PillarEpochHistory(Model):
    _decimal_fields = ('weight',)

class PillarEpochHistoryList(Model):
    _decimal_fields = ()

class PillarEpochStats(Model):
    _decimal_fields = ()

class PillarInfo(Model):
    _decimal_fields = ('weight',)

class PillarInfoList(Model):
    _decimal_fields = ()

class PillarVote(Model):
    _decimal_fields = ()

class PlasmaInfo(Model):
    _decimal_fields = ('qsrAmount',)

class ProcessInfo(Model):
    _decimal_fields = ()

class Project(Model):
    _decimal_fields = ()

class ProjectList(Model):
    _decimal_fields = ()

class RewardDeposit(Model):
    _decimal_fields = ('znnAmount', 'qsrAmount')

class RewardHistoryEntry(Model):
    _decimal_fields = ('znnAmount', 'qsrAmount')

class RewardHistoryList(Model):
    _decimal_fields = ()

class SecurityInfo(Model):
    _decimal_fields = ()

class SentinelInfo(Model):
    _decimal_fields = ()

class SentinelInfoList(Model):
    _decimal_fields = ()

class Spork(Model):
    _decimal_fields = ()

class SporkList(Model):
    _decimal_fields = ()

class StakeEntry(Model):
    _decimal_fields = ('amount', 'weightedAmount')

class StakeList(Model):
    _decimal_fields = ('totalAmount', 'totalWeightedAmount')

class SwapAssetEntry(Model):
    _decimal_fields = ('qsr', 'znn')

class SwapAssetList(Model):
    _decimal_fields = ()

class SwapLegacyPillarEntry(Model):
    _decimal_fields = ()

class SwapLegacyPillarList(Model):
    _decimal_fields = ()

class SyncInfo(Model):
    _decimal_fields = ()

class TimeChallengeInfo(Model):
    _decimal_fields = ()

class TimeChallengesList(Model):
    _decimal_fields = ()

class Token(Model):
    _decimal_fields = ('totalSupply', 'maxSupply')

class TokenList(Model):
    _decimal_fields = ()

class TokenPair(Model):
    _decimal_fields = ('minAmount',)

class TokenTuple(Model):
    _decimal_fields = ('minAmount',)

class UncollectedReward(Model):
    _decimal_fields = ('znnAmount', 'qsrAmount')

class UnwrapTokenRequest(Model):
    _decimal_fields = ('amount',)

class UnwrapTokenRequestList(Model):
    _decimal_fields = ()

class VoteBreakdown(Model):
    _decimal_fields = ()

class WrapTokenRequest(Model):
    _decimal_fields = ('amount', 'fee')

class WrapTokenRequestList(Model):
    _decimal_fields = ()

class ZtsFeesInfo(Model):
    _decimal_fields = ('accumulatedFee',)

MODEL_TYPES = {
    "AcceleratorProject": AcceleratorProject,
    "AccountBlockConfirmationDetail": AccountBlockConfirmationDetail,
    "AccountBlockList": AccountBlockList,
    "AccountBlockTemplate": AccountBlockTemplate,
    "AccountHeader": AccountHeader,
    "AccountInfo": AccountInfo,
    "BalanceInfoListItem": BalanceInfoListItem,
    "BridgeInfo": BridgeInfo,
    "BridgeNetworkInfo": BridgeNetworkInfo,
    "BridgeNetworkInfoList": BridgeNetworkInfoList,
    "DelegationInfo": DelegationInfo,
    "DetailedMomentum": DetailedMomentum,
    "DetailedMomentumList": DetailedMomentumList,
    "FusionEntry": FusionEntry,
    "FusionEntryList": FusionEntryList,
    "GetRequiredPowParam": GetRequiredPowParam,
    "GetRequiredPowResponse": GetRequiredPowResponse,
    "HtlcInfo": HtlcInfo,
    "LiquidityInfo": LiquidityInfo,
    "LiquidityStakeEntry": LiquidityStakeEntry,
    "LiquidityStakeList": LiquidityStakeList,
    "Momentum": Momentum,
    "MomentumList": MomentumList,
    "NetworkInfo": NetworkInfo,
    "OrchestratorInfo": OrchestratorInfo,
    "OsInfo": OsInfo,
    "Peer": Peer,
    "Phase": Phase,
    "PillarEpochHistory": PillarEpochHistory,
    "PillarEpochHistoryList": PillarEpochHistoryList,
    "PillarEpochStats": PillarEpochStats,
    "PillarInfo": PillarInfo,
    "PillarInfoList": PillarInfoList,
    "PillarVote": PillarVote,
    "PlasmaInfo": PlasmaInfo,
    "ProcessInfo": ProcessInfo,
    "Project": Project,
    "ProjectList": ProjectList,
    "RewardDeposit": RewardDeposit,
    "RewardHistoryEntry": RewardHistoryEntry,
    "RewardHistoryList": RewardHistoryList,
    "SecurityInfo": SecurityInfo,
    "SentinelInfo": SentinelInfo,
    "SentinelInfoList": SentinelInfoList,
    "Spork": Spork,
    "SporkList": SporkList,
    "StakeEntry": StakeEntry,
    "StakeList": StakeList,
    "SwapAssetEntry": SwapAssetEntry,
    "SwapAssetList": SwapAssetList,
    "SwapLegacyPillarEntry": SwapLegacyPillarEntry,
    "SwapLegacyPillarList": SwapLegacyPillarList,
    "SyncInfo": SyncInfo,
    "TimeChallengeInfo": TimeChallengeInfo,
    "TimeChallengesList": TimeChallengesList,
    "Token": Token,
    "TokenList": TokenList,
    "TokenPair": TokenPair,
    "TokenTuple": TokenTuple,
    "UncollectedReward": UncollectedReward,
    "UnwrapTokenRequest": UnwrapTokenRequest,
    "UnwrapTokenRequestList": UnwrapTokenRequestList,
    "VoteBreakdown": VoteBreakdown,
    "WrapTokenRequest": WrapTokenRequest,
    "WrapTokenRequestList": WrapTokenRequestList,
    "ZtsFeesInfo": ZtsFeesInfo,
    "Model": Model,
}
