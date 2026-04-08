"""Tests for retryback.retry."""

import random

import pytest

from retryback import RetryError, retry


def make_recorded_sleep() -> tuple[list[float], "object"]:
    sleeps: list[float] = []

    def sleeper(delay: float) -> None:
        sleeps.append(delay)

    return sleeps, sleeper


class TestRetryHappyPath:
    def test_retry_returns_value_when_function_succeeds_first_try(self) -> None:
        @retry(attempts=3, base_delay=0)
        def succeed() -> int:
            return 42

        assert succeed() == 42

    def test_retry_returns_value_after_two_failures(self) -> None:
        calls: list[int] = []
        sleeps, sleeper = make_recorded_sleep()

        @retry(attempts=5, base_delay=0, jitter=0, sleep=sleeper)
        def flaky() -> str:
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("not yet")
            return "ok"

        assert flaky() == "ok"
        assert len(calls) == 3
        assert len(sleeps) == 2

    def test_retry_raises_retry_error_when_all_attempts_fail(self) -> None:
        sleeps, sleeper = make_recorded_sleep()

        @retry(attempts=3, base_delay=0, jitter=0, sleep=sleeper)
        def always_fails() -> None:
            raise RuntimeError("nope")

        with pytest.raises(RetryError) as exc_info:
            always_fails()
        assert isinstance(exc_info.value.__cause__, RuntimeError)
        assert len(sleeps) == 2  # one fewer than attempts

    def test_retry_passes_args_and_kwargs_through(self) -> None:
        @retry(attempts=2, base_delay=0)
        def add(left: int, right: int = 0) -> int:
            return left + right

        assert add(1, right=2) == 3

    def test_retry_preserves_function_name_via_functools_wraps(self) -> None:
        @retry(attempts=1, base_delay=0)
        def my_function() -> int:
            return 1

        assert my_function.__name__ == "my_function"


class TestRetryBackoff:
    def test_retry_uses_exponential_backoff_without_jitter(self) -> None:
        sleeps, sleeper = make_recorded_sleep()

        @retry(
            attempts=4,
            base_delay=1.0,
            multiplier=2.0,
            max_delay=100.0,
            jitter=0,
            sleep=sleeper,
        )
        def fail() -> None:
            raise ValueError("boom")

        with pytest.raises(RetryError):
            fail()
        # 1, 2, 4 — exponential growth
        assert sleeps == [1.0, 2.0, 4.0]

    def test_retry_caps_delay_at_max_delay(self) -> None:
        sleeps, sleeper = make_recorded_sleep()

        @retry(
            attempts=5,
            base_delay=10.0,
            multiplier=10.0,
            max_delay=50.0,
            jitter=0,
            sleep=sleeper,
        )
        def fail() -> None:
            raise ValueError("boom")

        with pytest.raises(RetryError):
            fail()
        # Without cap: 10, 100, 1000, 10000. With cap of 50: 10, 50, 50, 50.
        assert sleeps == [10.0, 50.0, 50.0, 50.0]

    def test_retry_jitter_keeps_delay_within_expected_range(self) -> None:
        sleeps, sleeper = make_recorded_sleep()
        seeded_rng = random.Random(12345)

        @retry(
            attempts=3,
            base_delay=10.0,
            multiplier=1.0,
            max_delay=100.0,
            jitter=0.5,
            sleep=sleeper,
            rng=seeded_rng,
        )
        def fail() -> None:
            raise ValueError("boom")

        with pytest.raises(RetryError):
            fail()
        for delay in sleeps:
            assert 5.0 <= delay <= 15.0


class TestRetryEdgeCases:
    def test_retry_propagates_unlisted_exceptions_immediately(self) -> None:
        calls: list[int] = []

        @retry(attempts=5, base_delay=0, exceptions=(ValueError,))
        def func() -> None:
            calls.append(1)
            raise TypeError("not retried")

        with pytest.raises(TypeError):
            func()
        assert len(calls) == 1

    def test_retry_with_attempts_one_calls_function_exactly_once(self) -> None:
        calls: list[int] = []

        @retry(attempts=1, base_delay=0)
        def func() -> None:
            calls.append(1)
            raise ValueError("boom")

        with pytest.raises(RetryError):
            func()
        assert len(calls) == 1

    def test_retry_with_zero_attempts_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="positive int"):
            retry(attempts=0)

    def test_retry_with_negative_base_delay_raises(self) -> None:
        with pytest.raises(ValueError, match="base_delay"):
            retry(attempts=2, base_delay=-1)

    def test_retry_with_multiplier_below_one_raises(self) -> None:
        with pytest.raises(ValueError, match="multiplier"):
            retry(attempts=2, multiplier=0.5)

    def test_retry_with_jitter_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match="jitter"):
            retry(attempts=2, jitter=1.5)

    def test_retry_with_negative_jitter_raises(self) -> None:
        with pytest.raises(ValueError, match="jitter"):
            retry(attempts=2, jitter=-0.1)

    def test_retry_error_chains_original_exception(self) -> None:
        @retry(attempts=2, base_delay=0)
        def fail() -> None:
            raise KeyError("missing")

        with pytest.raises(RetryError) as exc_info:
            fail()
        assert isinstance(exc_info.value.__cause__, KeyError)
        assert str(exc_info.value.__cause__) == "'missing'"
