"""Field-aware JSON wire models generated from the stable SDK specification."""

from __future__ import annotations

import base64
import re
from collections.abc import Mapping
from copy import deepcopy
from enum import IntEnum

from znn.model._base64 import decode_model_base64
from znn.model.primitives.address import Address
from znn.model.primitives.hash import Hash
from znn.model.primitives.hash_height import HashHeight
from znn.model.primitives.token_standard import TokenStandard


_DECIMAL = re.compile(r"^-?(?:0|[1-9][0-9]*)$")
_MISSING = object()


def _get_path(value, path):
    current = value
    if path == "":
        return value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return _MISSING
        current = current[part]
    return current


def _set_path(value, path, item):
    if path == "":
        return item
    current = value
    parts = path.split(".")
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = item
    return value


def _default_value(text):
    if text is None:
        return _MISSING
    if text == "0":
        return 0
    if text == "{}":
        return {}
    if text == "[]":
        return []
    if text == "false":
        return False
    if text == "true":
        return True
    if re.fullmatch(r"-?[0-9]+n", text):
        return int(text[:-1])
    return _MISSING


def _decode_target(target, value, strict):
    if not strict and value in ({}, []):
        return deepcopy(value)
    if target == "Address":
        return Address.parse(value) if isinstance(value, str) else Address.from_json(value)
    if target == "Hash":
        return Hash.parse(value.removeprefix("0x")) if isinstance(value, str) else Hash.from_json(value)
    if target == "HashHeight":
        return HashHeight.from_json(value, strict=strict)
    if target == "TokenStandard":
        return TokenStandard.parse(value) if isinstance(value, str) else TokenStandard.from_json(value)
    if target == "AccountBlock":
        from znn.model.nom.account_block import AccountBlock
        return AccountBlock.from_json(
            value, strict=strict, require_response=strict
        )
    cls = MODEL_TYPES.get(target)
    if cls is None:
        raise ValueError(f"Unknown nested model {target!r}")
    if isinstance(cls, type) and issubclass(cls, IntEnum):
        return cls(value)
    return cls.from_json(value, strict=strict)


def _decode_field(field, value, strict):
    name, _key, wire_type, encoding, target, _required, _default, object_item = field
    if value is None:
        raise ValueError(f"{name} cannot be null")
    if wire_type == "decimal-string":
        if not isinstance(value, str) or not _DECIMAL.fullmatch(value):
            raise ValueError(f"{name} must be a canonical base-10 integer string")
        return int(value)
    if wire_type == "number":
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"{name} must be an integer")
        return value
    if wire_type == "boolean":
        if not isinstance(value, bool):
            raise TypeError(f"{name} must be a boolean")
        return value
    if wire_type == "string":
        if not isinstance(value, str):
            raise TypeError(f"{name} must be a string")
        if encoding == "hex-32":
            return Hash.parse(value.removeprefix("0x"))
        if encoding == "bech32-address":
            return Address.parse(value)
        if encoding == "bech32-token-standard":
            return TokenStandard.parse(value)
        if encoding == "base64":
            return decode_model_base64(value, name)
        return value
    if wire_type == "model":
        return _decode_target(target, value, strict)
    if wire_type == "array":
        if not isinstance(value, list):
            raise TypeError(f"{name} must be an array")
        return [_decode_target(target, item, strict) for item in value]
    if wire_type == "object":
        if not isinstance(value, dict):
            raise TypeError(f"{name} must be an object")
        if object_item:
            return {key: _decode_target(object_item, item, strict) for key, item in value.items()}
        return deepcopy(value)
    raise ValueError(f"Unsupported wire type {wire_type!r}")


def _encode_target(value):
    if isinstance(value, (Address, Hash, TokenStandard)):
        return str(value)
    if isinstance(value, HashHeight):
        return value.to_json()
    if isinstance(value, IntEnum):
        return int(value)
    if hasattr(value, "to_json"):
        return value.to_json()
    return deepcopy(value)


def _encode_field(field, value):
    _name, _key, wire_type, encoding, _target, _required, _default, _object_item = field
    if wire_type == "decimal-string":
        return str(value)
    if wire_type == "string":
        if encoding in {"hex-32", "bech32-address", "bech32-token-standard"}:
            return str(value)
        if encoding == "base64":
            return base64.b64encode(bytes(value)).decode()
        return value
    if wire_type == "model":
        return _encode_target(value)
    if wire_type == "array":
        return [_encode_target(item) for item in value]
    if wire_type == "object":
        return {key: _encode_target(item) for key, item in value.items()}
    return int(value) if isinstance(value, IntEnum) else value


class Model(Mapping):
    _fields = ()

    def __init__(self, **values):
        object.__setattr__(self, "_wire", {})
        object.__setattr__(self, "_values", {})
        names = {field[0] for field in self._fields}
        unknown = set(values) - names
        if unknown:
            raise TypeError(f"Unknown {type(self).__name__} fields: {sorted(unknown)}")
        self._values.update(values)

    @classmethod
    def from_json(cls, value, *, strict=True, nested_strict=None):
        root = len(cls._fields) == 1 and cls._fields[0][1] == ""
        if root:
            if not isinstance(value, list):
                raise TypeError(f"{cls.__name__} JSON must be an array")
        elif not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} JSON must be an object")
        instance = cls()
        object.__setattr__(instance, "_wire", deepcopy(value))
        for field in cls._fields:
            raw = _get_path(value, field[1])
            if raw is _MISSING:
                default = _default_value(field[6])
                if default is not _MISSING:
                    instance._values[field[0]] = default
                elif field[5] and strict:
                    raise ValueError(f"Missing required {cls.__name__}.{field[1]}")
                continue
            decode_strict = strict if nested_strict is None else nested_strict
            instance._values[field[0]] = _decode_field(field, raw, decode_strict)
        return instance

    def to_json(self):
        root = len(self._fields) == 1 and self._fields[0][1] == ""
        if root:
            field = self._fields[0]
            return _encode_field(field, self._values.get(field[0], []))
        result = deepcopy(self._wire) if isinstance(self._wire, dict) else {}
        for field in self._fields:
            if field[0] in self._values:
                _set_path(result, field[1], _encode_field(field, self._values[field[0]]))
        return result

    def __getattr__(self, name):
        values = object.__getattribute__(self, "_values")
        if name in values:
            return values[name]
        raise AttributeError(name)

    def __setattr__(self, name, value):
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        if name not in {field[0] for field in self._fields}:
            raise AttributeError(f"Unknown {type(self).__name__} field {name!r}")
        self._values[name] = value

    def __getitem__(self, key):
        if key in self._values:
            return self._values[key]
        for field in self._fields:
            if field[1] == key and field[0] in self._values:
                return self._values[field[0]]
        raise KeyError(key)

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __repr__(self):
        return f"{type(self).__name__}({self._values!r})"

    def __eq__(self, other):
        return type(self) is type(other) and self.to_json() == other.to_json()


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
    _fields = (('id', 'id', 'string', 'hex-32', None, True, None, None), ('name', 'name', 'string', None, None, True, None, None), ('description', 'description', 'string', None, None, True, None, None), ('url', 'url', 'string', None, None, True, None, None), ('znnFundsNeeded', 'znnFundsNeeded', 'decimal-string', 'base-10', None, True, None, None), ('qsrFundsNeeded', 'qsrFundsNeeded', 'decimal-string', 'base-10', None, True, None, None), ('creationTimestamp', 'creationTimestamp', 'number', None, None, True, None, None), ('statusInt', 'status', 'number', None, None, True, None, None), ('voteBreakdown', 'votes', 'model', None, 'VoteBreakdown', True, None, None))


class AccountBlockConfirmationDetail(Model):
    _fields = (('numConfirmations', 'numConfirmations', 'number', None, None, True, None, None), ('momentumHeight', 'momentumHeight', 'number', None, None, True, None, None), ('momentumHash', 'momentumHash', 'string', 'hex-32', None, True, None, None), ('momentumTimestamp', 'momentumTimestamp', 'number', None, None, True, None, None))


