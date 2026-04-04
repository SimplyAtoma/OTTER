"""Shared exceptions for the OTTER Python package (avoids import cycles)."""


class TranscriptionCancelled(Exception):
    """Raised when the main process requests cancellation."""
