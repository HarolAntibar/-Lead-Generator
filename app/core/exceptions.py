from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class NotFoundError(Exception):
    def __init__(self, resource: str, identifier: int | str) -> None:
        self.resource = resource
        self.identifier = identifier


class ConflictError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message


class ExternalServiceError(Exception):
    def __init__(self, service: str, message: str) -> None:
        self.service = service
        self.message = message


async def _not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": f"{exc.resource} '{exc.identifier}' not found"},
    )


async def _conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": exc.message})


async def _external_service_handler(
    request: Request, exc: ExternalServiceError
) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={"detail": f"{exc.service} error: {exc.message}"},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(NotFoundError, _not_found_handler)
    app.add_exception_handler(ConflictError, _conflict_handler)
    app.add_exception_handler(ExternalServiceError, _external_service_handler)