class AccountBlockList(Model):
    _fields = (('count', 'count', 'number', None, None, False, '0', None), ('list', 'list', 'array', None, 'AccountBlock', False, '[]', None), ('more', 'more', 'boolean', None, None, False, 'false', None))


class AccountBlockTemplate(Model):
    _fields = (('version', 'version', 'number', None, None, True, None, None), ('chainIdentifier', 'chainIdentifier', 'number', None, None, True, None, None), ('blockType', 'blockType', 'number', None, None, True, None, None), ('hash', 'hash', 'string', 'hex-32', None, True, None, None), ('previousHash', 'previousHash', 'string', 'hex-32', None, True, None, None), ('height', 'height', 'number', None, None, True, None, None), ('momentumAcknowledged', 'momentumAcknowledged', 'model', None, 'HashHeight', True, None, None), ('address', 'address', 'string', 'bech32-address', None, True, None, None), ('toAddress', 'toAddress', 'string', 'bech32-address', None, True, None, None), ('amount', 'amount', 'decimal-string', 'base-10', None, True, None, None), ('tokenStandard', 'tokenStandard', 'string', 'bech32-token-standard', None, True, None, None), ('fromBlockHash', 'fromBlockHash', 'string', 'hex-32', None, True, None, None), ('data', 'data', 'string', 'base64', None, True, None, None), ('fusedPlasma', 'fusedPlasma', 'number', None, None, True, None, None), ('difficulty', 'difficulty', 'number', None, None, True, None, None), ('nonce', 'nonce', 'string', None, None, True, None, None), ('publicKey', 'publicKey', 'string', 'base64', None, True, None, None), ('signature', 'signature', 'string', 'base64', None, True, None, None))


class AccountHeader(Model):
    _fields = (('address', 'address', 'string', 'bech32-address', None, True, None, None), ('hash', 'hash', 'string', 'hex-32', None, True, None, None), ('height', 'height', 'number', None, None, True, None, None))


class AccountInfo(Model):
    _fields = (('address', 'address', 'string', 'bech32-address', None, True, None, None), ('blockCount', 'accountHeight', 'number', None, None, False, '0', None), ('balanceInfoMap', 'balanceInfoMap', 'object', None, None, False, '{}', 'BalanceInfoListItem'))


class BalanceInfoListItem(Model):
    _fields = (('token', 'token', 'model', None, 'Token', True, None, None), ('balance', 'balance', 'decimal-string', 'base-10', None, True, None, None))


class BridgeInfo(Model):
    _fields = (('administrator', 'administrator', 'string', 'bech32-address', None, True, None, None), ('compressedTssECDSAPubKey', 'compressedTssECDSAPubKey', 'string', None, None, True, None, None), ('decompressedTssECDSAPubKey', 'decompressedTssECDSAPubKey', 'string', None, None, True, None, None), ('allowKeyGen', 'allowKeyGen', 'boolean', None, None, True, None, None), ('halted', 'halted', 'boolean', None, None, True, None, None), ('unhaltedAt', 'unhaltedAt', 'number', None, None, True, None, None), ('unhaltDurationInMomentums', 'unhaltDurationInMomentums', 'number', None, None, True, None, None), ('tssNonce', 'tssNonce', 'number', None, None, True, None, None), ('metadata', 'metadata', 'string', None, None, True, None, None))


class BridgeNetworkInfo(Model):
    _fields = (('networkClass', 'networkClass', 'number', None, None, True, None, None), ('chainId', 'chainId', 'number', None, None, True, None, None), ('name', 'name', 'string', None, None, True, None, None), ('contractAddress', 'contractAddress', 'string', None, None, True, None, None), ('metadata', 'metadata', 'string', None, None, True, None, None), ('tokenPairs', 'tokenPairs', 'array', None, 'TokenPair', True, None, None))


class BridgeNetworkInfoList(Model):
    _fields = (('count', 'count', 'number', None, None, True, None, None), ('list', 'list', 'array', None, 'BridgeNetworkInfo', True, None, None))


class DelegationInfo(Model):
    _fields = (('name', 'name', 'string', None, None, True, None, None), ('status', 'status', 'number', None, None, True, None, None), ('weight', 'weight', 'decimal-string', 'base-10', None, True, None, None))


class DetailedMomentum(Model):
    _fields = (('blocks', 'blocks', 'array', None, 'AccountBlock', False, '[]', None), ('momentum', 'momentum', 'model', None, 'Momentum', True, None, None))


class DetailedMomentumList(Model):
    _fields = (('count', 'count', 'number', None, None, False, '0', None), ('list', 'list', 'array', None, 'DetailedMomentum', False, '[]', None))


class FusionEntry(Model):
    _fields = (('qsrAmount', 'qsrAmount', 'decimal-string', 'base-10', None, True, None, None), ('beneficiary', 'beneficiary', 'string', 'bech32-address', None, True, None, None), ('expirationHeight', 'expirationHeight', 'number', None, None, True, None, None), ('id', 'id', 'string', 'hex-32', None, True, None, None))


class FusionEntryList(Model):
    _fields = (('qsrAmount', 'qsrAmount', 'decimal-string', 'base-10', None, False, '0n', None), ('count', 'count', 'number', None, None, False, '0', None), ('list', 'list', 'array', None, 'FusionEntry', False, '[]', None))


class GetRequiredPowParam(Model):
    _fields = (('address', 'address', 'string', 'bech32-address', None, True, None, None), ('blockType', 'blockType', 'number', None, None, True, None, None), ('toAddress', 'toAddress', 'string', 'bech32-address', None, False, 'undefined', None), ('data', 'data', 'string', 'base64', None, False, 'undefined', None))


class GetRequiredPowResponse(Model):
    _fields = (('availablePlasma', 'availablePlasma', 'number', None, None, True, None, None), ('basePlasma', 'basePlasma', 'number', None, None, True, None, None), ('requiredDifficulty', 'requiredDifficulty', 'number', None, None, True, None, None))


class HtlcInfo(Model):
    _fields = (('id', 'id', 'string', 'hex-32', None, True, None, None), ('timeLocked', 'timeLocked', 'string', 'bech32-address', None, True, None, None), ('hashLocked', 'hashLocked', 'string', 'bech32-address', None, True, None, None), ('tokenStandard', 'tokenStandard', 'string', 'bech32-token-standard', None, True, None, None), ('amount', 'amount', 'decimal-string', 'base-10', None, True, None, None), ('expirationTime', 'expirationTime', 'number', None, None, True, None, None), ('hashType', 'hashType', 'number', None, None, True, None, None), ('keyMaxSize', 'keyMaxSize', 'number', None, None, True, None, None), ('hashLock', 'hashLock', 'string', 'base64', 'Uint8Array', True, None, None))


class LiquidityInfo(Model):
    _fields = (('administrator', 'administrator', 'string', 'bech32-address', None, True, None, None), ('isHalted', 'isHalted', 'boolean', None, None, True, None, None), ('znnReward', 'znnReward', 'decimal-string', 'base-10', None, True, None, None), ('qsrReward', 'qsrReward', 'decimal-string', 'base-10', None, True, None, None), ('tokenTuples', 'tokenTuples', 'array', None, 'TokenTuple', True, None, None))


class LiquidityStakeEntry(Model):
    _fields = (('amount', 'amount', 'decimal-string', 'base-10', None, True, None, None), ('tokenStandard', 'tokenStandard', 'string', 'bech32-token-standard', None, True, None, None), ('weightedAmount', 'weightedAmount', 'decimal-string', 'base-10', None, True, None, None), ('startTime', 'startTime', 'number', None, None, True, None, None), ('revokeTime', 'revokeTime', 'number', None, None, True, None, None), ('expirationTime', 'expirationTime', 'number', None, None, True, None, None), ('stakeAddress', 'stakeAddress', 'string', 'bech32-address', None, True, None, None), ('id', 'id', 'string', 'hex-32', None, True, None, None))


