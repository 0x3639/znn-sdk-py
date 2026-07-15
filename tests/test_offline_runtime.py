import asyncio
import importlib
import inspect
import io
import json
import os
from pathlib import Path

import pytest
from nacl.encoding import RawEncoder

from znn.abi import ABI, ABIError
from znn.abi import utils as abi_utils
from znn.amount import from_base_units, to_base_units
from znn.api._response import parse_rpc_response
from znn.api.client import ApiClient, get_api_client
from znn.api.embedded.plasma import PlasmaApi
from znn.api.embedded.token import TokenApi
from znn.api.subscribe import SubscribeApi
from znn.client.errors import JsonRpcError, TransportError
from znn.client.http import HttpClient
from znn.client.protocol import build_request, normalize_notification, rpc_error
from znn.client.websocket import Subscription, WsClient, get_default_client
from znn.model.models import (
    AcceleratorProjectStatus,
    MODEL_TYPES, Model,
    _decode_field,
    _decode_target,
    _default_value,
    _encode_field,
    _encode_target,
    _get_path,
    _set_path,
)
from znn.model.nom.account_block import AccountBlock
from znn.model.primitives.address import Address, EMPTY_ADDRESS
from znn.model.primitives.hash import EMPTY_HASH, Hash
from znn.model.primitives.hash_height import EMPTY_HASH_HEIGHT, HashHeight
from znn.model.primitives.token_standard import EMPTY_ZTS, TokenStandard
from znn.pow import account_block_data_hash, generate, verify
from znn.sdk import Zenon
from znn.wallet.keypair import KeyPair
from znn.wallet.keystore import KeyStore
from znn.wallet.utils import from_ascii, remove_prefix, to_ascii


PRIVATE_KEY = "f58cb2e1add0382c2004fa8e04895a65a3c755553e60187d697c2e5ab9df67ea"


class RecordingClient(ApiClient):
    def __init__(self):
        self.calls = []

    async def send_request(self, method, params):
        self.calls.append((method, params))
        return None

    async def send_and_listen(self, method, params):
        self.calls.append((method, params))
        return "subscription"


def _spec_root():
    configured = os.environ.get("ZNN_SPEC_ROOT")
    return (
        Path(configured)
        if configured
        else Path(__file__).resolve().parents[2] / "zenon-sdk-spec"
    )


def _argument(parameter):
    name = parameter.name
    if name in {"account_block", "block"}:
        return AccountBlock()
    if name in {"zts", "token_standard"}:
        return EMPTY_ZTS
    if name in {"id", "tx_hash"}:
        return EMPTY_HASH
    if name == "hashes":
        return []
    if name == "pow_param":
        return {}
    if name == "topic":
        return "momentums"
    if name in {
        "network_class", "chain_id", "log_index", "time", "height", "count",
        "epoch",
    }:
        return 1
    if "address" in name:
        return EMPTY_ADDRESS
    if "hash" in name:
        return str(EMPTY_HASH)
    return "fixture"


def test_every_rpc_facade_dispatches_the_spec_wire_method_offline():
    root = _spec_root()
    if not root.exists():
        pytest.skip("stable specification checkout is not available")
    manifest = json.loads(Path("conformance/manifest.json").read_text())
    methods = json.loads((root / "spec/rpc.json").read_text())["methods"]

    async def scenario():
        checked = 0
        for record in methods:
            symbol = manifest["capabilities"][record["id"]]["symbol"]
            module_name, class_name, method_name = symbol.rsplit(".", 2)
            if class_name == "WsClient":
                continue
            cls = getattr(importlib.import_module(module_name), class_name)
            client = RecordingClient()
            method = getattr(cls(client), method_name)
            arguments = [
                _argument(parameter)
                for parameter in inspect.signature(method).parameters.values()
                if parameter.default is inspect.Parameter.empty
            ]
            await method(*arguments)
            assert client.calls[-1][0] == record["wireMethod"]
            checked += 1
        assert checked == 75

    asyncio.run(scenario())


