"""Tests for SAP session API.

Comprehensive unit tests with >80% coverage for session.py and inspector.py.
All tests use mocking — no real SAP COM calls.

Test Structure:
    - TestSessionInitialization: Constructor and state tests
    - TestSessionConnectionLifecycle: connect/disconnect tests
    - TestSessionNavigation: start_transaction, go_back, go_home, get_screen
    - TestSessionFieldOperations: get/set field, field properties
    - TestSessionControlInteractions: button clicks, key sends, element clicks
    - TestSessionElementDiscovery: find_element, find_elements_by_type, get_tree
    - TestSessionDataExtraction: read_grid, get_cell, set_cell
    - TestSessionScreenshots: screenshot, focus, status bar
    - TestElementTreeWalker: element tree walking and filtering
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call
import asyncio
from typing import Any, Dict, cast

from sap.session import Session, FieldValue
from sap.inspector import ElementInfo, ElementTreeWalker


# ─────────────────────────────────────────────────────────────────
# Fixtures for mock queue_manager and mock COM objects
# ─────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_queue_manager() -> MagicMock:
    """Create a mock QueueManager with AsyncMock for call_async."""
    qm = MagicMock()
    qm.call_async = AsyncMock()
    return qm


@pytest.fixture
def session(mock_queue_manager: MagicMock) -> Session:
    """Create a Session instance with mocked queue_manager."""
    return Session(
        queue_manager=mock_queue_manager,
        username="testuser",
        session_id="test_session_001"
    )


# ─────────────────────────────────────────────────────────────────
# TestSessionInitialization
# ─────────────────────────────────────────────────────────────────

class TestSessionInitialization:
    """Tests for Session initialization."""
    
    def test_session_initializes_with_queue_manager(self, mock_queue_manager: MagicMock) -> None:
        """Test that Session initializes correctly."""
        session = Session(mock_queue_manager, "user123")
        
        assert session._queue_manager is mock_queue_manager
        assert session._username == "user123"
        assert session._connected is True
        assert session._session_id is not None
    
    def test_session_initializes_with_custom_session_id(self, mock_queue_manager: MagicMock) -> None:
        """Test that Session uses custom session_id if provided."""
        session = Session(mock_queue_manager, "user123", session_id="my_session")
        
        assert session._session_id == "my_session"
    
    def test_session_rejects_none_queue_manager(self) -> None:
        """Test that Session rejects None queue_manager."""
        with pytest.raises(ValueError, match="queue_manager cannot be None"):
            # Cast None to QueueManager type for testing error handling
            # The actual runtime validation in __init__ will catch this and raise ValueError
            invalid_qm = cast(Any, None)
            Session(invalid_qm, "user123")
    
    def test_session_is_connected_initially_true(self, session: Session) -> None:
        """Test that session is connected initially."""
        assert session.is_connected() is True


# ─────────────────────────────────────────────────────────────────
# TestSessionConnectionLifecycle
# ─────────────────────────────────────────────────────────────────

class TestSessionConnectionLifecycle:
    """Tests for session connection lifecycle methods."""
    
    @pytest.mark.asyncio
    async def test_close_disconnects_session(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test that close() disconnects the session."""
        mock_queue_manager.call_async.return_value = None
        
        await session.close()
        
        assert session.is_connected() is False
        mock_queue_manager.call_async.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close_is_idempotent(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test that close() can be called multiple times safely."""
        mock_queue_manager.call_async.return_value = None
        
        await session.close()
        await session.close()
        
        # Should only call once (second close exits early)
        assert mock_queue_manager.call_async.call_count == 1
    
    @pytest.mark.asyncio
    async def test_close_raises_when_queue_manager_fails(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test that close() raises when queue_manager fails."""
        mock_queue_manager.call_async.side_effect = RuntimeError("COM error")
        
        with pytest.raises(RuntimeError, match="Failed to close session"):
            await session.close()
        
        assert session.is_connected() is False


# ─────────────────────────────────────────────────────────────────
# TestSessionNavigation
# ─────────────────────────────────────────────────────────────────

class TestSessionNavigation:
    """Tests for navigation methods."""
    
    @pytest.mark.asyncio
    async def test_start_transaction(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test starting a transaction."""
        mock_queue_manager.call_async.return_value = None
        
        await session.start_transaction('VA01')
        
        mock_queue_manager.call_async.assert_called_once_with(
            'GuiSession.StartTransaction',
            session_id='test_session_001',
            transaction_code='VA01'
        )
    
    @pytest.mark.asyncio
    async def test_start_transaction_when_disconnected(self, session: Session) -> None:
        """Test start_transaction raises when disconnected."""
        session._connected = False
        
        with pytest.raises(RuntimeError, match="Session not connected"):
            await session.start_transaction('VA01')
    
    @pytest.mark.asyncio
    async def test_get_current_screen_id(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test getting the current screen ID."""
        mock_queue_manager.call_async.return_value = "wnd[0]"
        
        result = await session.get_current_screen_id()
        
        assert result == "wnd[0]"
        mock_queue_manager.call_async.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_go_back(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test going back to previous screen."""
        mock_queue_manager.call_async.return_value = None
        
        await session.go_back()
        
        mock_queue_manager.call_async.assert_called_once_with(
            'GuiSession.GoBack',
            session_id='test_session_001'
        )
    
    @pytest.mark.asyncio
    async def test_go_home(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test going to SAP home."""
        mock_queue_manager.call_async.return_value = None
        
        await session.go_home()
        
        mock_queue_manager.call_async.assert_called_once_with(
            'GuiSession.GoHome',
            session_id='test_session_001'
        )


# ─────────────────────────────────────────────────────────────────
# TestSessionFieldOperations
# ─────────────────────────────────────────────────────────────────

class TestSessionFieldOperations:
    """Tests for field get/set operations."""
    
    @pytest.mark.asyncio
    async def test_get_field_value(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test reading a field value."""
        mock_queue_manager.call_async.return_value = "12345"
        
        result = await session.get_field_value('I[:VBELN]')
        
        assert result == "12345"
        mock_queue_manager.call_async.assert_called_once_with(
            'GuiElement.GetValue',
            session_id='test_session_001',
            field_id='I[:VBELN]'
        )
    
    @pytest.mark.asyncio
    async def test_get_field_value_when_disconnected(self, session: Session) -> None:
        """Test get_field_value raises when disconnected."""
        session._connected = False
        
        with pytest.raises(RuntimeError, match="Session not connected"):
            await session.get_field_value('I[:FIELD]')
    
    @pytest.mark.asyncio
    async def test_set_field_value(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test setting a field value."""
        mock_queue_manager.call_async.return_value = None
        
        await session.set_field_value('I[:VBELN]', '12345')
        
        mock_queue_manager.call_async.assert_called_once_with(
            'GuiElement.SetValue',
            session_id='test_session_001',
            field_id='I[:VBELN]',
            value='12345'
        )
    
    @pytest.mark.asyncio
    async def test_set_field_value_converts_to_string(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test that set_field_value converts values to string."""
        mock_queue_manager.call_async.return_value = None
        
        await session.set_field_value('I[:QTY]', 100)  # int
        
        call_args = mock_queue_manager.call_async.call_args
        assert call_args[1]['value'] == '100'
    
    @pytest.mark.asyncio
    async def test_get_field_property(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test getting a field property."""
        mock_queue_manager.call_async.return_value = True
        
        result = await session.get_field_property('I[:FIELD]', 'Visible')
        
        assert result is True
        mock_queue_manager.call_async.assert_called_once()


# ─────────────────────────────────────────────────────────────────
# TestSessionControlInteractions
# ─────────────────────────────────────────────────────────────────

class TestSessionControlInteractions:
    """Tests for control interaction methods."""
    
    @pytest.mark.asyncio
    async def test_click_button(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test clicking a button."""
        mock_queue_manager.call_async.return_value = None
        
        await session.click_button('ENTER')
        
        mock_queue_manager.call_async.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_click_button_with_path(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test clicking a button by element path."""
        mock_queue_manager.call_async.return_value = None
        
        await session.click_button('[/app/scr/btn_ok]')
        
        mock_queue_manager.call_async.assert_called_once_with(
            'GuiElement.Click',
            session_id='test_session_001',
            button_id='[/app/scr/btn_ok]'
        )
    
    @pytest.mark.asyncio
    async def test_send_key(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test sending a virtual key."""
        mock_queue_manager.call_async.return_value = None
        
        await session.send_key(0)  # Enter
        
        mock_queue_manager.call_async.assert_called_once_with(
            'GuiSession.SendKey',
            session_id='test_session_001',
            key_code=0
        )
    
    @pytest.mark.asyncio
    async def test_send_key_f8(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test sending F8 (Execute)."""
        mock_queue_manager.call_async.return_value = None
        
        await session.send_key(8)  # F8
        
        mock_queue_manager.call_async.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_left_click(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test left-clicking an element."""
        mock_queue_manager.call_async.return_value = None
        
        await session.left_click('[/app/scr/grid_0]')
        
        mock_queue_manager.call_async.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_right_click(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test right-clicking an element."""
        mock_queue_manager.call_async.return_value = None
        
        await session.right_click('[/app/scr/grid_0]')
        
        mock_queue_manager.call_async.assert_called_once()


# ─────────────────────────────────────────────────────────────────
# TestSessionElementDiscovery
# ─────────────────────────────────────────────────────────────────

class TestSessionElementDiscovery:
    """Tests for element discovery methods."""
    
    @pytest.mark.asyncio
    async def test_find_element(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test finding an element."""
        mock_queue_manager.call_async.return_value = {
            'id': 'I[:VBELN]',
            'type': 'GuiTextField',
            'text': 'Sales Order',
            'value': '12345',
            'visible': True,
            'enabled': True
        }
        
        result = await session.find_element('I[:VBELN]')
        
        assert result['id'] == 'I[:VBELN]'
        assert result['type'] == 'GuiTextField'
        mock_queue_manager.call_async.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_find_elements_by_type(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test finding all elements by type."""
        mock_queue_manager.call_async.return_value = [
            {'id': 'btn[1]', 'type': 'GuiButton', 'text': 'Save'},
            {'id': 'btn[2]', 'type': 'GuiButton', 'text': 'Delete'},
        ]
        
        result = await session.find_elements_by_type('GuiButton')
        
        assert len(result) == 2
        assert result[0]['text'] == 'Save'
        mock_queue_manager.call_async.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_find_elements_by_type_empty_result(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test find_elements_by_type returns empty list when no matches."""
        mock_queue_manager.call_async.return_value = []
        
        result = await session.find_elements_by_type('NonExistentType')
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_get_element_tree(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test getting element tree."""
        mock_queue_manager.call_async.return_value = {
            'id': '[/app/con[0]/ses[0]/wnd[0]]',
            'type': 'GuiMainWindow',
            'text': 'SAP',
            'children': [
                {'id': 'toolbar', 'type': 'GuiToolbar', 'text': '', 'children': []}
            ]
        }
        
        result = await session.get_element_tree()
        
        # get_element_tree returns a flattened list of element dicts
        assert isinstance(result, list)
        assert len(result) >= 1
        assert result[0]['element_type'] == 'GuiMainWindow'
        mock_queue_manager.call_async.assert_called_once()


# ─────────────────────────────────────────────────────────────────
# TestSessionDataExtraction
# ─────────────────────────────────────────────────────────────────

class TestSessionDataExtraction:
    """Tests for grid and data extraction methods."""
    
    @pytest.mark.asyncio
    async def test_read_grid(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test reading data from a grid."""
        mock_queue_manager.call_async.return_value = [
            {'column1': 'value1', 'column2': 'value2'},
            {'column1': 'value3', 'column2': 'value4'},
        ]
        
        result = await session.read_grid('[/app/scr/grid_0]')
        
        assert len(result) == 2
        assert result[0]['column1'] == 'value1'
        mock_queue_manager.call_async.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_read_grid_empty(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test reading an empty grid."""
        mock_queue_manager.call_async.return_value = []
        
        result = await session.read_grid('[/app/scr/grid_0]')
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_read_grid_with_max_rows(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test reading grid with max_rows parameter."""
        mock_queue_manager.call_async.return_value = []
        
        await session.read_grid('[/app/scr/grid_0]', max_rows=100)
        
        call_kwargs = mock_queue_manager.call_async.call_args[1]
        assert call_kwargs['max_rows'] == 100
    
    @pytest.mark.asyncio
    async def test_get_grid_value(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test getting a single grid cell."""
        mock_queue_manager.call_async.return_value = "cell_value"
        
        result = await session.get_grid_value('[/app/scr/grid_0]', 0, 1)
        
        assert result == "cell_value"
        mock_queue_manager.call_async.assert_called_once_with(
            'GuiGrid.GetValue',
            session_id='test_session_001',
            grid_id='[/app/scr/grid_0]',
            row=0,
            col=1
        )
    
    @pytest.mark.asyncio
    async def test_set_grid_value(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test setting a grid cell value."""
        mock_queue_manager.call_async.return_value = None
        
        await session.set_grid_value('[/app/scr/grid_0]', 0, 1, 'new_value')
        
        mock_queue_manager.call_async.assert_called_once_with(
            'GuiGrid.SetValue',
            session_id='test_session_001',
            grid_id='[/app/scr/grid_0]',
            row=0,
            col=1,
            value='new_value'
        )


# ─────────────────────────────────────────────────────────────────
# TestSessionScreenshots
# ─────────────────────────────────────────────────────────────────

class TestSessionScreenshots:
    """Tests for screenshot and state methods."""
    
    @pytest.mark.asyncio
    async def test_take_screenshot(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test taking a screenshot."""
        mock_queue_manager.call_async.return_value = b'\x89PNG\r\n\x1a\n'
        
        result = await session.take_screenshot()
        
        assert isinstance(result, bytes)
        mock_queue_manager.call_async.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_focus_element(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test getting focused element."""
        mock_queue_manager.call_async.return_value = "I[:FOCUSED_FIELD]"
        
        result = await session.get_focus_element()
        
        assert result == "I[:FOCUSED_FIELD]"
        mock_queue_manager.call_async.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_status_bar(self, session: Session, mock_queue_manager: MagicMock) -> None:
        """Test getting status bar text."""
        mock_queue_manager.call_async.return_value = "Ready"
        
        result = await session.get_status_bar()
        
        assert result == "Ready"
        mock_queue_manager.call_async.assert_called_once()


# ─────────────────────────────────────────────────────────────────
# TestElementTreeWalker
# ─────────────────────────────────────────────────────────────────

class TestElementTreeWalker:
    """Tests for ElementTreeWalker functionality."""
    
    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Create mock session."""
        session = MagicMock()
        session.get_element_tree = AsyncMock()
        return session
    
    def test_walker_initializes(self, mock_session: MagicMock) -> None:
        """Test ElementTreeWalker initialization."""
        walker = ElementTreeWalker(mock_session)
        
        assert walker.session is mock_session
        assert walker._cache == {}
    
    def test_walker_rejects_none_session(self) -> None:
        """Test walker rejects None session."""
        with pytest.raises(ValueError, match="session cannot be None"):
            ElementTreeWalker(None)
    
    @pytest.mark.asyncio
    async def test_get_element_tree(self, mock_session: MagicMock) -> None:
        """Test getting element tree."""
        mock_session.get_element_tree.return_value = [
            {'element_id': '[/app/con[0]/ses[0]/wnd[0]]', 'element_type': 'GuiMainWindow', 'name': 'Main', 
             'text': 'SAP', 'x': 0, 'y': 0, 'width': 800, 'height': 600,
             'visible': True, 'enabled': True, 'value': None, 'parent_id': None}
        ]
        
        walker = ElementTreeWalker(mock_session)
        result = await walker.get_element_tree()
        
        assert isinstance(result, ElementInfo)
        assert result.element_id == '[/app/con[0]/ses[0]/wnd[0]]'
        assert result.element_type == 'GuiMainWindow'
    
    @pytest.mark.asyncio
    async def test_get_element_tree_caches_result(self, mock_session: MagicMock) -> None:
        """Test that get_element_tree caches results."""
        mock_session.get_element_tree.return_value = [
            {'element_id': '[/app/con[0]/ses[0]/wnd[0]]', 'element_type': 'GuiMainWindow', 'name': 'Main',
             'text': 'SAP', 'x': 0, 'y': 0, 'width': 800, 'height': 600,
             'visible': True, 'enabled': True, 'value': None, 'parent_id': None}
        ]
        
        walker = ElementTreeWalker(mock_session)
        
        result1 = await walker.get_element_tree()
        result2 = await walker.get_element_tree()  # Should use cache
        
        # Should be called only once (cached on second call)
        assert mock_session.get_element_tree.call_count == 1
    
    @pytest.mark.asyncio
    async def test_get_element_tree_with_refresh(self, mock_session: MagicMock) -> None:
        """Test that refresh=True bypasses cache."""
        mock_session.get_element_tree.return_value = [
            {'element_id': '[/app/con[0]/ses[0]/wnd[0]]', 'element_type': 'GuiMainWindow', 'name': 'Main',
             'text': 'SAP', 'x': 0, 'y': 0, 'width': 800, 'height': 600,
             'visible': True, 'enabled': True, 'value': None, 'parent_id': None}
        ]
        
        walker = ElementTreeWalker(mock_session)
        
        await walker.get_element_tree()
        await walker.get_element_tree(refresh=True)
        
        # Should be called twice (refresh bypasses cache)
        assert mock_session.get_element_tree.call_count == 2
    
    @pytest.mark.asyncio
    async def test_find_element_by_type(self, mock_session: MagicMock) -> None:
        """Test finding element by type."""
        mock_session.get_element_tree.return_value = [
            {'element_id': '[/app/con[0]/ses[0]/wnd[0]]', 'element_type': 'GuiMainWindow', 'name': 'Main',
             'text': 'SAP', 'x': 0, 'y': 0, 'width': 800, 'height': 600,
             'visible': True, 'enabled': True, 'value': None, 'parent_id': None},
            {'element_id': 'field1', 'element_type': 'GuiTextField', 'name': 'Order',
             'text': 'Sales Order', 'x': 0, 'y': 30, 'width': 100, 'height': 20,
             'visible': True, 'enabled': True, 'value': None, 'parent_id': '[/app/con[0]/ses[0]/wnd[0]]'}
        ]
        
        walker = ElementTreeWalker(mock_session)
        result = await walker.find_element(element_type='GuiTextField')
        
        assert result is not None
        assert result.element_type == 'GuiTextField'
    
    @pytest.mark.asyncio
    async def test_find_element_by_name(self, mock_session: MagicMock) -> None:
        """Test finding element by name."""
        mock_session.get_element_tree.return_value = [
            {'element_id': '[/app/con[0]/ses[0]/wnd[0]]', 'element_type': 'GuiMainWindow', 'name': 'Main',
             'text': 'SAP', 'x': 0, 'y': 0, 'width': 800, 'height': 600,
             'visible': True, 'enabled': True, 'value': None, 'parent_id': None},
            {'element_id': 'field1', 'element_type': 'GuiTextField', 'name': 'Order',
             'text': 'Sales Order', 'x': 0, 'y': 30, 'width': 100, 'height': 20,
             'visible': True, 'enabled': True, 'value': None, 'parent_id': '[/app/con[0]/ses[0]/wnd[0]]'}
        ]
        
        walker = ElementTreeWalker(mock_session)
        result = await walker.find_element(name='Order')
        
        assert result is not None
        assert result.name == 'Order'
    
    @pytest.mark.asyncio
    async def test_find_element_with_predicate(self, mock_session: MagicMock) -> None:
        """Test finding element with custom predicate."""
        mock_session.get_element_tree.return_value = [
            {'element_id': '[/app/con[0]/ses[0]/wnd[0]]', 'element_type': 'GuiMainWindow', 'name': 'Main',
             'text': 'SAP', 'x': 0, 'y': 0, 'width': 800, 'height': 600,
             'visible': True, 'enabled': True, 'value': None, 'parent_id': None},
            {'element_id': 'field1', 'element_type': 'GuiTextField', 'name': 'Order',
             'text': 'Sales Order', 'x': 0, 'y': 30, 'width': 100, 'height': 20,
             'visible': True, 'enabled': True, 'value': None, 'parent_id': '[/app/con[0]/ses[0]/wnd[0]]'}
        ]
        
        walker = ElementTreeWalker(mock_session)
        result = await walker.find_element(
            predicate=lambda e: e.visible and 'Order' in e.name
        )
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_find_elements_returns_multiple(self, mock_session: MagicMock) -> None:
        """Test finding multiple elements."""
        mock_session.get_element_tree.return_value = [
            {'element_id': '[/app/con[0]/ses[0]/wnd[0]]', 'element_type': 'GuiMainWindow', 'name': 'Main',
             'text': 'SAP', 'x': 0, 'y': 0, 'width': 800, 'height': 600,
             'visible': True, 'enabled': True, 'value': None, 'parent_id': None},
            {'element_id': 'btn1', 'element_type': 'GuiButton', 'name': 'Save',
             'text': 'Save', 'x': 0, 'y': 30, 'width': 80, 'height': 20,
             'visible': True, 'enabled': True, 'value': None, 'parent_id': '[/app/con[0]/ses[0]/wnd[0]]'},
            {'element_id': 'btn2', 'element_type': 'GuiButton', 'name': 'Delete',
             'text': 'Delete', 'x': 100, 'y': 30, 'width': 80, 'height': 20,
             'visible': True, 'enabled': True, 'value': None, 'parent_id': '[/app/con[0]/ses[0]/wnd[0]]'}
        ]
        
        walker = ElementTreeWalker(mock_session)
        results = await walker.find_elements(element_type='GuiButton')
        
        assert len(results) == 2
    
    @pytest.mark.asyncio
    async def test_find_elements_returns_empty_list(self, mock_session: MagicMock) -> None:
        """Test find_elements returns empty list when no matches."""
        mock_session.get_element_tree.return_value = [
            {
                'element_id': '[/app/con[0]/ses[0]/wnd[0]]',
                'element_type': 'GuiMainWindow',
                'name': 'Main',
                'text': 'SAP',
                'x': 0, 'y': 0, 'width': 800, 'height': 600,
                'visible': True, 'enabled': True, 'value': None,
                'parent_id': None
            }
        ]
        
        walker = ElementTreeWalker(mock_session)
        results = await walker.find_elements(element_type='NonExistent')
        
        assert results == []
    
    def test_clear_cache(self, mock_session: MagicMock) -> None:
        """Test clearing cache."""
        walker = ElementTreeWalker(mock_session)
        walker._cache['test'] = MagicMock()
        
        walker.clear_cache()
        
        assert walker._cache == {}
    
    def test_get_cache_info(self, mock_session: MagicMock) -> None:
        """Test getting cache info."""
        walker = ElementTreeWalker(mock_session)
        
        info = walker.get_cache_info()
        
        assert 'item_count' in info
        assert 'cache_size_bytes' in info
        assert info['item_count'] == 0
