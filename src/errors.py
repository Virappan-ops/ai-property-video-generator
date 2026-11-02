"""Custom exception classes with mandatory message and suggestion attributes."""


class PropertyVideoError(Exception):
    """Base exception for all expected application errors."""

    exit_code: int = 1

    def __init__(self, message: str, suggestion: str = "Check your inputs and try again.") -> None:
        super().__init__(message)
        self.message = message
        self.suggestion = suggestion


class InputError(PropertyVideoError):
    """Raised on missing or invalid fields, malformed JSON, or missing input files."""

    exit_code = 1


class ImageError(PropertyVideoError):
    """Raised when zero usable images exist or image processing fails critically."""

    exit_code = 1


class ConfigError(PropertyVideoError):
    """Raised when configuration parameters are invalid."""

    exit_code = 1


class RenderError(PropertyVideoError):
    """Raised when video composition or encoding fails."""

    exit_code = 2


class DependencyError(PropertyVideoError):
    """Raised when FFmpeg or a required Python library is missing."""

    exit_code = 3