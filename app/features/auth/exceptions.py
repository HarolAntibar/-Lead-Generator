from app.core.exceptions import ConflictError, NotFoundError
from app.features.auth.constants import USER_RESOURCE_NAME


class NotAuthenticatedException(Exception):
    pass


class UserNotFoundError(NotFoundError):
    def __init__(self, identifier: int | str) -> None:
        super().__init__(USER_RESOURCE_NAME, identifier)


class InvalidCredentialsError(Exception):
    pass


class InactiveUserError(Exception):
    pass


class EmailAlreadyRegisteredError(ConflictError):
    def __init__(self) -> None:
        super().__init__("Email is already registered")


class PermissionDeniedError(Exception):
    pass
