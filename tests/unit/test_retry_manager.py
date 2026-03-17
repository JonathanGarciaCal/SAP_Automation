"""Comprehensive unit tests for retry manager and circuit breaker.

Tests cover:
    - RetryPolicy backoff calculations (EXPONENTIAL, LINEAR, FIBONACCI)
    - RetryConfig parameter validation
    - CircuitBreaker state machine (CLOSED → OPEN → HALF_OPEN → CLOSED)
    - Retry decoration on async functions
    - Jitter handling and delay capping
   - Integration of retry + circuit breaker
    - Error classification for recoverable vs permanent errors

All tests are async-compatible using pytest-asyncio.
"""

import pytest
import asyncio
import logging
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Set, Type
from datetime import datetime, timedelta

# Import from retry_manager after it's created by conftest
from sap.retry_manager import (
    RetryPolicy,
    RetryConfig,
    CircuitBreaker,
    CircuitBreakerState,
    RetryManager,
    retry_async
)

logger = logging.getLogger(__name__)


# ============================================================================
# Test Group 1: RetryPolicy Backoff Calculations (3 tests)
# ============================================================================

class TestRetryPolicyBackoff:
    """Test backoff calculation for each RetryPolicy strategy."""

    def test_exponential_backoff_calculation(self):
        """Test exponential backoff: delay = initial * (factor ^ attempt)."""
        config = RetryConfig(
            max_retries=5,
            initial_delay=1.0,
            backoff_factor=2.0,
            jitter=False  # Disable jitter for deterministic testing
        )
        manager = RetryManager(config=config)

        # Expected delays: 1.0, 2.0, 4.0, 8.0, 16.0, 30.0 (capped)
        expected = [1.0, 2.0, 4.0, 8.0, 16.0, 30.0]

        for attempt, expected_delay in enumerate(expected[:6]):
            actual_delay = manager._calculate_delay(attempt)
            assert actual_delay == expected_delay, (
                f"Attempt {attempt}: expected {expected_delay}, "
                f"got {actual_delay}"
            )

    def test_linear_backoff_calculation(self):
        """Test linear backoff: delay = initial * (attempt + 1)."""
        config = RetryConfig(
            max_retries=5,
            initial_delay=0.5,
            backoff_factor=1.0,  # Unused in LINEAR
            policy=RetryPolicy.LINEAR,
            jitter=False
        )
        manager = RetryManager(config=config)

        # Expected delays: 0.5, 1.0, 1.5, 2.0, 2.5, 3.0
        expected = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]

        for attempt, expected_delay in enumerate(expected):
            actual_delay = manager._calculate_delay(attempt)
            assert actual_delay == expected_delay, (
                f"Attempt {attempt}: expected {expected_delay}, "
                f"got {actual_delay}"
            )

    def test_fibonacci_backoff_calculation(self):
        """Test Fibonacci backoff: delay = fib(attempt + 1) * initial."""
        config = RetryConfig(
            max_retries=5,
            initial_delay=0.5,
            policy=RetryPolicy.FIBONACCI,
            jitter=False
        )
        manager = RetryManager(config=config)

        # Fibonacci: fib(1)=1, fib(2)=1, fib(3)=2, fib(4)=3, fib(5)=5, fib(6)=8
        # Delays: 0.5*1, 0.5*1, 0.5*2, 0.5*3, 0.5*5, 0.5*8 = 0.5, 0.5, 1.0, 1.5, 2.5, 4.0
        expected = [0.5, 0.5, 1.0, 1.5, 2.5, 4.0]

        for attempt, expected_delay in enumerate(expected):
            actual_delay = manager._calculate_delay(attempt)
            assert actual_delay == expected_delay, (
                f"Attempt {attempt}: expected {expected_delay}, "
                f"got {actual_delay}"
            )


# ============================================================================
# Test Group 2: RetryConfig and RetryPolicy Validation (2 tests)
# ============================================================================

class TestRetryConfig:
    """Test RetryConfig parameter validation."""

    def test_retry_config_defaults(self):
        """Test default values in RetryConfig."""
        config = RetryConfig()

        assert config.max_retries == 3
        assert config.initial_delay == 0.5
        assert config.max_delay == 30.0
        assert config.backoff_factor == 2.0
        assert config.jitter is True
        assert config.policy == RetryPolicy.EXPONENTIAL

    def test_retry_config_custom_values(self):
        """Test custom RetryConfig values."""
        config = RetryConfig(
            max_retries=5,
            initial_delay=0.1,
            max_delay=60.0,
            backoff_factor=3.0,
            jitter=False,
            policy=RetryPolicy.LINEAR
        )

        assert config.max_retries == 5
        assert config.initial_delay == 0.1
        assert config.max_delay == 60.0
        assert config.backoff_factor == 3.0
        assert config.jitter is False
        assert config.policy == RetryPolicy.LINEAR


