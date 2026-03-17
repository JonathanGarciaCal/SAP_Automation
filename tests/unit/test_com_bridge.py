"""Tests for COM bridge, queue manager, and connection.

Comprehensive unit tests covering:
    - SAPBridge: Initialization, threading, command processing
    - QueueManager: Async interface, timeouts, metrics
    - SAPConnection: Connection lifecycle, session creation

All COM objects are mocked - no SAP instance required for tests.
"""

import pytest
import asyncio
import threading
import time
from unittest.mock import Mock, MagicMock, patch, call
from typing import Any

from sap.bridge import SAPBridge, Command, CommandStatus, CommandResponse
from sap.queue_manager import QueueManager, RetryStrategy, QueueMetrics
from sap.connection import SAPConnection
from config import SAPConfig


# ============================================================================
# VBScript Examples for Converter Testing
# ============================================================================

VBS_SIMPLE_NAVIGATION = r"""
' Simple transaction navigation
session.FindById("wnd[0]/tbar[0]/okcd").Text = "/nVA01"
session.FindById("wnd[0]").SendVKey(0)
result = "Navigation complete"
"""

VBS_SET_FIELD = r"""
' Set a material field
Dim objField, strMaterial
Set objField = session.FindById("wnd[0]/usr/ctxtRMATNR")
objField.Text = "MATERIALID"
objField.Press
"""

VBS_COMPLEX_LOOP = r"""
' Loop through grid and read values
Dim objGrid, i, value
Set objGrid = session.FindById("wnd[0]/usr/cntlGRID/shellcont/shell")

For i = 0 To objGrid.RowCount - 1
    value = objGrid.GetCellValue(i, 0)
    ' Process value
Next

result = "Grid processed"
"""

VBS_IF_ELSE = r"""
' Conditional logic example
If objField.Enabled = True Then
    objField.Text = "Active"
Else
    objField.Text = "Inactive"
End If
"""

VBS_STRING_CONCAT = r"""
' String concatenation
Dim strResult
strResult = "Material: " & strMatID & " Qty: " & intQty & " Units"
MsgBox strResult
"""

VBS_FUNCTION_DEF = r"""
' Function definition
Function CalculateTotal(price, qty)
    CalculateTotal = price * qty
End Function

Dim total
total = CalculateTotal(100, 5)
"""

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sap_config() -> SAPConfig:
    """Provide test SAP configuration."""
    return SAPConfig(
        logon_path=r"C:\Program Files\SAP\FrontEnd\SAP GUI\saplogon.ini",
        username="testuser",
        password="testpass",
        client="100",
        lang="EN"
    )


@pytest.fixture
def bridge():
    """Provide SAPBridge instance (singleton, restart for each test)."""
    # Reset singleton
    SAPBridge._instance = None
    instance = SAPBridge()
    yield instance
    # Cleanup
    if instance.is_running():
        instance.stop(timeout_sec=5.0)


@pytest.fixture
def queue_manager() -> QueueManager:
    """Provide QueueManager instance."""
    return QueueManager(timeout=30.0)


# ============================================================================
# SAPBRIDGE TESTS
# ============================================================================

