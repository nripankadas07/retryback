"""retryback: a tiny retry decorator with exponential backoff and jitter."""

from .core import RetryError, retry

__all__ = ["retry", "RetryError"]
__version__ = "0.1.0"
