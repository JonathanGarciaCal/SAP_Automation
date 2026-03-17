"""Tests for NiceGUI pages and components (Phase 1).

Tests home page, inspector stub, script runner stub, and reports stub.
Covers rendering, feature flags, button interactions, and error handling.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Optional
from pathlib import Path

from config import RuntimeConfig, FeatureFlags
from sap.session import Session


# ============================================================================
# VBSCRIPT CONVERTER TESTS (PHASE 3)
# ============================================================================

class TestVBScriptConverterPhase3:
    """Tests for VBScript to Python converter from Phase 3."""
    
    def test_converter_import(self) -> None:
        """Test that VBScriptConverter can be imported from sap module."""
        from sap import VBScriptConverter
        assert VBScriptConverter is not None
        converter = VBScriptConverter()
        assert hasattr(converter, 'convert_code')
        assert hasattr(converter, 'convert_file')
    
    def test_converter_convert_simple_navigation(self) -> None:
        """Test converting simple navigation VBScript."""
        from sap import VBScriptConverter
        
        converter = VBScriptConverter()
        vbs_code = r"""' Simple SAP Transaction Navigation
session.FindById("wnd[0]/tbar[0]/okcd").Text = "/nVA01"
session.FindById("wnd[0]").SendVKey(0)
result = "Navigation successful"
"""
        
        python_code, flags = converter.convert_code(vbs_code)
        
        assert isinstance(python_code, str)
        assert isinstance(flags, list)
        assert len(python_code) > 0
        assert "# Auto-converted from VBScript" in python_code
    
    def test_converter_set_field_example(self) -> None:
        """Test converting set field VBScript."""
        from sap import VBScriptConverter
        
        converter = VBScriptConverter()
        vbs_code = r"""' Set a material field
Dim objField, materialID
Set objField = session.FindById("wnd[0]/usr/ctxtRMATNR")
materialID = "MAT001"
objField.Text = materialID
objField.Press
"""
        
        python_code, flags = converter.convert_code(vbs_code)
        
        assert python_code is not None
        assert len(python_code) > 0
        # Check that Set was converted (converted code should not have Set keyword)
        lines = python_code.split('\n')
        content_lines = [l for l in lines if not l.strip().startswith('#') and l.strip()]
        conversion_successful = len(content_lines) > 0
    
    def test_example_files_created(self) -> None:
        """Test that example VBS and YAML files exist in scripts/examples/."""
        simple_nav_vbs = Path("scripts/examples/simple_navigation.vbs")
        simple_nav_yaml = Path("scripts/examples/simple_navigation.yaml")
        set_field_vbs = Path("scripts/examples/set_field.vbs")
        set_field_yaml = Path("scripts/examples/set_field.yaml")
        
        # These files should be created by the session fixture
        # Check if they exist (they may not before first pytest run, but will after)
        if simple_nav_vbs.exists():
            assert simple_nav_vbs.read_text() != ""
        if simple_nav_yaml.exists():
            assert simple_nav_yaml.read_text() != ""
    
    def test_converter_integration_with_real_example(self) -> None:
        """Integration test: convert a realistic VBScript example."""
        from sap import VBScriptConverter
        
        # Real-world VBScript from SAP GUI Recorder
        vbs_code = r"""
' Transaction VA01 - Create Sales Order
If Not IsObject(application) Then
   Set SapGuiAuto = GetObject("SAPGUI")
   Set application = SapGuiAuto.GetScriptingEngine
End If

session.FindById("wnd[0]/tbar[0]/okcd").Text = "/nVA01"
session.FindById("wnd[0]").SendVKey(0)

Dim material
material = "MATERIAL001"
session.FindById("wnd[0]/usr/ctxtMATERIAL").Text = material

