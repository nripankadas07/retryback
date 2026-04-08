# retryback

A tiny, dependency-free retry decorator for Python with exponential backoff
and jitter. Designed to be obvious, testable, and easy to drop into any
project.

```python
from retryback import retry, RetryError

@retry(attempts=5, base_delay=0.5, multiplier=2.0, max_delay=30, jitter=0.1)
def fetch():
    return some_flaky_call()

try:
    fetch()
except RetryError as exc:
    print("gave up:", exc.__cause__)
```

## Install

```bash
pip install retryback
```

From source:

```bash
git clone https://github.com/nripankadas07/retryback.git
cd retryback
pip install -e .[dev]
```

## API

### `retry(attempts=3, base_delay=0.1, max_delay=30.0, multiplier=2.0, jitter=0.1, exceptions=(Exception,), sleep=time.sleep, rng=None)`

Returns a decorator. Parameters:

- `attempts` — total number of attempts (>= 1).
- `base_delay` — initial delay in seconds before the first retry.
- `max_delay` — cap on the delay between attempts. Use `0` to disable.
- `multiplier` — exponential growth factor (>= 1).
- `jitter` — random jitter as a fraction of the current delay, in `[0, 1]`.
- `exceptions` — tuple of exception types that trigger a retry. Other
  exceptions propagate immediately.
- `sleep` — sleep function (injected for testing).
- `rng` — `random.Random` instance (injected for deterministic testing).

When all attempts fail, `retry` raises `RetryError`. The original exception
is chained via `__cause__`.

### `RetryError`

Subclass of `RuntimeError` raised after the final attempt fails.

## Running tests

```bash
pip install -e .[dev]
pytest
```

## License

MIT