def test_subscription_facade_convenience_methods_and_client_adapter():
    async def scenario():
        client = RecordingClient()
        api = SubscribeApi(client)
        assert await api.subscribe_to("momentums") == "subscription"
        await api.subscribe_to("accountBlocksByAddress", "z")
        await api.to_momentums()
        await api.to_all_account_blocks()
        await api.to_account_blocks_by_address("z")
        await api.to_unreceived_account_blocks_by_address("z")
        assert [params for _, params in client.calls] == [
            ["momentums"],
            ["accountBlocksByAddress", "z"],
            ["momentums"],
            ["allAccountBlocks"],
            ["accountBlocksByAddress", "z"],
            ["unreceivedAccountBlocksByAddress", "z"],
        ]

        class Transport:
            marker = "delegated"

            async def send_request(self, method, params):
                assert (method, params) == ("embedded.pillar.getDepositedQsr", [])
                return "12"

        adapter = get_api_client(Transport())
        assert await adapter.send_request("embedded.pillar.getDepositedQsr", []) == 12
        assert adapter.marker == "delegated"
        assert get_api_client(adapter) is adapter
        assert get_api_client().transport is get_default_client()

    asyncio.run(scenario())


def test_rpc_response_routing_accepts_and_rejects_each_scalar_shape():
    marker = object()
    assert parse_rpc_response("future.method", marker) is marker
    assert parse_rpc_response("embedded.pillar.getQsrRegistrationCost", "42") == 42
    assert parse_rpc_response("embedded.htlc.getProxyUnlockStatus", True) is True
    assert parse_rpc_response("embedded.pillar.getByOwner", []) == []
    assert parse_rpc_response("ledger.subscribe", "sub") == "sub"
    assert parse_rpc_response("ledger.getMomentumByHash", None) is None
    assert parse_rpc_response("ledger.publishRawTransaction", None) is None

    with pytest.raises(ValueError, match="non-nullable"):
        parse_rpc_response("stats.osInfo", None)
    with pytest.raises(ValueError, match="decimal"):
        parse_rpc_response("embedded.pillar.getQsrRegistrationCost", "01")
    with pytest.raises(TypeError, match="boolean"):
        parse_rpc_response("embedded.htlc.getProxyUnlockStatus", 1)
    with pytest.raises(TypeError, match="array"):
        parse_rpc_response("embedded.pillar.getByOwner", {})
    for value in (1, ""):
        with pytest.raises(TypeError, match="subscription ID"):
            parse_rpc_response("ledger.subscribe", value)
    with pytest.raises(TypeError, match="must return null"):
        parse_rpc_response("ledger.publishRawTransaction", "published")