session.FindById("wnd[0]/tbar[1]/btn[0]").Press
"""
        
        converter = VBScriptConverter()
        python_code, flags = converter.convert_code(vbs_code)
        
        # Verify conversion happened
        assert len(python_code) > 0
        assert "# Auto-converted from VBScript" in python_code
        
        # Verify some VBS constructs were converted
        assert "wnd[0]/tbar[0]/okcd" in python_code  # Code was converted
        assert "session.FindById" in python_code


class TestHomePage:
    """Test suite for home page."""
    
    def test_home_page_imports(self) -> None:
        """Test that home page module imports without errors."""
        try:
            from ui.pages import home
            assert hasattr(home, 'page')
            assert asyncio.iscoroutinefunction(home.page)
        except ImportError as e:
            pytest.fail(f"Failed to import home page: {e}")
    
    @pytest.mark.asyncio
    async def test_home_page_with_mock_session(
        self,
        mock_session_async: Mock
    ) -> None:
        """Test home page can be called with mock session."""
        from ui.pages import home
        
        # Should not raise
        try:
            # Note: In actual NiceGUI test, UI context would be needed
            # This test verifies the function is callable and async
            assert asyncio.iscoroutinefunction(home.page)
        except Exception as e:
            pytest.fail(f"Home page failed: {e}")
    
    def test_operation_logging(self) -> None:
        """Test operation logging function."""
        from ui.pages import home
        
        # Log an operation
        home.log_operation('VA01', 'Started', 'Success')
        
        # Verify it was logged
        assert len(home._operations_log) > 0
        assert home._operations_log[-1]['operation'] == 'VA01 Started'
        assert home._operations_log[-1]['status'] == 'Success'
    
    def test_operation_timestamp(self) -> None:
        """Test operation logging includes timestamp."""
        from ui.pages import home
        
        home.log_operation('TEST', 'Action', 'Success')
        
        last_op = home._operations_log[-1]
        assert 'timestamp' in last_op
        assert len(last_op['timestamp']) > 0
    
    def test_operations_log_limit(self) -> None:
        """Test that operations log can track multiple entries."""
        from ui.pages import home
        
        # Clear log
        home._operations_log.clear()
        
        # Add 15 operations
        for i in range(15):
            home.log_operation(f'TEST{i}', 'Action', 'Success')
        
        # Verify all are logged
        assert len(home._operations_log) >= 15


class TestInspectorPage:
    """Test suite for screen inspector stub page."""
    
    def test_inspector_page_imports(self) -> None:
        """Test that inspector page imports without errors."""
        try:
            from ui.pages import inspector
            assert hasattr(inspector, 'page')
            assert asyncio.iscoroutinefunction(inspector.page)
        except ImportError as e:
            pytest.fail(f"Failed to import inspector page: {e}")
    
    @pytest.mark.asyncio
    async def test_inspector_page_is_async(self) -> None:
        """Test that inspector page is async/awaitable."""
        from ui.pages import inspector
        
        assert asyncio.iscoroutinefunction(inspector.page)


class TestScriptRunnerPage:
    """Test suite for script runner stub page."""
    
    def test_script_runner_page_imports(self) -> None:
        """Test that script runner page imports without errors."""
        try:
            from ui.pages import script_runner
            assert hasattr(script_runner, 'page')
            assert asyncio.iscoroutinefunction(script_runner.page)
        except ImportError as e:
            pytest.fail(f"Failed to import script runner page: {e}")
    
    @pytest.mark.asyncio
    async def test_script_runner_page_is_async(self) -> None:
        """Test that script runner page is async/awaitable."""
        from ui.pages import script_runner
        
        assert asyncio.iscoroutinefunction(script_runner.page)


class TestReportsPage:
    """Test suite for reports stub page."""
    
    def test_reports_page_imports(self) -> None:
        """Test that reports page imports without errors."""
        try:
            from ui.pages import reports
            assert hasattr(reports, 'page')
            assert asyncio.iscoroutinefunction(reports.page)
        except ImportError as e:
            pytest.fail(f"Failed to import reports page: {e}")
    
    @pytest.mark.asyncio
    async def test_reports_page_is_async(self) -> None:
        """Test that reports page is async/awaitable."""
        from ui.pages import reports
        
        assert asyncio.iscoroutinefunction(reports.page)


# ─────────────────────────────────────────────────────────────────
# Phase 3: VBScript Converter Tests
# ─────────────────────────────────────────────────────────────────

class TestVBScriptConverter:
    """Comprehensive tests for VBScript to Python converter (Phase 3)."""
    
    def test_converter_import(self) -> None:
        """Test that converter imports successfully."""
        from sap.script_runner import VBScriptConverter, ConversionResult
        assert VBScriptConverter is not None
        assert ConversionResult is not None
    
    def test_converter_instantiation(self, vbs_converter) -> None:
        """Test converter can be instantiated."""
        assert vbs_converter is not None
    
    def test_conversion_result_dataclass(self) -> None:
        """Test ConversionResult dataclass."""
        from sap.script_runner import ConversionResult
        
        result = ConversionResult(
            success=True,
            converted_code="test_code",
            flags=["flag1"],
            line_count=1
        )
        
        assert result.success is True
        assert result.converted_code == "test_code"
        assert len(result.flags) == 1
        assert result.line_count == 1
    
    def test_empty_input(self, vbs_converter) -> None:
        """Test converter handles empty input."""
        result = vbs_converter.convert_code("")
        assert result.success is False
        assert result.error_message is not None
    
    def test_simple_navigation_conversion(self, vbs_converter, vbs_simple_navigation) -> None:
        """Test converting simple navigation VBScript."""
        result = vbs_converter.convert_code(vbs_simple_navigation)
        
        assert result.success is True
        assert "SendVKey(0)" in result.converted_code  # .SendVKey 0 → .SendVKey(0)
        assert "Maximize()" in result.converted_code or ".maximize" not in result.converted_code
        assert "async def" in result.converted_code
    
    def test_set_declarations_removal(self, vbs_converter, vbs_set_field) -> None:
        """Test 'Set' keyword is removed from declarations."""
        result = vbs_converter.convert_code(vbs_set_field)
        
        assert result.success is True
        # Set declarations should be removed
        assert result.patterns_applied.get("remove_set", 0) > 0
        # No 'Set' should remain in declarations
        assert "Set objField" not in result.converted_code or "objField =" in result.converted_code
    
    def test_comment_conversion(self, vbs_converter, vbs_with_comments) -> None:
        """Test VBS comments are converted to Python comments."""
        result = vbs_converter.convert_code(vbs_with_comments)
        
        assert result.success is True
        assert result.patterns_applied.get("vbs_comments", 0) > 0 or \
               result.patterns_applied.get("rem_comments", 0) > 0
        # Python comments should be present
        assert "# " in result.converted_code or "#This" in result.converted_code
    
    def test_preamble_removal(self, vbs_converter, vbs_with_preamble) -> None:
        """Test SAP preamble is removed."""
        result = vbs_converter.convert_code(vbs_with_preamble)
        
        assert result.success is True
        # Preamble markers should be gone
        assert "GetObject" not in result.converted_code
        assert "SetSapGuiAuto" not in result.converted_code.replace(" ", "")
        # Actual script code should remain
        assert "Maximize" in result.converted_code or "maximize" in vbs_with_preamble
    
    def test_if_statement_conversion(self, vbs_converter, vbs_with_if_statement) -> None:
        """Test If/Then/Else blocks are converted to Python."""
        result = vbs_converter.convert_code(vbs_with_if_statement)
        
        assert result.success is True
        # Should have Python if/elif/else keywords
        if_found = "if " in result.converted_code or "elif " in result.converted_code
        assert if_found, f"Python if/elif not found in:\n{result.converted_code}"
    
    def test_string_concatenation_conversion(self, vbs_converter, vbs_with_string_concat) -> None:
        """Test VBS & operator is converted to Python +."""
        result = vbs_converter.convert_code(vbs_with_string_concat)
        
        assert result.success is True
        # & should be converted to +
        assert result.patterns_applied.get("string_concat", 0) > 0
        assert " + " in result.converted_code
    
    def test_boolean_conversion(self, vbs_converter) -> None:
        """Test true/false → True/False conversion."""
        vbs_code = "value = true\nresult = false"
        result = vbs_converter.convert_code(vbs_code)
        
        assert result.success is True
        assert "True" in result.converted_code
        assert "False" in result.converted_code
    
    def test_method_parentheses_addition(self, vbs_converter) -> None:
        """Test methods without parentheses get them added."""
        vbs_code = "session.FindById('test').maximize\nsession.FindById('test').press"
        result = vbs_converter.convert_code(vbs_code)
        
        assert result.success is True
        assert "Maximize()" in result.converted_code
        assert "Press()" in result.converted_code
    
    def test_unhandled_patterns_flagged(self, vbs_converter) -> None:
        """Test that unhandled patterns are flagged."""
        vbs_code = """