# ============================================================================
# Test Group 3: CircuitBreaker State Machine (4 tests)
# ============================================================================

class TestCircuitBreakerStates:
    """Test CircuitBreaker state transitions."""

    def test_circuit_breaker_initial_state_is_closed(self):
        """Test circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker()

        assert cb.state() == CircuitBreakerState.CLOSED
        assert not cb.is_open()

    def test_circuit_breaker_closed_to_open_transition(self):
        """Test CLOSED → OPEN transition after failures."""
        cb = CircuitBreaker(failure_threshold=3)

        # Record 2 failures (threshold is 3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state() == CircuitBreakerState.CLOSED

        # Record 3rd failure → should transition to OPEN
        cb.record_failure()
        assert cb.state() == CircuitBreakerState.OPEN
        assert cb.is_open()

    def test_circuit_breaker_open_to_half_open_transition(self):
        """Test OPEN → HALF_OPEN transition after timeout."""
        cb = CircuitBreaker(failure_threshold=2, timeout=0.1)

        # Transition to OPEN
        cb.record_failure()
        cb.record_failure()
        assert cb.state() == CircuitBreakerState.OPEN

        # Manually set last_open_time to simulate elapsed time
        cb._last_open_time = datetime.now() - timedelta(seconds=0.2)

        # Should auto-transition to HALF_OPEN
        assert cb.state() == CircuitBreakerState.HALF_OPEN

    def test_circuit_breaker_half_open_to_closed_transition(self):
        """Test HALF_OPEN → CLOSED transition after successes."""
        cb = CircuitBreaker(
            failure_threshold=2,
            success_threshold=2,
            timeout=0.1
        )

        # Transition to OPEN
        cb.record_failure()
        cb.record_failure()
        assert cb.state() == CircuitBreakerState.OPEN

        # Force transition to HALF_OPEN
        cb._last_open_time = datetime.now() - timedelta(seconds=0.2)
        assert cb.state() == CircuitBreakerState.HALF_OPEN

        # Record success (threshold is 2)
        cb.record_success()
        assert cb.state() == CircuitBreakerState.HALF_OPEN  # Not yet

        # Record 2nd success → should transition to CLOSED
        cb.record_success()
        assert cb.state() == CircuitBreakerState.CLOSED


# ============================================================================
# Test Group 4: Retry Decorator on Async Functions (4 tests)
# ============================================================================

class TestRetryDecorator:
    """Test @retry_async decorator on async functions."""

    @pytest.mark.asyncio
    async def test_retry_decorator_success_on_first_attempt(self):
        """Test successful execution without retries."""
        @retry_async(max_retries=3)
        async def successful_function():
            return "success"

        result = await successful_function()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_decorator_recovers_from_transient_error(self):
        """Test recovery from transient error after retries."""
        attempt_count = 0

        @retry_async(max_retries=3, initial_delay=0.01)
        async def function_with_transient_error():
            nonlocal attempt_count
            attempt_count += 1

            if attempt_count < 2:
                raise asyncio.TimeoutError("Transient timeout")

            return "recovered"

        result = await function_with_transient_error()
        assert result == "recovered"
        assert attempt_count == 2

    @pytest.mark.asyncio
    async def test_retry_decorator_exhausts_retries(self):
        """Test exhaustion of retries on persistent failure."""
        @retry_async(max_retries=2, initial_delay=0.01)
        async def always_fails():
            raise asyncio.TimeoutError("Persistent failure")

        with pytest.raises(RuntimeError, match="Failed after"):
            await always_fails()

    @pytest.mark.asyncio
    async def test_retry_decorator_non_recoverable_error_fails_fast(self):
        """Test non-recoverable error fails without retries."""
        attempt_count = 0

        @retry_async(max_retries=3)
        async def fails_with_non_recoverable():
            nonlocal attempt_count
            attempt_count += 1
            raise ValueError("Non-recoverable error")

        with pytest.raises(ValueError):
            await fails_with_non_recoverable()

        assert attempt_count == 1, "Should not retry non-recoverable error"


# ============================================================================
# Test Group 5: Jitter Handling (2 tests)
# ============================================================================

class TestJitterHandling:
    """Test jitter functionality in backoff calculations."""

    def test_jitter_produces_variation_in_delay(self):
        """Test that jitter adds randomness to delays."""
        config = RetryConfig(
            max_retries=5,
            initial_delay=1.0,
            jitter=True
        )
        manager = RetryManager(config=config)

        # Sample multiple delays; at least some should differ
        delays = [manager._calculate_delay(0) for _ in range(10)]

        # With jitter=True, delays should not all be identical
        assert len(set(delays)) > 1, "Jitter should produce variation"

        # Delays should be within ±10% of base delay (1.0)
        for delay in delays:
            assert 0.9 <= delay <= 1.1

    def test_delay_capped_at_max_delay(self):
        """Test that delays are capped at max_delay."""
        config = RetryConfig(
            max_retries=10,
            initial_delay=1.0,
            max_delay=5.0,
            backoff_factor=2.0,
            jitter=False
        )
        manager = RetryManager(config=config)

        # Without cap: 1 * 2^8 = 256, but capped at 5.0
        for attempt in range(10):
            delay = manager._calculate_delay(attempt)
            assert delay <= 5.0, f"Delay {delay} exceeds max_delay 5.0"


# ============================================================================
# Test Group 6: Retry Manager Integration (3 tests)
# ============================================================================

class TestRetryManagerIntegration:
    """Test RetryManager coordinating retries + circuit breaker."""

    @pytest.mark.asyncio
    async def test_execute_with_retry_respects_circuit_breaker_open(self):
        """Test execute_with_retry fails fast when circuit is OPEN."""
        manager = RetryManager()

        # Force circuit to OPEN
        manager.circuit_breaker._state = CircuitBreakerState.OPEN

        async def dummy_coro():
            return "result"

        with pytest.raises(RuntimeError, match="OPEN"):
            await manager.execute_with_retry(
                lambda: dummy_coro(),
                operation_name="test_op"
            )

    @pytest.mark.asyncio
    async def test_execute_with_retry_allows_single_attempt_in_half_open(self):
        """Test single attempt without retries in HALF_OPEN state."""
        config = RetryConfig(max_retries=5, initial_delay=0.01)
        manager = RetryManager(config=config)

        # Force circuit to HALF_OPEN
        manager.circuit_breaker._state = CircuitBreakerState.HALF_OPEN

        attempt_count = 0

        async def sometimes_fails():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                raise asyncio.TimeoutError("First attempt fails")
            return "success"

        # In HALF_OPEN, should not retry
        with pytest.raises(RuntimeError):
            await manager.execute_with_retry(
                lambda: sometimes_fails(),
                operation_name="half_open_test",
                recoverable_errors={asyncio.TimeoutError}
            )

        assert attempt_count == 1, "HALF_OPEN should allow only 1 attempt"

    @pytest.mark.asyncio
    async def test_circuit_breaker_records_success_and_failure(self):
        """Test circuit breaker records success and failure."""
        config = RetryConfig(max_retries=1, initial_delay=0.01)
        manager = RetryManager(config=config)

        # Success case
        async def successful():
            return "result"

        result = await manager.execute_with_retry(
            lambda: successful(),
            operation_name="success_op"
        )
        assert result == "result"
        assert manager.circuit_breaker._consecutive_failures == 0

        # Failure case
        async def fails():
            raise asyncio.TimeoutError("Failed")

        with pytest.raises(RuntimeError):
            await manager.execute_with_retry(
                lambda: fails(),
                operation_name="fail_op",
                recoverable_errors={asyncio.TimeoutError}
            )

        assert manager.circuit_breaker._consecutive_failures > 0


# ============================================================================
# Test Group 7: Error Classification and Recovery (3 tests)
# ============================================================================

class TestErrorClassification:
    """Test error classification for retry decisions."""

    @pytest.mark.asyncio
    async def test_timeout_error_is_recoverable(self):
        """Test that asyncio.TimeoutError triggers retry."""
        manager = RetryManager(config=RetryConfig(max_retries=1, initial_delay=0.01))

        attempt_count = 0

        async def timeout_error():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                raise asyncio.TimeoutError()
            return "recovered"

        result = await manager.execute_with_retry(
            lambda: timeout_error(),
            operation_name="timeout_test"
        )

        assert result == "recovered"
        assert attempt_count == 2

    @pytest.mark.asyncio
    async def test_connection_error_is_recoverable(self):
        """Test that ConnectionError triggers retry."""
        manager = RetryManager(config=RetryConfig(max_retries=1, initial_delay=0.01))

        attempt_count = 0

        async def connection_error():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                raise ConnectionError("Connection failed")
            return "recovered"

        result = await manager.execute_with_retry(
            lambda: connection_error(),
            operation_name="connection_test"
        )

        assert result == "recovered"
        assert attempt_count == 2

    @pytest.mark.asyncio
    async def test_value_error_is_non_recoverable(self):
        """Test that ValueError fails fast without retry."""
        manager = RetryManager()

        attempt_count = 0

        async def value_error():
            nonlocal attempt_count
            attempt_count += 1
            raise ValueError("Invalid value")

        with pytest.raises(ValueError):
            await manager.execute_with_retry(
                lambda: value_error(),
                operation_name="value_error_test"
            )

        assert attempt_count == 1, "Should not retry ValueError"


# ============================================================================
# Test Group 8: Advanced Scenarios (3 tests)
# ============================================================================

class TestAdvancedRetryScenarios:
    """Test advanced retry scenarios."""

    def test_circuit_breaker_reset(self):
        """Test manual circuit breaker reset."""
        cb = CircuitBreaker(failure_threshold=2)

        cb.record_failure()
        cb.record_failure()
        assert cb.state() == CircuitBreakerState.OPEN

        cb.reset()
        assert cb.state() == CircuitBreakerState.CLOSED
        assert cb._consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_retry_with_custom_recoverable_errors(self):
        """Test retry with custom recoverable error types."""
        custom_recoverable = {ConnectionError, ValueError}
        manager = RetryManager(config=RetryConfig(max_retries=1, initial_delay=0.01))

        attempt_count = 0

        async def custom_error():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                raise ValueError("Custom error")
            return "recovered"

        result = await manager.execute_with_retry(
            lambda: custom_error(),
            operation_name="custom_error_test",
            recoverable_errors=custom_recoverable
        )

        assert result == "recovered"
        assert attempt_count == 2

    @pytest.mark.asyncio
    async def test_concurrent_retries_with_single_circuit_breaker(self):
        """Test multiple concurrent operations sharing circuit breaker."""
        manager = RetryManager(config=RetryConfig(max_retries=1, initial_delay=0.01))

        async def operation(op_id, should_fail):
            if should_fail:
                raise asyncio.TimeoutError(f"Op {op_id} failed")
            return f"Op {op_id} success"

        # Run 3 successful and 1 failed concurrently
        tasks = [
            manager.execute_with_retry(lambda: operation(1, False), "op1"),
            manager.execute_with_retry(lambda: operation(2, True), "op2"),
            manager.execute_with_retry(lambda: operation(3, False), "op3"),
        ]

        results = []
        exception_count = 0

        for task in tasks:
            try:
                result = await task
                results.append(result)
            except RuntimeError:
                exception_count += 1

        assert len(results) >= 2, "At least 2 should succeed"
        assert exception_count >= 1, "At least 1 should fail"


# ============================================================================
# Test Group 9: CircuitBreaker Edge Cases (2 tests)
# ============================================================================

class TestCircuitBreakerEdgeCases:
    """Test edge cases in circuit breaker behavior."""

    def test_circuit_breaker_invalid_parameters(self):
        """Test circuit breaker rejects invalid parameters."""
        with pytest.raises(ValueError):
            CircuitBreaker(failure_threshold=0)

        with pytest.raises(ValueError):
            CircuitBreaker(success_threshold=-1)

        with pytest.raises(ValueError):
            CircuitBreaker(timeout=-5)

    def test_circuit_breaker_half_open_failure_reopens(self):
        """Test failure in HALF_OPEN state reopens circuit."""
        cb = CircuitBreaker(failure_threshold=1, success_threshold=1)

        # Transition to OPEN
        cb.record_failure()
        assert cb.state() == CircuitBreakerState.OPEN

        # Force to HALF_OPEN
        cb._last_open_time = datetime.now() - timedelta(seconds=100)
        assert cb.state() == CircuitBreakerState.HALF_OPEN

        # Failure in HALF_OPEN should reopen
        cb.record_failure()
        assert cb.state() == CircuitBreakerState.OPEN
