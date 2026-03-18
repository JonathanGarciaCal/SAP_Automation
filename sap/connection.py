"""SAP connection wrapper.

Provides a high-level interface to establish and manage SAP GUI connections
via COM scripting. Wraps the SAP Logon COM object and manages session lifecycle.

Architecture:
    - Reads SAP Logon file path from config
    - Creates SAPLogon.Application COM object (on worker thread)
    - Opens connection via COM (on worker thread)
    - Wraps connection in Session object for user interaction

Example:
    ```python
    from config import get_config
    from sap.connection import SAPConnection
    
    config = get_config()
    conn = SAPConnection(config.sap)
    session = await conn.open(system_id='D00', use_sso=True)
    await session.start_transaction('VA01')
    ```

CRITICAL CONSTRAINT:
    - All COM operations run on the worker thread, not asyncio main thread
    - Connection object itself is a lightweight wrapper
    - Session is placeholder for Phase 1; Phase 2 will add actual methods
    - Only SSO authentication is supported; credential-based login is disabled
"""

from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field
import logging
import asyncio
import time
import subprocess
import os

from config import SAPConfig
from sap.queue_manager import QueueManager
from sap.bridge import SAPBridge
from sap.session_manager import SAP_Session_Manager

logger = logging.getLogger(__name__)