class LiquidityStakeList(Model):
    _fields = (('totalAmount', 'totalAmount', 'decimal-string', 'base-10', None, True, None, None), ('totalWeightedAmount', 'totalWeightedAmount', 'decimal-string', 'base-10', None, True, None, None), ('count', 'count', 'number', None, None, True, None, None), ('list', 'list', 'array', None, 'LiquidityStakeEntry', True, None, None))


class Momentum(Model):
    _fields = (('version', 'version', 'number', None, None, True, None, None), ('chainIdentifier', 'chainIdentifier', 'number', None, None, True, None, None), ('hash', 'hash', 'string', 'hex-32', None, True, None, None), ('previousHash', 'previousHash', 'string', 'hex-32', None, True, None, None), ('height', 'height', 'number', None, None, True, None, None), ('timestamp', 'timestamp', 'number', None, None, True, None, None), ('data', 'data', 'string', 'base64', None, True, None, None), ('content', 'content', 'array', None, 'AccountHeader', True, None, None), ('changesHash', 'changesHash', 'string', 'hex-32', None, True, None, None), ('publicKey', 'publicKey', 'string', 'base64', None, True, None, None), ('signature', 'signature', 'string', 'base64', None, True, None, None), ('producer', 'producer', 'string', 'bech32-address', None, True, None, None))


class MomentumList(Model):
    _fields = (('count', 'count', 'number', None, None, False, '0', None), ('list', 'list', 'array', None, 'Momentum', False, '[]', None))


class NetworkInfo(Model):
    _fields = (('numPeers', 'numPeers', 'number', None, None, True, None, None), ('self', 'self', 'model', None, 'Peer', True, None, None), ('peers', 'peers', 'array', None, 'Peer', True, None, None))


class OrchestratorInfo(Model):
    _fields = (('windowSize', 'windowSize', 'number', None, None, True, None, None), ('keyGenThreshold', 'keyGenThreshold', 'number', None, None, True, None, None), ('confirmationsToFinality', 'confirmationsToFinality', 'number', None, None, True, None, None), ('estimatedMomentumTime', 'estimatedMomentumTime', 'number', None, None, True, None, None), ('allowKeyGenHeight', 'allowKeyGenHeight', 'number', None, None, True, None, None))


class OsInfo(Model):
    _fields = (('os', 'os', 'string', None, None, True, None, None), ('platform', 'platform', 'string', None, None, True, None, None), ('platformFamily', 'platformFamily', 'string', None, None, True, None, None), ('platformVersion', 'platformVersion', 'string', None, None, True, None, None), ('kernelVersion', 'kernelVersion', 'string', None, None, True, None, None), ('memoryTotal', 'memoryTotal', 'number', None, None, True, None, None), ('memoryFree', 'memoryFree', 'number', None, None, True, None, None), ('numCPU', 'numCPU', 'number', None, None, True, None, None), ('numGoroutine', 'numGoroutine', 'number', None, None, True, None, None))


class Peer(Model):
    _fields = (('publicKey', 'publicKey', 'string', None, None, True, None, None), ('ip', 'ip', 'string', None, None, True, None, None))


class Phase(Model):
    _fields = (('projectId', 'phase.projectID', 'string', 'hex-32', None, True, None, None), ('acceptedTimestamp', 'phase.acceptedTimestamp', 'number', None, None, True, None, None))


class PillarEpochHistory(Model):
    _fields = (('name', 'name', 'string', None, None, True, None, None), ('epoch', 'epoch', 'number', None, None, True, None, None), ('giveBlockRewardPercentage', 'giveBlockRewardPercentage', 'number', None, None, True, None, None), ('giveDelegateRewardPercentage', 'giveDelegateRewardPercentage', 'number', None, None, True, None, None), ('producedBlockNum', 'producedBlockNum', 'number', None, None, True, None, None), ('expectedBlockNum', 'expectedBlockNum', 'number', None, None, True, None, None), ('weight', 'weight', 'decimal-string', 'base-10', None, True, None, None))


class PillarEpochHistoryList(Model):
    _fields = (('count', 'count', 'number', None, None, True, None, None), ('list', 'list', 'array', None, 'PillarEpochHistory', True, None, None))


class PillarEpochStats(Model):
    _fields = (('producedMomentums', 'producedMomentums', 'number', None, None, True, None, None), ('expectedMomentums', 'expectedMomentums', 'number', None, None, True, None, None))


class PillarInfo(Model):
    _fields = (('name', 'name', 'string', None, None, True, None, None), ('rank', 'rank', 'number', None, None, True, None, None), ('type', 'type', 'number', None, None, True, None, None), ('ownerAddress', 'ownerAddress', 'string', 'bech32-address', None, True, None, None), ('producerAddress', 'producerAddress', 'string', 'bech32-address', None, True, None, None), ('withdrawAddress', 'withdrawAddress', 'string', 'bech32-address', None, True, None, None), ('giveMomentumRewardPercentage', 'giveMomentumRewardPercentage', 'number', None, None, True, None, None), ('giveDelegateRewardPercentage', 'giveDelegateRewardPercentage', 'number', None, None, True, None, None), ('isRevocable', 'isRevocable', 'boolean', None, None, True, None, None), ('revokeCooldown', 'revokeCooldown', 'number', None, None, True, None, None), ('revokeTimestamp', 'revokeTimestamp', 'number', None, None, True, None, None), ('currentStats', 'currentStats', 'model', None, 'PillarEpochStats', True, None, None), ('weight', 'weight', 'decimal-string', 'base-10', None, True, None, None))


class PillarInfoList(Model):
    _fields = (('count', 'count', 'number', None, None, True, None, None), ('list', 'list', 'array', None, 'PillarInfo', True, None, None))


class PillarVote(Model):
    _fields = (('id', 'id', 'string', 'hex-32', None, True, None, None), ('name', 'name', 'string', None, None, True, None, None), ('vote', 'vote', 'number', None, None, True, None, None))


class PlasmaInfo(Model):
    _fields = (('currentPlasma', 'currentPlasma', 'number', None, None, True, None, None), ('maxPlasma', 'maxPlasma', 'number', None, None, True, None, None), ('qsrAmount', 'qsrAmount', 'decimal-string', 'base-10', None, True, None, None))


class ProcessInfo(Model):
    _fields = (('commit', 'commit', 'string', None, None, True, None, None), ('version', 'version', 'string', None, None, True, None, None))


class Project(Model):
    _fields = (('owner', 'owner', 'string', 'bech32-address', None, True, None, None), ('lastUpdateTimestamp', 'lastUpdateTimestamp', 'number', None, None, True, None, None), ('phaseIds', 'phaseIds', 'array', None, 'Hash', True, None, None), ('phases', 'phases', 'array', None, 'Phase', True, None, None))


class ProjectList(Model):
    _fields = (('count', 'count', 'number', None, None, True, None, None), ('list', 'list', 'array', None, 'Project', True, None, None))


class RewardDeposit(Model):
    _fields = (('address', 'address', 'string', 'bech32-address', None, True, None, None), ('znnAmount', 'znnAmount', 'decimal-string', 'base-10', None, True, None, None), ('qsrAmount', 'qsrAmount', 'decimal-string', 'base-10', None, True, None, None))


class RewardHistoryEntry(Model):
    _fields = (('epoch', 'epoch', 'number', None, None, True, None, None), ('znnAmount', 'znnAmount', 'decimal-string', 'base-10', None, True, None, None), ('qsrAmount', 'qsrAmount', 'decimal-string', 'base-10', None, True, None, None))


class RewardHistoryList(Model):
    _fields = (('count', 'count', 'number', None, None, True, None, None), ('list', 'list', 'array', None, 'RewardHistoryEntry', True, None, None))


class SecurityInfo(Model):
    _fields = (('guardians', 'guardians', 'array', None, 'Address', True, None, None), ('guardiansVotes', 'guardiansVotes', 'array', None, 'Address', True, None, None), ('administratorDelay', 'administratorDelay', 'number', None, None, True, None, None), ('softDelay', 'softDelay', 'number', None, None, True, None, None))


