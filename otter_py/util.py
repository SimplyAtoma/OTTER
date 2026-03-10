"""Utility functions for OTTER."""
import sys


def eprint(*args, **kwargs) -> None:
    """Print to stderr (keeps stdout reserved for machine-readable JSON)."""
    print(*args, file=sys.stderr, **kwargs)