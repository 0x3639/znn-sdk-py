import asyncio
import json
import urllib.error

import pytest

from znn.abi import ABI, ABIError
from znn.amount import from_base_units, to_base_units
from znn.api.embedded.plasma import PlasmaApi
from znn.api.embedded.accelerator import AcceleratorApi
from znn.api._response import parse_rpc_response
from znn.client.errors import TransportError
from znn.client.http import HttpClient
from znn.client.protocol import build_request, normalize_notification, subscription_params
from znn.client.websocket import Subscription, WsClient
from znn.model.models import (
    AccountBlockList, GetRequiredPowResponse, Model, Momentum, _decode_field,
    wire_model_round_trip,
)
from znn.model.nom.account_block import AccountBlock
from znn.model.primitives.address import Address
from znn.model.primitives.hash import Hash
from znn.model.primitives.hash_height import HashHeight
from znn.model.primitives.token_standard import TokenStandard
from znn.pow import generate, verify
from znn.sdk import Zenon
from znn.wallet.keystore import KeyStore


ADDRESS = "z1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqsggv2f"


def test_primitive_json_reconstructs_validated_instances():
    address = Address.parse(ADDRESS)
    assert Address.from_json(address.to_json()) == address
    assert str(Address.from_json(address.to_json())) == ADDRESS
    assert hash(Address.from_json(address.to_json())) == hash(address)

    value_hash = Hash(bytes(range(32)))
    assert Hash.from_json(value_hash.to_json()) == value_hash
    assert bytes(Hash.from_json(value_hash.to_json())) == bytes(value_hash)

    token = TokenStandard.from_core(bytes(range(10)))
    assert TokenStandard.from_json(token.to_json()) == token
    assert str(TokenStandard.from_json(token.to_json())) == str(token)

    with pytest.raises(ValueError):
        Address.from_json({"hrp": "z", "core": "fixture"})
    with pytest.raises(TypeError, match="bytes-like"):
        Address.from_core(20)
    with pytest.raises(TypeError, match="bytes-like"):
        Hash(32)
    with pytest.raises(TypeError, match="bytes-like"):
        TokenStandard.from_core(10)
    with pytest.raises(TypeError, match="bytes-like"):
        Address.from_public_key(32)
    with pytest.raises(ValueError, match="requires height"):
        HashHeight.from_json({})
    with pytest.raises(TypeError, match="must be an integer"):
        HashHeight.from_json({"hash": "0" * 64, "height": "1"})


def test_model_parser_is_field_aware_and_wire_keys_cannot_shadow_methods():
    with pytest.raises(ValueError, match="Missing required Momentum.version"):
        Momentum.from_json({})
    with pytest.raises(TypeError, match="version must be an integer"):
        wire_model_round_trip("Momentum", {"version": "bad"})

    hostile = Model.from_json({"_wire": {"evil": 1}, "to_json": "hostile"})
    assert hostile.to_json() == {"_wire": {"evil": 1}, "to_json": "hostile"}
    assert callable(hostile.to_json)


def test_abi_hash_rejects_integer_coercion():
    abi = ABI([{"type": "function", "name": "Probe", "inputs": [{"name": "h", "type": "hash"}]}])
    with pytest.raises(ABIError, match="hash requires"):
        abi.encode("Probe", [32])

    address_abi = ABI([{
        "type": "function", "name": "Probe", "inputs": [{"name": "a", "type": "address"}]
    }])
    with pytest.raises(ABIError):
        address_abi.encode("Probe", [object()])


def test_amount_and_pow_boundaries_reject_noncanonical_coercions():
    with pytest.raises(TypeError):
        to_base_units(True, 8)
    with pytest.raises(TypeError):
        to_base_units(1.5, 8)
    with pytest.raises(ValueError, match="finite"):
        to_base_units("NaN", 8)
    with pytest.raises(TypeError):
        from_base_units(True, 8)
    with pytest.raises(ValueError, match="lowercase"):
        verify("AA" * 32, 1, "00" * 8)
    with pytest.raises(ValueError, match="lowercase"):
        verify("aa" * 32, 1, "AA" * 8)
    with pytest.raises(TypeError, match="bytes-like"):
        generate("aa" * 32, 2, 8)


def test_account_block_hash_rejects_invalid_unsigned_fields_explicitly():
    block = AccountBlock()
    block.height = -1
    with pytest.raises(ValueError, match="unsigned 64-bit"):
        block.get_hash()


def test_sdk_lifecycle_rejects_invalid_policy_inputs():
    sdk = Zenon()
    with pytest.raises(ValueError, match="network_id"):
        sdk.set_network_id(True)
    with pytest.raises(ValueError, match="chain_id"):
        sdk.set_chain_id(-1)
    with pytest.raises(TypeError, match="callable"):
        sdk.set_pow_provider(None)

    async def scenario():
        with pytest.raises(ValueError, match="timeout"):
            await sdk.initialize("http://example.test", timeout=0)

    asyncio.run(scenario())