class SentinelInfo(Model):
    _fields = (('owner', 'owner', 'string', 'bech32-address', None, True, None, None), ('registrationTimestamp', 'registrationTimestamp', 'number', None, None, True, None, None), ('isRevocable', 'isRevocable', 'boolean', None, None, True, None, None), ('revokeCooldown', 'revokeCooldown', 'number', None, None, True, None, None), ('active', 'active', 'boolean', None, None, True, None, None))


class SentinelInfoList(Model):
    _fields = (('count', 'count', 'number', None, None, True, None, None), ('list', 'list', 'array', None, 'SentinelInfo', True, None, None))


class Spork(Model):
    _fields = (('id', 'id', 'string', 'hex-32', None, True, None, None), ('name', 'name', 'string', None, None, True, None, None), ('description', 'description', 'string', None, None, True, None, None), ('activated', 'activated', 'boolean', None, None, True, None, None), ('enforcementHeight', 'enforcementHeight', 'number', None, None, True, None, None))


class SporkList(Model):
    _fields = (('count', 'count', 'number', None, None, True, None, None), ('list', 'list', 'array', None, 'Spork', True, None, None))


class StakeEntry(Model):
    _fields = (('amount', 'amount', 'decimal-string', 'base-10', None, True, None, None), ('weightedAmount', 'weightedAmount', 'decimal-string', 'base-10', None, True, None, None), ('startTimestamp', 'startTimestamp', 'number', None, None, True, None, None), ('expirationTimestamp', 'expirationTimestamp', 'number', None, None, True, None, None), ('address', 'address', 'string', 'bech32-address', None, True, None, None), ('id', 'id', 'string', 'hex-32', None, True, None, None))


class StakeList(Model):
    _fields = (('totalAmount', 'totalAmount', 'decimal-string', 'base-10', None, True, None, None), ('totalWeightedAmount', 'totalWeightedAmount', 'decimal-string', 'base-10', None, True, None, None), ('count', 'count', 'number', None, None, True, None, None), ('list', 'list', 'array', None, 'StakeEntry', True, None, None))


class SwapAssetEntry(Model):
    _fields = (('keyIdHash', 'keyIdHash', 'string', 'hex-32', None, True, None, None), ('qsr', 'qsr', 'decimal-string', 'base-10', None, True, None, None), ('znn', 'znn', 'decimal-string', 'base-10', None, True, None, None))


class SwapAssetList(Model):
    _fields = (('list', 'list', 'object', None, None, False, '{}', 'SwapAssetEntry'),)


class SwapLegacyPillarEntry(Model):
    _fields = (('numPillars', 'numPillars', 'number', None, None, True, None, None), ('keyIdHash', 'keyIdHash', 'string', 'hex-32', None, True, None, None))


class SwapLegacyPillarList(Model):
    _fields = (('list', '', 'array', None, 'SwapLegacyPillarEntry', False, '[]', None),)


class SyncInfo(Model):
    _fields = (('state', 'state', 'model', None, 'SyncState', True, None, None), ('currentHeight', 'currentHeight', 'number', None, None, True, None, None), ('targetHeight', 'targetHeight', 'number', None, None, True, None, None))


class TimeChallengeInfo(Model):
    _fields = (('methodName', 'MethodName', 'string', None, None, True, None, None), ('paramsHash', 'ParamsHash', 'string', 'hex-32', None, True, None, None), ('challengeStartHeight', 'ChallengeStartHeight', 'number', None, None, True, None, None))


class TimeChallengesList(Model):
    _fields = (('count', 'count', 'number', None, None, True, None, None), ('list', 'list', 'array', None, 'TimeChallengeInfo', True, None, None))


class Token(Model):
    _fields = (('name', 'name', 'string', None, None, True, None, None), ('symbol', 'symbol', 'string', None, None, True, None, None), ('domain', 'domain', 'string', None, None, True, None, None), ('totalSupply', 'totalSupply', 'decimal-string', 'base-10', None, True, None, None), ('decimals', 'decimals', 'number', None, None, True, None, None), ('owner', 'owner', 'string', 'bech32-address', None, True, None, None), ('tokenStandard', 'tokenStandard', 'string', 'bech32-token-standard', None, True, None, None), ('maxSupply', 'maxSupply', 'decimal-string', 'base-10', None, True, None, None), ('isBurnable', 'isBurnable', 'boolean', None, None, True, None, None), ('isMintable', 'isMintable', 'boolean', None, None, True, None, None), ('isUtility', 'isUtility', 'boolean', None, None, True, None, None))


class TokenList(Model):
    _fields = (('count', 'count', 'number', None, None, True, None, None), ('list', 'list', 'array', None, 'Token', True, None, None))


class TokenPair(Model):
    _fields = (('tokenStandard', 'tokenStandard', 'string', 'bech32-token-standard', None, True, None, None), ('tokenAddress', 'tokenAddress', 'string', None, None, True, None, None), ('bridgeable', 'bridgeable', 'boolean', None, None, True, None, None), ('redeemable', 'redeemable', 'boolean', None, None, True, None, None), ('owned', 'owned', 'boolean', None, None, True, None, None), ('minAmount', 'minAmount', 'decimal-string', 'base-10', None, True, None, None), ('feePercentage', 'feePercentage', 'number', None, None, True, None, None), ('redeemDelay', 'redeemDelay', 'number', None, None, True, None, None), ('metadata', 'metadata', 'string', None, None, True, None, None))


class TokenTuple(Model):
    _fields = (('tokenStandard', 'tokenStandard', 'string', 'bech32-token-standard', None, True, None, None), ('znnPercentage', 'znnPercentage', 'number', None, None, True, None, None), ('qsrPercentage', 'qsrPercentage', 'number', None, None, True, None, None), ('minAmount', 'minAmount', 'decimal-string', 'base-10', None, True, None, None))


class UncollectedReward(Model):
    _fields = (('address', 'address', 'string', 'bech32-address', None, True, None, None), ('znnAmount', 'znnAmount', 'decimal-string', 'base-10', None, True, None, None), ('qsrAmount', 'qsrAmount', 'decimal-string', 'base-10', None, True, None, None))


class UnwrapTokenRequest(Model):
    _fields = (('registrationMomentumHeight', 'registrationMomentumHeight', 'number', None, None, True, None, None), ('networkClass', 'networkClass', 'number', None, None, True, None, None), ('chainId', 'chainId', 'number', None, None, True, None, None), ('transactionHash', 'transactionHash', 'string', 'hex-32', None, True, None, None), ('logIndex', 'logIndex', 'number', None, None, True, None, None), ('toAddress', 'toAddress', 'string', 'bech32-address', None, True, None, None), ('tokenAddress', 'tokenAddress', 'string', None, None, True, None, None), ('tokenStandard', 'tokenStandard', 'string', 'bech32-token-standard', None, True, None, None), ('amount', 'amount', 'decimal-string', 'base-10', None, True, None, None), ('signature', 'signature', 'string', None, None, True, None, None), ('redeemed', 'redeemed', 'number', None, None, True, None, None), ('revoked', 'revoked', 'number', None, None, True, None, None), ('redeemableIn', 'redeemableIn', 'number', None, None, True, None, None))


class UnwrapTokenRequestList(Model):
    _fields = (('count', 'count', 'number', None, None, True, None, None), ('list', 'list', 'array', None, 'UnwrapTokenRequest', True, None, None))


class VoteBreakdown(Model):
    _fields = (('id', 'id', 'string', 'hex-32', None, True, None, None), ('yes', 'yes', 'number', None, None, True, None, None), ('no', 'no', 'number', None, None, True, None, None), ('total', 'total', 'number', None, None, True, None, None))