def test_generated_model_runtime_helpers_cover_nested_and_root_shapes():
    assert _get_path({"a": {"b": 1}}, "a.b") == 1
    assert _get_path({"a": 1}, "a.b") is not None
    assert _get_path("root", "") == "root"
    assert _set_path({}, "", 3) == 3
    assert _set_path({}, "a.b", 3) == {"a": {"b": 3}}
    assert [_default_value(value) for value in ("0", "{}", "[]", "false", "true", "-2n")] == [
        0, {}, [], False, True, -2,
    ]
    assert _default_value("unknown") is not None

    address = Address.from_core(bytes(range(20)))
    token = TokenStandard.from_core(bytes(range(10)))
    height = HashHeight(EMPTY_HASH, 2)
    assert _decode_target("Address", str(address), True) == address
    assert _decode_target("Address", address.to_json(), True) == address
    assert _decode_target("Hash", str(EMPTY_HASH), True) == EMPTY_HASH
    assert _decode_target("Hash", EMPTY_HASH.to_json(), True) == EMPTY_HASH
    assert _decode_target("HashHeight", height.to_json(), True).height == 2
    assert _decode_target("TokenStandard", str(token), True) == token
    assert _decode_target("TokenStandard", token.to_json(), True) == token
    assert _decode_target("AcceleratorProjectStatus", 1, True) is AcceleratorProjectStatus.active
    assert _decode_target("Address", {}, False) == {}
    with pytest.raises(ValueError, match="Unknown nested model"):
        _decode_target("FutureModel", {}, True)
    MODEL_TYPES["CoverageModel"] = Model
    try:
        assert isinstance(_decode_target("CoverageModel", {}, True), Model)
    finally:
        MODEL_TYPES.pop("CoverageModel")

    assert _encode_target(address) == str(address)
    assert _encode_target(height) == height.to_json()
    assert _encode_target(AcceleratorProjectStatus.active) == 1

    class Sample(Model):
        _fields = (
            ("amount", "nested.amount", "decimal-string", "base-10", None, True, None, None),
            ("enabled", "enabled", "boolean", None, None, False, "true", None),
            ("metadata", "metadata", "object", None, None, False, "{}", None),
        )

    sample = Sample.from_json({"nested": {"amount": "7"}})
    assert dict(sample) == {"amount": 7, "enabled": True, "metadata": {}}
    assert sample["amount"] == 7
    assert sample["nested.amount"] == 7
    assert len(sample) == 3
    assert "Sample" in repr(sample)
    sample.enabled = False
    sample._wire = sample._wire
    assert sample.to_json() == {
        "nested": {"amount": "7"}, "enabled": False, "metadata": {},
    }
    assert sample == Sample.from_json(sample.to_json())
    assert sample != Model()
    with pytest.raises(AttributeError):
        _ = sample.missing
    with pytest.raises(AttributeError):
        sample.unknown = 1
    with pytest.raises(KeyError):
        _ = sample["unknown"]
    with pytest.raises(TypeError, match="Unknown Sample fields"):
        Sample(unknown=1)
    with pytest.raises(TypeError, match="must be an object"):
        Sample.from_json([])
    assert Sample.from_json({}, strict=False).to_json() == {
        "enabled": True, "metadata": {},
    }

    invalid_fields = [
        (("value", "value", "decimal-string", None, None, True, None, None), None, ValueError),
        (("value", "value", "decimal-string", None, None, True, None, None), "01", ValueError),
        (("value", "value", "number", None, None, True, None, None), True, TypeError),
        (("value", "value", "boolean", None, None, True, None, None), 1, TypeError),
        (("value", "value", "string", None, None, True, None, None), 1, TypeError),
        (("value", "value", "array", None, "Hash", True, None, None), {}, TypeError),
        (("value", "value", "object", None, None, True, None, None), [], TypeError),
        (("value", "value", "future", None, None, True, None, None), 1, ValueError),
    ]
    for field, value, error in invalid_fields:
        with pytest.raises(error):
            _decode_field(field, value, True)
    object_field = ("value", "value", "object", None, None, True, None, "Hash")
    assert _decode_field(object_field, {"h": str(EMPTY_HASH)}, True) == {
        "h": EMPTY_HASH,
    }
    assert _encode_field(object_field, {"h": EMPTY_HASH}) == {
        "h": str(EMPTY_HASH),
    }
    assert _encode_target(Model()) == {}

    class RootHashes(Model):
        _fields = (("items", "", "array", None, "Hash", False, "[]", None),)

    root = RootHashes.from_json([str(EMPTY_HASH)])
    assert root.to_json() == [str(EMPTY_HASH)]
    with pytest.raises(TypeError, match="must be an array"):
        RootHashes.from_json({})


