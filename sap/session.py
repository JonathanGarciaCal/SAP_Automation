"""SAP session and window API.

Provides async Python methods to interact with SAP GUI via COM scripting.
All operations are queued to the COM worker thread via queue_manager.

All SAP COM calls are delegated to the worker thread. This module provides
a clean async API that the frontend (NiceGUI) can use without worrying about
COM threading constraints.

Example:
    ```python
    from sap.connection import SAPConnection
    from config import get_config
    
    config = get_config()
    conn = SAPConnection(config.sap)
    session = await conn.open('user', 'pass')
    
    # Navigate
    await session.start_transaction('VA01')
    
    # Field operations
    value = await session.get_field_value('VBAK-VBELN')
    await session.set_field_value('VBAK-VBELN', '12345')
    
    # Control interactions
    await session.click_button('ENTER')
    
    # Screenshots
    screenshot_bytes = await session.take_screenshot()
    
    # Cleanup
    await session.close()
    ```

Architecture:
    - Session wraps a GuiSession COM object (on worker thread)
    - Every method uses queue_manager.call_async() to execute on worker thread
    - Returns only primitives (str, int, bool, dict, list) — never COM objects
    - All methods are async/await compatible

CRITICAL CONSTRAINT:
    - Never call COM methods directly from asyncio main thread
    - Always use self._bridge.queue_manager.call_async()
    - See doc/06-architecture/patterns.md for threading pattern
"""

import logging
from typing import Any, List, Dict, Optional
from dataclasses import dataclass

from sap.element_tree import (
    normalize_element_payload,
    normalize_element_tree_payload,
    normalize_flat_element_list,
)
from sap.queue_manager import QueueManager

logger = logging.getLogger(__name__)


@dataclass
class FieldValue:
    """Field value with metadata.
    
    Attributes:
        name: Field name in SAP (internal name, e.g., 'I_VBELN')
        value: Field value (string representation)
        type: Data type (e.g., 'CHAR', 'NUMERIC', 'DATE')
    """
    
    name: str
    value: Any
    type: str = "CHAR"


