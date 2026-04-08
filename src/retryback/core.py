"""Retry decorator with exponential backoff and optional jitter.

Examples
--------
>>> from retryback import retry
>>> calls = []
>>> @retry(attempts=3, base_delay=0.0)
... def flaky():
...     calls.append(1)
...     if len(calls) < 3:
...         raise ValueError("not yet")
...     return "ok"
>>> flaky()
'ok'
>>> len(calls)
3
"""

from __future__ import annotations

import functools
import random
import time
from typing import Any, Callable, Tuple, Type, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


class RetryError(RuntimeError):
    """Raised when all retry attempts have been exhausted.

    The original exception is available via ``RetryError.__cause__``.
    """


def _validate_arguments(
    attempts: int,
    base_delay: float,
    max_delay: float,
    multiplier: float,
    jitter: float,
) -> None:
    """Validate retry parameters; raise ValueError on bad input."""
    if not isinstance(attempts, int) or attempts < 1:
        raise ValueError(f"attempts must be a positive int, got {attempts!r}")
    if base_delay < 0:
        raise ValueError(f"base_delay must be >= 0, got {base_delay!r}")
    if max_delay < 0:
        raise ValueError(f"max_delay must be >= 0, got {max_delay!r}")
    if multiplier < 1:
        raise ValueError(f"multiplier must be >= 1, got {multiplier!r}")
    if not 0.0 <= jitter <= 1.0:
        raise ValueError(f"jitter must be in [0, 1], got {jitter!r}")


def _compute_delay(
    attempt_index: int,
    base_delay: float,
    multiplier: float,
    max_delay: float,
    jitter: float,
    rng: random.Random,
) -> float:
    """Compute the delay before the next attempt (>= 0)."""
    raw = base_delay * (multiplier ** attempt_index)
    capped = min(raw, max_delay) if max_delay > 0 else raw
    if jitter > 0:
        spread = capped * jitter
        capped = capped + rng.uniform(-spread, spread)
    return max(0.0, capped)


def retry(
    attempts: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 30.0,
    multiplier: float = 2.0,
    jitter: float = 0.1,
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    sleep: Callable[[float], None] = time.sleep,
    rng: random.Random | None = None,
) -> Callable[[F], F]:
    """Return a decorator that retries the wrapped callable on failure.

    Args:
        attempts: Total number of attempts (>= 1). The function is called
            once and then retried up to ``attempts - 1`` more times.
        base_delay: Initial delay (seconds) before the first retry.
        max_delay: Cap on the delay between attempts. Use ``0`` to disable.
        multiplier: Exponential growth factor (>= 1).
        jitter: Random jitter as a fraction of the delay, in ``[0, 1]``.
        exceptions: Tuple of exception types that trigger a retry. Other
            exceptions propagate immediately.
        sleep: Sleep function (injected for testing).
        rng: Random number generator (injected for testing).

    Raises:
        ValueError: if any argument is out of range.
        RetryError: when all attempts are exhausted; ``__cause__`` is the
            last exception raised by the wrapped function.
    """
    _validate_arguments(attempts, base_delay, max_delay, multiplier, jitter)
    rng = rng or random.Random()

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: BaseException | None = None
            for attempt_index in range(attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt_index == attempts - 1:
                        break
                    delay = _compute_delay(
                        attempt_index, base_delay, multiplier, max_delay, jitter, rng
                    )
                    sleep(delay)
            raise RetryError(
                f"{func.__name__} failed after {attempts} attempts"
            ) from last_exc

        return wrapper  # type: ignore[return-value]

    return decorator