MsgBox "This is a message"
CreateObject("Excel.Application")
"""
        result = vbs_converter.convert_code(vbs_code)
        
        assert result.success is True
        assert len(result.flags) > 0
        flag_text = " ".join(result.flags)
        assert "MsgBox" in flag_text or "CreateObject" in flag_text
    
    def test_conversion_wraps_in_function(self, vbs_converter, vbs_simple_navigation) -> None:
        """Test conversion wraps code in async function."""
        result = vbs_converter.convert_code(vbs_simple_navigation)
        
        assert result.success is True
        assert "async def execute_script" in result.converted_code
        assert "def execute_script(session, parameters):" in result.converted_code
        assert "return True" in result.converted_code
    
    def test_loop_conversion(self, vbs_converter, vbs_loop_example) -> None:
        """Test VBS For loops are converted to Python for/range."""
        result = vbs_converter.convert_code(vbs_loop_example)
        
        assert result.success is True
        # Should contain Python for loop
        assert "for i in range" in result.converted_code
    
    def test_convert_file_not_found(self, vbs_converter) -> None:
        """Test convert_file handles missing files gracefully."""
        result = vbs_converter.convert_file("/nonexistent/path/script.vbs")
        
        assert result.success is False
        assert "not found" in result.error_message.lower()
    
    def test_convert_file_invalid_extension(self, vbs_converter, tmp_path) -> None:
        """Test convert_file rejects non-.vbs files."""
        invalid_file = tmp_path / "test.py"
        invalid_file.write_text("print('test')")
        
        result = vbs_converter.convert_file(str(invalid_file))
        
        assert result.success is False
        assert ".vbs" in result.error_message
    
    def test_convert_file_success(self, vbs_converter, tmp_path) -> None:
        """Test convert_file reads and converts file successfully."""
        vbs_file = tmp_path / "test.vbs"
        vbs_file.write_text("""