class WrapTokenRequest(Model):
    _fields = (('networkClass', 'networkClass', 'number', None, None, True, None, None), ('chainId', 'chainId', 'number', None, None, True, None, None), ('id', 'id', 'string', 'hex-32', None, True, None, None), ('toAddress', 'toAddress', 'string', None, None, True, None, None), ('tokenStandard', 'tokenStandard', 'string', 'bech32-token-standard', None, True, None, None), ('tokenAddress', 'tokenAddress', 'string', None, None, True, None, None), ('amount', 'amount', 'decimal-string', 'base-10', None, True, None, None), ('fee', 'fee', 'decimal-string', 'base-10', None, True, None, None), ('signature', 'signature', 'string', None, None, True, None, None), ('creationMomentumHeight', 'creationMomentumHeight', 'number', None, None, True, None, None), ('confirmationsToFinality', 'confirmationsToFinality', 'number', None, None, True, None, None))


class WrapTokenRequestList(Model):
    _fields = (('count', 'count', 'number', None, None, True, None, None), ('list', 'list', 'array', None, 'WrapTokenRequest', True, None, None))


class ZtsFeesInfo(Model):
    _fields = (('tokenStandard', 'tokenStandard', 'string', 'bech32-token-standard', None, True, None, None), ('accumulatedFee', 'accumulatedFee', 'decimal-string', 'base-10', None, True, None, None))


from znn.model.nom.account_block import AccountBlock

MODEL_TYPES = {
    'AcceleratorProject': AcceleratorProject,
    'AccountBlock': AccountBlock,
    'AccountBlockConfirmationDetail': AccountBlockConfirmationDetail,
    'AccountBlockList': AccountBlockList,
    'AccountBlockTemplate': AccountBlockTemplate,
    'AccountHeader': AccountHeader,
    'AccountInfo': AccountInfo,
    'Address': Address,
    'BalanceInfoListItem': BalanceInfoListItem,
    'BridgeInfo': BridgeInfo,
    'BridgeNetworkInfo': BridgeNetworkInfo,
    'BridgeNetworkInfoList': BridgeNetworkInfoList,
    'DelegationInfo': DelegationInfo,
    'DetailedMomentum': DetailedMomentum,
    'DetailedMomentumList': DetailedMomentumList,
    'FusionEntry': FusionEntry,
    'FusionEntryList': FusionEntryList,
    'GetRequiredPowParam': GetRequiredPowParam,
    'GetRequiredPowResponse': GetRequiredPowResponse,
    'Hash': Hash,
    'HashHeight': HashHeight,
    'HtlcInfo': HtlcInfo,
    'LiquidityInfo': LiquidityInfo,
    'LiquidityStakeEntry': LiquidityStakeEntry,
    'LiquidityStakeList': LiquidityStakeList,
    'Model': Model,
    'Momentum': Momentum,
    'MomentumList': MomentumList,
    'NetworkInfo': NetworkInfo,
    'OrchestratorInfo': OrchestratorInfo,
    'OsInfo': OsInfo,
    'Peer': Peer,
    'Phase': Phase,
    'PillarEpochHistory': PillarEpochHistory,
    'PillarEpochHistoryList': PillarEpochHistoryList,
    'PillarEpochStats': PillarEpochStats,
    'PillarInfo': PillarInfo,
    'PillarInfoList': PillarInfoList,
    'PillarVote': PillarVote,
    'PlasmaInfo': PlasmaInfo,
    'ProcessInfo': ProcessInfo,
    'Project': Project,
    'ProjectList': ProjectList,
    'RewardDeposit': RewardDeposit,
    'RewardHistoryEntry': RewardHistoryEntry,
    'RewardHistoryList': RewardHistoryList,
    'SecurityInfo': SecurityInfo,
    'SentinelInfo': SentinelInfo,
    'SentinelInfoList': SentinelInfoList,
    'Spork': Spork,
    'SporkList': SporkList,
    'StakeEntry': StakeEntry,
    'StakeList': StakeList,
    'SwapAssetEntry': SwapAssetEntry,
    'SwapAssetList': SwapAssetList,
    'SwapLegacyPillarEntry': SwapLegacyPillarEntry,
    'SwapLegacyPillarList': SwapLegacyPillarList,
    'SyncInfo': SyncInfo,
    'TimeChallengeInfo': TimeChallengeInfo,
    'TimeChallengesList': TimeChallengesList,
    'Token': Token,
    'TokenList': TokenList,
    'TokenPair': TokenPair,
    'TokenStandard': TokenStandard,
    'TokenTuple': TokenTuple,
    'UncollectedReward': UncollectedReward,
    'UnwrapTokenRequest': UnwrapTokenRequest,
    'UnwrapTokenRequestList': UnwrapTokenRequestList,
    'VoteBreakdown': VoteBreakdown,
    'WrapTokenRequest': WrapTokenRequest,
    'WrapTokenRequestList': WrapTokenRequestList,
    'ZtsFeesInfo': ZtsFeesInfo,
    'AcceleratorProjectStatus': AcceleratorProjectStatus,
    'AcceleratorProjectVote': AcceleratorProjectVote,
    'BlockTypeEnum': BlockTypeEnum,
    'ReceiveBlockTypeEnum': ReceiveBlockTypeEnum,
    'SendBlockTypeEnum': SendBlockTypeEnum,
    'SyncState': SyncState,
}

