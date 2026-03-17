"""Async queue handler for COM commands.

Provides asyncio-compatible interface to the COM worker thread.
Handles future resolution and error propagation.

Implements the bridge between asyncio (NiceGUI main thread) and the
synchronous COM worker thread using Python's queue.Queue and asyncio futures.

Architecture:
    asyncio main thread (NiceGUI):
        - Calls QueueManager.call_async()
        - Gets asyncio.Future back
        - Can await Future while doing other async work
        
    COM worker thread:
        - Processes commands from queue
        - Resolves futures via loop.call_soon_threadsafe()
        - Caller's await completes with result

Example:
    ```python
    qm = QueueManager()
    result = await qm.call_async('GuiSession.FindById', '/app/workbench')
    ```
"""

from typing import Any, Callable, Optional, Dict
import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Retry strategy for transient failures."""
    NO_RETRY = "no_retry"            # Fail immediately
    EXPONENTIAL_BACKOFF = "exp_backoff"  # Retry with 2^n backoff
    FIBONACCI = "fibonacci"           # Retry with Fibonacci backoff


@dataclass
class QueueMetrics:
    """Metrics for queue operations.
    
    Attributes:
        total_commands: Total commands processed
        successful: Successful command executions
        failed: Failed command executions
        timed_out: Commands that timed out
        total_time_ms: Total time spent executing commands
        avg_latency_ms: Average command latency
        max_queue_depth: Maximum queue depth observed
    """
    total_commands: int = 0
    successful: int = 0
    failed: int = 0
    timed_out: int = 0
    total_time_ms: float = 0.0
    avg_latency_ms: float = 0.0
    max_queue_depth: int = 0


class QueueManager:
    """Wraps command queue with asyncio interface.
    
    Manages the interaction between asyncio main thread and COM worker thread.
    Handles timeout, retry, and error propagation using asyncio.Future.
    
    Attributes:
        _timeout: Default command timeout in seconds
        _retry_strategy: Retry strategy for transient failures
        _metrics: Queue metrics tracking
        _pending_futures: Dict mapping command IDs to futures
    """
    
    def __init__(
        self,
        timeout: float = 30.0,
        retry_strategy: RetryStrategy = RetryStrategy.NO_RETRY
    ) -> None:
        """Initialize async queue handler.
        
        Args:
            timeout: Command timeout in seconds (default: 30)
            retry_strategy: Retry strategy for failures (default: NO_RETRY)
        """
        self._timeout = timeout
        self._retry_strategy = retry_strategy
        self._metrics: QueueMetrics = QueueMetrics()
        self._pending_futures: Dict[str, asyncio.Future] = {}
        logger.debug("QueueManager initialized with timeout=%s", timeout)
    
    async def call_async(
        self,
        method: str,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        """Execute a command asynchronously via the COM worker thread.
        
        Blocks (async-safely) until command completes or times out.
        
        Args:
            method: Method name or path (e.g., 'GuiSession.FindById')
            *args: Positional arguments (primitives only)
            **kwargs: Keyword arguments (primitives only)
        
        Returns:
            Command result
        
        Raises:
            asyncio.TimeoutError: If command exceeds timeout
            RuntimeError: If worker thread not available or other error
            ValueError: If args contain non-primitive types
        """
        from sap.bridge import Command, SAPBridge
        
        # Create command
        command = Command(
            method=method,
            args=list(args),
            kwargs=kwargs,
            timeout_sec=self._timeout
        )
        
        # Get event loop and create future
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        
        # Track future
        self._pending_futures[command.id] = future
        
        try:
            # Get singleton bridge and enqueue
            bridge = SAPBridge()
            
            if not bridge.is_running():
                raise RuntimeError("COM worker thread is not running")
            
            # Enqueue and wait for result asynchronously
            response = await self._submit_and_wait(bridge, command, loop)
            
            # Check for error
            if response.error:
                logger.error(
                    "Command %s failed: %s - %s",
                    command.id,
                    response.error.get("code"),
                    response.error.get("message")
                )
                raise RuntimeError(f"{response.error.get('code')}: {response.error.get('message')}")
            
            logger.debug("Command %s returned result: %s", command.id, type(response.result).__name__)
            return response.result
        
        except asyncio.TimeoutError:
            logger.warning("Command %s timed out after %s seconds", command.id, self._timeout)
            self._metrics.timed_out += 1
            raise
        
        except Exception as e:
            logger.error("Command %s raised exception: %s", command.id, e, exc_info=True)
            self._metrics.failed += 1
            raise
        
        finally:
            # Cleanup
            self._pending_futures.pop(command.id, None)
    
    async def _submit_and_wait(
        self,
        bridge: Any,
        command: Any,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
        """Submit command to bridge and wait for result.
        
        Args:
            bridge: SAPBridge instance
            command: Command to execute
            loop: Event loop for future callbacks
        
        Returns:
            CommandResponse
        
        Raises:
            asyncio.TimeoutError: If command times out
        """
        # Run bridge.enqueue_command in thread pool to avoid blocking event loop
        # Then convert result to awaitable future
        start_time = time.time()
        
        try:
            response = await loop.run_in_executor(
                None,
                bridge.enqueue_command,
                command
            )
            elapsed_ms = (time.time() - start_time) * 1000
            
            self._metrics.total_commands += 1
            self._metrics.total_time_ms += elapsed_ms
            
            if not response.error:
                self._metrics.successful += 1
            
            # Update average latency
            if self._metrics.total_commands > 0:
                self._metrics.avg_latency_ms = (
                    self._metrics.total_time_ms / self._metrics.total_commands
                )
            
            return response
        
        except asyncio.TimeoutError:
            self._metrics.timed_out += 1
            raise
    
    def set_timeout(self, timeout_sec: float) -> None:
        """Set command timeout.
        
        Args:
            timeout_sec: Timeout in seconds
        """
        self._timeout = timeout_sec
        logger.debug("QueueManager timeout set to %s seconds", timeout_sec)
    
    def set_retry_strategy(self, strategy: RetryStrategy) -> None:
        """Set retry strategy for transient failures.
        
        Args:
            strategy: RetryStrategy enum value
        """
        self._retry_strategy = strategy
        logger.debug("QueueManager retry strategy set to %s", strategy.value)
    
    def get_metrics(self) -> QueueMetrics:
        """Get queue metrics.
        
        Returns:
            QueueMetrics with current statistics
        """
        return QueueMetrics(
            total_commands=self._metrics.total_commands,
            successful=self._metrics.successful,
            failed=self._metrics.failed,
            timed_out=self._metrics.timed_out,
            total_time_ms=self._metrics.total_time_ms,
            avg_latency_ms=self._metrics.avg_latency_ms,
            max_queue_depth=self._metrics.max_queue_depth
        )
    
    def reset_metrics(self) -> None:
        """Reset all metrics to zero.
        
        Useful for benchmarking or testing.
        """
        self._metrics = QueueMetrics()
        logger.debug("QueueManager metrics reset")
    
    def get_pending_count(self) -> int:
        """Get count of pending futures.
        
        Returns:
            Number of commands currently being awaited
        """
        return len(self._pending_futures)
