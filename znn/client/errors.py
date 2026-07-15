from typing import Any


class JsonRpcError(Exception):
    def __init__(self, code: int, message: str, data: Any = None, method: str = "", parameters=None):
        super().__init__(message)
        self.code = int(code)
        self.message = message
        self.data = data
        self.method = method
        self.parameters = [] if parameters is None else parameters

    def to_json(self):
        return {"code": self.code, "message": self.message, "data": self.data,
                "method": self.method, "parameters": self.parameters}


class TransportError(ConnectionError):
    pass
