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
