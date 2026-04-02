from __future__ import annotations


class MCPServerError(RuntimeError):
    def __init__(self, message: str, *, code: str = "server_error", cause: Exception | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.cause = cause