WIRE_SCHEMAS = {'AcceleratorProject': (('id', 'id', 'string', 'hex-32', None, True, None, None), ('name', 'name', 'string', None, None, True, None, None), ('description', 'description', 'string', None, None, True, None, None), ('url', 'url', 'string', None, None, True, None, None), ('znnFundsNeeded', 'znnFundsNeeded', 'decimal-string', 'base-10', None, True, None, None), ('qsrFundsNeeded', 'qsrFundsNeeded', 'decimal-string', 'base-10', None, True, None, None), ('creationTimestamp', 'creationTimestamp', 'number', None, None, True, None, None), ('statusInt', 'status', 'number', None, None, True, None, None), ('voteBreakdown', 'votes', 'model', None, 'VoteBreakdown', True, None, None)), 'AccountBlock': (('token', 'token', 'model', None, 'Token', False, None, None), ('descendantBlocks', 'descendantBlocks', 'array', None, 'AccountBlock', True, None, None), ('basePlasma', 'basePlasma', 'number', None, None, True, None, None), ('usedPlasma', 'usedPlasma', 'number', None, None, True, None, None), ('changesHash', 'changesHash', 'string', 'hex-32', None, True, None, None), ('confirmationDetail', 'confirmationDetail', 'model', None, 'AccountBlockConfirmationDetail', False, None, None), ('pairedAccountBlock', 'pairedAccountBlock', 'model', None, 'AccountBlock', False, None, None)), 'AccountBlockConfirmationDetail': (('numConfirmations', 'numConfirmations', 'number', None, None, True, None, None), ('momentumHeight', 'momentumHeight', 'number', None, None, True, None, None), ('momentumHash', 'momentumHash', 'string', 'hex-32', None, True, None, None), ('momentumTimestamp', 'momentumTimestamp', 'number', None, None, True, None, None)), 'AccountBlockList': (('count', 'count', 'number', None, None, False, '0', None), ('list', 'list', 'array', None, 'AccountBlock', False, '[]', None), ('more', 'more', 'boolean', None, None, False, 'false', None)), 'AccountBlockTemplate': (('version', 'version', 'number', None, None, True, None, None), ('chainIdentifier', 'chainIdentifier', 'number', None, None, True, None, None), ('blockType', 'blockType', 'number', None, None, True, None, None), ('hash', 'hash', 'string', 'hex-32', None, True, None, None), ('previousHash', 'previousHash', 'string', 'hex-32', None, True, None, None), ('height', 'height', 'number', None, None, True, None, None), ('momentumAcknowledged', 'momentumAcknowledged', 'model', None, 'HashHeight', True, None, None), ('address', 'address', 'string', 'bech32-address', None, True, None, None), ('toAddress', 'toAddress', 'string', 'bech32-address', None, True, None, None), ('amount', 'amount', 'decimal-string', 'base-10', None, True, None, None), ('tokenStandard', 'tokenStandard', 'string', 'bech32-token-standard', None, True, None, None), ('fromBlockHash', 'fromBlockHash', 'string', 'hex-32', None, True, None, None), ('data', 'data', 'string', 'base64', None, True, None, None), ('fusedPlasma', 'fusedPlasma', 'number', None, None, True, None, None), ('difficulty', 'difficulty', 'number', None, None, True, None, None), ('nonce', 'nonce', 'string', None, None, True, None, None), ('publicKey', 'publicKey', 'string', 'base64', None, True, None, None), ('signature', 'signature', 'string', 'base64', None, True, None, None)), 'AccountHeader': (('address', 'address', 'string', 'bech32-address', None, True, None, None), ('hash', 'hash', 'string', 'hex-32', None, True, None, None), ('height', 'height', 'number', None, None, True, None, None)), 'AccountInfo': (('address', 'address', 'string', 'bech32-address', None, True, None, None), ('blockCount', 'accountHeight', 'number', None, None, False, '0', None), ('balanceInfoMap', 'balanceInfoMap', 'object', None, None, False, '{}', 'BalanceInfoListItem')), 'Address': (('hrp', 'hrp', 'string', None, None, True, None, None), ('core', 'core', 'string', 'model-specific-binary', None, True, None, None)), 'BalanceInfoListItem': (('token', 'token', 'model', None, 'Token', True, None, None), ('balance', 'balance', 'decimal-string', 'base-10', None, True, None, None)), 'BridgeInfo': (('administrator', 'administrator', 'string', 'bech32-address', None, True, None, None), ('compressedTssECDSAPubKey', 'compressedTssECDSAPubKey', 'string', None, None, True, None, None), ('decompressedTssECDSAPubKey', 'decompressedTssECDSAPubKey', 'string', None, None, True, None, None), ('allowKeyGen', 'allowKeyGen', 'boolean', None, None, True, None, None), ('halted', 'halted', 'boolean', None, None, True, None, None), ('unhaltedAt', 'unhaltedAt', 'number', None, None, True, None, None), ('unhaltDurationInMomentums', 'unhaltDurationInMomentums', 'number', None, None, True, None, None), ('tssNonce', 'tssNonce', 'number', None, None, True, None, None), ('metadata', 'metadata', 'string', None, None, True, None, None)), 'BridgeNetworkInfo': (('networkClass', 'networkClass', 'number', None, None, True, None, None), ('chainId', 'chainId', 'number', None, None, True, None, None), ('name', 'name', 'string', None, None, True, None, None), ('contractAddress', 'contractAddress', 'string', None, None, True, None, None), ('metadata', 'metadata', 'string', None, None, True, None, None), ('tokenPairs', 'tokenPairs', 'array', None, 'TokenPair', True, None, None)), 'BridgeNetworkInfoList': (('count', 'count', 'number', None, None, True, None, None), ('list', 'list', 'array', None, 'BridgeNetworkInfo', True, None, None)), 'DelegationInfo': (('name', 'name', 'string', None, None, True, None, None), ('status', 'status', 'number', None, None, True, None, None), ('weight', 'weight', 'decimal-string', 'base-10', None, True, None, None)), 'DetailedMomentum': (('blocks', 'blocks', 'array', None, 'AccountBlock', False, '[]', None), ('momentum', 'momentum', 'model', None, 'Momentum', True, None, None)), 'DetailedMomentumList': (('count', 'count', 'number', None, None, False, '0', None), ('list', 'list', 'array', None, 'DetailedMomentum', False, '[]', None)), 'FusionEntry': (('qsrAmount', 'qsrAmount', 'decimal-string', 'base-10', None, True, None, None), ('beneficiary', 'beneficiary', 'string', 'bech32-address', None, True, None, None), ('expirationHeight', 'expirationHeight', 'number', None, None, True, None, None), ('id', 'id', 'string', 'hex-32', None, True, None, None)), 'FusionEntryList': (('qsrAmount', 'qsrAmount', 'decimal-string', 'base-10', None, False, '0n', None), ('count', 'count', 'number', None, None, False, '0', None), ('list', 'list', 'array', None, 'FusionEntry', False, '[]', None)), 'GetRequiredPowParam': (('address', 'address', 'string', 'bech32-address', None, True, None, None), ('blockType', 'blockType', 'number', None, None, True, None, None), ('toAddress', 'toAddress', 'string', 'bech32-address', None, False, 'undefined', None), ('data', 'data', 'string', 'base64', None, False, 'undefined', None)), 'GetRequiredPowResponse': (('availablePlasma', 'availablePlasma', 'number', None, None, True, None, None), ('basePlasma', 'basePlasma', 'number', None, None, True, None, None), ('requiredDifficulty', 'requiredDifficulty', 'number', None, None, True, None, None)), 'Hash': (('core', 'core', 'string', 'model-specific-binary', None, True, None, None),), 'HashHeight': (('hash', 'hash', 'string', 'hex-32', None, False, 'EMPTY_HASH', None), ('height', 'height', 'number', None, None, True, None, None)), 'HtlcInfo': (('id', 'id', 'string', 'hex-32', None, True, None, None), ('timeLocked', 'timeLocked', 'string', 'bech32-address', None, True, None, None), ('hashLocked', 'hashLocked', 'string', 'bech32-address', None, True, None, None), ('tokenStandard', 'tokenStandard', 'string', 'bech32-token-standard', None, True, None, None), ('amount', 'amount', 'decimal-string', 'base-10', None, True, None, None), ('expirationTime', 'expirationTime', 'number', None, None, True, None, None), ('hashType', 'hashType', 'number', None, None, True, None, None), ('keyMaxSize', 'keyMaxSize', 'number', None, None, True, None, None), ('hashLock', 'hashLock', 'string', 'base64', 'Uint8Array', True, None, None)), 'LiquidityInfo': (('administrator', 'administrator', 'string', 'bech32-address', None, True, None, None), ('isHalted', 'isHalted', 'boolean', None, None, True, None, None), ('znnReward', 'znnReward', 'decimal-string', 'base-10', None, True, None, None), ('qsrReward', 'qsrReward', 'decimal-string', 'base-10', None, True, None, None), ('tokenTuples', 'tokenTuples', 'array', None, 'TokenTuple', True, None, None)), 'LiquidityStakeEntry': (('amount', 'amount', 'decimal-string', 'base-10', None, True, None, None), ('tokenStandard', 'tokenStandard', 'string', 'bech32-token-standard', None, True, None, None), ('weightedAmount', 'weightedAmount', 'decimal-string', 'base-10', None, True, None, None), ('startTime', 'startTime', 'number', None, None, True, None, None), ('revokeTime', 'revokeTime', 'number', None, None, True, None, None), ('expirationTime', 'expirationTime', 'number', None, None, True, None, None), ('stakeAddress', 'stakeAddress', 'string', 'bech32-address', None, True, None, None), ('id', 'id', 'string', 'hex-32', None, True, None, None)), 'LiquidityStakeList': (('totalAmount', 'totalAmount', 'decimal-string', 'base-10', None, True, None, None), ('totalWeightedAmount', 'totalWeightedAmount', 'decimal-string', 'base-10', None, True, None, None), ('count', 'count', 'number', None, None, True, None, None), ('list', 'list', 'array', None, 'LiquidityStakeEntry', True, None, None)), 'Model': (), 'Momentum': (('version', 'version', 'number', None, None, True, None, None), ('chainIdentifier', 'chainIdentifier', 'number', None, None, True, None, None), ('hash', 'hash', 'string', 'hex-32', None, True, None, None), ('previousHash', 'previousHash', 'string', 'hex-32', None, True, None, None), ('height', 'height', 'number', None, None, True, None, None), ('timestamp', 'timestamp', 'number', None, None, True, None, None), ('data', 'data', 'string', 'base64', None, True, None, None), ('content', 'content', 'array', None, 'AccountHeader', True, None, None), ('changesHash', 'changesHash', 'string', 'hex-32', None, True, None, None), ('publicKey', 'publicKey', 'string', 'base64', None, True, None, None), ('signature', 'signature', 'string', 'base64', None, True, None, None), ('producer', 'producer', 'string', 'bech32-address', None, True, None, None)), 'MomentumList': (('count', 'count', 'number', None, None, False, '0', None), ('list', 'list', 'array', None, 'Momentum', False, '[]', None)), 'NetworkInfo': (('numPeers', 'numPeers', 'number', None, None, True, None, None), ('self', 'self', 'model', None, 'Peer', True, None, None), ('peers', 'peers', 'array', None, 'Peer', True, None, None)), 'OrchestratorInfo': (('windowSize', 'windowSize', 'number', None, None, True, None, None), ('keyGenThreshold', 'keyGenThreshold', 'number', None, None, True, None, None), ('confirmationsToFinality', 'confirmationsToFinality', 'number', None, None, True, None, None), ('estimatedMomentumTime', 'estimatedMomentumTime', 'number', None, None, True, None, None), ('allowKeyGenHeight', 'allowKeyGenHeight', 'number', None, None, True, None, None)), 'OsInfo': (('os', 'os', 'string', None, None, True, None, None), ('platform', 'platform', 'string', None, None, True, None, None), ('platformFamily', 'platformFamily', 'string', None, None, True, None, None), ('platformVersion', 'platformVersion', 'string', None, None, True, None, None), ('kernelVersion', 'kernelVersion', 'string', None, None, True, None, None), ('memoryTotal', 'memoryTotal', 'number', None, None, True, None, None), ('memoryFree', 'memoryFree', 'number', None, None, True, None, None), ('numCPU', 'numCPU', 'number', None, None, True, None, None), ('numGoroutine', 'numGoroutine', 'number', None, None, True, None, None)), 'Peer': (('publicKey', 'publicKey', 'string', None, None, True, None, None), ('ip', 'ip', 'string', None, None, True, None, None)), 'Phase': (('projectId', 'phase.projectID', 'string', 'hex-32', None, True, None, None), ('acceptedTimestamp', 'phase.acceptedTimestamp', 'number', None, None, True, None, None)), 'PillarEpochHistory': (('name', 'name', 'string', None, None, True, None, None), ('epoch', 'epoch', 'number', None, None, True, None, None), ('giveBlockRewardPercentage', 'giveBlockRewardPercentage', 'number', None, None, True, None, None), ('giveDelegateRewardPercentage', 'giveDelegateRewardPercentage', 'number', None, None, True, None, None), ('producedBlockNum', 'producedBlockNum', 'number', None, None, True, None, None), ('expectedBlockNum', 'expectedBlockNum', 'number', None, None, True, None, None), ('weight', 'weight', 'decimal-string', 'base-10', None, True, None, None)), 'PillarEpochHistoryList': (('count', 'count', 'number', None, None, True, None, None), ('list', 'list', 'array', None, 'PillarEpochHistory', True, None, None)), 'PillarEpochStats': (('producedMomentums', 'producedMomentums', 'number', None, None, True, None, None), ('expectedMomentums', 'expectedMomentums', 'number', None, None, True, None, None)), 'PillarInfo': (('name', 'name', 'string', None, None, True, None, None), ('rank', 'rank', 'number', None, None, True, None, None), ('type', 'type', 'number', None, None, True, None, None), ('ownerAddress', 'ownerAddress', 'string', 'bech32-address', None, True, None, None), ('producerAddress', 'producerAddress', 'string', 'bech32-address', None, True, None, None), ('withdrawAddress', 'withdrawAddress', 'string', 'bech32-address', None, True, None, None), ('giveMomentumRewardPercentage', 'giveMomentumRewardPercentage', 'number', None, None, True, None, None), ('giveDelegateRewardPercentage', 'giveDelegateRewardPercentage', 'number', None, None, True, None, None), ('isRevocable', 'isRevocable', 'boolean', None, None, True, None, None), ('revokeCooldown', 'revokeCooldown', 'number', None, None, True, None, None), ('revokeTimestamp', 'revokeTimestamp', 'number', None, None, True, None, None), ('currentStats', 'currentStats', 'model', None, 'PillarEpochStats', True, None, None), ('weight', 'weight', 'decimal-string', 'base-10', None, True, None, None)), 'PillarInfoList': (('count', 'count', 'number', None, None, True, None, None), ('list', 'list', 'array', None, 'PillarInfo', True, None, None)), 'PillarVote': (('id', 'id', 'string', 'hex-32', None, True, None, None), ('name', 'name', 'string', None, None, True, None, None), ('vote', 'vote', 'number', None, None, True, None, None)), 'PlasmaInfo': (('currentPlasma', 'currentPlasma', 'number', None, None, True, None, None), ('maxPlasma', 'maxPlasma', 'number', None, None, True, None, None), ('qsrAmount', 'qsrAmount', 'decimal-string', 'base-10', None, True, None, None)), 'ProcessInfo': (('commit', 'commit', 'string', None, None, True, None, None), ('version', 'version', 'string', None, None, True, None, None)), 'Project': (('owner', 'owner', 'string', 'bech32-address', None, True, None, None), ('lastUpdateTimestamp', 'lastUpdateTimestamp', 'number', None, None, True, None, None), ('phaseIds', 'phaseIds', 'array', None, 'Hash', True, None, None), ('phases', 'phases', 'array', None, 'Phase', True, None, None)), 'ProjectList': (('count', 'count', 'number', None, None, True, None, None), ('list', 'list', 'array', None, 'Project', True, None, None)), 'RewardDeposit': (('address', 'address', 'string', 'bech32-address', None, True, None, None), ('znnAmount', 'znnAmount', 'decimal-string', 'base-10', None, True, None, None), ('qsrAmount', 'qsrAmount', 'decimal-string', 'base-10', None, True, None, None)), 'RewardHistoryEntry': (('epoch', 'epoch', 'number', None, None, True, None, None), ('znnAmount', 'znnAmount', 'decimal-string', 'base-10', None, True, None, None), ('qsrAmount', 'qsrAmount', 'decimal-string', 'base-10', None, True, None, None)), 'RewardHistoryList': (('count', 'count', 'number', None, None, True, None, None), ('list', 'list', 'array', None, 'RewardHistoryEntry', True, None, None)), 'SecurityInfo': (('guardians', 'guardians', 'array', None, 'Address', True, None, None), ('guardiansVotes', 'guardiansVotes', 'array', None, 'Address', True, None, None), ('administratorDelay', 'administratorDelay', 'number', None, None, True, None, None), ('softDelay', 'softDelay', 'number', None, None, True, None, None)), 'SentinelInfo': (('owner', 'owner', 'string', 'bech32-address', None, True, None, None), ('registrationTimestamp', 'registrationTimestamp', 'number', None, None, True, None, None), ('isRevocable', 'isRevocable', 'boolean', None, None, True, None, None), ('revokeCooldown', 'revokeCooldown', 'number', None, None, True, None, None), ('active', 'active', 'boolean', None, None, True, None, None)), 'SentinelInfoList': (('count', 'count', 'number', None, None, True, None, None), ('list', 'list', 'array', None, 'SentinelInfo', True, None, None)), 'Spork': (('id', 'id', 'string', 'hex-32', None, True, None, None), ('name', 'name', 'string', None, None, True, None, None), ('description', 'description', 'string', None, None, True, None, None), ('activated', 'activated', 'boolean', None, None, True, None, None), ('enforcementHeight', 'enforcementHeight', 'number', None, None, True, None, None)), 'SporkList': (('count', 'count', 'number', None, None, True, None, None), ('list', 'list', 'array', None, 'Spork', True, None, None)), 'StakeEntry': (('amount', 'amount', 'decimal-string', 'base-10', None, True, None, None), ('weightedAmount', 'weightedAmount', 'decimal-string', 'base-10', None, True, None, None), ('startTimestamp', 'startTimestamp', 'number', None, None, True, None, None), ('expirationTimestamp', 'expirationTimestamp', 'number', None, None, True, None, None), ('address', 'address', 'string', 'bech32-address', None, True, None, None), ('id', 'id', 'string', 'hex-32', None, True, None, None)), 'StakeList': (('totalAmount', 'totalAmount', 'decimal-string', 'base-10', None, True, None, None), ('totalWeightedAmount', 'totalWeightedAmount', 'decimal-string', 'base-10', None, True, None, None), ('count', 'count', 'number', None, None, True, None, None), ('list', 'list', 'array', None, 'StakeEntry', True, None, None)), 'SwapAssetEntry': (('keyIdHash', 'keyIdHash', 'string', 'hex-32', None, True, None, None), ('qsr', 'qsr', 'decimal-string', 'base-10', None, True, None, None), ('znn', 'znn', 'decimal-string', 'base-10', None, True, None, None)), 'SwapAssetList': (('list', 'list', 'object', None, None, False, '{}', 'SwapAssetEntry'),), 'SwapLegacyPillarEntry': (('numPillars', 'numPillars', 'number', None, None, True, None, None), ('keyIdHash', 'keyIdHash', 'string', 'hex-32', None, True, None, None)), 'SwapLegacyPillarList': (('list', '', 'array', None, 'SwapLegacyPillarEntry', False, '[]', None),), 'SyncInfo': (('state', 'state', 'model', None, 'SyncState', True, None, None), ('currentHeight', 'currentHeight', 'number', None, None, True, None, None), ('targetHeight', 'targetHeight', 'number', None, None, True, None, None)), 'TimeChallengeInfo': (('methodName', 'MethodName', 'string', None, None, True, None, None), ('paramsHash', 'ParamsHash', 'string', 'hex-32', None, True, None, None), ('challengeStartHeight', 'ChallengeStartHeight', 'number', None, None, True, None, None)), 'TimeChallengesList': (('count', 'count', 'number', None, None, True, None, None), ('list', 'list', 'array', None, 'TimeChallengeInfo', True, None, None)), 'Token': (('name', 'name', 'string', None, None, True, None, None), ('symbol', 'symbol', 'string', None, None, True, None, None), ('domain', 'domain', 'string', None, None, True, None, None), ('totalSupply', 'totalSupply', 'decimal-string', 'base-10', None, True, None, None), ('decimals', 'decimals', 'number', None, None, True, None, None), ('owner', 'owner', 'string', 'bech32-address', None, True, None, None), ('tokenStandard', 'tokenStandard', 'string', 'bech32-token-standard', None, True, None, None), ('maxSupply', 'maxSupply', 'decimal-string', 'base-10', None, True, None, None), ('isBurnable', 'isBurnable', 'boolean', None, None, True, None, None), ('isMintable', 'isMintable', 'boolean', None, None, True, None, None), ('isUtility', 'isUtility', 'boolean', None, None, True, None, None)), 'TokenList': (('count', 'count', 'number', None, None, True, None, None), ('list', 'list', 'array', None, 'Token', True, None, None)), 'TokenPair': (('tokenStandard', 'tokenStandard', 'string', 'bech32-token-standard', None, True, None, None), ('tokenAddress', 'tokenAddress', 'string', None, None, True, None, None), ('bridgeable', 'bridgeable', 'boolean', None, None, True, None, None), ('redeemable', 'redeemable', 'boolean', None, None, True, None, None), ('owned', 'owned', 'boolean', None, None, True, None, None), ('minAmount', 'minAmount', 'decimal-string', 'base-10', None, True, None, None), ('feePercentage', 'feePercentage', 'number', None, None, True, None, None), ('redeemDelay', 'redeemDelay', 'number', None, None, True, None, None), ('metadata', 'metadata', 'string', None, None, True, None, None)), 'TokenStandard': (('core', 'core', 'string', 'model-specific-binary', None, True, None, None),), 'TokenTuple': (('tokenStandard', 'tokenStandard', 'string', 'bech32-token-standard', None, True, None, None), ('znnPercentage', 'znnPercentage', 'number', None, None, True, None, None), ('qsrPercentage', 'qsrPercentage', 'number', None, None, True, None, None), ('minAmount', 'minAmount', 'decimal-string', 'base-10', None, True, None, None)), 'UncollectedReward': (('address', 'address', 'string', 'bech32-address', None, True, None, None), ('znnAmount', 'znnAmount', 'decimal-string', 'base-10', None, True, None, None), ('qsrAmount', 'qsrAmount', 'decimal-string', 'base-10', None, True, None, None)), 'UnwrapTokenRequest': (('registrationMomentumHeight', 'registrationMomentumHeight', 'number', None, None, True, None, None), ('networkClass', 'networkClass', 'number', None, None, True, None, None), ('chainId', 'chainId', 'number', None, None, True, None, None), ('transactionHash', 'transactionHash', 'string', 'hex-32', None, True, None, None), ('logIndex', 'logIndex', 'number', None, None, True, None, None), ('toAddress', 'toAddress', 'string', 'bech32-address', None, True, None, None), ('tokenAddress', 'tokenAddress', 'string', None, None, True, None, None), ('tokenStandard', 'tokenStandard', 'string', 'bech32-token-standard', None, True, None, None), ('amount', 'amount', 'decimal-string', 'base-10', None, True, None, None), ('signature', 'signature', 'string', None, None, True, None, None), ('redeemed', 'redeemed', 'number', None, None, True, None, None), ('revoked', 'revoked', 'number', None, None, True, None, None), ('redeemableIn', 'redeemableIn', 'number', None, None, True, None, None)), 'UnwrapTokenRequestList': (('count', 'count', 'number', None, None, True, None, None), ('list', 'list', 'array', None, 'UnwrapTokenRequest', True, None, None)), 'VoteBreakdown': (('id', 'id', 'string', 'hex-32', None, True, None, None), ('yes', 'yes', 'number', None, None, True, None, None), ('no', 'no', 'number', None, None, True, None, None), ('total', 'total', 'number', None, None, True, None, None)), 'WrapTokenRequest': (('networkClass', 'networkClass', 'number', None, None, True, None, None), ('chainId', 'chainId', 'number', None, None, True, None, None), ('id', 'id', 'string', 'hex-32', None, True, None, None), ('toAddress', 'toAddress', 'string', None, None, True, None, None), ('tokenStandard', 'tokenStandard', 'string', 'bech32-token-standard', None, True, None, None), ('tokenAddress', 'tokenAddress', 'string', None, None, True, None, None), ('amount', 'amount', 'decimal-string', 'base-10', None, True, None, None), ('fee', 'fee', 'decimal-string', 'base-10', None, True, None, None), ('signature', 'signature', 'string', None, None, True, None, None), ('creationMomentumHeight', 'creationMomentumHeight', 'number', None, None, True, None, None), ('confirmationsToFinality', 'confirmationsToFinality', 'number', None, None, True, None, None)), 'WrapTokenRequestList': (('count', 'count', 'number', None, None, True, None, None), ('list', 'list', 'array', None, 'WrapTokenRequest', True, None, None)), 'ZtsFeesInfo': (('tokenStandard', 'tokenStandard', 'string', 'bech32-token-standard', None, True, None, None), ('accumulatedFee', 'accumulatedFee', 'decimal-string', 'base-10', None, True, None, None))}


def wire_model_round_trip(name, value):
    """Validate a spec wire fixture without weakening strict runtime primitives.

    The corpus uses placeholder strings for model-specific binary fields and for
    AccountBlock nonce, so those schema-only fixtures cannot be constructed as
    valid runtime primitives. All declared keys and wire types are still checked.
    """
    fields = WIRE_SCHEMAS.get(name)
    if fields is None:
        raise ValueError(f"Unknown wire model {name!r}")
    if name == "AccountBlock":
        fields = WIRE_SCHEMAS["AccountBlockTemplate"] + fields
    if name in SPECIAL_MODEL_NAMES:
        wire_type = type(f"_{name}Wire", (Model,), {"_fields": fields})
        return wire_type.from_json(value, strict=True, nested_strict=False).to_json()
    return MODEL_TYPES[name].from_json(value, strict=True, nested_strict=False).to_json()


SPECIAL_MODEL_NAMES = frozenset({"AccountBlock", "Address", "Hash", "HashHeight", "TokenStandard"})
