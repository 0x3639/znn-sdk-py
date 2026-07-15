"""Persistent, correlated JSON-RPC WebSocket transport."""

from __future__ import annotations

import asyncio
import json
from itertools import count
from urllib.parse import urlparse

import websockets

from znn.client.errors import TransportError
from znn.client.protocol import build_request, normalize_notification, rpc_error


class Subscription:
    def __init__(self, subscription_id: str, params: list[str]):
        self.id, self.params = subscription_id, params
        self.queue = asyncio.Queue()

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self.queue.get()


class WsClient:
    def __init__(self, url: str | None = None, reconnect=True, reconnect_interval=1.0, maximum_attempts=0):
        if url is not None and urlparse(url).scheme not in {"ws", "wss"}:
            raise ValueError("WebSocket client URL must use ws or wss")
        self.url = url
        self.reconnect = reconnect
        self.reconnect_interval = reconnect_interval
        self.maximum_attempts = maximum_attempts
        self._socket = None
        self._listener = None
        self._ids = count(1)
        self._pending = {}
        self._subscriptions = {}
        self._orphan_updates = {}
        self._connect_lock = asyncio.Lock()
        self._closed = False

    async def connect(self):
        if self.url is None:
            raise TransportError("No default Zenon endpoint is configured; pass an explicit URL")
        async with self._connect_lock:
            if self._socket is None or self._socket.closed:
                self._socket = await websockets.connect(self.url)
                self._closed = False
                self._listener = asyncio.create_task(self._listen())
        return self

    async def _listen(self):
        try:
            async for frame in self._socket:
                message = json.loads(frame)
                if message.get("method") == "ledger.subscription":
                    normalized = normalize_notification(message)
                    subscription = self._subscriptions.get(normalized["subscriptionId"])
                    if subscription:
                        for update in normalized["updates"]:
                            await subscription.queue.put(update)
                    else:
                        self._orphan_updates.setdefault(normalized["subscriptionId"], []).extend(
                            normalized["updates"]
                        )
                    continue
                future = self._pending.pop(message.get("id"), None)
                if future and not future.done():
                    future.set_result(message)
            if not self._closed and self.reconnect:
                asyncio.create_task(self._recover(TransportError("WebSocket closed")))
        except Exception as error:
            if not self._closed and self.reconnect:
                asyncio.create_task(self._recover(error))
            else:
                self._fail_pending(error)

    def _fail_pending(self, error):
        for future in self._pending.values():
            if not future.done():
                future.set_exception(TransportError(str(error)))
        self._pending.clear()

    async def _recover(self, cause):
        self._fail_pending(cause)
        self._socket = None
        attempts = 0
        while not self._closed and (self.maximum_attempts == 0 or attempts < self.maximum_attempts):
            attempts += 1
            try:
                await asyncio.sleep(self.reconnect_interval)
                await self.connect()
                old = list(self._subscriptions.values())
                self._subscriptions.clear()
                for subscription in old:
                    new_id = await self.send_request("ledger.subscribe", subscription.params)
                    subscription.id = new_id
                    self._subscriptions[new_id] = subscription
                return
            except Exception:
                self._socket = None
        self._fail_pending(cause)

    async def send_request(self, method: str, params: list):
        await self.connect()
        request_id = next(self._ids)
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        await self._socket.send(json.dumps(build_request(request_id, method, params), separators=(",", ":")))
        message = await future
        if "error" in message:
            raise rpc_error(message["error"], method, params)
        return message.get("result")

    async def subscribe(self, topic: str, address: str | None = None):
        params = [topic] if address is None else [topic, address]
        subscription_id = await self.send_request("ledger.subscribe", params)
        subscription = Subscription(subscription_id, params)
        self._subscriptions[subscription_id] = subscription
        for update in self._orphan_updates.pop(subscription_id, []):
            await subscription.queue.put(update)
        return subscription

    async def send_and_listen(self, method: str, params: list):
        if method != "ledger.subscribe":
            return await self.send_request(method, params)
        return await self.subscribe(params[0], params[1] if len(params) > 1 else None)

    async def disconnect(self):
        self._closed = True
        self._subscriptions.clear()
        self._orphan_updates.clear()
        self._fail_pending(TransportError("WebSocket disconnected"))
        if self._socket is not None:
            await self._socket.close()
        if self._listener and self._listener is not asyncio.current_task():
            self._listener.cancel()
        self._socket = None


_default_client = WsClient()


def get_default_client():
    return _default_client
