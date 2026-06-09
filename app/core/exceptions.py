from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse


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


async def _invalid_credentials_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"detail": "Invalid email or password"},
    )


async def _inactive_user_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"detail": "Account is disabled"},
    )


async def _permission_denied_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"detail": "You do not have permission to perform this action"},
    )


async def _not_authenticated_handler(
    request: Request, exc: Exception
) -> JSONResponse | RedirectResponse:
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
    next_path = request.url.path
    return RedirectResponse(f"/auth/login?next={next_path}", status_code=303)


def register_exception_handlers(app: FastAPI) -> None:
    from app.features.auth.exceptions import (
        InactiveUserError,
        InvalidCredentialsError,
        NotAuthenticatedException,
        PermissionDeniedError,
    )

    app.add_exception_handler(NotFoundError, _not_found_handler)
    app.add_exception_handler(ConflictError, _conflict_handler)
    app.add_exception_handler(ExternalServiceError, _external_service_handler)
    app.add_exception_handler(InvalidCredentialsError, _invalid_credentials_handler)
    app.add_exception_handler(InactiveUserError, _inactive_user_handler)
    app.add_exception_handler(PermissionDeniedError, _permission_denied_handler)
    app.add_exception_handler(NotAuthenticatedException, _not_authenticated_handler)