def test_entropy_import_matches_sdk_profile_sizes():
    assert len(KeyStore.from_entropy(bytes(16)).entropy) == 32
    assert len(KeyStore.from_entropy(bytes(32)).entropy) == 64
    with pytest.raises(ValueError, match="16 or 32 bytes"):
        KeyStore.from_entropy(bytes(20))


def test_api_client_constructs_declared_rpc_model():
    class Transport:
        async def send_request(self, method, params):
            assert method == "embedded.plasma.getRequiredPoWForAccountBlock"
            return {"availablePlasma": 1, "basePlasma": 2, "requiredDifficulty": 3}

    async def scenario():
        result = await PlasmaApi(Transport()).get_required_pow_for_account_block({})
        assert isinstance(result, GetRequiredPowResponse)
        assert result.requiredDifficulty == 3
        assert result.to_json()["requiredDifficulty"] == 3

    asyncio.run(scenario())


def test_rpc_account_block_response_enforces_and_decodes_extended_fields():
    value = AccountBlock().to_json()
    value.update({
        "descendantBlocks": [],
        "basePlasma": 1,
        "usedPlasma": 2,
        "changesHash": "0" * 64,
    })
    block = parse_rpc_response("ledger.getFrontierAccountBlock", value)
    assert isinstance(block, AccountBlock)
    assert isinstance(block._extra_fields["changesHash"], Hash)
    assert block.to_json() == value

    blocks = parse_rpc_response(
        "ledger.getAccountBlocksByPage",
        {"count": 1, "list": [value], "more": False},
    )
    assert isinstance(blocks, AccountBlockList)
    assert isinstance(blocks.list[0], AccountBlock)

    incomplete = dict(value)
    incomplete.pop("changesHash")
    with pytest.raises(ValueError, match="response fields"):
        parse_rpc_response("ledger.getFrontierAccountBlock", incomplete)


def test_accelerator_exposes_canonical_get_all_with_compatibility_alias():
    class Transport:
        async def send_request(self, method, params):
            assert method == "embedded.accelerator.getAll"
            assert params == [0, 1024]
            return {"count": 0, "list": []}

    async def scenario():
        api = AcceleratorApi(Transport())
        assert (await api.get_all()).count == 0
        assert (await api.get_account_blocks_by_page()).count == 0

    asyncio.run(scenario())


def test_protocol_rejects_invalid_request_and_subscription_shapes():
    with pytest.raises(TypeError, match="request ID"):
        build_request(True, "method", [])
    with pytest.raises(ValueError, match="requires an address"):
        subscription_params("accountBlocksByAddress")
    with pytest.raises(ValueError, match="does not accept"):
        subscription_params("momentums", ADDRESS)
    with pytest.raises(ValueError, match="Unknown subscription"):
        subscription_params("futureTopic")
    with pytest.raises(ValueError, match="Malformed"):
        normalize_notification({
            "method": "ledger.subscription",
            "params": {"subscription": 1, "result": []},
        })


def test_recovery_drains_notification_that_races_resubscribe_response():
    async def scenario():
        client = WsClient("ws://example.test", reconnect_interval=0)
        subscription = Subscription("sub-1", ["momentums"])
        client._subscriptions[subscription.id] = subscription

        async def connect():
            return client

        async def send_request(method, params):
            assert method == "ledger.subscribe"
            client._buffer_orphan_updates("sub-2", [{"height": 200}])
            return "sub-2"

        client.connect = connect
        client.send_request = send_request
        await client._recover(TransportError("closed"))
        assert subscription.id == "sub-2"
        assert await asyncio.wait_for(subscription.__anext__(), 0.1) == {"height": 200}
        assert client._orphan_updates == {}

    asyncio.run(scenario())


def test_recovery_retries_the_complete_subscription_set_and_closes_failed_socket():
    class Socket:
        def __init__(self):
            self.closed = False

        async def close(self):
            self.closed = True

    async def scenario():
        client = WsClient(
            "ws://example.test", reconnect_interval=0, maximum_attempts=2
        )
        first = Subscription("old-a", ["momentums"])
        second = Subscription("old-b", ["allAccountBlocks"])
        client._subscriptions = {first.id: first, second.id: second}
        sockets = []
        calls = []

        async def connect():
            socket = Socket()
            sockets.append(socket)
            client._socket = socket
            return client

        async def send_request(method, params):
            assert method == "ledger.subscribe"
            calls.append(tuple(params))
            attempt = len(sockets)
            if attempt == 1 and params == second.params:
                raise TransportError("transient resubscribe failure")
            return f"attempt-{attempt}-{len(calls)}"

        client.connect = connect
        client.send_request = send_request
        await client._recover(TransportError("closed"))

        assert calls == [
            ("momentums",),
            ("allAccountBlocks",),
            ("momentums",),
            ("allAccountBlocks",),
        ]
        assert sockets[0].closed is True
        assert sockets[1].closed is False
        assert set(client._subscriptions.values()) == {first, second}

    asyncio.run(scenario())