def test_abi_edge_shapes_and_legacy_registry_helpers():
    definition = [{
        "type": "function",
        "name": "Probe",
        "inputs": [
            {"name": "hashes", "type": "hash[1]"},
            {"name": "payload", "type": "bytes2"},
            {"name": "owner", "type": "address"},
            {"name": "zts", "type": "tokenStandard"},
        ],
    }]
    abi = ABI.from_json(json.dumps(definition))
    encoded = abi.encode(
        "Probe", [[EMPTY_HASH], b"ab", EMPTY_ADDRESS, EMPTY_ZTS]
    )
    assert abi.functions()[0]["name"] == "Probe"
    decoded = abi.decode_call_data(encoded)
    assert decoded[0] == "Probe"
    assert decoded[1]["hashes"] == [f"0x{EMPTY_HASH}"]
    assert decoded[1]["owner"] == str(EMPTY_ADDRESS)
    assert decoded[1]["zts"] == str(EMPTY_ZTS)

    with pytest.raises(ABIError, match="not found"):
        abi.encode("Missing", [])
    with pytest.raises(ABIError, match="Expected 4"):
        abi.encode("Probe", [])
    with pytest.raises(ABIError, match="array"):
        abi.encode("Probe", [EMPTY_HASH, b"ab", EMPTY_ADDRESS, EMPTY_ZTS])
    with pytest.raises(ABIError, match="exactly 1"):
        abi.encode("Probe", [[], b"ab", EMPTY_ADDRESS, EMPTY_ZTS])
    with pytest.raises(ABIError, match="exactly 2 bytes"):
        abi.encode("Probe", [[EMPTY_HASH], b"a", EMPTY_ADDRESS, EMPTY_ZTS])
    with pytest.raises(ABIError, match="Unknown function selector"):
        abi.decode_call_data(b"xxxx")
    with pytest.raises(ABIError, match="not found"):
        abi.decode("Missing", encoded)
    with pytest.raises(ABIError):
        abi.decode("Probe", b"bad")

    assert abi_utils.is_recognized_type("uint256[]")
    assert abi_utils.is_probably_enum("Library.Value")
    normalized = abi_utils.normalize_event_input_types([
        {"name": "a", "type": "uint8"},
        {"name": "b", "type": "Library.Value"},
        {"name": "c", "type": "custom"},
    ])
    assert [item["type"] for item in normalized] == ["uint8", "uint8", "custom"]

    legacy = importlib.import_module("znn.abi.registry")
    assert legacy.encode_hash(EMPTY_HASH) == bytes(32)
    assert legacy.encode_hash("0x" + "11" * 32) == bytes.fromhex("11" * 32)
    assert legacy.encode_hash("22" * 32) == bytes.fromhex("22" * 32)
    marker = object()
    assert legacy.encode_hash(marker) is marker
    assert legacy.decode_hash(io.BytesIO(bytes.fromhex("33" * 32))) == "0x" + "33" * 32
    assert len(legacy.encode_token_standard(EMPTY_ZTS)) == 32
    assert len(legacy.encode_token_standard(str(EMPTY_ZTS))) == 32
    assert legacy.decode_token_standard(io.BytesIO(bytes(32))) == "0" * 20
    assert len(legacy.encode_address(EMPTY_ADDRESS)) == 32
    assert len(legacy.encode_address(str(EMPTY_ADDRESS))) == 32
    assert legacy.decode_address(io.BytesIO(bytes(32))) == "0" * 40
    isolated = ABI([{
        "type": "function", "name": "AddressProbe",
        "inputs": [{"name": "address", "type": "address"}],
    }])
    assert isolated.encode("AddressProbe", [EMPTY_ADDRESS])
    constants = importlib.import_module("znn.embedded.constants")
    assert constants.PROJECT_DESC_MAX_LEN == 240