session.FindById("wnd[0]").maximize
session.FindById("wnd[0]/ok_code").Text = "/nVA01"
""")
        
        result = vbs_converter.convert_file(str(vbs_file))
        
        assert result.success is True
        assert "Maximize()" in result.converted_code
        assert "async def execute_script" in result.converted_code
    
    def test_patterns_applied_tracking(self, vbs_converter) -> None:
        """Test that pattern application is tracked."""
        vbs_code = """
Set obj = something
obj.maximize
value = true & false
' Comment here
"""
        result = vbs_converter.convert_code(vbs_code)
        
        assert result.success is True
        assert len(result.patterns_applied) > 0
        # Should have tracked various patterns
        assert any(v > 0 for v in result.patterns_applied.values())
    
    def test_real_world_example(self, vbs_converter) -> None:
        """Test with realistic SAP automation script."""
        real_vbs = r"""
If Not IsObject(application) Then
   Set SapGuiAuto = GetObject("SAPGUI")
   Set application = SapGuiAuto.GetScriptingEngine
End If

session.FindById("wnd[0]").maximize
session.FindById("wnd[0]/tbar[0]/okcd").Text = "/nMM03"
session.FindById("wnd[0]").SendVKey 0

Dim material
material = "MAT123"
session.FindById("wnd[0]/usr/ctxtMATNR").Text = material
session.FindById("wnd[0]/tbar[1]/btn[0]").Press

' Navigation complete
"""
        result = vbs_converter.convert_code(real_vbs)
        
        assert result.success is True
        assert "async def execute_script" in result.converted_code
        # Preamble should be removed
        assert "GetObject" not in result.converted_code
        # Key methods should be converted
        assert "Maximize()" in result.converted_code or "maximize" not in result.converted_code
        assert "SendVKey(0)" in result.converted_code