def test_permanent_recovery_failure_terminates_subscription_consumers():
    class Socket:
        closed = False

        async def close(self):
            self.closed = True

    async def scenario():
        client = WsClient(
            "ws://example.test", reconnect_interval=0, maximum_attempts=1
        )
        subscription = Subscription("old", ["momentums"])
        client._subscriptions[subscription.id] = subscription
        socket = Socket()

        async def connect():
            client._socket = socket
            return client

        async def send_request(_method, _params):
            raise TransportError("permanent resubscribe failure")

        client.connect = connect
        client.send_request = send_request
        await client._recover(TransportError("closed"))

        assert socket.closed is True
        with pytest.raises(TransportError, match="recovery failed"):
            await asyncio.wait_for(subscription.__anext__(), 0.1)
        with pytest.raises(TransportError, match="recovery failed"):
            await asyncio.wait_for(subscription.__anext__(), 0.1)

    asyncio.run(scenario())


def test_stale_listener_cannot_schedule_recovery_for_healthy_socket():
    async def scenario():
        client = WsClient("ws://example.test", reconnect_interval=0)
        healthy_socket = object()
        stale_socket = object()
        client._socket = healthy_socket

        assert client._schedule_recovery(TransportError("stale"), stale_socket) is None
        assert client._recovery_task is None

    asyncio.run(scenario())


def test_generated_models_accept_unpadded_standard_base64():
    field = ("data", "data", "string", "base64", None, True, None, None)
    assert _decode_field(field, "SGVsbG8", strict=True) == b"Hello"
    with pytest.raises(ValueError, match="base64"):
        _decode_field(field, "AA-_", strict=True)


def test_clean_websocket_close_fails_pending_request_without_reconnect():
    class ClosedSocket:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    async def scenario():
        client = WsClient("ws://example.test", reconnect=False)
        client._socket = ClosedSocket()
        future = asyncio.get_running_loop().create_future()
        client._pending[1] = future
        await client._listen()
        with pytest.raises(TransportError, match="WebSocket closed"):
            await future
        assert client._pending == {}

    asyncio.run(scenario())


def test_disconnect_cancels_recovery_without_resurrecting_socket():
    async def scenario():
        client = WsClient("ws://example.test", reconnect_interval=0.1)
        connect_calls = 0

        async def connect():
            nonlocal connect_calls
            connect_calls += 1
            return client

        client.connect = connect
        recovery = client._schedule_recovery(TransportError("closed"))
        await asyncio.sleep(0)
        await client.disconnect()
        with pytest.raises(asyncio.CancelledError):
            await recovery
        assert connect_calls == 0
        assert client._closed is True
        assert client._socket is None

    asyncio.run(scenario())


def test_websocket_send_failure_is_normalized_and_does_not_leak_pending_future():
    class BrokenSocket:
        closed = False

        async def send(self, _message):
            raise RuntimeError("socket gone")

    async def scenario():
        client = WsClient("ws://example.test", reconnect=False)
        client._socket = BrokenSocket()

        async def connect():
            return client

        client.connect = connect
        with pytest.raises(TransportError, match="WebSocket send failed"):
            await client.send_request("ledger.getFrontierMomentum", [])
        assert client._pending == {}

    asyncio.run(scenario())


def test_websocket_connection_failure_is_normalized(monkeypatch):
    async def unavailable(*_args, **_kwargs):
        raise OSError("offline")

    async def scenario():
        monkeypatch.setattr("websockets.connect", unavailable)
        client = WsClient("ws://example.test")
        with pytest.raises(TransportError, match="WebSocket connection failed"):
            await client.connect()

    asyncio.run(scenario())


def test_orphan_subscription_buffers_are_bounded():
    client = WsClient("ws://example.test")
    client._buffer_orphan_updates("sub", list(range(client._MAX_ORPHAN_UPDATES + 5)))
    assert len(client._orphan_updates["sub"]) == client._MAX_ORPHAN_UPDATES
    for index in range(client._MAX_ORPHAN_SUBSCRIPTIONS + 5):
        client._buffer_orphan_updates(f"unknown-{index}", [index])
    assert len(client._orphan_updates) == client._MAX_ORPHAN_SUBSCRIPTIONS


def test_http_failures_and_invalid_json_rpc_responses_are_normalized(monkeypatch):
    client = HttpClient("http://example.test")

    def unavailable(*_args, **_kwargs):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr("urllib.request.urlopen", unavailable)
    with pytest.raises(TransportError, match="HTTP JSON-RPC request failed"):
        client._send("ledger.getFrontierMomentum", [])

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return json.dumps({"jsonrpc": "2.0", "id": 999, "result": None}).encode()

    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: Response())
    with pytest.raises(TransportError, match="response ID"):
        client._send("ledger.getFrontierMomentum", [])
