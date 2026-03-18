"""Retry logic and circuit breaker for transient SAP failures.

Provides:
    - Configurable retry policies (exponential, linear, fibonacci backoff)
    - Circuit breaker pattern (fail-fast on cascading failures)
    - Async-compatible retry decorator
    - Error classification and recovery strategies

Integrates with:
    - error_handler.ErrorCategory for transient vs permanent error classification
    - queue_manager.QueueManager for COM thread execution
    - session.Session for SAP operations

Example:
    ```python
    from sap.retry_manager import RetryManager, RetryConfig, RetryPolicy, retry_async

    # Initialize retry manager
    config = RetryConfig(max_retries=3, initial_delay=0.5, backoff_factor=2.0)
    manager = RetryManager(config)

    # Option 1: Use execute_with_retry on single operation
    result = await manager.execute_with_retry(
        session.get_field_value('VBAK-VBELN'),
        operation_name='get_field'
    )

    # Option 2: Use @retry_async decorator on methods
    @retry_async(max_retries=3, policy=RetryPolicy.EXPONENTIAL)
    async def fetch_data():
        return await session.get_field_value('VBAK-VBELN')

    result = await fetch_data()
    ```

Architecture:
    - RetryConfig stores configuration parameters
    - RetryPolicy enum defines backoff calculation strategies
    - CircuitBreaker tracks failure state (CLOSED/OPEN/HALF_OPEN)
    - RetryManager orchestrates retries and circuit breaker logic
    - @retry_async decorator wraps coroutines for transparent retry
    - All async-first design for NiceGUI integration
"""

