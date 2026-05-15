from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.protocol.constants import ErrorCode


class DomainException(Exception):
    def __init__(
        self,
        code: ErrorCode | str,
        message: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code.value if isinstance(code, ErrorCode) else code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)

    def to_error(self) -> dict[str, Any]:
        return {
            "type": "error",
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            },
        }


async def domain_exception_handler(_: Request, exc: DomainException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_error())

