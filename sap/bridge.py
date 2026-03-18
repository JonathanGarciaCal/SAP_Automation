"""COM worker thread and queue manager.

Manages the dedicated Single-Threaded Apartment (STA) thread required for
SAP COM operations. Implements the command queue pattern to decouple asyncio
main thread from blocking COM calls.

Architecture:
    Main thread (asyncio):
        - Creates Command objects
        - Puts Command on queue
        - Awaits future via loop.call_soon_threadsafe()

    COM worker thread:
        - Calls pythoncom.CoInitialize()
        - Consumes queue in while loop
        - Executes command, resolves future
        - Catches exceptions, returns errors via future

Example:
    ```python
    bridge = SAPBridge()
    bridge.start()
    
    # Bridge provides queue_manager for command execution
    result = bridge.queue_manager.call_method(obj, 'method_name', *args, **kwargs)
    
    bridge.stop()
    ```

CRITICAL CONSTRAINT:
    - No COM objects are ever passed on the queue
    - Only primitive types (str, int, bool, list, dict) on the queue
    - COM objects must stay in the worker thread
    - All access to COM objects is serialized through the queue
"""

from typing import Any, Dict, Optional, Callable
import threading
import queue
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

try:
    import win32com.client  # type: ignore
except ImportError:  # pragma: no cover - handled at runtime on Windows deployments
    win32com = None


class CommandStatus(Enum):
    """Status of a command execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class Command:
    """COM command to execute on worker thread.
    
    This class carries only primitive types across thread boundaries.
    Never put COM objects in args/kwargs.
    
    Attributes:
        id: Unique command ID (UUID)
        method: Method name or dotted path (e.g., 'GuiSession.FindById')
        args: Positional arguments (primitives only: str, int, bool, dict, list)
        kwargs: Keyword arguments (primitives only)
        timeout_sec: Command timeout in seconds (default: 30)
        callback: Optional callback to invoke on completion
        created_at: Timestamp when command was created
        status: Current status of the command
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    method: str = ""
    args: list = field(default_factory=list)
    kwargs: dict = field(default_factory=dict)
    timeout_sec: float = 30.0
    callback: Optional[Callable] = None
    created_at: float = field(default_factory=time.time)
    status: CommandStatus = CommandStatus.PENDING
    
    def __post_init__(self) -> None:
        """Validate command has non-empty method name."""
        if not self.method:
            raise ValueError("Command.method cannot be empty")


@dataclass
class CommandResponse:
    """Response from COM worker thread execution.
    
    Attributes:
        command_id: ID of the command that was executed
        result: Command result (or None if error occurred)
        error: Error dict with code, message, traceback (or None if success)
        elapsed_ms: Time to execute command in milliseconds
        status: Final status of command execution
    """
    command_id: str
    result: Any = None
    error: Optional[Dict[str, str]] = None
    elapsed_ms: float = 0.0
    status: CommandStatus = CommandStatus.COMPLETED