import asyncio
import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, Type
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RetryPolicy(Enum):
    """Backoff calculation strategy for retries.

    Attributes:
        EXPONENTIAL: delay = initial_delay * (backoff_factor ^ attempt)
        LINEAR: delay = initial_delay * attempt
        FIBONACCI: delay = fibonacci(attempt) * initial_delay
    """
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIBONACCI = "fibonacci"


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Base delay in seconds between retries (default: 0.5)
        max_delay: Maximum delay cap in seconds (default: 30.0)
        backoff_factor: Multiplier for exponential backoff (default: 2.0)
        jitter: Add random jitter to delays if True (default: True)
        policy: Backoff strategy (default: EXPONENTIAL)
    """
    max_retries: int = 3
    initial_delay: float = 0.5
    max_delay: float = 30.0
    backoff_factor: float = 2.0
    jitter: bool = True
    policy: RetryPolicy = RetryPolicy.EXPONENTIAL


class CircuitBreakerState(Enum):
    """Circuit breaker states.

    Attributes:
        CLOSED: Normal operation; requests pass through
        OPEN: Too many failures; requests fail immediately
        HALF_OPEN: Testing if service recovered; allow limited requests
    """
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Implements circuit breaker pattern to prevent cascading failures.

    Transitions:
        CLOSED → OPEN: failure_threshold consecutive failures reached
        OPEN → HALF_OPEN: timeout seconds elapsed
        HALF_OPEN → CLOSED: success_threshold consecutive successes
        HALF_OPEN → OPEN: Any failure in HALF_OPEN state

    Attributes:
        failure_threshold: Failures needed to OPEN circuit (default: 5)
        success_threshold: Successes needed to close HALF_OPEN (default: 2)
        timeout: Seconds before OPEN→HALF_OPEN transition (default: 60.0)
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 60.0
    ) -> None:
        """Initialize circuit breaker.

        Args:
            failure_threshold: Consecutive failures to trip circuit (default: 5)
            success_threshold: Consecutive successes to reset (default: 2)
            timeout: Seconds in OPEN state before HALF_OPEN (default: 60)

        Raises:
            ValueError: If thresholds or timeout are invalid
        """
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if success_threshold < 1:
            raise ValueError("success_threshold must be >= 1")
        if timeout < 0:
            raise ValueError("timeout must be >= 0")

        self._state = CircuitBreakerState.CLOSED
        self._failure_threshold = failure_threshold
        self._success_threshold = success_threshold
        self._timeout = timeout

        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._last_failure_time: Optional[datetime] = None
        self._last_open_time: Optional[datetime] = None

        logger.debug(
            "CircuitBreaker initialized: failure_threshold=%d, "
            "success_threshold=%d, timeout=%.1f",
            failure_threshold,
            success_threshold,
            timeout
        )

    def state(self) -> CircuitBreakerState:
        """Get current circuit breaker state.

        Automatically transitions OPEN→HALF_OPEN if timeout expired.

        Returns:
            Current CircuitBreakerState
        """
        # Auto-transition OPEN → HALF_OPEN after timeout
        if (
            self._state == CircuitBreakerState.OPEN
            and self._last_open_time is not None
            and datetime.now() - self._last_open_time > timedelta(seconds=self._timeout)
        ):
            logger.info(
                "Circuit breaker OPEN→HALF_OPEN (timeout %.1fs elapsed)",
                self._timeout
            )
            self._state = CircuitBreakerState.HALF_OPEN
            self._consecutive_successes = 0
            self._consecutive_failures = 0

        return self._state

    def record_success(self) -> None:
        """Record a successful operation.

        Increments success counter and may transition:
            HALF_OPEN → CLOSED (if success_threshold reached)
            CLOSED → CLOSED (no change)
            OPEN → OPEN (state() manages transition)
        """
        if self.state() == CircuitBreakerState.CLOSED:
            self._consecutive_failures = 0
            logger.debug("Circuit breaker CLOSED: success recorded")

        elif self.state() == CircuitBreakerState.HALF_OPEN:
            self._consecutive_successes += 1

            if self._consecutive_successes >= self._success_threshold:
                logger.info(
                    "Circuit breaker HALF_OPEN→CLOSED "
                    "(%d successes, threshold %d)",
                    self._consecutive_successes,
                    self._success_threshold
                )
                self._state = CircuitBreakerState.CLOSED
                self._consecutive_failures = 0
                self._consecutive_successes = 0
            else:
                logger.debug(
                    "Circuit breaker HALF_OPEN: success %d/%d",
                    self._consecutive_successes,
                    self._success_threshold
                )

    def record_failure(self) -> None:
        """Record a failed operation.

        Increments failure counter and may transition:
            CLOSED → OPEN (if failure_threshold reached)
            HALF_OPEN → OPEN (immediately on failure)
        """
        self._last_failure_time = datetime.now()
        self._consecutive_successes = 0

        if self.state() == CircuitBreakerState.CLOSED:
            self._consecutive_failures += 1

            if self._consecutive_failures >= self._failure_threshold:
                logger.warning(
                    "Circuit breaker CLOSED→OPEN "
                    "(%d failures, threshold %d)",
                    self._consecutive_failures,
                    self._failure_threshold
                )
                self._state = CircuitBreakerState.OPEN
                self._last_open_time = datetime.now()
            else:
                logger.debug(
                    "Circuit breaker CLOSED: failure %d/%d",
                    self._consecutive_failures,
                    self._failure_threshold
                )

        elif self.state() == CircuitBreakerState.HALF_OPEN:
            logger.warning(
                "Circuit breaker HALF_OPEN→OPEN (failed recovery attempt)"
            )
            self._state = CircuitBreakerState.OPEN
            self._last_open_time = datetime.now()
            self._consecutive_failures = 1

    def is_open(self) -> bool:
        """Check if circuit is OPEN (fail-fast).

        Returns:
            True if OPEN or will transition to OPEN, False otherwise
        """
        return self.state() == CircuitBreakerState.OPEN

    def reset(self) -> None:
        """Reset circuit breaker to CLOSED state."""
        logger.info("Circuit breaker manually reset to CLOSED")
        self._state = CircuitBreakerState.CLOSED
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._last_failure_time = None
        self._last_open_time = None


class RetryManager:
    """Manages retry logic and circuit breaking for SAP operations.

    Coordinates exponential backoff with circuit breaker to handle:
        - Transient failures (network timeouts, temporary unavailability)
        - Cascading failures (rapid-fire requests to downed service)
        - Partial recovery (HALF_OPEN state with limited retries)

    Attributes:
        config: RetryConfig with policy and timing parameters
        circuit_breaker: CircuitBreaker for cascading failure protection
    """

    def __init__(
        self,
        config: Optional[RetryConfig] = None,
        circuit_breaker: Optional[CircuitBreaker] = None
    ) -> None:
        """Initialize retry manager.

        Args:
            config: RetryConfig instance (default: RetryConfig())
            circuit_breaker: CircuitBreaker instance (default: CircuitBreaker())
        """
        self.config = config or RetryConfig()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()

        logger.debug(
            "RetryManager initialized: policy=%s, max_retries=%d, "
            "initial_delay=%.2fs, backoff_factor=%.1f, jitter=%s",
            self.config.policy.value,
            self.config.max_retries,
            self.config.initial_delay,
            self.config.backoff_factor,
            self.config.jitter
        )

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number.

        Args:
            attempt: Attempt number (0-based)

        Returns:
            Delay in seconds, capped at max_delay
        """
        if attempt < 0:
            return 0.0

        if self.config.policy == RetryPolicy.EXPONENTIAL:
            delay = self.config.initial_delay * (
                self.config.backoff_factor ** attempt
            )

        elif self.config.policy == RetryPolicy.LINEAR:
            delay = self.config.initial_delay * (attempt + 1)

        elif self.config.policy == RetryPolicy.FIBONACCI:
            # Fibonacci: 1, 1, 2, 3, 5, 8, ...
            fib = self._fibonacci(attempt + 1)
            delay = self.config.initial_delay * fib

        else:
            delay = self.config.initial_delay

        # Cap at max_delay
        delay = min(delay, self.config.max_delay)

        # Add optional jitter (±10%)
        if self.config.jitter:
            jitter_factor = random.uniform(0.9, 1.1)
            delay = delay * jitter_factor

        return delay

    @staticmethod
    def _fibonacci(n: int) -> int:
        """Compute nth Fibonacci number.

        Args:
            n: Position (1-based)

        Returns:
            Fibonacci(n)
        """
        if n <= 1:
            return 1
        a, b = 1, 1
        for _ in range(n - 1):
            a, b = b, a + b
        return a

    async def execute_with_retry(
        self,
        coro_func: Callable[[], Awaitable[Any]],
        operation_name: str = "SAP operation",
        recoverable_errors: Optional[Set[Type[Exception]]] = None
    ) -> Any:
        """Execute coroutine with retries and circuit breaker.

        Behavior:
            - If circuit is OPEN: raises RuntimeError immediately
            - If circuit is HALF_OPEN: allows one attempt with no retries
            - If circuit is CLOSED: retries with backoff on recoverable errors

        Args:
            coro_func: Callable that returns an Awaitable (e.g., lambda: func())
            operation_name: Name for logging (default: "SAP operation")
            recoverable_errors: Exception types to retry on (default: timeout + connection errors)

        Returns:
            Result of awaitable if successful

        Raises:
            RuntimeError: If circuit is OPEN or max retries exceeded
            Exception: Original exception if non-recoverable

        Example:
            ```python
            try:
                result = await manager.execute_with_retry(
                    lambda: session.get_field_value('VBAK-VBELN'),
                    operation_name='get_order_number'
                )
            except RuntimeError as e:
                if "OPEN" in str(e):
                    print("SAP service temporarily unavailable")
                else:
                    print(f"All retries exhausted: {e}")
            ```
        """
        # Default recoverable errors: timeouts and connection issues
        if recoverable_errors is None:
            recoverable_errors = {
                asyncio.TimeoutError,
                ConnectionError,
                BrokenPipeError,
                TimeoutError,
                OSError
            }

        # Check circuit breaker state
        if self.circuit_breaker.is_open():
            msg = (
                f"Operation '{operation_name}' failed: Circuit breaker is OPEN. "
                f"SAP service appears unavailable. Retry in {self.circuit_breaker._timeout}s."
            )
            logger.error("CircuitBreaker OPEN: %s", msg)
            raise RuntimeError(msg)

        # In HALF_OPEN state: single attempt, no retries
        state = self.circuit_breaker.state()
        max_attempts = (
            1 if state == CircuitBreakerState.HALF_OPEN
            else self.config.max_retries + 1  # +1 for initial attempt
        )

        last_exception: Optional[Exception] = None

        for attempt in range(max_attempts):
            try:
                logger.debug(
                    "Executing '%s' (attempt %d/%d)",
                    operation_name,
                    attempt + 1,
                    max_attempts
                )

                # Call coro_func to create a fresh coroutine for each attempt
                coro = coro_func()
                result = await asyncio.wait_for(coro, timeout=None)

                # Success: record and return
                self.circuit_breaker.record_success()
                logger.debug(
                    "Operation '%s' succeeded on attempt %d",
                    operation_name,
                    attempt + 1
                )
                return result

            except Exception as e:
                last_exception = e
                is_recoverable = any(isinstance(e, error_type) for error_type in recoverable_errors)

                # Non-recoverable error: fail immediately
                if not is_recoverable:
                    logger.error(
                        "Non-recoverable error in '%s': %s",
                        operation_name,
                        type(e).__name__,
                        exc_info=True
                    )
                    self.circuit_breaker.record_failure()
                    raise

                # Last attempt: record failure and raise
                if attempt >= max_attempts - 1:
                    logger.error(
                        "All %d attempts exhausted for '%s': %s",
                        max_attempts,
                        operation_name,
                        e
                    )
                    self.circuit_breaker.record_failure()
                    raise RuntimeError(
                        f"Failed after {max_attempts} attempts: {type(e).__name__}: {e}"
                    )

                # Intermediate failure: calculate backoff
                delay = self._calculate_delay(attempt)
                logger.warning(
                    "Transient error in '%s' (attempt %d/%d): %s. "
                    "Retrying in %.2fs",
                    operation_name,
                    attempt + 1,
                    max_attempts,
                    type(e).__name__,
                    delay
                )

                # Wait before retry
                await asyncio.sleep(delay)

        # Should not reach here, but fail-safe
        if last_exception:
            self.circuit_breaker.record_failure()
            raise last_exception


