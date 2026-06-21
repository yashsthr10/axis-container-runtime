class AxisError(Exception):
    """Base exception for user-facing Axis errors."""


class AxisfileError(AxisError):
    """Raised when an Axisfile cannot be parsed or validated."""


class CommandError(AxisError):
    """Raised when an external command fails."""