class SAPConnection:
    """Manages SAP GUI connection via COM scripting.
    
    Handles SSO-only connection, attach-first strategy, and session lifecycle.
    All COM operations are delegated to the worker thread.
    
    Attributes:
        config: SAP connection configuration
        _queue_manager: Queue manager for async COM operations
        _sap_logon: Reference to SAP Logon COM object (on worker thread)
        _session: Current active session (or None)
        _connected: Flag indicating if connected
        _connection_pool: Dict of available connections (for pooling)
        _heartbeat_task: Asyncio task for keep-alive
        _last_activity: Timestamp of last activity
        _last_connection_diagnostics: Dict tracking connection stage, error, and attempted candidates
    """
    
    def __init__(self, config: SAPConfig) -> None:
        """Initialize SAP connection wrapper.
        
        Args:
            config: SAPConfig with logon_path, client, lang
        
        Raises:
            ValueError: If required config fields are missing
        """
        if not config.logon_path:
            raise ValueError("SAP logon_path must be configured")
        
        self.config = config
        self._queue_manager = QueueManager(timeout=30.0)
        self._sap_logon: Optional[Any] = None
        self._session: Optional[Any] = None
        self._connected: bool = False
        self._connection_pool: Dict[str, Any] = {}
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._last_activity: float = time.time()
        self._last_connection_diagnostics: Dict[str, Any] = {}
        
        logger.debug("SAPConnection initialized (SSO-only mode) with client=%s, lang=%s", config.client, config.lang)
    
    async def open(self, system_id: str, use_sso: bool = True) -> "Session":
        """Open SAP GUI connection using SSO authentication with attach-first strategy.
        
        Attempts to attach to an already-running SAP GUI instance before launching
        a new one. Tracks connection stage and errors for diagnostics.
        
        Args:
            system_id: SAP system ID (e.g., 'D00', 'P00')
            use_sso: Must be True (only SSO is supported)
        
        Returns:
            Session object for interacting with SAP
        
        Raises:
            RuntimeError: If connection fails
            ValueError: If use_sso=False (credential-based login not supported)
        """
        logger.info("Opening SAP connection to system %s (SSO-only)", system_id)
        
        # Enforce SSO-only mode
        if not use_sso:
            raise ValueError("Only SSO mode is supported")
        
        # Initialize diagnostics
        self._last_connection_diagnostics = {
            "system_id": system_id,
            "stage": None,
            "error": None,
            "attach_first_error": None,
            "attempted_candidates": []
        }
        
        try:
            # Stage 1: Attach-first probe
            self._last_connection_diagnostics["stage"] = "attach_first_check"
            logger.debug("Stage 1/3: Attempting to attach to running SAP GUI instance")
            
            if await self._probe_running_sap(system_id):
                logger.info("Attached to existing SAP GUI instance for system %s", system_id)
                self._connected = True
                self._last_activity = time.time()
                self._session = Session(self._queue_manager, system_id=system_id)
                self._start_heartbeat()
                return self._session
            else:
                self._last_connection_diagnostics["attach_first_error"] = "No running SAP GUI instance found"
                logger.debug("No running SAP instance; will launch new one")
            
            # Stage 2: Launcher resolution and launch
            self._last_connection_diagnostics["stage"] = "launcher_resolution"
            logger.debug("Stage 2/3: Resolving SAP launcher candidates")
            launcher_path = self._resolve_sap_launcher_candidates()
            
            if not launcher_path:
                error_msg = "No suitable SAP launcher found in PATH"
                self._last_connection_diagnostics["error"] = error_msg
                raise RuntimeError(error_msg)
            
            logger.debug("Launching SAP GUI via %s", launcher_path)
            await self._launch_sap_gui(launcher_path, system_id)
            
            # Stage 3: Waiting for SAP to become active
            self._last_connection_diagnostics["stage"] = "waiting_for_active_session"
            logger.debug("Stage 3/3: Waiting for SAP session to become active")
            
            # Start bridge if needed
            bridge = SAPBridge()
            if not bridge.is_running():
                logger.info("Starting COM worker thread")
                bridge.start()
                await asyncio.sleep(0.5)
            
            # Create Session stub (Phase 2 will add actual COM calls)
            self._sap_logon = object()  # Placeholder
            self._connected = True
            self._last_activity = time.time()
            self._session = Session(self._queue_manager, system_id=system_id)
            self._start_heartbeat()
            
            logger.info("SAP connection opened successfully for system %s", system_id)
            self._last_connection_diagnostics["stage"] = "connected"
            return self._session
        
        except Exception as e:
            logger.error("Failed to open SAP connection: %s", e, exc_info=True)
            self._connected = False
            if self._last_connection_diagnostics["error"] is None:
                self._last_connection_diagnostics["error"] = str(e)
            self._last_connection_diagnostics["stage"] = "connection_failed"
            raise RuntimeError(f"Failed to open SAP connection at stage '{self._last_connection_diagnostics['stage']}': {e}")
    
    async def close(self) -> None:
        """Close SAP connection gracefully.
        
        Logs out, releases session, and stops heartbeat.
        
        Raises:
            RuntimeError: If disconnection fails
        """
        logger.info("Closing SAP connection")
        
        try:
            # Cancel heartbeat
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
                try:
                    await self._heartbeat_task
                except asyncio.CancelledError:
                    pass
            
            # Close session
            if self._session:
                await self._session.close()
                self._session = None
            
            self._connected = False
            logger.info("SAP connection closed successfully")
        
        except Exception as e:
            logger.error("Error closing SAP connection: %s", e)
            raise RuntimeError(f"Failed to close SAP connection: {e}")
    
    def is_connected(self) -> bool:
        """Check if connection is active.
        
        Returns:
            True if connected, False otherwise
        """
        return self._connected
    
    async def health_check(self) -> bool:
        """Perform health check on connection.
        
        Useful for monitoring connection status.
        
        Returns:
            True if connection is healthy, False otherwise
        """
        if not self._connected:
            return False
        
        try:
            # In Phase 2, would call actual SAP method
            # For now, just check if within timeout
            idle_time = time.time() - self._last_activity
            return idle_time < 300.0  # 5 minute timeout
        
        except Exception as e:
            logger.error("Health check failed: %s", e)
            return False
    
    def get_queue_manager(self) -> QueueManager:
        """Get the queue manager for this connection.
        
        Returns:
            QueueManager instance
        """
        return self._queue_manager
    
    def get_last_connection_diagnostics(self) -> Dict[str, Any]:
        """Get diagnostics from the last connection attempt.
        
        Returns:
            Dict with keys: system_id, stage, error, attach_first_error, attempted_candidates
            - stage: One of 'attach_first_check', 'launcher_resolution', 'waiting_for_active_session', 'connected', 'connection_failed'
            - error: Error message if connection failed
            - attach_first_error: Reason why attach-first probe failed (if applicable)
            - attempted_candidates: List of launcher paths tried
        """
        return self._last_connection_diagnostics.copy()
    
    def _resolve_sap_launcher_candidates(self) -> Optional[str]:
        """Resolve SAP launcher executable path.
        
        Tries multiple candidates in order of preference:
        1. sapshcut.exe (newer SAP GUI)
        2. saplogon.exe (classic SAP Logon)
        
        Returns:
            Path to first found launcher, or None if no launchers found
        """
        candidates = ["sapshcut.exe", "saplogon.exe"]
        self._last_connection_diagnostics["attempted_candidates"] = []
        
        for candidate in candidates:
            logger.debug("Attempting to resolve launcher: %s", candidate)
            self._last_connection_diagnostics["attempted_candidates"].append(candidate)
            
            try:
                # Try to find in PATH or common SAP locations
                result = subprocess.run(
                    f"where {candidate}",
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    path = result.stdout.strip().split('\n')[0]
                    logger.debug("Found %s at %s", candidate, path)
                    return path
            except Exception as e:
                logger.debug("Failed to find %s: %s", candidate, e)
        
        logger.warning("No SAP launcher candidates found in PATH")
        return None
    
    async def _probe_running_sap(self, system_id: str) -> bool:
        """Probe for already-running SAP GUI instance.
        
        Attach-first strategy: check if SAP GUI is already running before launching.
        
        Args:
            system_id: SAP system ID
        
        Returns:
            True if running SAP GUI instance found, False otherwise
        """
        try:
            logger.debug("Probing for running SAP GUI instance (system=%s)", system_id)
            
            # In Phase 2, this will use COM to:
            # 1. Try win32com.client.GetObject("SAPLOGON.Application")
            # 2. Check if any sessions exist for the target system
            # For now, return False (always launch new)
            return False
        
        except Exception as e:
            logger.debug("Attach-first probe failed: %s", e)
            return False
    
    async def _launch_sap_gui(self, launcher_path: str, system_id: str) -> None:
        """Launch SAP GUI application.
        
        Args:
            launcher_path: Path to sapshcut.exe or saplogon.exe
            system_id: SAP system ID
        
        Raises:
            RuntimeError: If launch fails
        """
        try:
            logger.debug("Launching SAP GUI: %s (system=%s)", launcher_path, system_id)
            # In Phase 2, will actually invoke the launcher
            # For now, Phase 1 is a stub
        except Exception as e:
            logger.error("Failed to launch SAP GUI: %s", e)
            raise RuntimeError(f"Failed to launch SAP GUI: {e}")
    
    @staticmethod
    def get_all_sessions() -> List[Dict]:
        """Get all open SAP sessions across all systems.
        
        Convenience method that delegates to SAP_Session_Manager.
        
        Returns:
            List of dicts with session metadata:
            [{'system': str, 'client': str, 'user': str, 'transaction': str, ...}, ...]
        
        Example:
            ```python
            sessions = SAPConnection.get_all_sessions()
            for session in sessions:
                print(f"{session['system']}/{session['client']}: {session['transaction']}")
            ```
        """
        mgr = SAP_Session_Manager()
        return mgr.get_all_sessions()
    
    @staticmethod
    def validate_session(session: Any) -> bool:
        """Validate if session is still alive and responsive.
        
        Convenience method that delegates to SAP_Session_Manager.
        
        Args:
            session: GuiSession COM object to validate
        
        Returns:
            True if session is valid and alive, False if closed or unresponsive
        
        Example:
            ```python
            if SAPConnection.validate_session(session):
                print("Session is active")
            else:
                print("Session disconnected")
            ```
        """
        mgr = SAP_Session_Manager()
        return mgr.validate_session(session)
    
    def _start_heartbeat(self) -> None:
        """Start periodic heartbeat to keep-alive connection.
        
        Sends periodic query to SAP to prevent session timeout.
        """
        logger.debug("Starting heartbeat task")
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
    
    async def _heartbeat_loop(self) -> None:
        """Heartbeat loop - runs periodically to keep connection alive.
        
        Sends keep-alive command to SAP every 4 minutes.
        """
        try:
            while self._connected:
                await asyncio.sleep(240.0)  # 4 minutes
                
                if self._connected:
                    try:
                        logger.debug("Sending heartbeat to SAP")
                        # In Phase 2, would call actual SAP method
                        self._last_activity = time.time()
                    except Exception as e:
                        logger.warning("Heartbeat failed: %s", e)
        
        except asyncio.CancelledError:
            logger.debug("Heartbeat task cancelled")
            raise


class Session:
    """SAP session API.
    
    Wraps SAP session and provides async methods for interaction.
    All methods are async to allow non-blocking execution.
    
    In Phase 1, this is a skeleton. Phase 2 will add actual implementations.
    
    Attributes:
        _queue_manager: Queue manager for COM operations
        _system_id: SAP system ID
        _window: SAP window COM object (None in Phase 1)
        _connected: Flag indicating if session is connected
    """
    
    def __init__(self, queue_manager: QueueManager, system_id: str) -> None:
        """Initialize session.
        
        Args:
            queue_manager: QueueManager for async COM operations
            system_id: SAP system ID (e.g., 'D00', 'P00')
        """
        self._queue_manager = queue_manager
        self._system_id = system_id
        self._window: Optional[Any] = None
        self._connected: bool = True
        logger.debug("Session initialized for system=%s", system_id)
    
    async def close(self) -> None:
        """Close session gracefully.
        
        Raises:
            RuntimeError: If close fails
        """
        if not self._connected:
            logger.debug("Session already closed")
            return
        
        logger.info("Closing SAP session for system=%s", self._system_id)
        self._connected = False
    
    def is_connected(self) -> bool:
        """Check if session is still connected.
        
        Returns:
            True if connected, False otherwise
        """
        return self._connected
    
    async def start_transaction(self, code: str) -> Dict[str, Any]:
        """Start a SAP transaction.
        
        In Phase 1, returns stub response.
        In Phase 2, sends /NCODE to SAP.
        
        Args:
            code: Transaction code (e.g., 'VA01', 'MM01')
        
        Returns:
            Screen info dict with transaction details
        
        Raises:
            RuntimeError: If transaction start fails
        """
        if not self._connected:
            raise RuntimeError("Session not connected")
        
        logger.debug("Starting transaction %s", code)
        
        # Phase 1: Return stub
        return {
            "transaction": code,
            "status": "started",
            "screen": None
        }
    
    async def get_field_value(self, field_name: str) -> Any:
        """Get a field value from current screen.
        
        In Phase 1, returns None.
        In Phase 2, reads field via COM.
        
        Args:
            field_name: Field name (SAP internal name, e.g., 'VBAK-VBELN')
        
        Returns:
            Field value (type depends on field)
        
        Raises:
            RuntimeError: If field read fails
        """
        if not self._connected:
            raise RuntimeError("Session not connected")
        
        logger.debug("Getting field value: %s", field_name)
        
        # Phase 1: Return stub
        return None
    
    async def set_field_value(self, field_name: str, value: Any) -> None:
        """Set a field value on current screen.
        
        In Phase 1, does nothing.
        In Phase 2, writes field via COM.
        
        Args:
            field_name: Field name (SAP internal name)
            value: Value to set
        
        Raises:
            RuntimeError: If field write fails
        """
        if not self._connected:
            raise RuntimeError("Session not connected")
        
        logger.debug("Setting field %s = %s", field_name, value)
        
        # Phase 1: Stub implementation
        pass
    
    async def click_button(self, button_name: str) -> None:
        """Click a button on current screen.
        
        In Phase 1, does nothing.
        In Phase 2, clicks button via COM.
        
        Args:
            button_name: Button name or ID
        
        Raises:
            RuntimeError: If button click fails
        """
        if not self._connected:
            raise RuntimeError("Session not connected")
        
        logger.debug("Clicking button: %s", button_name)
        
        # Phase 1: Stub implementation
        pass
    
    async def send_key(self, key: str) -> None:
        """Send a key or key combination.
        
        In Phase 1, does nothing.
        In Phase 2, sends key via COM.
        
        Args:
            key: Key name (e.g., 'Enter', 'Ctrl+S')
        
        Raises:
            RuntimeError: If key send fails
        """
        if not self._connected:
            raise RuntimeError("Session not connected")
        
        logger.debug("Sending key: %s", key)
        
        # Phase 1: Stub implementation
        pass
