class AppError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class DuplicateEmailError(AppError):
    def __init__(self, message: str = "Email already registered") -> None:
        super().__init__(message, status_code=409)


class InvalidCredentialsError(AppError):
    def __init__(self, message: str = "Invalid email or password") -> None:
        super().__init__(message, status_code=401)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Unauthorized") -> None:
        super().__init__(message, status_code=401)


class NotFoundError(AppError):
    def __init__(self, message: str = "Not found") -> None:
        super().__init__(message, status_code=404)


class SessionNotFoundError(NotFoundError):
    def __init__(self, message: str = "Session not found") -> None:
        super().__init__(message)


class NotMemberError(AppError):
    def __init__(self, session_id: str, user_id: str) -> None:
        super().__init__(
            f"User {user_id} is not a member of session {session_id}",
            status_code=403,
        )
        self.session_id = session_id
        self.user_id = user_id


class SessionFullError(AppError):
    def __init__(self, session_id: str) -> None:
        super().__init__(f"Session {session_id} is full", status_code=409)
        self.session_id = session_id


class SessionNotJoinableError(AppError):
    def __init__(self, session_id: str, status: str) -> None:
        super().__init__(
            f"Session {session_id} is not joinable (status={status})",
            status_code=409,
        )
        self.session_id = session_id


class ForbiddenHostActionError(AppError):
    def __init__(self, message: str = "Only the host can perform this action") -> None:
        super().__init__(message, status_code=403)


class CannotKickSelfError(AppError):
    def __init__(self) -> None:
        super().__init__("Host cannot kick themselves", status_code=400)


class AlreadyMemberError(AppError):
    def __init__(self, session_id: str, user_id: str) -> None:
        super().__init__(
            f"User {user_id} is already a member of session {session_id}",
            status_code=409,
        )
        self.session_id = session_id
        self.user_id = user_id


class GameNotFoundError(NotFoundError):
    def __init__(self, session_id: str) -> None:
        super().__init__(f"No active game for session {session_id}")


class GameVersionConflictError(AppError):
    def __init__(self, session_id: str) -> None:
        super().__init__(
            f"Game state conflict for session {session_id}; retry with latest snapshot",
            status_code=409,
        )
        self.session_id = session_id


class InvalidTelegramLoginError(AppError):
    def __init__(self, message: str = "Invalid Telegram login") -> None:
        super().__init__(message, status_code=401)


class TelegramUnavailableError(AppError):
    def __init__(self, message: str = "Telegram service unavailable") -> None:
        super().__init__(message, status_code=503)


class AlreadyLinkedError(AppError):
    def __init__(self, message: str = "Identity already linked") -> None:
        super().__init__(message, status_code=409)


class AlreadyHasEmailError(AppError):
    def __init__(self, message: str = "Account already has an email address") -> None:
        super().__init__(message, status_code=409)