class TestSAPBridge:
    """Tests for SAPBridge COM worker thread manager."""
    
    def test_bridge_is_singleton(self) -> None:
        """Test that SAPBridge follows singleton pattern."""
        SAPBridge._instance = None  # Reset
        
        bridge1 = SAPBridge()
        bridge2 = SAPBridge()
        
        assert bridge1 is bridge2
    
    def test_bridge_initializes_without_error(self, bridge: SAPBridge) -> None:
        """Test that SAPBridge initializes successfully."""
        assert bridge is not None
        assert not bridge.is_running()
        assert bridge._metrics["commands_processed"] == 0
    
    def test_bridge_starts_worker_thread(self, bridge: SAPBridge) -> None:
        """Test that worker thread starts successfully."""
        bridge.start()
        
        assert bridge.is_running()
        assert bridge._worker_thread is not None
        assert bridge._worker_thread.is_alive()
    
    def test_bridge_stops_worker_thread(self, bridge: SAPBridge) -> None:
        """Test that worker thread stops gracefully."""
        bridge.start()
        assert bridge.is_running()
        
        bridge.stop(timeout_sec=5.0)
        assert not bridge.is_running()
    
    def test_bridge_stop_with_timeout_raises_on_hanging_thread(
        self, bridge: SAPBridge
    ) -> None:
        """Test that stop() raises if worker thread doesn't exit in time."""
        from unittest.mock import patch
        
        bridge.start()
        
        # Mock thread.join() to simulate hanging thread
        with patch.object(bridge._worker_thread, 'join', side_effect=lambda timeout: None):
            with pytest.raises(RuntimeError, match="did not stop"):
                bridge.stop(timeout_sec=0.01)
    
    def test_bridge_start_is_idempotent(self, bridge: SAPBridge) -> None:
        """Test that calling start() multiple times is safe."""
        bridge.start()
        thread1 = bridge._worker_thread
        
        bridge.start()  # Should be no-op
        thread2 = bridge._worker_thread
        
        assert thread1 is thread2
    
    def test_bridge_enqueue_requires_running_thread(
        self, bridge: SAPBridge
    ) -> None:
        """Test that enqueue_command raises if worker thread not running."""
        cmd = Command(method="test_method")
        
        with pytest.raises(RuntimeError, match="not running"):
            bridge.enqueue_command(cmd)
    
    def test_bridge_validates_command_primitives(
        self, bridge: SAPBridge
    ) -> None:
        """Test that enqueue_command validates only primitives allowed."""
        bridge.start()
        
        # Non-primitive in args
        cmd_bad_args = Command(
            method="test",
            args=[object()]  # Invalid: not a primitive
        )
        
        with pytest.raises(TypeError, match="only primitives allowed"):
            bridge.enqueue_command(cmd_bad_args)
        
        # Non-primitive in kwargs
        cmd_bad_kwargs = Command(
            method="test",
            kwargs={"key": object()}  # Invalid
        )
        
        with pytest.raises(TypeError, match="only primitives allowed"):
            bridge.enqueue_command(cmd_bad_kwargs)
    
    def test_bridge_accepts_valid_primitives(
        self, bridge: SAPBridge
    ) -> None:
        """Test that enqueue_command accepts valid primitive types."""
        bridge.start()
        
        cmd = Command(
            method="test",
            args=[1, "string", 3.14, True, None, {"key": "value"}, [1, 2, 3]],
            kwargs={"int": 1, "str": "val", "bool": True, "none": None}
        )
        
        # Should not raise
        response = bridge.enqueue_command(cmd)
        assert response is not None
    
    def test_bridge_get_metrics_returns_dict(
        self, bridge: SAPBridge
    ) -> None:
        """Test that get_metrics returns metrics dictionary."""
        bridge.start()
        
        metrics = bridge.get_metrics()
        
        assert isinstance(metrics, dict)
        assert "commands_processed" in metrics
        assert "total_time_ms" in metrics
        assert "errors" in metrics
    
    def test_bridge_health_check(self, bridge: SAPBridge) -> None:
        """Test that health_check returns True when running."""
        assert not bridge.health_check()
        
        bridge.start()
        assert bridge.health_check()
        
        bridge.stop()
        assert not bridge.health_check()


# ============================================================================
# COMMAND TESTS
# ============================================================================

