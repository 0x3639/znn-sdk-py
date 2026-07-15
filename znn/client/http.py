from __future__ import annotations

import asyncio
import json
import urllib.request
from itertools import count
from urllib.parse import urlparse

from znn.client.protocol import build_request, rpc_error


class HttpClient:
    def __init__(self, url: str, timeout: float = 30.0):
        if urlparse(url).scheme not in {"http", "https"}:
            raise ValueError("HTTP client URL must use http or https")
        self.url, self.timeout, self._ids = url, timeout, count(1)

    def _send(self, method, params):
        body = json.dumps(build_request(next(self._ids), method, params)).encode()
        request = urllib.request.Request(self.url, body, {"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            result = json.loads(response.read())
        if "error" in result:
            raise rpc_error(result["error"], method, params)
        return result.get("result")

    async def send_request(self, method: str, params: list):
        return await asyncio.to_thread(self._send, method, params)

    async def disconnect(self):
        return None
