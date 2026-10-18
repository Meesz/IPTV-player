class IPTVError(Exception):
    """Base error type for domain-related failures."""


class ValidationError(IPTVError):
    """Raised when input data is invalid."""


class NetworkError(IPTVError):
    """Raised when remote resources fail to load."""


class DownloadLimitError(NetworkError):
    """Raised when a download exceeds its byte budget or wall-clock deadline."""


class ParsingError(IPTVError):
    """Raised when parsing a playlist or EPG payload fails."""


class RepositoryError(IPTVError):
    """Raised when persistence layer fails."""
