class IllegalMove(Exception):
    """Raised when a command is not legal in the current game state."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)
