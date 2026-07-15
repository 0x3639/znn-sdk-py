from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from itertools import count
from urllib.parse import urlparse

from znn.client.errors import TransportError
from znn.client.protocol import build_request, rpc_error


class HttpClient:
    def __init__(self, url: str, timeout: float = 30.0):
        if urlparse(url).scheme not in {"http", "https"}:
            raise ValueError("HTTP client URL must use http or https")
        if (
            not isinstance(timeout, (int, float))
            or isinstance(timeout, bool)
            or timeout <= 0
        ):
            raise ValueError("HTTP timeout must be a positive number")
        self.url, self.timeout, self._ids = url, timeout, count(1)

    def _send(self, method, params):
        request_id = next(self._ids)
        body = json.dumps(build_request(request_id, method, params)).encode()
        request = urllib.request.Request(self.url, body, {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read())
        except (
            urllib.error.URLError, OSError, UnicodeDecodeError, json.JSONDecodeError
        ) as error:
            raise TransportError(f"HTTP JSON-RPC request failed: {error}") from error
        if not isinstance(result, dict):
            raise TransportError("HTTP JSON-RPC response must be an object")
        if result.get("jsonrpc") != "2.0":
            raise TransportError("HTTP JSON-RPC response has an invalid protocol version")
        if type(result.get("id")) is not int or result["id"] != request_id:
            raise TransportError("HTTP JSON-RPC response ID does not match the request")
        if "error" in result:
            raise rpc_error(result["error"], method, params)
        return result.get("result")

    async def send_request(self, method: str, params: list):
        return await asyncio.to_thread(self._send, method, params)

    async def disconnect(self):
        return None
