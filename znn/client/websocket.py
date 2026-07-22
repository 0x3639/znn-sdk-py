"""Persistent, correlated JSON-RPC WebSocket transport."""

from __future__ import annotations

import asyncio
import json
import logging
from itertools import count
from urllib.parse import urlparse

import websockets

from znn.client.errors import TransportError
from znn.client.protocol import (
    build_request, normalize_notification, rpc_error, subscription_params,
)


logger = logging.getLogger(__name__)

_SUBSCRIPTION_TERMINATED = object()


class Subscription:
    def __init__(self, subscription_id: str, params: list[str]):
        self.id, self.params = subscription_id, params
        self.queue = asyncio.Queue()
        self._terminal_error = None

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._terminal_error is not None and self.queue.empty():
            raise self._terminal_error
        update = await self.queue.get()
        if update is _SUBSCRIPTION_TERMINATED:
            error = self._terminal_error
            raise error if error is not None else TransportError(
                "Subscription terminated"
            )
        return update

    def _fail(self, error):
        if self._terminal_error is None:
            self._terminal_error = TransportError(str(error))
            self.queue.put_nowait(_SUBSCRIPTION_TERMINATED)


class WsClient:
    _MAX_ORPHAN_SUBSCRIPTIONS = 128
    _MAX_ORPHAN_UPDATES = 1024

    def __init__(
        self,
        url: str | None = None,
        reconnect=True,
        reconnect_interval=1.0,
        maximum_attempts=0,
        connect_timeout=30.0,
        request_timeout=30.0,
    ):
        if url is not None and urlparse(url).scheme not in {"ws", "wss"}:
            raise ValueError("WebSocket client URL must use ws or wss")
        if not isinstance(reconnect, bool):
            raise TypeError("reconnect must be a boolean")
        if (
            not isinstance(reconnect_interval, (int, float))
            or isinstance(reconnect_interval, bool)
            or reconnect_interval < 0
        ):
            raise ValueError("reconnect_interval must be non-negative")
        if (
            not isinstance(maximum_attempts, int)
            or isinstance(maximum_attempts, bool)
            or maximum_attempts < 0
        ):
            raise ValueError("maximum_attempts must be a non-negative integer")
        if (
            not isinstance(connect_timeout, (int, float))
            or isinstance(connect_timeout, bool)
            or connect_timeout <= 0
        ):
            raise ValueError("connect_timeout must be positive")
        if request_timeout is not None and (
            not isinstance(request_timeout, (int, float))
            or isinstance(request_timeout, bool)
            or request_timeout <= 0
        ):
            raise ValueError("request_timeout must be positive or None")
        self.request_timeout = request_timeout
        self.url = url
        self.reconnect = reconnect
        self.reconnect_interval = reconnect_interval
        self.maximum_attempts = maximum_attempts
        self.connect_timeout = connect_timeout
        self._socket = None
        self._listener = None
        self._recovery_task = None
        self._queued_recovery = None
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
            if self._socket is None or getattr(self._socket, "closed", False):
                try:
                    self._socket = await websockets.connect(
                        self.url, open_timeout=self.connect_timeout
                    )
                except Exception as error:
                    raise TransportError(
                        f"WebSocket connection failed: {error}"
                    ) from error
                self._closed = False
                self._listener = asyncio.create_task(self._listen())
        return self

    async def _listen(self):
        socket = self._socket
        try:
            async for frame in socket:
                message = json.loads(frame)
                if not isinstance(message, dict):
                    raise TransportError("WebSocket JSON-RPC message must be an object")
                if message.get("method") == "ledger.subscription":
                    normalized = normalize_notification(message)
                    subscription = self._subscriptions.get(normalized["subscriptionId"])
                    if subscription:
                        for update in normalized["updates"]:
                            await subscription.queue.put(update)
                    else:
                        self._buffer_orphan_updates(
                            normalized["subscriptionId"], normalized["updates"]
                        )
                    continue
                if message.get("jsonrpc") != "2.0":
                    raise TransportError("WebSocket JSON-RPC response has an invalid protocol version")
                response_id = message.get("id")
                if type(response_id) is not int:
                    raise TransportError("WebSocket JSON-RPC response has an invalid ID")
                future = self._pending.pop(response_id, None)
                if future and not future.done():
                    future.set_result(message)
            if not self._closed and self.reconnect:
                self._schedule_recovery(TransportError("WebSocket closed"), socket)
            elif not self._closed:
                error = TransportError("WebSocket closed")
                self._fail_pending(error)
                self._fail_subscriptions(error)
        except Exception as error:
            if not self._closed and self.reconnect:
                self._schedule_recovery(error, socket)
            else:
                self._fail_pending(error)
                self._fail_subscriptions(error)
        finally:
            if self._listener is asyncio.current_task():
                self._listener = None

    def _fail_pending(self, error):
        for future in self._pending.values():
            if not future.done():
                future.set_exception(TransportError(str(error)))
        self._pending.clear()

    def _fail_subscriptions(self, error, subscriptions=None):
        active = self._subscriptions.values() if subscriptions is None else subscriptions
        for subscription in dict.fromkeys(active):
            subscription._fail(error)
        self._subscriptions.clear()

    def _schedule_recovery(self, cause, socket=None):
        if socket is not None and self._socket is not socket:
            return None
        if self._recovery_task is not None and not self._recovery_task.done():
            self._queued_recovery = (cause, socket)
            return self._recovery_task
        logger.warning("WebSocket connection lost (%s); starting recovery", cause)
        self._recovery_task = asyncio.create_task(self._recover(cause))
        self._recovery_task.add_done_callback(self._recovery_finished)
        return self._recovery_task

    def _recovery_finished(self, task):
        if self._recovery_task is task:
            self._recovery_task = None
        queued, self._queued_recovery = self._queued_recovery, None
        if queued is None or self._closed:
            return
        cause, socket = queued
        if socket is None or self._socket is socket:
            self._schedule_recovery(cause, socket)

    async def _discard_socket(self, socket):
        if socket is None:
            return
        if self._socket is socket:
            self._socket = None
        try:
            await socket.close()
        except Exception:
            pass

    async def _recover(self, cause):
        self._fail_pending(cause)
        subscriptions = list(dict.fromkeys(self._subscriptions.values()))
        self._subscriptions.clear()
        await self._discard_socket(self._socket)
        attempts = 0
        last_error = cause
        while not self._closed and (self.maximum_attempts == 0 or attempts < self.maximum_attempts):
            attempts += 1
            attempt_socket = None
            logger.info("WebSocket reconnect attempt %d", attempts)
            try:
                await asyncio.sleep(self.reconnect_interval)
                if self._closed:
                    return
                await self.connect()
                attempt_socket = self._socket
                self._subscriptions.clear()
                for subscription in subscriptions:
                    new_id = await self.send_request("ledger.subscribe", subscription.params)
                    if not isinstance(new_id, str) or not new_id:
                        raise TransportError(
                            "ledger.subscribe returned an invalid subscription ID"
                        )
                    subscription.id = new_id
                    self._subscriptions[new_id] = subscription
                    for update in self._orphan_updates.pop(new_id, []):
                        await subscription.queue.put(update)
                return
            except asyncio.CancelledError:
                await self._discard_socket(self._socket or attempt_socket)
                raise
            except Exception as error:
                last_error = error
                failed_socket = self._socket or attempt_socket
                self._subscriptions.clear()
                await self._discard_socket(failed_socket)
        if not self._closed:
            logger.warning("WebSocket recovery failed: %s", last_error)
            failure = TransportError(f"WebSocket recovery failed: {last_error}")
            self._fail_pending(failure)
            self._fail_subscriptions(failure, subscriptions)
            self._orphan_updates.clear()

    async def send_request(self, method: str, params: list):
        await self.connect()
        request_id = next(self._ids)
        try:
            payload = json.dumps(
                build_request(request_id, method, params), separators=(",", ":")
            )
        except Exception as error:
            raise TransportError(f"WebSocket send failed: {error}") from error
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future

        async def send_and_wait():
            try:
                await self._socket.send(payload)
            except Exception as error:
                raise TransportError(f"WebSocket send failed: {error}") from error
            return await future

        try:
            if self.request_timeout is None:
                message = await send_and_wait()
            else:
                message = await asyncio.wait_for(send_and_wait(), self.request_timeout)
        except asyncio.TimeoutError as error:
            raise TransportError(
                f"JSON-RPC request {method!r} timed out after "
                f"{self.request_timeout} seconds"
            ) from error
        finally:
            self._pending.pop(request_id, None)
            if not future.done():
                future.cancel()
            elif not future.cancelled():
                future.exception()
        if "error" in message:
            raise rpc_error(message["error"], method, params)
        return message.get("result")

    async def subscribe(self, topic: str, address: str | None = None):
        params = subscription_params(topic, address)
        subscription_id = await self.send_request("ledger.subscribe", params)
        if not isinstance(subscription_id, str) or not subscription_id:
            raise TransportError("ledger.subscribe returned an invalid subscription ID")
        subscription = Subscription(subscription_id, params)
        self._subscriptions[subscription_id] = subscription
        for update in self._orphan_updates.pop(subscription_id, []):
            await subscription.queue.put(update)
        return subscription

    def _buffer_orphan_updates(self, subscription_id, updates):
        bucket = self._orphan_updates.setdefault(subscription_id, [])
        bucket.extend(updates)
        if len(bucket) > self._MAX_ORPHAN_UPDATES:
            del bucket[:-self._MAX_ORPHAN_UPDATES]
        while len(self._orphan_updates) > self._MAX_ORPHAN_SUBSCRIPTIONS:
            self._orphan_updates.pop(next(iter(self._orphan_updates)))

    async def send_and_listen(self, method: str, params: list):
        if method != "ledger.subscribe":
            return await self.send_request(method, params)
        return await self.subscribe(params[0], params[1] if len(params) > 1 else None)

    async def disconnect(self):
        self._closed = True
        self._queued_recovery = None
        self._fail_subscriptions(TransportError("WebSocket disconnected"))
        self._orphan_updates.clear()
        self._fail_pending(TransportError("WebSocket disconnected"))
        socket, self._socket = self._socket, None
        if self._listener and self._listener is not asyncio.current_task():
            self._listener.cancel()
        if self._recovery_task and self._recovery_task is not asyncio.current_task():
            self._recovery_task.cancel()
        await self._discard_socket(socket)


_default_client = WsClient()


def get_default_client():
    return _default_client