class Session:
    """SAP session API.
    
    Wraps SAP GuiSession COM object and provides async Python interface.
    All methods are async and thread-safe via queue_manager.
    
    Attributes:
        _queue_manager: QueueManager for COM operations
        _session_id: Session ID (for logging/debugging)
        _system_id: SAP system ID (e.g., 'D00', 'P00')
        _username: Username of logged-in user
        _connected: Flag indicating if session is active
        _sap_session: Reference to GuiSession COM object (on worker thread)
    """
    
    def __init__(
        self,
        queue_manager: QueueManager,
        username: Optional[str] = None,
        session_id: Optional[str] = None,
        system_id: Optional[str] = None
    ) -> None:
        """Initialize SAP session.
        
        Args:
            queue_manager: QueueManager for async COM operations
            username: Username of logged-in user (optional for SSO mode)
            session_id: Session ID for logging (generated if not provided)
            system_id: SAP system ID (e.g., 'D00', 'P00')
        
        Raises:
            ValueError: If queue_manager is None
        """
        if not queue_manager:
            raise ValueError("queue_manager cannot be None")
        
        self._queue_manager = queue_manager
        self._username = username
        self._system_id = system_id
        self._session_id = session_id or f"session_{id(self)}"
        self._connected = True
        self._sap_session: Optional[Any] = None
        
        logger.debug(
            "Session initialized: id=%s, system=%s, username=%s",
            self._session_id,
            system_id,
            username
        )
    
    # ─────────────────────────────────────────────────────────────────
    # Connection Lifecycle (2 methods)
    # ─────────────────────────────────────────────────────────────────
    
    async def close(self) -> None:
        """Close session gracefully.
        
        Logs off from SAP and cleans up resources.
        
        Raises:
            RuntimeError: If close operation fails
        """
        if not self._connected:
            logger.debug("Session already closed: %s", self._session_id)
            return
        
        try:
            logger.info("Closing session: %s", self._session_id)

            await self._dispatch(
                'GuiSession.EndSession',
                operation='close',
                wrap_error='Failed to close session'
            )
        
        except Exception as e:
            logger.error("Error closing session: %s", e, exc_info=True)
            self._connected = False
            raise

        self._connected = False
        logger.info("Session closed successfully: %s", self._session_id)
    
    def is_connected(self) -> bool:
        """Check if session is active.
        
        Returns:
            True if session is connected, False otherwise
        """
        return self._connected

    def _ensure_connected(self) -> None:
        """Raise if the session is no longer connected."""
        if not self._connected:
            raise RuntimeError("Session not connected")

    async def _dispatch(
        self,
        method: str,
        *,
        operation: str,
        wrap_error: Optional[str] = None,
        detect_disconnect: bool = False,
        require_connected: bool = True,
        handled_exceptions: tuple[type[Exception], ...] = (Exception,),
        **kwargs: Any
    ) -> Any:
        """Dispatch a session command through QueueManager.call_async()."""
        if require_connected:
            self._ensure_connected()

        try:
            return await self._queue_manager.call_async(
                method,
                session_id=self._session_id,
                **kwargs
            )
        except handled_exceptions as error:
            if detect_disconnect:
                self._handle_runtime_disconnect(operation, error)

            if wrap_error is None:
                raise

            raise RuntimeError(f"{wrap_error}: {error}") from error

    @staticmethod
    def _empty_connection_status() -> Dict[str, str]:
        """Return the default empty connection status payload."""
        return {
            "system": "",
            "client": "",
            "user": "",
            "transaction": "",
            "screen": "",
        }
    
    def _handle_runtime_disconnect(self, operation: str, error: Exception) -> None:
        """Handle runtime disconnect detection.
        
        Inspects error text for known COM/SAP disconnect indicators and marks
        the session as disconnected if a disconnect is detected.
        
        Known disconnect indicators:
        - "SAPGuiAPIServer object has been deleted"
        - "The remote object no longer exists"
        - "Session not connected"
        - "Object reference not set"
        - "COM error: Catastrophic failure"
        
        Args:
            operation: Name of the operation that failed (e.g., 'start_transaction')
            error: The exception that was raised
        """
        error_text = str(error).lower()
        disconnect_keywords = [
            "has been deleted",
            "remote object no longer exists",
            "not connected",
            "object reference not set",
            "catastrophic failure",
            "interface not supported",
            "target object does not exist"
        ]
        
        is_disconnect = any(keyword in error_text for keyword in disconnect_keywords)
        
        if is_disconnect:
            self._connected = False
            logger.warning(
                "Runtime disconnect detected in %s (system=%s): %s",
                operation,
                self._system_id,
                error_text
            )
        else:
            logger.debug(
                "Operation %s failed but session still connected: %s",
                operation,
                error_text
            )
    
    # ─────────────────────────────────────────────────────────────────
    # Navigation (4 methods)
    # ─────────────────────────────────────────────────────────────────
    
    async def start_transaction(self, transaction_code: str) -> None:
        """Start a SAP transaction.
        
        Sends /N<transaction_code> to SAP and waits for screen ready.
        
        Args:
            transaction_code: Transaction code (e.g., 'VA01', 'SE11', 'ME23N')
        
        Raises:
            RuntimeError: If session not connected
            asyncio.TimeoutError: If COM call exceeds timeout
        
        Example:
            ```python
            await session.start_transaction('VA01')  # Sales Order Create
            await session.start_transaction('ME23N')  # Purchase Order Display
            ```
        """
        try:
            logger.info(
                "Starting transaction %s on session %s",
                transaction_code,
                self._session_id
            )

            await self._dispatch(
                'GuiSession.StartTransaction',
                operation='start_transaction',
                detect_disconnect=True,
                transaction_code=transaction_code
            )
            
            logger.debug("Transaction %s started", transaction_code)
        
        except Exception as e:
            logger.error("Failed to start transaction %s: %s", transaction_code, e)
            raise
    
    async def get_current_screen_id(self) -> str:
        """Get the current SAP screen ID.
        
        Returns the active window ID (typically "wnd[0]" for main window).
        
        Returns:
            Screen ID string (e.g., "wnd[0]", "wnd[1]" for modal)
        
        Raises:
            RuntimeError: If session not connected or screen not found
            asyncio.TimeoutError: If COM call exceeds timeout
        
        Example:
            ```python
            screen_id = await session.get_current_screen_id()
            # Returns: "wnd[0]" or "wnd[1]" for modal dialogs
            ```
        """
        try:
            logger.debug("Getting current screen ID for session %s", self._session_id)

            screen_id: str = await self._dispatch(
                'GuiSession.GetCurrentScreen',
                operation='get_current_screen_id',
                wrap_error='Failed to get current screen',
                detect_disconnect=True
            )
            
            logger.debug("Current screen: %s", screen_id)
            return screen_id
        
        except RuntimeError as e:
            logger.error("Failed to get current screen: %s", e)
            raise
    
    async def go_back(self) -> None:
        """Go back one screen (press Back button / F3).
        
        Waits for screen ready after going back.
        
        Raises:
            RuntimeError: If session not connected
            asyncio.TimeoutError: If COM call exceeds timeout
        
        Example:
            ```python
            await session.go_back()  # Return to previous screen
            ```
        """
        try:
            logger.info("Going back on session %s", self._session_id)

            await self._dispatch(
                'GuiSession.GoBack',
                operation='go_back',
                detect_disconnect=True
            )
            
            logger.debug("Returned to previous screen")
        
        except Exception as e:
            logger.error("Failed to go back: %s", e)
            raise
    
    async def go_home(self) -> None:
        """Return to SAP home screen (press Home button).
        
        Typically returns to the main SAP Easy Access menu.
        
        Raises:
            RuntimeError: If session not connected
            asyncio.TimeoutError: If COM call exceeds timeout
        
        Example:
            ```python
            await session.go_home()  # Return to SAP home/menu
            ```
        """
        try:
            logger.info("Going to SAP home on session %s", self._session_id)

            await self._dispatch(
                'GuiSession.GoHome',
                operation='go_home',
                detect_disconnect=True
            )
            
            logger.debug("Returned to SAP home")
        
        except Exception as e:
            logger.error("Failed to go home: %s", e)
            raise
    
    # ─────────────────────────────────────────────────────────────────
    # Field Operations (3 methods)
    # ─────────────────────────────────────────────────────────────────
    
    async def get_field_value(self, field_id: str) -> Any:
        """Read a field value from the current screen.
        
        Field ID is a SAP element path, e.g., "I[:VBELN]" or "[/app/scr/txt_customer]".
        
        Args:
            field_id: SAP field identifier (internal name or path)
        
        Returns:
            Field value (string representation from SAP)
        
        Raises:
            RuntimeError: If session not connected or field not found
            asyncio.TimeoutError: If COM call exceeds timeout
        
        Example:
            ```python
            sales_order = await session.get_field_value('I[:VBELN]')
            print(f"Order: {sales_order}")  # Output: Order: 1000001
            ```
        """
        try:
            logger.debug(
                "Getting field value: %s on session %s",
                field_id,
                self._session_id
            )

            value: Any = await self._dispatch(
                'GuiElement.GetValue',
                operation='get_field_value',
                wrap_error=f'Failed to get field value {field_id}',
                field_id=field_id
            )
            
            logger.debug("Field %s value: %s", field_id, value)
            return value
        
        except RuntimeError as e:
            logger.error("Failed to get field value %s: %s", field_id, e)
            raise
    
    async def set_field_value(self, field_id: str, value: Any) -> None:
        """Set a field value on the current screen.
        
        Field ID is a SAP element path, e.g., "I[:VBELN]" or "[/app/scr/txt_customer]".
        
        Args:
            field_id: SAP field identifier (internal name or path)
            value: Value to set (will be converted to string)
        
        Raises:
            RuntimeError: If session not connected or field not found
            asyncio.TimeoutError: If COM call exceeds timeout
        
        Example:
            ```python
            await session.set_field_value('I[:VBELN]', '1000001')
            await session.set_field_value('I[:QTY]', '100')
            ```
        """
        try:
            logger.info(
                "Setting field %s = %s on session %s",
                field_id,
                value,
                self._session_id
            )

            await self._dispatch(
                'GuiElement.SetValue',
                operation='set_field_value',
                wrap_error=f'Failed to set field {field_id}',
                field_id=field_id,
                value=str(value)
            )
            
            logger.debug("Field %s set successfully", field_id)
        
        except RuntimeError as e:
            logger.error("Failed to set field %s: %s", field_id, e)
            raise
    
    async def get_field_property(
        self,
        field_id: str,
        property_name: str
    ) -> Any:
        """Get a property of a field element.
        
        Common properties: 'Text', 'Value', 'Type', 'AbsoluteXPos', 'AbsoluteYPos', etc.
        
        Args:
            field_id: SAP field identifier
            property_name: Property name (e.g., 'Text', 'Value', 'Type')
        
        Returns:
            Property value
        
        Raises:
            RuntimeError: If session not connected or element not found
            asyncio.TimeoutError: If COM call exceeds timeout
        
        Example:
            ```python
            is_visible = await session.get_field_property('I[:FIELD1]', 'Visible')
            field_type = await session.get_field_property('I[:FIELD1]', 'Type')
            ```
        """
        try:
            logger.debug(
                "Getting field property: %s.%s on session %s",
                field_id,
                property_name,
                self._session_id
            )

            prop_value: Any = await self._dispatch(
                'GuiElement.GetProperty',
                operation='get_field_property',
                wrap_error=f'Failed to get field property {field_id}.{property_name}',
                field_id=field_id,
                property_name=property_name
            )
            
            return prop_value
        
        except RuntimeError as e:
            logger.error(
                "Failed to get field property %s.%s: %s",
                field_id,
                property_name,
                e
            )
            raise
    
    # ─────────────────────────────────────────────────────────────────
    # Control Interactions (4 methods)
    # ─────────────────────────────────────────────────────────────────
    
    async def click_button(self, button_id: str) -> None:
        """Click a button on the screen.
        
        Button ID can be:
        - SAP element path: "[/app/scr/btn_ok]"
        - SAP command code: "=SAVE", "=ENTER", etc.
        - Standard function key via send_key: use send_key(0) for Enter
        
        Args:
            button_id: Button identifier (path or command code)
        
        Raises:
            RuntimeError: If session not connected or button not found
            asyncio.TimeoutError: If COM call exceeds timeout
        
        Example:
            ```python
            await session.click_button('ENTER')  # Press Enter
            await session.click_button('=SAVE')  # Click Save button
            await session.click_button('[/app/btn_ok]')  # Click OK
            ```
        """
        try:
            logger.info(
                "Clicking button %s on session %s",
                button_id,
                self._session_id
            )

            await self._dispatch(
                'GuiElement.Click',
                operation='click_button',
                wrap_error=f'Failed to click button {button_id}',
                button_id=button_id
            )
            
            logger.debug("Button %s clicked", button_id)
        
        except RuntimeError as e:
            logger.error("Failed to click button %s: %s", button_id, e)
            raise
    
    async def send_key(self, key_code: int) -> None:
        """Send a virtual key to SAP.
        
        Key codes map to SAP virtual keys (see sendVKey reference):
        - 0: Enter
        - 1: F1 (Help)
        - 3: F3 (Back)
        - 8: F8 (Execute)
        - 11: Ctrl+S (Save)
        - 12: F12 (Cancel)
        
        Args:
            key_code: Virtual key code (0-82+)
        
        Raises:
            RuntimeError: If session not connected
            asyncio.TimeoutError: If COM call exceeds timeout
        
        Example:
            ```python
            await session.send_key(0)   # Press Enter
            await session.send_key(8)   # Press F8 (Execute)
            await session.send_key(12)  # Press F12 (Cancel)
            ```
        """
        try:
            logger.debug(
                "Sending key %d on session %s",
                key_code,
                self._session_id
            )

            await self._dispatch(
                'GuiSession.SendKey',
                operation='send_key',
                wrap_error=f'Failed to send key {key_code}',
                detect_disconnect=True,
                key_code=key_code
            )
            
            logger.debug("Key %d sent", key_code)
        
        except RuntimeError as e:
            logger.error("Failed to send key %d: %s", key_code, e)
            raise
    
    async def left_click(self, field_id: str) -> None:
        """Left-click an element on the screen.
        
        Similar to click_button but explicitly performs a left click.
        Useful for tables, trees, or multi-click interactions.
        
        Args:
            field_id: Element identifier (path)
        
        Raises:
            RuntimeError: If session not connected or element not found
            asyncio.TimeoutError: If COM call exceeds timeout
        
        Example:
            ```python
            await session.left_click('[/app/scr/grid_0]')  # Click grid cell
            ```
        """
        try:
            logger.debug(
                "Left-clicking element %s on session %s",
                field_id,
                self._session_id
            )

            await self._dispatch(
                'GuiElement.LeftClick',
                operation='left_click',
                wrap_error=f'Failed to left-click element {field_id}',
                field_id=field_id
            )
            
            logger.debug("Element %s left-clicked", field_id)
        
        except RuntimeError as e:
            logger.error("Failed to left-click element %s: %s", field_id, e)
            raise
    
    async def right_click(self, field_id: str) -> None:
        """Right-click an element on the screen.
        
        Typically brings up a context menu.
        
        Args:
            field_id: Element identifier (path)
        
        Raises:
            RuntimeError: If session not connected or element not found
            asyncio.TimeoutError: If COM call exceeds timeout
        
        Example:
            ```python
            await session.right_click('[/app/scr/grid_0]')  # Context menu
            ```
        """
        try:
            logger.debug(
                "Right-clicking element %s on session %s",
                field_id,
                self._session_id
            )

            await self._dispatch(
                'GuiElement.RightClick',
                operation='right_click',
                wrap_error=f'Failed to right-click element {field_id}',
                field_id=field_id
            )
            
            logger.debug("Element %s right-clicked", field_id)
        
        except RuntimeError as e:
            logger.error("Failed to right-click element %s: %s", field_id, e)
            raise
    
    # ─────────────────────────────────────────────────────────────────
    # Element Discovery (3 methods)
    # ─────────────────────────────────────────────────────────────────
    
    async def find_element(self, path: str) -> Dict[str, Any]:
        """Find an element by path and return its metadata.
        
        Element path format: "[/app/scr/txt_field_name]" or "I[:FIELD_NAME]"
        
        Args:
            path: Element path or SAP ID
        
        Returns:
            Dict with element metadata: {
                'element_id': element ID,
                'element_type': element type (e.g., 'GuiTextField'),
                'name': element name or label,
                'text': display text,
                'value': current value if applicable,
                'visible': visibility flag,
                'enabled': enabled flag,
                'x': X position,
                'y': Y position,
                'width': width,
                'height': height,
                'parent_id': parent element ID if available
            }
        
        Raises:
            RuntimeError: If session not connected or element not found
            asyncio.TimeoutError: If COM call exceeds timeout
        
        Example:
            ```python
            elem = await session.find_element('I[:VBELN]')
            print(
                f"Element type: {elem['element_type']}, "
                f"visible: {elem['visible']}"
            )
            ```
        """
        try:
            logger.debug(
                "Finding element %s on session %s",
                path,
                self._session_id
            )

            elem_data: Dict[str, Any] = await self._dispatch(
                'GuiSession.FindElement',
                operation='find_element',
                wrap_error=f'Failed to find element {path}',
                path=path
            )

            normalized_element = normalize_element_payload(elem_data)
            
            logger.debug(
                "Found element %s: %s",
                path,
                normalized_element.get('element_type')
            )
            return normalized_element
        
        except (RuntimeError, TypeError, ValueError) as e:
            logger.error("Failed to find element %s: %s", path, e)
            raise
    
    async def find_elements_by_type(self, element_type: str) -> List[Dict[str, Any]]:
        """Find all elements of a specific type on current screen.
        
        Element types: 'GuiTextField', 'GuiButton', 'GuiGridView', etc.
        
        Args:
            element_type: Element type to search for
        
        Returns:
            List of canonical element metadata dicts using the same contract as
            find_element() and get_element_tree().
        
        Raises:
            RuntimeError: If session not connected
            asyncio.TimeoutError: If COM call exceeds timeout
        
        Example:
            ```python
            buttons = await session.find_elements_by_type('GuiButton')
            print(f"Found {len(buttons)} buttons")
            for btn in buttons:
                print(f"  - {btn['element_id']}: {btn['text']}")
            ```
        """
        try:
            logger.debug(
                "Finding all elements of type %s on session %s",
                element_type,
                self._session_id
            )

            elements: List[Dict[str, Any]] = await self._dispatch(
                'GuiSession.FindElementsByType',
                operation='find_elements_by_type',
                wrap_error=f'Failed to find elements by type {element_type}',
                element_type=element_type
            )

            normalized_elements = normalize_flat_element_list(elements)
            
            logger.debug(
                "Found %d elements of type %s",
                len(normalized_elements),
                element_type
            )
            return normalized_elements
        
        except (RuntimeError, TypeError, ValueError) as e:
            logger.error(
                "Failed to find elements by type %s: %s",
                element_type,
                e
            )
            raise
    
    async def get_element_tree(
        self,
        root_id: str = "[/app/con[0]/ses[0]/wnd[0]]",
        max_depth: int = 20,
        max_elements: int = 5000
    ) -> List[Dict[str, Any]]:
        """Get all elements on screen as a flattened list with parent references.
        
        Returns a normalized flat list describing the SAP element hierarchy.
        Each element dict contains the canonical Session element keys plus a
        parent_id back-reference for tree reconstruction.
        
        Args:
            root_id: Root element ID (default: main window)
            max_depth: Maximum recursion depth to prevent infinite loops
            max_elements: Maximum total elements to return (safety limit)
        
        Returns:
            List[Dict[str, Any]] where each dict contains:
            {
                'element_id': str,      # Unique identifier
                'element_type': str,    # Element class name (GuiTextField, etc.)
                'name': str,            # User-facing name/label
                'text': str,            # Display text
                'x': int,               # X position in pixels
                'y': int,               # Y position in pixels
                'width': int,           # Width in pixels
                'height': int,          # Height in pixels
                'visible': bool,        # Visibility flag
                'enabled': bool,        # Enabled flag
                'value': Optional[Any], # Current value (for fields)
                'parent_id': Optional[str]  # Parent element ID (for tree linking)
            }
        
        Raises:
            RuntimeError: If session not connected
            asyncio.TimeoutError: If COM call exceeds timeout
        
        Example:
            ```python
            elements = await session.get_element_tree()
            print(f"Found {len(elements)} elements")
            for elem in elements:
                print(f"  [{elem['element_type']}] {elem['name']}")
            ```
        """
        try:
            logger.debug(
                "Getting element tree from %s (max_depth=%d, max_elements=%d) on session %s",
                root_id,
                max_depth,
                max_elements,
                self._session_id
            )
            
            # Get nested tree from COM worker thread
            result: Any = await self._dispatch(
                'GuiSession.GetElementTree',
                operation='get_element_tree',
                wrap_error='Failed to get element tree',
                root_id=root_id
            )

            flat_list = normalize_element_tree_payload(
                result,
                max_depth=max_depth,
                max_elements=max_elements,
            )

            logger.debug(
                "Element tree normalized from %s payload: %d elements",
                type(result).__name__,
                len(flat_list),
            )
            return flat_list

        except (RuntimeError, TypeError, ValueError) as e:
            logger.error("Failed to get element tree: %s", e)
            raise
    
    # ─────────────────────────────────────────────────────────────────
    # Data Extraction (3 methods)
    # ─────────────────────────────────────────────────────────────────
    
    async def read_grid(self, grid_id: str, max_rows: int = 10000) -> List[Dict[str, Any]]:
        """Read all rows from an ALV grid or table.
        
        Extracts all visible rows from a GuiGridView or GuiTableControl.
        Handles pagination internally for large grids.
        
        Args:
            grid_id: Grid element ID (path)
            max_rows: Maximum rows to read (default: 10000, safety limit)
        
        Returns:
            List of row dicts, each with column data:
            [
                {'column1': 'value1', 'column2': 'value2', ...},
                ...
            ]
        
        Raises:
            RuntimeError: If session not connected or grid not found
            asyncio.TimeoutError: If COM call exceeds timeout
        
        Example:
            ```python
            rows = await session.read_grid('[/app/scr/grid_0]')
            print(f"Read {len(rows)} rows from grid")
            for row in rows:
                print(f"  Row: {row}")
            ```
        """
        try:
            logger.info(
                "Reading grid %s (max_rows=%d) on session %s",
                grid_id,
                max_rows,
                self._session_id
            )

            rows: List[Dict[str, Any]] = await self._dispatch(
                'GuiGrid.ReadGrid',
                operation='read_grid',
                wrap_error=f'Failed to read grid {grid_id}',
                grid_id=grid_id,
                max_rows=max_rows
            )
            
            logger.info("Grid read complete: %d rows", len(rows))
            return rows
        
        except RuntimeError as e:
            logger.error("Failed to read grid %s: %s", grid_id, e)
            raise
    
    async def get_grid_value(
        self,
        grid_id: str,
        row: int,
        col: int
    ) -> Any:
        """Get a single cell value from a grid.
        
        Args:
            grid_id: Grid element ID
            row: Row index (0-based)
            col: Column index (0-based)
        
        Returns:
            Cell value
        
        Raises:
            RuntimeError: If session not connected or grid/cell not found
            asyncio.TimeoutError: If COM call exceeds timeout
        
        Example:
            ```python
            value = await session.get_grid_value('[/app/scr/grid_0]', 0, 1)
            print(f"Cell [0,1] = {value}")
            ```
        """
        try:
            logger.debug(
                "Getting grid value [%d,%d] from grid %s",
                row,
                col,
                grid_id
            )

            value: Any = await self._dispatch(
                'GuiGrid.GetValue',
                operation='get_grid_value',
                wrap_error=f'Failed to get grid value [{row},{col}] from {grid_id}',
                grid_id=grid_id,
                row=row,
                col=col
            )
            
            return value
        
        except RuntimeError as e:
            logger.error(
                "Failed to get grid value [%d,%d] from %s: %s",
                row,
                col,
                grid_id,
                e
            )
            raise
    
    async def set_grid_value(
        self,
        grid_id: str,
        row: int,
        col: int,
        value: Any
    ) -> None:
        """Set a single cell value in a grid (if editable).
        
        Args:
            grid_id: Grid element ID
            row: Row index (0-based)
            col: Column index (0-based)
            value: Value to set
        
        Raises:
            RuntimeError: If session not connected or grid/cell not found
            asyncio.TimeoutError: If COM call exceeds timeout
        
        Example:
            ```python
            await session.set_grid_value('[/app/scr/grid_0]', 0, 1, '12345')
            ```
        """
        try:
            logger.info(
                "Setting grid value [%d,%d] = %s on grid %s",
                row,
                col,
                value,
                grid_id
            )

            await self._dispatch(
                'GuiGrid.SetValue',
                operation='set_grid_value',
                wrap_error=f'Failed to set grid value [{row},{col}] on {grid_id}',
                grid_id=grid_id,
                row=row,
                col=col,
                value=str(value)
            )
            
            logger.debug("Grid value [%d,%d] set", row, col)
        
        except RuntimeError as e:
            logger.error(
                "Failed to set grid value [%d,%d] on %s: %s",
                row,
                col,
                grid_id,
                e
            )
            raise
    
    # ─────────────────────────────────────────────────────────────────
    # Screenshots & State (3 methods)
    # ─────────────────────────────────────────────────────────────────
    
    async def take_screenshot(self) -> bytes:
        """Capture current SAP screen.
        
        Returns screenshot as PNG bytes.
        
        Returns:
            Screenshot image data (PNG format bytes)
        
        Raises:
            RuntimeError: If session not connected or screenshot fails
            asyncio.TimeoutError: If COM call exceeds timeout
        
        Example:
            ```python
            png_bytes = await session.take_screenshot()
            with open('screenshot.png', 'wb') as f:
                f.write(png_bytes)
            ```
        """
        try:
            logger.debug("Taking screenshot on session %s", self._session_id)

            screenshot_data: bytes = await self._dispatch(
                'GuiSession.TakeScreenshot',
                operation='take_screenshot',
                wrap_error='Failed to take screenshot'
            )
            
            logger.debug("Screenshot captured: %d bytes", len(screenshot_data))
            return screenshot_data
        
        except RuntimeError as e:
            logger.error("Failed to take screenshot: %s", e)
            raise
    
    async def get_focus_element(self) -> str:
        """Get the ID of the currently focused element.
        
        Returns:
            Element ID of focused control
        
        Raises:
            RuntimeError: If session not connected
            asyncio.TimeoutError: If COM call exceeds timeout
        
        Example:
            ```python
            focused_id = await session.get_focus_element()
            print(f"Focused element: {focused_id}")
            ```
        """
        try:
            logger.debug(
                "Getting focused element on session %s",
                self._session_id
            )

            elem_id: str = await self._dispatch(
                'GuiSession.GetFocusElement',
                operation='get_focus_element',
                wrap_error='Failed to get focused element'
            )
            
            logger.debug("Focused element: %s", elem_id)
            return elem_id
        
        except RuntimeError as e:
            logger.error("Failed to get focused element: %s", e)
            raise
    
    async def get_status_bar(self) -> str:
        """Get status bar text from current screen.
        
        Reads the status bar at bottom of SAP window.
        
        Returns:
            Status bar text
        
        Raises:
            RuntimeError: If session not connected
            asyncio.TimeoutError: If COM call exceeds timeout
        
        Example:
            ```python
            status = await session.get_status_bar()
            print(f"Status: {status}")
            ```
        """
        try:
            logger.debug(
                "Getting status bar on session %s",
                self._session_id
            )

            status_text: str = await self._dispatch(
                'GuiSession.GetStatusBar',
                operation='get_status_bar',
                wrap_error='Failed to get status bar'
            )
            
            logger.debug("Status bar: %s", status_text)
            return status_text
        
        except RuntimeError as e:
            logger.error("Failed to get status bar: %s", e)
            raise

    async def get_connection_status(self) -> Dict[str, str]:
        """Get normalized SAP connection status details.

        Returns a consistent structure suitable for UI status panels.
        All values are strings and default to empty string when unavailable.

        Returns:
            Dict with keys: system, client, user, transaction, screen
        """
        if not self._connected:
            return self._empty_connection_status()

        try:
            status: Dict[str, Any] = await self._dispatch(
                'GuiSession.GetConnectionStatus',
                operation='get_connection_status',
                detect_disconnect=True,
                require_connected=False,
                handled_exceptions=(RuntimeError,)
            )
        except RuntimeError as e:
            logger.debug("Failed to get connection status details: %s", e)
            return self._empty_connection_status()

        return {
            "system": str(status.get("system", "") or ""),
            "client": str(status.get("client", "") or ""),
            "user": str(status.get("user", "") or ""),
            "transaction": str(status.get("transaction", "") or ""),
            "screen": str(status.get("screen", "") or ""),
        }