class TestCommand:
    """Tests for Command dataclass."""
    
    def test_command_requires_method(self) -> None:
        """Test that Command requires non-empty method."""
        with pytest.raises(ValueError, match="method cannot be empty"):
            Command(method="")
    
    def test_command_has_unique_id(self) -> None:
        """Test that each Command gets unique ID."""
        cmd1 = Command(method="test1")
        cmd2 = Command(method="test2")
        
        assert cmd1.id != cmd2.id
    
    def test_command_has_default_timeout(self) -> None:
        """Test that Command has 30 second default timeout."""
        cmd = Command(method="test")
        assert cmd.timeout_sec == 30.0
    
    def test_command_status_defaults_to_pending(self) -> None:
        """Test that Command status defaults to PENDING."""
        cmd = Command(method="test")
        assert cmd.status == CommandStatus.PENDING


# ============================================================================
# QUEUEMANAGER TESTS
# ============================================================================

class TestQueueManager:
    """Tests for QueueManager async wrapper."""
    
    def test_queue_manager_initializes(self, queue_manager: QueueManager) -> None:
        """Test that QueueManager initializes successfully."""
        assert queue_manager._timeout == 30.0
        assert queue_manager.get_pending_count() == 0
    
    def test_queue_manager_custom_timeout(self) -> None:
        """Test that QueueManager accepts custom timeout."""
        qm = QueueManager(timeout=60.0)
        assert qm._timeout == 60.0
    
    def test_queue_manager_set_timeout(self, queue_manager: QueueManager) -> None:
        """Test that set_timeout updates timeout."""
        queue_manager.set_timeout(45.0)
        assert queue_manager._timeout == 45.0
    
    def test_queue_manager_set_retry_strategy(
        self, queue_manager: QueueManager
    ) -> None:
        """Test that set_retry_strategy updates strategy."""
        queue_manager.set_retry_strategy(RetryStrategy.EXPONENTIAL_BACKOFF)
        assert queue_manager._retry_strategy == RetryStrategy.EXPONENTIAL_BACKOFF
    
    def test_queue_manager_get_metrics(self, queue_manager: QueueManager) -> None:
        """Test that get_metrics returns QueueMetrics."""
        metrics = queue_manager.get_metrics()
        
        assert isinstance(metrics, QueueMetrics)
        assert metrics.total_commands == 0
        assert metrics.successful == 0
        assert metrics.failed == 0
    
    def test_queue_manager_reset_metrics(self, queue_manager: QueueManager) -> None:
        """Test that reset_metrics clears all metrics."""
        # Manually set some metrics
        queue_manager._metrics.total_commands = 10
        queue_manager._metrics.successful = 5
        
        queue_manager.reset_metrics()
        
        metrics = queue_manager.get_metrics()
        assert metrics.total_commands == 0
        assert metrics.successful == 0
    
    @pytest.mark.asyncio
    async def test_queue_manager_call_async_requires_running_bridge(
        self, queue_manager: QueueManager
    ) -> None:
        """Test that call_async raises if worker thread not running."""
        with pytest.raises(RuntimeError, match="not running"):
            await queue_manager.call_async("test_method")
    
    @pytest.mark.asyncio
    async def test_queue_manager_call_async_with_bridge(
        self, queue_manager: QueueManager
    ) -> None:
        """Test that call_async works with running bridge and handles timeouts."""
        bridge = SAPBridge()
        SAPBridge._instance = None  # Reset singleton
        bridge = SAPBridge()
        bridge.start()
        
        try:
            # Mock the worker thread to pause processing, causing a timeout
            original_process = bridge._process_command
            pause_event = threading.Event()
            
            def slow_process_command(command: Command) -> None:
                """Process command with artificial delay to trigger timeout."""
                # Wait for pause event (or timeout after 5 seconds)
                pause_event.wait(timeout=5.0)
                # Never actually respond - this causes the command to timeout
            
            bridge._process_command = slow_process_command
            
            try:
                # Command timeout is 1 second, but pause_event never sets, so it times out
                with pytest.raises(RuntimeError, match="TIMEOUT"):
                    result = await queue_manager.call_async("test_method", timeout_sec=1)
            finally:
                # Cleanup pause
                pause_event.set()
                bridge._process_command = original_process
        finally:
            bridge.stop()
    
    def test_queue_manager_get_pending_count(
        self, queue_manager: QueueManager
    ) -> None:
        """Test that get_pending_count returns number of pending futures."""
        assert queue_manager.get_pending_count() == 0
        
        # Manually add futures
        loop = asyncio.new_event_loop()
        future = loop.create_future()
        queue_manager._pending_futures["id1"] = future
        
        assert queue_manager.get_pending_count() == 1


