"""Error hierarchy for the storage layer."""


class StorageError(Exception):
    """Base class for all storage errors."""


class IndexNotFoundError(StorageError):
    """Database file missing."""


class IndexVersionError(StorageError):
    """Schema version mismatch."""

    def __init__(self, found, expected):
        self.found = found
        self.expected = expected
        super().__init__(
            f"Schema version mismatch: found {found}, expected {expected}"
        )