def test_primitives_pow_keypair_keystore_and_legacy_encoding_boundaries(monkeypatch):
    address = Address.from_core(bytes(range(20)))
    assert Address.from_hex(address.core_to_hex) == address
    assert Address.from_public_key(bytes(32)) == Address.from_public_key_hex("00" * 32)
    assert address.to_bytes() == bytes(address)
    assert address != object()
    for args, error in [
        (("x", bytes(20)), ValueError),
        (("z", bytes(19)), ValueError),
        (("z", 20), TypeError),
    ]:
        with pytest.raises(error):
            Address(*args)
    with pytest.raises(ValueError, match="32 bytes"):
        Address.from_public_key_hex("00")
    with pytest.raises(ValueError):
        Address.parse("not-an-address")
    with pytest.raises(TypeError):
        Address.from_json("not-json")
    for core in ("A" * 40, "g" * 40):
        with pytest.raises(ValueError):
            Address.from_json({"hrp": "z", "core": core})

    token = TokenStandard.from_core(bytes(range(10)))
    assert TokenStandard.from_hex(token.core_to_hex) == token
    assert token.to_bytes() == bytes(token)
    assert token != object()
    with pytest.raises(ValueError):
        TokenStandard.parse("invalid")
    with pytest.raises(TypeError):
        TokenStandard.from_json([])
    for core in ("A" * 20, "g" * 20, "00"):
        with pytest.raises(ValueError):
            TokenStandard.from_json({"core": core})

    assert Hash.id("probe").startswith("0x")
    assert EMPTY_HASH.to_bytes() == bytes(EMPTY_HASH)
    assert EMPTY_HASH != object()
    with pytest.raises(ValueError):
        Hash.parse("00")
    with pytest.raises(ValueError):
        Hash.parse("G" * 64)
    with pytest.raises(TypeError):
        Hash.from_json("bad")
    with pytest.raises(ValueError):
        Hash(bytes(31))

    assert bytes(EMPTY_HASH_HEIGHT) == bytes(40)
    assert str(EMPTY_HASH_HEIGHT) == "0" * 80
    assert HashHeight.from_json(None, strict=False) is EMPTY_HASH_HEIGHT
    with pytest.raises(TypeError):
        HashHeight("hash", 1)
    with pytest.raises(TypeError):
        HashHeight(EMPTY_HASH, True)
    with pytest.raises(ValueError):
        HashHeight(EMPTY_HASH, -1)
    with pytest.raises(TypeError):
        HashHeight.from_json([])

    assert verify("00" * 32, 0, "00" * 8)
    assert not verify("00" * 32, 0, "01" + "00" * 7)
    monkeypatch.setattr("znn.pow.secrets.token_bytes", lambda size: bytes(size))
    assert generate("00" * 32, 1) == "00" * 8
    with pytest.raises(ValueError, match="hexadecimal"):
        verify("g" * 64, 1, "00" * 8)
    with pytest.raises(ValueError, match="difficulty"):
        verify("00" * 32, -1, "00" * 8)
    with pytest.raises(ValueError, match="nonce"):
        verify("00" * 32, 1, "00")
    with pytest.raises(ValueError, match="starting nonce"):
        generate("00" * 32, 1, b"short")
    with pytest.raises(ValueError, match="20-byte"):
        account_block_data_hash(bytes(19), bytes(32))

    pair = KeyPair(bytes.fromhex(PRIVATE_KEY))
    assert pair.public_key_bytes == bytes.fromhex(pair.public_key)
    assert len(pair.sign(EMPTY_HASH)) == 64
    assert len(pair.sign(b"bytes", RawEncoder)) == 64
    with pytest.raises(TypeError):
        pair.sign(1)
    with pytest.raises(ValueError, match="32 bytes"):
        pair.sign_hash(b"short")
    pair.clear()
    assert pair.private_key == pair.public_key == ""
    assert pair.signing_key is None

    store = KeyStore.from_entropy(bytes(16))
    assert KeyStore.from_mnemonic(store.mnemonic).entropy == store.entropy
    with pytest.raises(ValueError, match="non-negative"):
        store.get_key_pair(True)
    store.clear()
    assert store.mnemonic == store.seed == store.entropy == ""

    for encoding in ("base64", "base32", "base16", "hex"):
        encoded = to_ascii(b"hello", b"p", encoding)
        assert from_ascii(encoded, b"p", encoding) == b"hello"
    assert remove_prefix("prefix-value", "prefix-") == "value"
    with pytest.raises(ValueError, match="expected"):
        remove_prefix("value", "prefix-")
    with pytest.raises(NotImplementedError):
        to_ascii(b"hello", encoding="future")
    with pytest.raises(NotImplementedError):
        from_ascii("hello", encoding="future")


def test_sdk_lifecycle_and_delegation_without_network(monkeypatch):
    class FakeWs:
        def __init__(self, url, connect_timeout, **options):
            self.url = url
            self.timeout = connect_timeout
            self.options = options
            self.connected = False
            self.disconnected = False

        async def connect(self):
            self.connected = True

        async def disconnect(self):
            self.disconnected = True

    class FakeTransact:
        instances = []

        def __init__(self, private_key, ledger, plasma, provider):
            self.private_key = private_key
            self.provider = provider
            self.instances.append(self)

        async def prepare_block(self, block):
            return ("prepared", block)

        async def fast_forward_block(self, block):
            return ("sent", block)

    async def scenario():
        sdk = Zenon()
        await sdk.initialize("http://example.test", timeout=2)
        assert isinstance(sdk.client, HttpClient)
        await sdk.disconnect()
        assert sdk.client is None

        monkeypatch.setattr("znn.sdk.WsClient", FakeWs)
        await sdk.initialize("ws://example.test", timeout=3, reconnect=False)
        websocket = sdk.client
        assert websocket.connected and websocket.options == {"reconnect": False}
        await sdk.disconnect()
        assert websocket.disconnected

        sdk.set_network_id(2)
        sdk.set_chain_id(3)
        assert sdk.get_network_id() == 2
        assert sdk.get_chain_id() == 3
        provider = lambda *_args: "00" * 8
        sdk.set_pow_provider(provider)
        assert sdk.pow_provider is provider
        sdk.clear_pow_provider()
        assert sdk.pow_provider is None
        with pytest.raises(RuntimeError, match="not initialized"):
            sdk._transact(PRIVATE_KEY)

        monkeypatch.setattr("znn.sdk.Transact", FakeTransact)
        sdk.client = object()
        sdk.set_pow_provider(provider)
        block = AccountBlock()
        assert await sdk.prepare_block(block, PRIVATE_KEY) == ("prepared", block)
        assert block.chain_identifier == 3
        assert await sdk.send(block, PRIVATE_KEY) == ("sent", block)
        assert FakeTransact.instances[-1].provider is provider

    asyncio.run(scenario())


