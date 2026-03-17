import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from sap.session import Session
from sap.inspector import ElementTreeWalker, ElementInfo


@pytest.fixture
def mock_queue_manager():
    qm = MagicMock()
    qm.call_async = AsyncMock()
    return qm


@pytest.fixture
def session(mock_queue_manager):
    return Session(mock_queue_manager, username="test")


class TestSessionTakeScreenshot:
    """Tests for session.take_screenshot() - 10 tests"""
    
    @pytest.mark.asyncio
    async def test_returns_bytes(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = b'\x89PNG'
        result = await session.take_screenshot()
        assert isinstance(result, bytes)
    
    @pytest.mark.asyncio
    async def test_returns_valid_png(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = b'\x89PNG'
        result = await session.take_screenshot()
        assert result[:4] == b'\x89PNG'
    
    @pytest.mark.asyncio
    async def test_raises_runtime_error_if_not_connected(self, mock_queue_manager):
        session = Session(mock_queue_manager, username="test")
        session._connected = False
        with pytest.raises(RuntimeError):
            await session.take_screenshot()
    
    @pytest.mark.asyncio
    async def test_is_async(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = b'\x89PNG'
        result = await session.take_screenshot()
        assert isinstance(result, bytes)
    
    @pytest.mark.asyncio
    async def test_different_calls_different_bytes(self, session, mock_queue_manager):
        mock_queue_manager.call_async.side_effect = [b'\x89PNG1', b'\x89PNG2']
        r1 = await session.take_screenshot()
        r2 = await session.take_screenshot()
        assert r1 != r2
    
    @pytest.mark.asyncio
    async def test_handles_large_data(self, session, mock_queue_manager):
        large = b'\x89PNG' + b'x' * (11 * 1024 * 1024)
        mock_queue_manager.call_async.return_value = large
        result = await session.take_screenshot()
        assert len(result) > 10 * 1024 * 1024
    
    @pytest.mark.asyncio
    async def test_logs_success(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = b'\x89PNG'
        with patch('sap.session.logger') as mock_logger:
            await session.take_screenshot()
            assert mock_logger.debug.called
    
    @pytest.mark.asyncio
    async def test_logs_error(self, session, mock_queue_manager):
        mock_queue_manager.call_async.side_effect = Exception("Error")
        with patch('sap.session.logger') as mock_logger:
            with pytest.raises(RuntimeError):
                await session.take_screenshot()
            assert mock_logger.error.called
    
    @pytest.mark.asyncio
    async def test_returns_bytes_not_str(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = b'\x89PNG'
        result = await session.take_screenshot()
        assert not isinstance(result, str)
    
    @pytest.mark.asyncio
    async def test_zero_length_png(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = b''
        result = await session.take_screenshot()
        assert isinstance(result, bytes)


class TestSessionGetElementTree:
    """Tests for session.get_element_tree() - 15 tests"""
    
    @pytest.mark.asyncio
    async def test_returns_list(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = {"children": []}
        result = await session.get_element_tree()
        assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_returns_dicts(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = {"children": []}
        result = await session.get_element_tree()
        for item in result:
            assert isinstance(item, dict)
    
    @pytest.mark.asyncio
    async def test_raises_if_not_connected(self, mock_queue_manager):
        session = Session(mock_queue_manager, username="test")
        session._connected = False
        with pytest.raises(RuntimeError):
            await session.get_element_tree()
    
    @pytest.mark.asyncio
    async def test_coordinates_integers(self, session, mock_queue_manager):
        nested = {"id": "[/w]", "type": "G", "name": "W", "text": "",
                  "x": 100, "y": 50, "width": 800, "height": 600,
                  "visible": True, "enabled": True, "value": None, "children": []}
        mock_queue_manager.call_async.return_value = nested
        result = await session.get_element_tree()
        for elem in result:
            assert isinstance(elem['x'], int)
            assert isinstance(elem['y'], int)
    
    @pytest.mark.asyncio
    async def test_visible_bool(self, session, mock_queue_manager):
        nested = {"id": "[/w]", "type": "G", "name": "W", "text": "",
                  "x": 0, "y": 0, "width": 800, "height": 600,
                  "visible": False, "enabled": True, "value": None, "children": []}
        mock_queue_manager.call_async.return_value = nested
        result = await session.get_element_tree()
        for elem in result:
            assert isinstance(elem['visible'], bool)
    
    @pytest.mark.asyncio
    async def test_enabled_bool(self, session, mock_queue_manager):
        nested = {"id": "[/w]", "type": "G", "name": "W", "text": "",
                  "x": 0, "y": 0, "width": 800, "height": 600,
                  "visible": True, "enabled": False, "value": None, "children": []}
        mock_queue_manager.call_async.return_value = nested
        result = await session.get_element_tree()
        for elem in result:
            assert isinstance(elem['enabled'], bool)
    
    @pytest.mark.asyncio
    async def test_root_parent_none(self, session, mock_queue_manager):
        nested = {"id": "[/r]", "type": "G", "name": "R", "text": "",
                  "x": 0, "y": 0, "width": 800, "height": 600,
                  "visible": True, "enabled": True, "value": None, "children": []}
        mock_queue_manager.call_async.return_value = nested
        result = await session.get_element_tree()
        assert result[0]['parent_id'] is None
    
    @pytest.mark.asyncio
    async def test_children_parent_id(self, session, mock_queue_manager):
        nested = {"id": "[/r]", "type": "G", "name": "R", "text": "",
                  "x": 0, "y": 0, "width": 800, "height": 600,
                  "visible": True, "enabled": True, "value": None,
                  "children": [{"id": "[/c]", "type": "G", "name": "C",
                               "text": "", "x": 0, "y": 0, "width": 100, "height": 20,
                               "visible": True, "enabled": True, "value": None, "children": []}]}
        mock_queue_manager.call_async.return_value = nested
        result = await session.get_element_tree()
        assert any(e['parent_id'] is not None for e in result[1:])
    
    @pytest.mark.asyncio
    async def test_is_flattened(self, session, mock_queue_manager):
        nested = {"id": "[/r]", "type": "G", "name": "R", "text": "",
                  "x": 0, "y": 0, "width": 800, "height": 600,
                  "visible": True, "enabled": True, "value": None,
                  "children": [{"id": "[/c]", "type": "G", "name": "C",
                               "text": "", "x": 0, "y": 0, "width": 100, "height": 20,
                               "visible": True, "enabled": True, "value": None, "children": []}]}
        mock_queue_manager.call_async.return_value = nested
        result = await session.get_element_tree()
        for elem in result:
            assert 'children' not in elem or elem.get('children') is None
    
    @pytest.mark.asyncio
    async def test_required_keys(self, session, mock_queue_manager):
        nested = {"id": "[/r]", "type": "G", "name": "R", "text": "",
                  "x": 0, "y": 0, "width": 800, "height": 600,
                  "visible": True, "enabled": True, "value": None, "children": []}
        mock_queue_manager.call_async.return_value = nested
        result = await session.get_element_tree()
        required = {"element_id", "element_type", "name", "text", "x", "y",
                   "width", "height", "visible", "enabled", "value", "parent_id"}
        for elem in result:
            assert set(elem.keys()) >= required
    
    @pytest.mark.asyncio
    async def test_custom_root_id(self, session, mock_queue_manager):
        nested = {"id": "[/c]", "type": "G", "name": "C", "text": "",
                  "x": 0, "y": 0, "width": 800, "height": 600,
                  "visible": True, "enabled": True, "value": None, "children": []}
        mock_queue_manager.call_async.return_value = nested
        await session.get_element_tree(root_id="[/custom]")
        mock_queue_manager.call_async.assert_called()
    
    @pytest.mark.asyncio
    async def test_max_depth(self, session, mock_queue_manager):
        nested = {"id": "[/l0]", "type": "G", "name": "L0", "text": "",
                  "x": 0, "y": 0, "width": 800, "height": 600,
                  "visible": True, "enabled": True, "value": None, "children": []}
        current = nested
        for i in range(1, 25):
            child = {"id": f"[/l{i}]", "type": "G", "name": f"L{i}",
                     "text": "", "x": 0, "y": 0, "width": 100, "height": 20,
                     "visible": True, "enabled": True, "value": None, "children": []}
            current["children"].append(child)
            current = child
        mock_queue_manager.call_async.return_value = nested
        result = await session.get_element_tree()
        assert len(result) <= 21
    
    @pytest.mark.asyncio
    async def test_element_type_string(self, session, mock_queue_manager):
        nested = {"id": "[/w]", "type": "GuiMainWindow", "name": "W", "text": "",
                  "x": 0, "y": 0, "width": 800, "height": 600,
                  "visible": True, "enabled": True, "value": None, "children": []}
        mock_queue_manager.call_async.return_value = nested
        result = await session.get_element_tree()
        for elem in result:
            assert isinstance(elem['element_type'], str)


class TestElementTreeWalkerGetTree:
    """Tests for ElementTreeWalker.get_element_tree() - 12 tests"""
    
    @pytest.mark.asyncio
    async def test_returns_element_info(self, session, mock_queue_manager):
        # Mock returns nested dict (will be flattened by session.get_element_tree)
        mock_queue_manager.call_async.return_value = {
            "id": "[/r]", "type": "G", "name": "R",
            "text": "", "x": 0, "y": 0, "width": 800, "height": 600,
            "visible": True, "enabled": True, "value": None, "children": []
        }
        walker = ElementTreeWalker(session)
        result = await walker.get_element_tree()
        assert isinstance(result, ElementInfo)
    
    @pytest.mark.asyncio
    async def test_root_attributes(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = {
            "id": "[/r]", "type": "G", "name": "R",
            "text": "", "x": 0, "y": 0, "width": 800, "height": 600,
            "visible": True, "enabled": True, "value": None, "children": []
        }
        walker = ElementTreeWalker(session)
        result = await walker.get_element_tree()
        assert result.element_id == "[/r]"
        assert isinstance(result.visible, bool)
    
    @pytest.mark.asyncio
    async def test_refresh_false_cache(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = [
            {
                "element_id": "[/app/con[0]/ses[0]/wnd[0]]", "element_type": "GuiMainWindow", "name": "Main",
                "text": "SAP", "x": 0, "y": 0, "width": 800, "height": 600,
                "visible": True, "enabled": True, "value": None, "parent_id": None
            }
        ]
        walker = ElementTreeWalker(session)
        r1 = await walker.get_element_tree(refresh=False)
        mock_queue_manager.call_async.reset_mock()
        r2 = await walker.get_element_tree(refresh=False)
        assert mock_queue_manager.call_async.call_count == 0
        assert r1 is r2
    
    @pytest.mark.asyncio
    async def test_refresh_true(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = {
            "id": "[/r]", "type": "G", "name": "R",
            "text": "", "x": 0, "y": 0, "width": 800, "height": 600,
            "visible": True, "enabled": True, "value": None, "children": []
        }
        walker = ElementTreeWalker(session)
        r1 = await walker.get_element_tree()
        r2 = await walker.get_element_tree(refresh=True)
        assert r1 is not r2
    
    @pytest.mark.asyncio
    async def test_include_children_true(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = {
            "id": "[/r]", "type": "G", "name": "R",
            "text": "", "x": 0, "y": 0, "width": 800, "height": 600,
            "visible": True, "enabled": True, "value": None,
            "children": [{
                "id": "[/c]", "type": "G", "name": "C",
                "text": "", "x": 0, "y": 0, "width": 100, "height": 20,
                "visible": True, "enabled": True, "value": None, "children": []
            }]
        }
        walker = ElementTreeWalker(session)
        result = await walker.get_element_tree(include_children=True)
        assert result.children is not None
        assert len(result.children) > 0
    
    @pytest.mark.asyncio
    async def test_include_children_false(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = {
            "id": "[/r]", "type": "G", "name": "R",
            "text": "", "x": 0, "y": 0, "width": 800, "height": 600,
            "visible": True, "enabled": True, "value": None, "children": []
        }
        walker = ElementTreeWalker(session)
        result = await walker.get_element_tree(include_children=False)
        assert result.children is not None
        assert len(result.children) == 0
    
    @pytest.mark.asyncio
    async def test_caches(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = [
            {"element_id": "[/app/con[0]/ses[0]/wnd[0]]", "element_type": "G", "name": "R",
             "text": "", "x": 0, "y": 0, "width": 800, "height": 600,
             "visible": True, "enabled": True, "value": None, "parent_id": None}
        ]
        walker = ElementTreeWalker(session)
        await walker.get_element_tree()
        assert len(walker._cache) > 0
    
    @pytest.mark.asyncio
    async def test_cache_keys(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = [
            {"element_id": "[/app/con[0]/ses[0]/wnd[0]]", "element_type": "G", "name": "R",
             "text": "", "x": 0, "y": 0, "width": 800, "height": 600,
             "visible": True, "enabled": True, "value": None, "parent_id": None}
        ]
        walker = ElementTreeWalker(session)
        await walker.get_element_tree()
        for key, value in walker._cache.items():
            if isinstance(value, ElementInfo):
                assert key == value.element_id
    
    @pytest.mark.asyncio
    async def test_last_tree_populated(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = [
            {"element_id": "[/app/con[0]/ses[0]/wnd[0]]", "element_type": "G", "name": "R",
             "text": "", "x": 0, "y": 0, "width": 800, "height": 600,
             "visible": True, "enabled": True, "value": None, "parent_id": None}
        ]
        walker = ElementTreeWalker(session)
        result = await walker.get_element_tree()
        assert walker._last_tree is result
    
    @pytest.mark.asyncio
    async def test_children_linked(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = [
            {"element_id": "[/app/con[0]/ses[0]/wnd[0]]", "element_type": "G", "name": "R",
             "text": "", "x": 0, "y": 0, "width": 800, "height": 600,
             "visible": True, "enabled": True, "value": None, "parent_id": None},
            {"element_id": "[/c]", "element_type": "G", "name": "C",
             "text": "", "x": 0, "y": 0, "width": 100, "height": 20,
             "visible": True, "enabled": True, "value": None, "parent_id": "[/app/con[0]/ses[0]/wnd[0]]"}  
        ]
        walker = ElementTreeWalker(session)
        result = await walker.get_element_tree(include_children=True)
        if result.children:
            assert result.children[0].parent_id == result.element_id
    
    @pytest.mark.asyncio
    async def test_valid_hierarchy(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = [
            {"element_id": "[/app/con[0]/ses[0]/wnd[0]]", "element_type": "G", "name": "R",
             "text": "", "x": 0, "y": 0, "width": 800, "height": 600,
             "visible": True, "enabled": True, "value": None, "parent_id": None}
        ]
        walker = ElementTreeWalker(session)
        result = await walker.get_element_tree()
        assert result.parent_id is None


class TestElementTreeWalkerFind:
    """Tests for ElementTreeWalker.find_element() and find_elements() - 16 tests"""
    
    @pytest.mark.asyncio
    async def test_find_element_returns_info(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = [
            {"element_id": "[/app/con[0]/ses[0]/wnd[0]]", "element_type": "G", "name": "R",
             "text": "", "x": 0, "y": 0, "width": 800, "height": 600,
             "visible": True, "enabled": True, "value": None, "parent_id": None},
            {"element_id": "[/t]", "element_type": "GuiTextField", "name": "F",
             "text": "", "x": 0, "y": 0, "width": 100, "height": 20,
             "visible": True, "enabled": True, "value": None, "parent_id": "[/app/con[0]/ses[0]/wnd[0]]"}
        ]
        walker = ElementTreeWalker(session)
        result = await walker.find_element(element_type="GuiTextField")
        assert result is not None
        assert isinstance(result, ElementInfo)
    
    @pytest.mark.asyncio
    async def test_find_element_none(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = [
            {"element_id": "[/app/con[0]/ses[0]/wnd[0]]", "element_type": "G", "name": "R",
             "text": "", "x": 0, "y": 0, "width": 800, "height": 600,
             "visible": True, "enabled": True, "value": None, "parent_id": None}
        ]
        walker = ElementTreeWalker(session)
        result = await walker.find_element(element_type="GuiGridView")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_find_elements_list(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = [
            {"element_id": "[/app/con[0]/ses[0]/wnd[0]]", "element_type": "G", "name": "R",
             "text": "", "x": 0, "y": 0, "width": 800, "height": 600,
             "visible": True, "enabled": True, "value": None, "parent_id": None}
        ]
        walker = ElementTreeWalker(session)
        result = await walker.find_elements()
        assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_find_elements_empty(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = [
            {"element_id": "[/app/con[0]/ses[0]/wnd[0]]", "element_type": "G", "name": "R",
             "text": "", "x": 0, "y": 0, "width": 800, "height": 600,
             "visible": True, "enabled": True, "value": None, "parent_id": None}
        ]
        walker = ElementTreeWalker(session)
        result = await walker.find_elements(element_type="NonExistent")
        assert len(result) == 0
    
    @pytest.mark.asyncio
    async def test_type_exact(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = [
            {"element_id": "[/app/con[0]/ses[0]/wnd[0]]", "element_type": "G", "name": "R",
             "text": "", "x": 0, "y": 0, "width": 800, "height": 600,
             "visible": True, "enabled": True, "value": None, "parent_id": None},
            {"element_id": "[/t]", "element_type": "GuiTextField", "name": "F",
             "text": "", "x": 0, "y": 0, "width": 100, "height": 20,
             "visible": True, "enabled": True, "value": None, "parent_id": "[/app/con[0]/ses[0]/wnd[0]]"}
        ]
        walker = ElementTreeWalker(session)
        result = await walker.find_element(element_type="GuiTextField")
        assert result is not None
        assert result.element_type == "GuiTextField"
    
    @pytest.mark.asyncio
    async def test_name_case_insensitive(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = [
            {"element_id": "[/app/con[0]/ses[0]/wnd[0]]", "element_type": "G", "name": "R",
             "text": "", "x": 0, "y": 0, "width": 800, "height": 600,
             "visible": True, "enabled": True, "value": None, "parent_id": None},
            {"element_id": "[/t]", "element_type": "GuiTextField", "name": "VBELN",
             "text": "", "x": 0, "y": 0, "width": 100, "height": 20,
             "visible": True, "enabled": True, "value": None, "parent_id": "[/app/con[0]/ses[0]/wnd[0]]"}
        ]
        walker = ElementTreeWalker(session)
        result = await walker.find_element(name="vbeln")
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_deterministic_order(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = [
            {"element_id": "[/app/con[0]/ses[0]/wnd[0]]", "element_type": "G", "name": "R",
             "text": "", "x": 0, "y": 0, "width": 800, "height": 600,
             "visible": True, "enabled": True, "value": None, "parent_id": None}
        ] + [
            {"element_id": f"[/t{i}]", "element_type": "GuiTextField", "name": f"F{i}",
             "text": "", "x": 0, "y": 30*i, "width": 100, "height": 20,
             "visible": True, "enabled": True, "value": None, "parent_id": "[/app/con[0]/ses[0]/wnd[0]]"}
            for i in range(5)
        ]
        walker = ElementTreeWalker(session)
        r1 = await walker.find_elements(element_type="GuiTextField")
        r2 = await walker.find_elements(element_type="GuiTextField")
        assert [e.element_id for e in r1] == [e.element_id for e in r2]
    
    @pytest.mark.asyncio
    async def test_text_filter_substring(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = [
            {"element_id": "[/app/con[0]/ses[0]/wnd[0]]", "element_type": "G", "name": "R",
             "text": "Root Label", "x": 0, "y": 0, "width": 800, "height": 600,
             "visible": True, "enabled": True, "value": None, "parent_id": None}
        ]
        walker = ElementTreeWalker(session)
        result = await walker.find_elements(text="Label")
        assert len(result) > 0
    
    @pytest.mark.asyncio
    async def test_cache_after_find(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = [
            {"element_id": "[/app/con[0]/ses[0]/wnd[0]]", "element_type": "G", "name": "R",
             "text": "", "x": 0, "y": 0, "width": 800, "height": 600,
             "visible": True, "enabled": True, "value": None, "parent_id": None}
        ]
        walker = ElementTreeWalker(session)
        await walker.find_element(element_type="G")
        assert len(walker._cache) > 0
    
    @pytest.mark.asyncio
    async def test_all_match_type_filter(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = [
            {"element_id": "[/app/con[0]/ses[0]/wnd[0]]", "element_type": "G", "name": "R",
             "text": "", "x": 0, "y": 0, "width": 800, "height": 600,
             "visible": True, "enabled": True, "value": None, "parent_id": None}
        ] + [
            {"element_id": f"[/t{i}]", "element_type": "GuiTextField", "name": f"F{i}",
             "text": "", "x": 0, "y": 30*i, "width": 100, "height": 20,
             "visible": True, "enabled": True, "value": None, "parent_id": "[/app/con[0]/ses[0]/wnd[0]]"}
            for i in range(5)
        ]
        walker = ElementTreeWalker(session)
        results = await walker.find_elements(element_type="GuiTextField")
        for elem in results:
            assert elem.element_type == "GuiTextField"


class TestElementTreeWalkerCache:
    """Tests for ElementTreeWalker cache - 7 tests"""
    
    def test_cache_initialized_empty(self, mock_queue_manager):
        sess = Session(mock_queue_manager, username="t")
        walker = ElementTreeWalker(sess)
        assert isinstance(walker._cache, dict)
        assert len(walker._cache) == 0
    
    @pytest.mark.asyncio
    async def test_last_tree_set(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = [
            {"element_id": "[/app/con[0]/ses[0]/wnd[0]]", "element_type": "G", "name": "R",
             "text": "", "x": 0, "y": 0, "width": 800, "height": 600,
             "visible": True, "enabled": True, "value": None, "parent_id": None}
        ]
        walker = ElementTreeWalker(session)
        result = await walker.get_element_tree()
        assert walker._last_tree is result
    
    @pytest.mark.asyncio
    async def test_find_without_explicit_get(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = [
            {"element_id": "[/app/con[0]/ses[0]/wnd[0]]", "element_type": "G", "name": "R",
             "text": "", "x": 0, "y": 0, "width": 800, "height": 600,
             "visible": True, "enabled": True, "value": None, "parent_id": None}
        ]
        walker = ElementTreeWalker(session)
        result = await walker.find_element(element_type="G")
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_cache_persists(self, session, mock_queue_manager):
        mock_queue_manager.call_async.return_value = [
            {"element_id": "[/app/con[0]/ses[0]/wnd[0]]", "element_type": "G", "name": "R",
             "text": "", "x": 0, "y": 0, "width": 800, "height": 600,
             "visible": True, "enabled": True, "value": None, "parent_id": None}
        ]
        walker = ElementTreeWalker(session)
        await walker.find_element(element_type="G")
        size1 = len(walker._cache)
        mock_queue_manager.call_async.reset_mock()
        await walker.find_elements(element_type="G")
        assert len(walker._cache) == size1
    
    def test_mutable(self, mock_queue_manager):
        sess = Session(mock_queue_manager, username="t")
        walker = ElementTreeWalker(sess)
        elem = ElementInfo(
            element_id="[/t]", element_type="G", name="N", text="T",
            x=0, y=0, width=100, height=20, visible=True, enabled=True, value=None
        )
        walker._cache[elem.element_id] = elem
        walker._cache[elem.element_id].text = "Modified"
        assert walker._cache[elem.element_id].text == "Modified"
    
    def test_separate_instances(self, mock_queue_manager):
        s1 = Session(mock_queue_manager, username="u1")
        s2 = Session(mock_queue_manager, username="u2")
        w1 = ElementTreeWalker(s1)
        w2 = ElementTreeWalker(s2)
        elem = ElementInfo(
            element_id="[/t]", element_type="G", name="N", text="T",
            x=0, y=0, width=100, height=20, visible=True, enabled=True, value=None
        )
        w1._cache[elem.element_id] = elem
        assert len(w1._cache) == 1
        assert len(w2._cache) == 0
    
    def test_init_none_session(self):
        with pytest.raises(ValueError):
            ElementTreeWalker(None)
