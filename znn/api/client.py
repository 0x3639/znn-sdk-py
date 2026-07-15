"""Model-aware client adapter used by public RPC API classes."""

from znn.client.websocket import get_default_client
from znn.api._response import parse_rpc_response


class ApiClient:
    def __init__(self, transport):
        self.transport = transport

    async def send_request(self, method, params):
        value = await self.transport.send_request(method, params)
        return parse_rpc_response(method, value)

    def __getattr__(self, name):
        return getattr(self.transport, name)


def get_api_client(transport=None):
    if isinstance(transport, ApiClient):
        return transport
    return ApiClient(get_default_client() if transport is None else transport)