class SAPBridge:
    """Singleton manager for COM worker thread.
    
    Provides thread-safe interface to enqueue COM commands and retrieve results.
    Handles all COM initialization and threading.
    
    Attributes:
        _worker_thread: Dedicated COM worker thread
        _queue: Command queue
        _running: Flag indicating if worker thread is active
        _metrics: Metrics tracking (queue depth, latency)
        _lock: Threading lock for state changes
    """
    
    _instance: Optional["SAPBridge"] = None
    _lock: threading.Lock = threading.Lock()
    
    def __new__(cls) -> "SAPBridge":
        """Ensure singleton pattern - only one SAPBridge per process."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        """Initialize bridge (idempotent on repeated calls)."""
        if hasattr(self, "_initialized"):
            return
        
        self._worker_thread: Optional[threading.Thread] = None
        self._queue: queue.Queue = queue.Queue()
        self._result_queue: queue.Queue = queue.Queue()
        self._running: bool = False
        self._shutdown_event: threading.Event = threading.Event()
        self._metrics: Dict[str, Any] = {
            "commands_processed": 0,
            "total_time_ms": 0.0,
            "errors": 0,
            "queue_depth": 0,
            "max_queue_depth": 0,
        }
        self._initialized: bool = True
        logger.debug("SAPBridge initialized")
    
    def start(self) -> None:
        """Start the COM worker thread.
        
        Creates and starts a new worker thread that will initialize COM
        and begin processing commands from the queue.
        
        Raises:
            RuntimeError: If worker thread is already running
        """
        if self._running:
            logger.warning("SAPBridge worker thread already running")
            return
        
        self._shutdown_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="SAPBridgeWorker",
            daemon=False
        )
        self._worker_thread.start()
        self._running = True
        logger.info("SAPBridge worker thread started (thread_id=%s)", self._worker_thread.ident)
    
    def stop(self, timeout_sec: float = 5.0) -> None:
        """Stop the COM worker thread gracefully.
        
        Signals the worker thread to stop and waits for it to exit.
        
        Args:
            timeout_sec: Time to wait for thread to stop (default: 5 seconds)
        
        Raises:
            RuntimeError: If worker thread fails to stop within timeout
        """
        if not self._running:
            logger.debug("SAPBridge worker thread not running, skipping stop")
            return
        
        logger.info("Stopping SAPBridge worker thread")
        self._shutdown_event.set()
        
        if self._worker_thread:
            self._worker_thread.join(timeout=timeout_sec)
            if self._worker_thread.is_alive():
                logger.error("SAPBridge worker thread did not stop within %s seconds", timeout_sec)
                raise RuntimeError(f"Worker thread did not stop within {timeout_sec}s")
        
        self._running = False
        logger.info("SAPBridge worker thread stopped")
    
    def is_running(self) -> bool:
        """Check if worker thread is running.
        
        Returns:
            True if worker thread is active, False otherwise
        """
        return self._running and self._worker_thread is not None and self._worker_thread.is_alive()
    
    def enqueue_command(self, command: Command) -> CommandResponse:
        """Enqueue a command and wait for result.
        
        Blocks until the command completes or times out.
        
        Args:
            command: Command to execute
        
        Returns:
            CommandResponse with result or error
        
        Raises:
            RuntimeError: If worker thread is not running
            queue.Full: If queue is full (should not happen with unlimited queue)
        """
        if not self.is_running():
            raise RuntimeError("Worker thread is not running")
        
        # Validate command only has primitives
        self._validate_command_primitives(command)
        
        # Track metrics
        self._metrics["queue_depth"] = self._queue.qsize()
        self._metrics["max_queue_depth"] = max(
            self._metrics["max_queue_depth"],
            self._metrics["queue_depth"]
        )
        
        command.status = CommandStatus.PENDING
        self._queue.put(command)
        
        # Wait for result
        try:
            response = self._result_queue.get(timeout=command.timeout_sec)
            return response
        except queue.Empty:
            logger.error("Command %s timed out after %s seconds", command.id, command.timeout_sec)
            return CommandResponse(
                command_id=command.id,
                error={"code": "TIMEOUT", "message": f"Command timed out after {command.timeout_sec}s"},
                status=CommandStatus.TIMEOUT
            )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get bridge metrics.
        
        Returns:
            Dict with metrics: commands_processed, total_time_ms, errors, queue_depth, max_queue_depth
        """
        return self._metrics.copy()
    
    def health_check(self) -> bool:
        """Check worker thread health.
        
        Returns:
            True if worker thread is running and responsive
        """
        return self.is_running()
    
    @staticmethod
    def _validate_command_primitives(command: Command) -> None:
        """Validate that command args/kwargs contain only primitives.
        
        Raises:
            TypeError: If non-primitive types found in args/kwargs
        """
        allowed_types = (str, int, float, bool, type(None), dict, list, tuple)
        
        for arg in command.args:
            if not isinstance(arg, allowed_types):
                raise TypeError(f"Argument {arg} is type {type(arg).__name__}, only primitives allowed")
        
        for key, value in command.kwargs.items():
            if not isinstance(value, allowed_types):
                raise TypeError(f"Kwarg {key}={value} is type {type(value).__name__}, only primitives allowed")
    
    def _worker_loop(self) -> None:
        """Worker thread main loop (runs on worker thread, not main thread).
        
        Initializes COM, processes commands from queue, and resolves futures.
        """
        try:
            # Initialize COM in worker thread
            try:
                import pythoncom  # type: ignore
            except ImportError:
                logger.error("pythoncom not available - ensure pywin32 is installed")
                return
            
            pythoncom.CoInitialize()  # type: ignore
            logger.info("COM initialized on worker thread")
        except Exception as e:
            logger.error("Failed to initialize COM: %s", e)
            return
        
        try:
            while not self._shutdown_event.is_set():
                try:
                    # Wait for command with timeout (allows shutdown signal to be checked)
                    command = self._queue.get(timeout=1.0)
                    
                    if command is None:  # Sentinel value for shutdown
                        break
                    
                    self._process_command(command)
                
                except queue.Empty:
                    # Timeout is normal - allows periodic shutdown check
                    continue
                except Exception as e:
                    logger.error("Unexpected error in worker loop: %s", e, exc_info=True)
        
        finally:
            # Cleanup COM
            try:
                import pythoncom  # type: ignore
                pythoncom.CoUninitialize()  # type: ignore
                logger.info("COM uninitialized on worker thread")
            except Exception as e:
                logger.error("Error during COM cleanup: %s", e)
    
    def _process_command(self, command: Command) -> None:
        """Process a single command.
        
        Args:
            command: Command to process
        """
        start_time = time.time()
        command.status = CommandStatus.RUNNING
        response: Optional[CommandResponse] = None
        
        try:
            result = self._execute_command(command)
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            response = CommandResponse(
                command_id=command.id,
                result=result,
                status=CommandStatus.COMPLETED,
                elapsed_ms=elapsed_ms
            )
            
            self._metrics["commands_processed"] += 1
            self._metrics["total_time_ms"] += elapsed_ms
            
            logger.debug("Command %s completed in %.1f ms", command.id, elapsed_ms)
            
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            import traceback
            logger.error("Command %s failed: %s", command.id, e, exc_info=True)
            
            response = CommandResponse(
                command_id=command.id,
                error={
                    "code": "EXECUTION_ERROR",
                    "message": str(e),
                    "traceback": traceback.format_exc()
                },
                status=CommandStatus.FAILED,
                elapsed_ms=elapsed_ms
            )
            
            self._metrics["errors"] += 1
        
        finally:
            if response is not None:
                # Invoke callback if provided
                if command.callback:
                    try:
                        command.callback(response)
                    except Exception as e:
                        logger.error("Error in command callback: %s", e, exc_info=True)
                
                # Send result back to caller
                self._result_queue.put(response)

    def _execute_command(self, command: Command) -> Any:
        """Execute a supported SAP GUI command on the COM worker thread.

        Args:
            command: Command with method and kwargs to execute

        Returns:
            Primitive result from SAP COM call

        Raises:
            RuntimeError: If COM is unavailable, no active SAP session exists, or method is unsupported
        """
        method = command.method

        if method.startswith("GuiSession."):
            session = self._get_active_gui_session()

            if method == "GuiSession.StartTransaction":
                transaction_code = command.kwargs.get("transaction_code")
                if not transaction_code:
                    raise ValueError("transaction_code is required")
                session.StartTransaction(str(transaction_code))
                return None

            if method == "GuiSession.GoBack":
                # SAP Back key (F3)
                session.SendVKey(3)
                return None

            if method == "GuiSession.GoHome":
                # Prefer direct command field navigation to SAP Easy Access.
                okcode = session.FindById("wnd[0]/tbar[0]/okcd")
                okcode.Text = "/n"
                session.FindById("wnd[0]").SendVKey(0)
                return None

            if method == "GuiSession.GetCurrentScreen":
                window = session.FindById("wnd[0]")
                return str(window.Id)

            if method == "GuiSession.EndSession":
                # Graceful close for current session.
                try:
                    session.EndTransaction()
                except Exception:
                    session.FindById("wnd[0]").Close()
                return None

        # Keep compatibility with existing placeholder behavior for unimplemented methods.
        return None

    def _get_active_gui_session(self) -> Any:
        """Resolve the first active SAP GUI session from COM.

        Returns:
            Active GuiSession COM object

        Raises:
            RuntimeError: If SAP GUI scripting engine or an active session is unavailable
        """
        if not win32com:
            raise RuntimeError("win32com is not available")

        sap_gui_auto = win32com.client.GetObject("SAPGUI")
        if sap_gui_auto is None:
            raise RuntimeError("SAP GUI COM object not available")

        app = sap_gui_auto.GetScriptingEngine
        if app is None or app.Children.Count == 0:
            raise RuntimeError("No active SAP connections found")

        connection = app.Children(0)
        if connection.Children.Count == 0:
            raise RuntimeError("No active SAP sessions found")

        return connection.Children(0)