def retry_async(
    max_retries: int = 3,
    policy: RetryPolicy = RetryPolicy.EXPONENTIAL,
    initial_delay: float = 0.5,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    recoverable_errors: Optional[Set[Type[Exception]]] = None
) -> Callable:
    """Decorator for automatic async retry with exponential backoff.

    Wraps an async function to automatically retry on transient failures
    using the specified backoff policy.

    Args:
        max_retries: Maximum number of retries (default: 3)
        policy: RetryPolicy for backoff calculation (default: EXPONENTIAL)
        initial_delay: Initial delay in seconds (default: 0.5)
        max_delay: Maximum delay cap in seconds (default: 30.0)
        backoff_factor: Exponential backoff multiplier (default: 2.0)
        jitter: Add random jitter to delays (default: True)
        recoverable_errors: Exception types to retry on (default: timeout + connection)

    Returns:
        Decorator function

    Raises:
        ValueError: If parameters invalid

    Example:
        ```python
        @retry_async(max_retries=5, policy=RetryPolicy.EXPONENTIAL)
        async def get_order_number():
            return await session.get_field_value('VBAK-VBELN')

        order_id = await get_order_number()
        ```
    """
    if max_retries < 0:
        raise ValueError("max_retries must be >= 0")
    if initial_delay < 0:
        raise ValueError("initial_delay must be >= 0")
    if max_delay < 0:
        raise ValueError("max_delay must be >= 0")
    if backoff_factor < 1.0:
        raise ValueError("backoff_factor must be >= 1.0")

    config = RetryConfig(
        max_retries=max_retries,
        initial_delay=initial_delay,
        max_delay=max_delay,
        backoff_factor=backoff_factor,
        jitter=jitter,
        policy=policy
    )
    manager = RetryManager(config=config)

    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        """Inner decorator function."""

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Wrapper that executes func with retry logic."""
            # Pass a callable that creates a fresh coroutine on each retry
            return await manager.execute_with_retry(
                lambda: func(*args, **kwargs),
                operation_name=f"{func.__module__}.{func.__name__}",
                recoverable_errors=recoverable_errors
            )

        return wrapper

    return decorator