def test_protocol_and_error_serialization_additional_boundaries():
    assert build_request(1, "method", []) == {
        "jsonrpc": "2.0", "id": 1, "method": "method", "params": [],
    }
    for method in ("", 1):
        with pytest.raises(TypeError, match="method"):
            build_request(1, method, [])
    with pytest.raises(TypeError, match="positional"):
        build_request(1, "method", ())
    with pytest.raises(ValueError, match="Not a ledger"):
        normalize_notification({"method": "other"})

    error = rpc_error({}, "method", [1])
    assert isinstance(error, JsonRpcError)
    assert error.to_json() == {
        "code": -1,
        "message": "Unknown error occurred",
        "data": None,
        "method": "method",
        "parameters": [1],
    }
    direct = JsonRpcError("2", "bad")
    assert direct.code == 2 and direct.parameters == []


def test_http_constructor_and_disconnect_additional_boundaries():
    for timeout in (0, True, "1"):
        with pytest.raises(ValueError, match="timeout"):
            HttpClient("http://example.test", timeout)

    async def scenario():
        client = HttpClient("https://example.test")
        assert await client.disconnect() is None

    asyncio.run(scenario())


def test_compatibility_aliases_and_removed_rpc_are_explicit():
    async def scenario():
        client = RecordingClient()
        token = TokenApi(client)
        await token.get_by_owner_address(EMPTY_ADDRESS)
        assert client.calls[-1][0] == "embedded.token.getByOwner"

        plasma = PlasmaApi(client)
        assert plasma.get_plasma_by_qsr("2") == 4200
        with pytest.warns(DeprecationWarning, match="removed"):
            with pytest.raises(NotImplementedError, match="does not expose"):
                await plasma.get_required_fusion_amount(1)

    asyncio.run(scenario())


def test_amount_conversion_additional_boundaries():
    assert to_base_units("1.239", 2) == 123
    assert from_base_units(-120, 2) == "-1.2"
    assert from_base_units(12, 0) == "12"
    assert from_base_units(100, 2) == "1"
    for decimals in (-1, True, "2"):
        with pytest.raises(ValueError, match="decimals"):
            to_base_units("1", decimals)
        with pytest.raises(ValueError, match="decimals"):
            from_base_units(1, decimals)
    with pytest.raises(ValueError):
        to_base_units("not-a-number", 2)
    with pytest.raises(ValueError):
        from_base_units("not-an-integer", 2)