# ============================================================================
# SAPCONNECTION TESTS
# ============================================================================

class TestSAPConnection:
    """Tests for SAPConnection wrapper."""
    
    def test_connection_requires_logon_path(self) -> None:
        """Test that SAPConnection requires logon_path in config."""
        config = SAPConfig(
            logon_path="",
            username="user",
            password="pass"
        )
        
        with pytest.raises(ValueError, match="logon_path must be configured"):
            SAPConnection(config)
    
    def test_connection_initializes_with_valid_config(
        self, sap_config: SAPConfig
    ) -> None:
        """Test that SAPConnection initializes with valid config."""
        conn = SAPConnection(sap_config)
        
        assert conn.config == sap_config
        assert not conn.is_connected()
    
    def test_connection_is_not_connected_initially(
        self, sap_config: SAPConfig
    ) -> None:
        """Test that new connection is not connected."""
        conn = SAPConnection(sap_config)
        assert not conn.is_connected()
    
    @pytest.mark.asyncio
    async def test_connection_open_requires_credentials(
        self, sap_config: SAPConfig
    ) -> None:
        """Test that open() requires username and password."""
        config = SAPConfig(
            logon_path=sap_config.logon_path,
            username=None,
            password=None
        )
        conn = SAPConnection(config)
        
        with pytest.raises(ValueError, match="Username and password required"):
            await conn.open()
    
    @pytest.mark.asyncio
    async def test_connection_open_starts_bridge(
        self, sap_config: SAPConfig
    ) -> None:
        """Test that open() starts bridge if needed."""
        # Reset bridge
        SAPBridge._instance = None
        
        conn = SAPConnection(sap_config)
        
        try:
            session = await conn.open(username="user", password="pass")
            
            assert conn.is_connected()
            assert session is not None
        finally:
            bridge = SAPBridge()
            if bridge.is_running():
                bridge.stop()
    
    @pytest.mark.asyncio
    async def test_connection_open_returns_session(
        self, sap_config: SAPConfig
    ) -> None:
        """Test that open() returns Session object."""
        SAPBridge._instance = None
        
        conn = SAPConnection(sap_config)
        
        try:
            session = await conn.open(username="user", password="pass")
            
            assert session is not None
            assert hasattr(session, 'start_transaction')
            assert hasattr(session, 'get_field_value')
        finally:
            bridge = SAPBridge()
            if bridge.is_running():
                bridge.stop()
    
    @pytest.mark.asyncio
    async def test_connection_close(self, sap_config: SAPConfig) -> None:
        """Test that close() closes connection gracefully."""
        SAPBridge._instance = None
        
        conn = SAPConnection(sap_config)
        session = await conn.open(username="user", password="pass")
        
        assert conn.is_connected()
        
        await conn.close()
        assert not conn.is_connected()
        
        bridge = SAPBridge()
        if bridge.is_running():
            bridge.stop()
    
    @pytest.mark.asyncio
    async def test_connection_health_check(
        self, sap_config: SAPConfig
    ) -> None:
        """Test that health_check returns status."""
        SAPBridge._instance = None
        
        conn = SAPConnection(sap_config)
        
        assert not await conn.health_check()
        
        session = await conn.open(username="user", password="pass")
        
        assert await conn.health_check()
        
        await conn.close()
        
        bridge = SAPBridge()
        if bridge.is_running():
            bridge.stop()
    
    def test_connection_get_queue_manager(
        self, sap_config: SAPConfig
    ) -> None:
        """Test that get_queue_manager returns QueueManager."""
        conn = SAPConnection(sap_config)
        qm = conn.get_queue_manager()
        
        assert isinstance(qm, QueueManager)


