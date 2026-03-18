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
    session = await conn.open(username='demo', password='pass')
    await session.start_transaction('VA01')
    ```

CRITICAL CONSTRAINT:
    - All COM operations run on the worker thread, not asyncio main thread
    - Connection object itself is a lightweight wrapper
    - Session is placeholder for Phase 1; Phase 2 will add actual methods
"""

from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field
import logging
import asyncio
import time

from config import SAPConfig
from sap.queue_manager import QueueManager
from sap.bridge import SAPBridge
from sap.session_manager import SAP_Session_Manager

logger = logging.getLogger(__name__)


class SAPConnection:
    """Manages SAP GUI connection via COM scripting.
    
    Handles connection pooling, credentials, and session lifecycle.
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
    """
    
    def __init__(self, config: SAPConfig) -> None:
        """Initialize SAP connection wrapper.
        
        Args:
            config: SAPConfig with logon_path, username, password, client, lang
        
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
        
        logger.debug("SAPConnection initialized with client=%s, lang=%s", config.client, config.lang)
    
    async def open(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> "Session":
        """Open SAP GUI connection.
        
        Establishes SAP Logon COM object, logs in with credentials, and returns
        a Session wrapper. Starts the COM worker thread if not already running.
        
        Args:
            username: SAP username (uses config if not provided)
            password: SAP password (uses config if not provided)
        
        Returns:
            Session object for interacting with SAP
        
        Raises:
            RuntimeError: If connection fails
            ValueError: If credentials not provided or invalid
        """
        logger.info("Opening SAP connection")
        
        # Get credentials
        user = username or self.config.username
        pwd = password or self.config.password
        
        if not user or not pwd:
            raise ValueError("Username and password required (provide in call or config)")
        
        # Start bridge if needed
        bridge = SAPBridge()
        if not bridge.is_running():
            logger.info("Starting COM worker thread")
            bridge.start()
            # Give thread time to initialize
            await asyncio.sleep(0.5)
        
        try:
            # Create SAP Logon object via queue manager
            # Note: Phase 1 uses placeholder - Phase 2 will implement actual COM calls
            logger.debug("Creating SAP Logon COM object for user=%s", user)
            
            # In Phase 2, this will actually call:
            # result = await self._queue_manager.call_async(
            #     'win32com.client.GetObject',
            #     'SAPLOGON.Application'
            # )
            
            # For Phase 1, create Session stub
            self._sap_logon = object()  # Placeholder
            self._connected = True
            self._last_activity = time.time()
            
            # Create session wrapper
            self._session = Session(self._queue_manager, user)
            
            # Start heartbeat
            self._start_heartbeat()
            
            logger.info("SAP connection opened successfully")
            return self._session
        
        except Exception as e:
            logger.error("Failed to open SAP connection: %s", e, exc_info=True)
            self._connected = False
            raise RuntimeError(f"Failed to open SAP connection: {e}")
    
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
        _username: Username of logged-in user
        _window: SAP window COM object (None in Phase 1)
        _closed: Flag indicating if session is closed
    """
    
    def __init__(self, queue_manager: QueueManager, username: str) -> None:
        """Initialize session.
        
        Args:
            queue_manager: QueueManager for async COM operations
            username: Username of logged-in user
        """
        self._queue_manager = queue_manager
        self._username = username
        self._window: Optional[Any] = None
        self._closed: bool = False
        logger.debug("Session initialized for user=%s", username)
    
    async def close(self) -> None:
        """Close session gracefully.
        
        Raises:
            RuntimeError: If close fails
        """
        if self._closed:
            logger.debug("Session already closed")
            return
        
        logger.info("Closing SAP session for user=%s", self._username)
        self._closed = True
    
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
        if self._closed:
            raise RuntimeError("Session is closed")
        
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
        if self._closed:
            raise RuntimeError("Session is closed")
        
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
        if self._closed:
            raise RuntimeError("Session is closed")
        
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
        if self._closed:
            raise RuntimeError("Session is closed")
        
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
        if self._closed:
            raise RuntimeError("Session is closed")
        
        logger.debug("Sending key: %s", key)
        
        # Phase 1: Stub implementation
        pass
