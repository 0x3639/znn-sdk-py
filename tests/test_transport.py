import asyncio
import sys
from pathlib import Path

import pytest

from znn.client.errors import JsonRpcError
from znn.client.http import HttpClient
from znn.client.protocol import build_request, normalize_notification, rpc_error, subscription_params
from znn.client.websocket import WsClient


def test_transport_protocol_values_and_errors():
    assert build_request(7, "method", [1]) == {
        "jsonrpc": "2.0", "id": 7, "method": "method", "params": [1]
    }
    assert subscription_params("accountBlocksByAddress", "z") == ["accountBlocksByAddress", "z"]
    assert normalize_notification({"method": "ledger.subscription", "params": {
        "subscription": "sub-1", "result": [{"height": 42}]
    }}) == {"subscriptionId": "sub-1", "updates": [{"height": 42}]}
    error = rpc_error({"code": -32000, "message": "bad", "data": {"x": 1}}, "method", [1])
    assert isinstance(error, JsonRpcError)
    assert error.to_json() == {"code": -32000, "message": "bad", "data": {"x": 1},
                               "method": "method", "parameters": [1]}


def test_transport_rejects_schemes_and_has_no_third_party_default():
    with pytest.raises(ValueError):
        WsClient("ftp://example.test")
    assert WsClient().url is None


def test_offline_http_websocket_transcript():
    spec = Path(__file__).resolve().parents[2] / "znn-ts-sdk-spec"
    if not spec.exists():
        pytest.skip("stable transport fixture is not available")
    sys.path.insert(0, str(spec / "tools"))
    from transport_fixture import ADDRESS, TransportFixture

    async def scenario():
        try:
            fixture = TransportFixture()
        except PermissionError:
            pytest.skip("sandbox does not permit binding localhost ports")
        fixture.start()
        try:
            http = HttpClient(fixture.http_url)
            assert await http.send_request("ledger.getAccountBlocksByPage", [ADDRESS, 0, 25]) == {"count": 0, "list": []}
            assert await http.send_request("ledger.publishRawTransaction", [{}]) is None
            with pytest.raises(JsonRpcError) as caught:
                await http.send_request("ledger.getFrontierMomentum", [])
            assert caught.value.code == -32000
            assert caught.value.data == {"retry": True}
            with pytest.raises(JsonRpcError) as pagination:
                await http.send_request("ledger.getAccountBlocksByPage", [ADDRESS, 0, 1025])
            assert pagination.value.message == "page-size parameter is too big"

            websocket = WsClient(fixture.websocket_url, reconnect_interval=0.01, maximum_attempts=3)
            subscription = await websocket.subscribe("accountBlocksByAddress", ADDRESS)
            assert (await asyncio.wait_for(subscription.__anext__(), 2))["height"] == 42
            # The fixture closes each socket; the transport reconnects and resubscribes.
            assert (await asyncio.wait_for(subscription.__anext__(), 2))["height"] == 42
            await websocket.disconnect()
        finally:
            fixture.close()

    asyncio.run(scenario())