def test_websocket_protocol_and_lifecycle_failure_matrix():
    class Frames:
        closed = False

        def __init__(self, frames=()):
            self.frames = iter(frames)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self.frames)
            except StopIteration:
                raise StopAsyncIteration

        async def close(self):
            self.closed = True

    async def scenario():
        with pytest.raises(TransportError, match="No default"):
            await WsClient().connect()
        for kwargs, message in [
            ({"reconnect": 1}, "boolean"),
            ({"reconnect_interval": -1}, "non-negative"),
            ({"maximum_attempts": True}, "non-negative integer"),
            ({"connect_timeout": 0}, "positive"),
        ]:
            with pytest.raises((TypeError, ValueError), match=message):
                WsClient("ws://example.test", **kwargs)

        client = WsClient("ws://example.test", reconnect=False)
        socket = Frames([
            json.dumps({
                "jsonrpc": "2.0",
                "method": "ledger.subscription",
                "params": {"subscription": "sub", "result": [{"height": 1}]},
            }),
            json.dumps({"jsonrpc": "2.0", "id": 1, "result": "ok"}),
        ])
        subscription = Subscription("sub", ["momentums"])
        future = asyncio.get_running_loop().create_future()
        client._socket = socket
        client._subscriptions["sub"] = subscription
        client._pending[1] = future
        await client._listen()
        assert await subscription.__anext__() == {"height": 1}
        assert await future == {"jsonrpc": "2.0", "id": 1, "result": "ok"}
        with pytest.raises(TransportError, match="closed"):
            await subscription.__anext__()
        assert subscription.__aiter__() is subscription

        for frame in (
            json.dumps([]),
            json.dumps({"jsonrpc": "1.0", "id": 1}),
            json.dumps({"jsonrpc": "2.0", "id": "1"}),
        ):
            invalid = WsClient("ws://example.test", reconnect=False)
            invalid._socket = Frames([frame])
            waiter = Subscription("sub", ["momentums"])
            invalid._subscriptions["sub"] = waiter
            await invalid._listen()
            with pytest.raises(TransportError):
                await waiter.__anext__()

        scheduled = []
        reconnecting = WsClient("ws://example.test")
        reconnecting._socket = Frames()
        reconnecting._schedule_recovery = (
            lambda cause, socket=None: scheduled.append((cause, socket))
        )
        await reconnecting._listen()
        assert len(scheduled) == 1
        reconnecting._socket = Frames(["not-json"])
        await reconnecting._listen()
        assert len(scheduled) == 2

        class BadClose:
            async def close(self):
                raise OSError("already gone")

        await client._discard_socket(None)
        await client._discard_socket(BadClose())

        invalid_subscription = WsClient("ws://example.test")

        async def invalid_id(*_args):
            return ""

        invalid_subscription.send_request = invalid_id
        with pytest.raises(TransportError, match="invalid subscription"):
            await invalid_subscription.subscribe("momentums")

        orphan_client = WsClient("ws://example.test")
        orphan_client._buffer_orphan_updates("new", [{"height": 2}])

        async def valid_id(*_args):
            return "new"

        orphan_client.send_request = valid_id
        restored = await orphan_client.subscribe("momentums")
        assert await restored.__anext__() == {"height": 2}

        direct = WsClient("ws://example.test")

        async def direct_request(method, params):
            return (method, params)

        direct.send_request = direct_request
        assert await direct.send_and_listen("method", [1]) == ("method", [1])

        subscribed = []

        async def subscribe(topic, address=None):
            subscribed.append((topic, address))
            return "subscription"

        direct.subscribe = subscribe
        assert await direct.send_and_listen("ledger.subscribe", ["momentums"]) == "subscription"
        assert await direct.send_and_listen(
            "ledger.subscribe", ["accountBlocksByAddress", "z"]
        ) == "subscription"
        assert subscribed == [("momentums", None), ("accountBlocksByAddress", "z")]

        class ErrorSocket:
            closed = False

            async def send(self, payload):
                request_id = json.loads(payload)["id"]
                direct._pending[request_id].set_result({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": 9, "message": "rejected"},
                })

        async def connected():
            return direct

        direct.connect = connected
        direct._socket = ErrorSocket()
        direct.send_request = WsClient.send_request.__get__(direct)
        with pytest.raises(JsonRpcError, match="rejected") as caught:
            await direct.send_request("method", [])
        assert caught.value.code == 9

        existing = WsClient("ws://example.test")
        existing._socket = ErrorSocket()
        assert await existing.connect() is existing

        queued = WsClient(
            "ws://example.test", reconnect_interval=1, maximum_attempts=1
        )
        recovery = queued._schedule_recovery(TransportError("first"))
        assert queued._schedule_recovery(TransportError("second")) is recovery
        assert queued._queued_recovery[0].args[0] == "second"
        queued._closed = True
        recovery.cancel()
        with pytest.raises(asyncio.CancelledError):
            await recovery

        invalid_recovery = WsClient(
            "ws://example.test", reconnect_interval=0, maximum_attempts=1
        )

        async def connected_without_listener():
            invalid_recovery._socket = Frames()
            return invalid_recovery

        async def invalid_resubscribe(*_args):
            return ""

        invalid_recovery.connect = connected_without_listener
        invalid_recovery.send_request = invalid_resubscribe
        invalid_recovery._subscriptions["old"] = Subscription("old", ["momentums"])
        await invalid_recovery._recover(TransportError("closed"))
        assert invalid_recovery._subscriptions == {}

    asyncio.run(scenario())
