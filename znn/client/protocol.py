from typing import Any

from znn.client.errors import JsonRpcError


def build_request(request_id: int, method: str, params: list[Any]) -> dict[str, Any]:
    if not isinstance(request_id, int) or isinstance(request_id, bool):
        raise TypeError("JSON-RPC request ID must be an integer")
    if not isinstance(method, str) or not method:
        raise TypeError("JSON-RPC method must be a non-empty string")
    if not isinstance(params, list):
        raise TypeError("JSON-RPC parameters must be a positional list")
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}


def subscription_params(topic: str, address: str | None = None) -> list[str]:
    address_topics = {"accountBlocksByAddress", "unreceivedAccountBlocksByAddress"}
    global_topics = {"momentums", "allAccountBlocks"}
    if topic in address_topics:
        if not isinstance(address, str) or not address:
            raise ValueError(f"Subscription topic {topic!r} requires an address")
    elif topic in global_topics:
        if address is not None:
            raise ValueError(f"Subscription topic {topic!r} does not accept an address")
    else:
        raise ValueError(f"Unknown subscription topic {topic!r}")
    return [topic] if address is None else [topic, address]


def normalize_notification(message: dict[str, Any]) -> dict[str, Any]:
    if message.get("method") != "ledger.subscription":
        raise ValueError("Not a ledger subscription notification")
    params = message.get("params", {})
    if (
        not isinstance(params, dict)
        or not isinstance(params.get("subscription"), str)
        or not params["subscription"]
        or not isinstance(params.get("result"), list)
    ):
        raise ValueError("Malformed ledger subscription notification")
    return {"subscriptionId": params["subscription"], "updates": params["result"]}


def rpc_error(error: dict[str, Any], method: str, params: list[Any]) -> JsonRpcError:
    return JsonRpcError(error.get("code", -1), error.get("message", "Unknown error occurred"),
                        error.get("data"), method, params)
