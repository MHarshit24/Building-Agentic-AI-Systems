class InvalidDataError(Exception):
    """Raised when a sales record contains invalid data."""
    pass


class FileProcessingError(Exception):
    """Raised when there is a problem processing the file."""
    pass
