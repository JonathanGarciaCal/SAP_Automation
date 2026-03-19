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
import re

try:
    import win32com.client
except ImportError:
    win32com = None

from config import SAPConfig
from sap.queue_manager import QueueManager
from sap.bridge import SAPBridge
from sap.session_manager import SAP_Session_Manager
from sap.session import Session as SAPSession

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
        self._session: Optional[SAPSession] = None
        self._connected: bool = False
        self._connection_pool: Dict[str, Any] = {}
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._last_activity: float = time.time()
        self._last_connection_diagnostics: Dict[str, Any] = {}
        
        logger.debug("SAPConnection initialized (SSO-only mode) with client=%s, lang=%s", config.client, config.lang)
    
    async def open(self, system_id: str, use_sso: bool = True) -> SAPSession:
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

                # Ensure COM worker is available for queued session calls.
                bridge = SAPBridge()
                if not bridge.is_running():
                    logger.info("Starting COM worker thread for attached SAP session")
                    bridge.start()
                    await asyncio.sleep(0.5)

                self._connected = True
                self._last_activity = time.time()
                self._session = SAPSession(self._queue_manager, system_id=system_id)
                self._start_heartbeat()
                self._last_connection_diagnostics["stage"] = "connected"
                return self._session
            else:
                if not self._last_connection_diagnostics.get("attach_first_error"):
                    self._last_connection_diagnostics["attach_first_error"] = "No running SAP GUI instance found"
                logger.debug("No running SAP instance; will launch new one")
            
            # Stage 2: Launcher resolution and launch
            self._last_connection_diagnostics["stage"] = "launcher_resolution"
            logger.debug("Stage 2/3: Resolving SAP launcher candidates")
            launcher_path = self._resolve_sap_launcher_candidates()
            
            if not launcher_path:
                error_msg = "No suitable SAP launcher found (checked config paths, common install locations, and system PATH)"
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
            self._session = SAPSession(self._queue_manager, system_id=system_id)
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
        
        Checks sources in this priority order:
        1. config.sapgui_exe_path (if explicitly configured)
        2. config.logon_path (if it's an executable file)
        3. Common default SAP installation directories
        4. System PATH search
        
        Returns:
            Path to first found launcher, or None if no launchers found
        """
        candidates = ["sapshcut.exe", "saplogon.exe"]
        self._last_connection_diagnostics["attempted_candidates"] = []
        
        # Priority 1: Check explicitly configured sapgui_exe_path
        if self.config.sapgui_exe_path:
            logger.debug("Checking configured sapgui_exe_path: %s", self.config.sapgui_exe_path)
            self._last_connection_diagnostics["attempted_candidates"].append(
                f"config.sapgui_exe_path: {self.config.sapgui_exe_path}"
            )
            if os.path.isfile(self.config.sapgui_exe_path):
                logger.debug("Found SAP launcher at configured path: %s", self.config.sapgui_exe_path)
                return self.config.sapgui_exe_path
        
        # Priority 2: Check if logon_path is an executable file
        if self.config.logon_path and self.config.logon_path.endswith(".exe"):
            logger.debug("Checking if logon_path is executable: %s", self.config.logon_path)
            self._last_connection_diagnostics["attempted_candidates"].append(
                f"config.logon_path (as exe): {self.config.logon_path}"
            )
            if os.path.isfile(self.config.logon_path):
                logger.debug("Found SAP launcher at logon_path: %s", self.config.logon_path)
                return self.config.logon_path
        
        # Priority 3: Check common default SAP installation directories
        common_sap_locations = [
            r"C:\Program Files (x86)\SAP\FrontEnd\SAPgui\sapshcut.exe",
            r"C:\Program Files (x86)\SAP\FrontEnd\SAPgui\saplogon.exe",
            r"C:\Program Files\SAP\FrontEnd\SAPgui\sapshcut.exe",
            r"C:\Program Files\SAP\FrontEnd\SAPgui\saplogon.exe",
        ]
        
        for location in common_sap_locations:
            logger.debug("Checking common SAP location: %s", location)
            self._last_connection_diagnostics["attempted_candidates"].append(
                f"common location: {location}"
            )
            if os.path.isfile(location):
                logger.debug("Found SAP launcher at common location: %s", location)
                return location
        
        # Priority 4: Search in system PATH
        for candidate in candidates:
            logger.debug("Attempting to resolve launcher from PATH: %s", candidate)
            self._last_connection_diagnostics["attempted_candidates"].append(
                f"PATH search: {candidate}"
            )
            
            try:
                # Try to find in PATH
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
                logger.debug("Failed to find %s in PATH: %s", candidate, e)
        
        logger.warning("No SAP launcher found in config, common locations, or PATH")
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

            target_system = self._normalize_system_id(system_id)
            target_client = self._normalize_client(self.config.client)

            if not target_system:
                self._last_connection_diagnostics["attach_first_error"] = (
                    "Cannot probe running SAP sessions: target system is empty after normalization"
                )
                return False

            sessions = SAPConnection.get_all_sessions()
            if not sessions:
                self._last_connection_diagnostics["attach_first_error"] = (
                    f"No running SAP sessions found for requested system '{target_system}'"
                )
                return False

            matching_without_client: List[Dict[str, Any]] = []
            matching_system_any_client: List[Dict[str, Any]] = []
            client_mismatch_samples: List[str] = []

            for session in sessions:
                session_system = self._normalize_system_id(str(session.get("system", "")))
                if session_system != target_system:
                    continue

                session_client = self._normalize_client(session.get("client"))

                # When client is configured, prefer exact match.
                if target_client:
                    if session_client == target_client:
                        logger.debug(
                            "Attach-first match found: system=%s client=%s",
                            session_system,
                            session_client,
                        )
                        self._last_connection_diagnostics["attach_first_error"] = None
                        return True

                    # If session client metadata is unavailable, still allow attach.
                    if not session_client:
                        matching_without_client.append(session)
                    else:
                        matching_system_any_client.append(session)
                        client_mismatch_samples.append(session_client)
                    continue

                # No configured client: any matching system is enough.
                logger.debug(
                    "Attach-first system match found without client requirement: system=%s",
                    session_system,
                )
                self._last_connection_diagnostics["attach_first_error"] = None
                return True

            if matching_without_client:
                logger.debug(
                    "Attach-first fallback match found: system=%s with unavailable session client metadata",
                    target_system,
                )
                self._last_connection_diagnostics["attach_first_error"] = None
                return True

            if matching_system_any_client:
                unique_clients = sorted(set(client_mismatch_samples))
                logger.warning(
                    "Attach-first fallback using system-only match for %s; configured client=%s, available clients=%s",
                    target_system,
                    target_client,
                    unique_clients,
                )
                self._last_connection_diagnostics["attach_first_error"] = None
                return True

            if target_client and client_mismatch_samples:
                unique_clients = sorted(set(client_mismatch_samples))
                self._last_connection_diagnostics["attach_first_error"] = (
                    f"Found running sessions for system '{target_system}' but clients did not match "
                    f"requested client '{target_client}' (available: {unique_clients})"
                )
            else:
                self._last_connection_diagnostics["attach_first_error"] = (
                    f"No running SAP sessions matched requested system '{target_system}'"
                )
            return False
        
        except Exception as e:
            self._last_connection_diagnostics["attach_first_error"] = (
                f"Attach-first probe failed: {e}"
            )
            logger.debug("Attach-first probe failed: %s", e)
            return False

    @staticmethod
    def _normalize_system_id(system_id: str) -> str:
        """Normalize system ID for robust matching.

        Handles decorated labels like "PAG - North American AG Production (SSO)"
        by extracting the leading system code.

        Args:
            system_id: Raw system identifier from UI/session metadata.

        Returns:
            Normalized uppercase system code.
        """
        if not system_id:
            return ""

        normalized = system_id.strip()
        normalized = re.split(r"\s+-\s+", normalized, maxsplit=1)[0]
        normalized = re.sub(r"\s*\([^)]*\)\s*$", "", normalized)
        return normalized.strip().upper()

    @staticmethod
    def _normalize_client(client: Optional[Any]) -> str:
        """Normalize SAP client for case-insensitive/whitespace-safe comparison.

        Args:
            client: Raw client value from config/session metadata.

        Returns:
            Normalized uppercase client value, or empty string if unavailable.
        """
        if client is None:
            return ""

        value = str(client).strip()
        if not value:
            return ""
        return value.upper()
    
    async def _launch_sap_gui(self, launcher_path: str, system_id: str) -> None:
        """Launch SAP GUI application with system connection.
        
        Launches SAP GUI and automatically connects to the specified system using SSO.
        Waits for SAP to become active before returning.
        
        Args:
            launcher_path: Path to sapshcut.exe or saplogon.exe
            system_id: SAP system descriptor (e.g., "PAG - North American AG Production (SSO)")
        
        Raises:
            RuntimeError: If launch fails or timeout waiting for SAP to become active
        """
        try:
            logger.debug("Launching SAP GUI: %s (system=%s)", launcher_path, system_id)
            
            # Extract system code from system_id (first part before " - ")
            # e.g., "PAG - North American AG Production (SSO)" → "PAG"
            system_code = system_id.split(" - ")[0].strip() if " - " in system_id else system_id
            
            # Build command-line arguments for SAP launcher
            # Examples:
            # - sapshcut.exe -system=PAG (without SSO flags, uses system from logon file)
            # - sapshcut.exe -client=410 (optional client override)
            cmd_args = [launcher_path, f"-system={system_code}"]
            
            # Optional: add client from config if needed
            if self.config.client:
                cmd_args.append(f"-client={self.config.client}")
            
            logger.debug("SAP launch command: %s", cmd_args)
            
            # Launch SAP GUI in separate process
            process = subprocess.Popen(
                cmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            logger.info("SAP GUI process launched (PID: %d)", process.pid)
            
            # Wait for SAP GUI to become available via COM scripting
            sap_available = await self._wait_for_sap_gui_active(system_id, timeout_sec=30)
            
            if not sap_available:
                logger.error("Timeout waiting for SAP GUI to become active")
                raise RuntimeError("SAP GUI launch timeout: failed to connect within 30 seconds")
            
            logger.debug("SAP GUI is now active and responsive")
            
        except subprocess.TimeoutExpired:
            logger.error("SAP launcher process timed out")
            raise RuntimeError("SAP launcher process timed out")
        except Exception as e:
            logger.error("Failed to launch SAP GUI: %s", e, exc_info=True)
            raise RuntimeError(f"Failed to launch SAP GUI: {e}")
    
    async def _wait_for_sap_gui_active(self, system_id: str, timeout_sec: int = 30) -> bool:
        """Wait for SAP GUI to become active and accessible.
        
        Polls for SAP GUI availability via COM scripting with exponential backoff.
        
        Args:
            system_id: SAP system descriptor for logging
            timeout_sec: Maximum seconds to wait (default 30)
        
        Returns:
            True if SAP GUI became active, False if timeout
        """
        if not win32com:
            logger.warning("win32com.client not available; cannot verify SAP GUI availability")
            # Still wait a bit for SAP to potentially start
            await asyncio.sleep(5)
            return True
        
        start_time = time.time()
        attempt = 0
        max_attempts = 30  # ~30 seconds with exponential backoff
        
        while time.time() - start_time < timeout_sec:
            try:
                attempt += 1
                
                # Try to get SAP Logon COM object
                sap_gui_auto = win32com.client.GetObject("SAPGUI")
                
                if sap_gui_auto is None:
                    logger.debug("Attempt %d: SAP GUI COM object not available yet", attempt)
                else:
                    logger.debug("Attempt %d: SAP GUI COM object found", attempt)
                    
                    # Try to access scripting engine
                    try:
                        app = sap_gui_auto.GetScriptingEngine
                        if app and app.Children.Count > 0:
                            logger.debug("SAP GUI active with %d connection(s)", app.Children.Count)
                            return True
                    except Exception as e:
                        logger.debug("Scripting engine check failed: %s", e)
                
            except Exception as e:
                logger.debug("Attempt %d: SAP GUI COM check failed: %s", attempt, e)
            
            # Exponential backoff: 0.5s, 1s, 1.5s, 2s...
            await asyncio.sleep(min(0.5 * attempt, 2.0))
        
        logger.warning("SAP GUI did not become active within %d seconds", timeout_sec)
        return False
    
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
