class ConcurrencyError(Exception):
    """Raised when a concurrent update/edit conflict is detected (stale data)."""
    def __init__(self, message: str = "Stale data detected. The record has been modified by another user."):
        self.message = message
        super().__init__(self.message)