# ============================================================================
# SESSION TESTS (PHASE 1 STUBS)
# ============================================================================

class TestSession:
    """Tests for Session API (Phase 1 stubs)."""
    
    @pytest.mark.asyncio
    async def test_session_initializes(self, sap_config: SAPConfig) -> None:
        """Test that Session initializes."""
        SAPBridge._instance = None
        
        conn = SAPConnection(sap_config)
        session = await conn.open(username="user", password="pass")
        
        assert session is not None
        
        await conn.close()
        
        bridge = SAPBridge()
        if bridge.is_running():
            bridge.stop()
    
    @pytest.mark.asyncio
    async def test_session_close(self, sap_config: SAPConfig) -> None:
        """Test that Session.close() works."""
        SAPBridge._instance = None
        
        conn = SAPConnection(sap_config)
        session = await conn.open(username="user", password="pass")
        
        await session.close()
        assert session._closed
        
        await conn.close()
        
        bridge = SAPBridge()
        if bridge.is_running():
            bridge.stop()
    
    @pytest.mark.asyncio
    async def test_session_start_transaction_returns_dict(
        self, sap_config: SAPConfig
    ) -> None:
        """Test that start_transaction returns dict."""
        SAPBridge._instance = None
        
        conn = SAPConnection(sap_config)
        session = await conn.open(username="user", password="pass")
        
        result = await session.start_transaction("VA01")
        
        assert isinstance(result, dict)
        assert "transaction" in result
        
        await conn.close()
        
        bridge = SAPBridge()
        if bridge.is_running():
            bridge.stop()
    
    @pytest.mark.asyncio
    async def test_session_methods_raise_when_closed(
        self, sap_config: SAPConfig
    ) -> None:
        """Test that Session methods raise RuntimeError when closed."""
        SAPBridge._instance = None
        
        conn = SAPConnection(sap_config)
        session = await conn.open(username="user", password="pass")
        
        await session.close()
        
        with pytest.raises(RuntimeError, match="Session is closed"):
            await session.start_transaction("VA01")
        
        with pytest.raises(RuntimeError, match="Session is closed"):
            await session.get_field_value("FIELD")
        
        with pytest.raises(RuntimeError, match="Session is closed"):
            await session.set_field_value("FIELD", "value")
        
        with pytest.raises(RuntimeError, match="Session is closed"):
            await session.click_button("BUTTON")
        
        with pytest.raises(RuntimeError, match="Session is closed"):
            await session.send_key("Enter")
        
        await conn.close()
        
        bridge = SAPBridge()
        if bridge.is_running():
            bridge.stop()


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests for bridge + queue + connection."""
    
    @pytest.mark.asyncio
    async def test_full_connection_lifecycle(
        self, sap_config: SAPConfig
    ) -> None:
        """Test complete connection open -> use -> close flow."""
        SAPBridge._instance = None
        
        try:
            # Connect
            conn = SAPConnection(sap_config)
            assert not conn.is_connected()
            
            session = await conn.open(username="user", password="pass")
            assert conn.is_connected()
            
            # Use session stub
            result = await session.start_transaction("VA01")
            assert result["transaction"] == "VA01"
            
            # Close
            await conn.close()
            assert not conn.is_connected()
        
        finally:
            bridge = SAPBridge()
            if bridge.is_running():
                bridge.stop()
    
    def test_bridge_thread_cleanup_on_error(self) -> None:
        """Test that bridge cleans up thread on error."""
        SAPBridge._instance = None
        
        bridge = SAPBridge()
        bridge.start()
        
        assert bridge.is_running()
        
        bridge.stop()
        
        # Thread should be dead
        assert bridge._worker_thread is not None
        assert not bridge._worker_thread.is_alive()

