from typing import Any

from znn.client.errors import JsonRpcError


def build_request(request_id: int, method: str, params: list[Any]) -> dict[str, Any]:
    if not isinstance(params, list):
        raise TypeError("JSON-RPC parameters must be a positional list")
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}


def subscription_params(topic: str, address: str | None = None) -> list[str]:
    return [topic] if address is None else [topic, address]


def normalize_notification(message: dict[str, Any]) -> dict[str, Any]:
    if message.get("method") != "ledger.subscription":
        raise ValueError("Not a ledger subscription notification")
    params = message.get("params", {})
    if "subscription" not in params or not isinstance(params.get("result"), list):
        raise ValueError("Malformed ledger subscription notification")
    return {"subscriptionId": params["subscription"], "updates": params["result"]}


def rpc_error(error: dict[str, Any], method: str, params: list[Any]) -> JsonRpcError:
    return JsonRpcError(error.get("code", -1), error.get("message", "Unknown error occurred"),
                        error.get("data"), method, params)
