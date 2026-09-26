"""Custom exceptions for JY-001 DIY-2 humidifier driver."""


class HumidifierError(Exception):
    """Base exception for humidifier driver errors."""
    pass


class GPIOError(HumidifierError):
    """Raised when GPIO operations fail."""
    pass


class InvalidLevelError(HumidifierError):
    """Raised when an invalid mist level is requested."""
    pass


class StateSyncError(HumidifierError):
    """Raised when driver cannot synchronize with humidifier state."""
    pass


class OffDetectionTimeoutError(HumidifierError):
    """Raised when OFF state is not detected within timeout."""
    pass


class OperationInProgressError(HumidifierError):
    """Raised when a control operation is already in progress."""
    pass


class HardwareError(HumidifierError):
    """Raised when hardware behaves unexpectedly."""
    pass