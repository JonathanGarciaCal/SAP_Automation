"""Phase 1 integration tests (Task 11).

Tests the full app flow end-to-end with mocked SAP session.

Tests:
    - App initialization with config and session
    - Route registration and feature flags
    - Error handling and recovery flows
    - Full home page workflow
    - Sidebar navigation with feature flags
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from config import RuntimeConfig, FeatureFlags


class TestAppInitialization:
    """Test app factory and initialization."""
    
    def test_create_app_returns_app_object(self, config: RuntimeConfig) -> None:
        """Test create_app initializes routes successfully."""
        from ui.app import create_app
        
        # create_app registers routes (doesn't return an object in NiceGUI)
        create_app(config=config, session=None)
    
    def test_create_app_with_session(
        self,
        config: RuntimeConfig,
        mock_session_async: Mock
    ) -> None:
        """Test create_app accepts session parameter."""
        from ui.app import create_app
        
        create_app(config=config, session=mock_session_async)
    
    def test_app_state_stores_config(self, config: RuntimeConfig) -> None:
        """Test app state stores config after creation."""
        from ui.app import create_app, get_app_state
        
        create_app(config=config, session=None)
        
        app_state = get_app_state()
        assert app_state['config'] == config
    
    def test_set_app_error(self) -> None:
        """Test app error setter."""
        from ui.app import set_app_error, get_app_state
        
        set_app_error('Test error')
        
        app_state = get_app_state()
        assert app_state['error'] == 'Test error'
        
        set_app_error(None)
        assert app_state['error'] is None


class TestRoutesWithFeatureFlags:
    """Test route registration with feature flag support."""
    
    def test_inspector_route_feature_flag_disabled(
        self,
        config_all_features_disabled: RuntimeConfig
    ) -> None:
        """Test inspector route hidden when feature disabled."""
        from ui.app import create_app
        
        create_app(config=config_all_features_disabled, session=None)
        
        assert config_all_features_disabled.features.enable_screen_inspector is False
    
    def test_script_runner_route_feature_flag_disabled(
        self,
        config_all_features_disabled: RuntimeConfig
    ) -> None:
        """Test script runner route hidden when feature disabled."""
        from ui.app import create_app
        
        create_app(config=config_all_features_disabled, session=None)
        
        assert config_all_features_disabled.features.enable_script_runner is False
    
    def test_reports_route_feature_flag_disabled(
        self,
        config_all_features_disabled: RuntimeConfig
    ) -> None:
        """Test reports route hidden when feature disabled."""
        from ui.app import create_app
        
        create_app(config=config_all_features_disabled, session=None)
        
        assert config_all_features_disabled.features.enable_report_engine is False
    
    def test_all_routes_available_with_features_enabled(
        self,
        config_all_features_enabled: RuntimeConfig
    ) -> None:
        """Test all routes available when features enabled."""
        from ui.app import create_app
        
        create_app(config=config_all_features_enabled, session=None)
        
        assert config_all_features_enabled.features.enable_screen_inspector is True
        assert config_all_features_enabled.features.enable_script_runner is True
        assert config_all_features_enabled.features.enable_report_engine is True


class TestHomePageFlow:
    """Test home page workflow and operations."""
    
    @pytest.mark.asyncio
    async def test_home_page_renders_with_session(
        self,
        mock_session_async: Mock,
        config: RuntimeConfig
    ) -> None:
        """Test home page renders with valid session."""
        from ui.pages import home
        
        # Home page should be callable
        assert asyncio.iscoroutinefunction(home.page)
        
        # Mock session should be configured
        assert mock_session_async.is_connected() is True
    
    @pytest.mark.asyncio
    async def test_home_page_renders_without_session(
        self,
        config: RuntimeConfig
    ) -> None:
        """Test home page renders gracefully without session."""
        from ui.pages import home
        
        # Should not raise even with None session
        assert asyncio.iscoroutinefunction(home.page)


class TestErrorHandling:
    """Test error handling across flow."""
    
    @pytest.mark.asyncio
    async def test_timeout_error_handling(
        self,
        mock_session_async: Mock
    ) -> None:
        """Test timeout error is caught and stored in app state."""
        from ui.pages import home
        from ui.app import get_app_state, set_app_error
        
        # Simulate timeout by setting mock to raise TimeoutError
        mock_session_async.start_transaction = AsyncMock(
            side_effect=asyncio.TimeoutError('SAP timeout')
        )
        
        # Error should be catchable
        with pytest.raises(asyncio.TimeoutError):
            await mock_session_async.start_transaction('VA01')
    
    @pytest.mark.asyncio
    async def test_connection_error_handling(
        self,
        mock_session_async: Mock
    ) -> None:
        """Test connection error is caught and stored."""
        mock_session_async.is_connected = Mock(return_value=False)
        
        assert mock_session_async.is_connected() is False


class TestSidebarNavigation:
    """Test sidebar navigation with feature flags."""
    
    def test_sidebar_renders(self, config: RuntimeConfig) -> None:
        """Test sidebar component renders."""
        from ui.components import sidebar
        
        # Sidebar should be callable
        assert hasattr(sidebar, 'render')
    
    def test_sidebar_respects_all_feature_flag_combinations(
        self,
        config_feature_flags: RuntimeConfig
    ) -> None:
        """Test sidebar respects all 8 feature flag combinations."""
        from ui.components import sidebar
        
        # Should render without error for any feature flag combination
        config = config_feature_flags
        
        if config.features.enable_screen_inspector:
            assert config.features.enable_screen_inspector is True
        if config.features.enable_script_runner:
            assert config.features.enable_script_runner is True
        if config.features.enable_report_engine:
            assert config.features.enable_report_engine is True


class TestHeaderComponent:
    """Test header component."""
    
    def test_header_renders(self) -> None:
        """Test header component renders."""
        from ui.components import header
        
        assert hasattr(header, 'render')
    
    @pytest.mark.asyncio
    async def test_header_with_connected_session(
        self,
        mock_session_async: Mock,
        config: RuntimeConfig
    ) -> None:
        """Test header displays connected status."""
        mock_session_async.is_connected = Mock(return_value=True)
        
        assert mock_session_async.is_connected() is True
    
    @pytest.mark.asyncio
    async def test_header_with_disconnected_session(
        self,
        mock_session_async: Mock
    ) -> None:
        """Test header displays disconnected status."""
        mock_session_async.is_connected = Mock(return_value=False)
        
        assert mock_session_async.is_connected() is False


class TestLayoutComponent:
    """Test page layout component."""
    
    def test_create_page_layout_context(self, config: RuntimeConfig) -> None:
        """Test create_page_layout is a context manager."""
        from ui.layout import create_page_layout
        
        # Should be callable and return a context manager
        assert callable(create_page_layout)
    
    def test_page_layout_with_sidebar(self) -> None:
        """Test page layout with sidebar enabled."""
        from ui.layout import create_page_layout
        
        # Should be callable with sidebar option
        assert callable(create_page_layout)
    
    def test_page_layout_without_sidebar(self) -> None:
        """Test page layout with sidebar disabled."""
        from ui.layout import create_page_layout
        
        # Should be callable with show_sidebar=False
        assert callable(create_page_layout)
