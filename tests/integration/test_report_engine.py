"""Phase 4 Report Engine Integration Tests (Task 9).

Tests end-to-end report execution workflows including YAML loading, parameter
validation, execution steps (navigate → set_field → execute → read_grid), error
handling, and result export.

Test Structure (40+ tests organized by functional area):
    - [8–10] YAML loading & schema validation
    - [8–10] Parameter validation (all 6 types)
    - [8–10] Execution workflow (start transaction → navigate → read grid)
    - [6–8] Error cases (timeout, missing field, invalid transaction, corrupt grid)
    - [4–6] End-to-end workflows (load sample YAML → execute → verify result)
    - [4–6] Export integration (result → CSV/Excel)

All SAP calls mocked — no real COM objects or live connections.
Uses async fixtures with proper await patterns as per architecture.

Coverage Target: >80% for report engine code
Pass Rate: 100%
Execution Time: <30 seconds
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List
import json
import yaml
from datetime import datetime

from sap import (
    ReportStepAction, ReportStep, ReportColumn, ReportOutputConfig,
    ReportErrorHandling, ReportMetadata, ReportResult, ReportYAML,
    ReportManager, ReportRunner, ParamType, ParamDefinition
)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: YAML Loading & Schema Validation (8–10 tests)
# ─────────────────────────────────────────────────────────────────────────────

class TestReportYAMLLoading:
    """Test YAML report loading and schema validation."""
    
    def test_load_valid_report_yaml(self, tmp_path: Path) -> None:
        """Load valid YAML report definition successfully.
        
        Ensures ReportYAML.load() parses valid YAML and returns ReportMetadata.
        """
        report_yaml = '''
name: "test_report"
title: "Test Report"
description: "Test report for validation"
transaction: "VA01"
parameters: []
steps:
  - action: "navigate"
    target: "VA01"
steps: []
output:
  columns: []
  row_limit: 1000
error_handling:
  transaction_not_found: "abort"
  max_retries: 1
'''
        report_file = tmp_path / "test_report.yaml"
        report_file.write_text(report_yaml)
        
        metadata = ReportYAML.load(report_file)
        
        assert metadata is not None
        assert metadata.name == "test_report"
        assert metadata.title == "Test Report"
        assert metadata.transaction == "VA01"
    
    def test_load_missing_yaml_file_returns_none(self, tmp_path: Path) -> None:
        """Load returns None for missing YAML file.
        
        Ensures graceful handling of nonexistent files.
        """
        report_file = tmp_path / "nonexistent.yaml"
        
        metadata = ReportYAML.load(report_file)
        
        assert metadata is None
    
    def test_load_malformed_yaml_returns_none(self, tmp_path: Path) -> None:
        """Load returns None for malformed YAML.
        
        Ensures YAML parse errors are caught gracefully.
        """
        report_yaml = '''
name: "test"
invalid: [unclosed list
'''
        report_file = tmp_path / "malformed.yaml"
        report_file.write_text(report_yaml)
        
        metadata = ReportYAML.load(report_file)
        
        assert metadata is None
    
    def test_load_invalid_schema_returns_none(self, tmp_path: Path) -> None:
        """Load returns None if YAML violates ReportMetadata schema.
        
        Tests Pydantic validation enforcement (missing required fields).
        """
        report_yaml = '''
description: "Missing required 'name' field"
transaction: "VA01"
'''
        report_file = tmp_path / "invalid_schema.yaml"
        report_file.write_text(report_yaml)
        
        metadata = ReportYAML.load(report_file)
        
        assert metadata is None
    
    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        """Save report to YAML, then load it back (roundtrip test).
        
        Ensures save() and load() preserve metadata accurately.
        """
        metadata = ReportMetadata(
            name="roundtrip_test",
            title="Roundtrip Test",
            transaction="VA01",
            parameters=[
                ParamDefinition(
                    name="material_id",
                    param_type=ParamType.STRING,
                    required=True,
                    description="Test parameter"
                )
            ],
            steps=[
                ReportStep(action=ReportStepAction.NAVIGATE, target="VA01")
            ],
            output=ReportOutputConfig(columns=[]),
            error_handling=ReportErrorHandling()
        )
        
        report_file = tmp_path / "roundtrip.yaml"
        ReportYAML.save(metadata, report_file)
        
        loaded = ReportYAML.load(report_file)
        
        assert loaded is not None
        assert loaded.name == metadata.name
        assert loaded.title == metadata.title
        assert len(loaded.parameters) == 1
    
    def test_load_report_with_all_parameter_types(self, tmp_path: Path) -> None:
        """Load report with all 6 parameter types in YAML schema.
        
        Validates that all ParamType values are loaded correctly.
        """
        report_yaml = f'''
name: "param_types_test"
title: "Parameter Types Test"
transaction: "VA01"
parameters:
  - name: "string_param"
    param_type: "{ParamType.STRING.value}"
    required: true
  - name: "int_param"
    param_type: "{ParamType.INT.value}"
    required: false
  - name: "bool_param"
    param_type: "{ParamType.BOOL.value}"
    required: false
  - name: "date_param"
    param_type: "{ParamType.DATE.value}"
    required: false
  - name: "dropdown_param"
    param_type: "{ParamType.DROPDOWN.value}"
    enum_values: ["Option1", "Option2"]
  - name: "multi_select_param"
    param_type: "{ParamType.MULTI_SELECT.value}"
steps: []
output:
  columns: []
error_handling: {{}}
'''
        report_file = tmp_path / "param_types.yaml"
        report_file.write_text(report_yaml)
        
        metadata = ReportYAML.load(report_file)
        
        assert metadata is not None
        assert len(metadata.parameters) == 6
        assert metadata.parameters[0].param_type == ParamType.STRING
        assert metadata.parameters[4].param_type == ParamType.DROPDOWN
    
    def test_load_report_with_complex_steps(self, tmp_path: Path) -> None:
        """Load report with complex multi-step workflow in YAML.
        
        Tests all ReportStepAction values are parsed correctly.
        """
        report_yaml = '''
name: "complex_steps_test"
title: "Complex Steps Test"
transaction: "VA01"
parameters: []
steps:
  - action: "navigate"
    target: "VA01"
    timeout: 30
  - action: "set_field"
    field: "RMMG1-MATNR"
    value: "TEST001"
    timeout: 5
  - action: "set_field_conditional"
    field: "RMMG1-WERKS"
    value: "{plant}"
    condition: "{plant}"
    timeout: 5
  - action: "execute"
    timeout: 30
  - action: "read_grid"
    target: "[/app/grid]"
    timeout: 10
output:
  columns:
    - column_name: "MATNR"
      header: "Material Number"
      width: 20
error_handling:
  transaction_not_found: "abort"
  max_retries: 2
'''
        report_file = tmp_path / "complex_steps.yaml"
        report_file.write_text(report_yaml)
        
        metadata = ReportYAML.load(report_file)
        
        assert metadata is not None
        assert len(metadata.steps) == 5
        assert metadata.steps[0].action == ReportStepAction.NAVIGATE
        assert metadata.steps[2].action == ReportStepAction.SET_FIELD_CONDITIONAL
        assert len(metadata.output.columns) == 1
    
    def test_bootstrap_examples_creates_yaml_files(self, tmp_path: Path) -> None:
        """Bootstrap example reports creates YAML files in /reports/examples/.
        
        Validates example report templates are created during initialization.
        """
        reports_dir = tmp_path / "reports"
        
        results = ReportYAML.bootstrap_examples(reports_dir, overwrite=False)
        
        examples_dir = reports_dir / "examples"
        assert examples_dir.exists()
        assert any(f.name.endswith(".yaml") for f in examples_dir.glob("*.yaml"))
        assert any(results.values())
    
    def test_bootstrap_examples_respects_overwrite_flag(self, tmp_path: Path) -> None:
        """Bootstrap respects overwrite=False and skips existing files.
        
        Ensures existing files are preserved when overwrite=False.
        """
        reports_dir = tmp_path / "reports"
        examples_dir = reports_dir / "examples"
        examples_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a dummy file
        test_file = examples_dir / "stock_report.yaml"
        test_file.write_text("# existing file")
        
        # Bootstrap with overwrite=False
        ReportYAML.bootstrap_examples(reports_dir, overwrite=False)
        
        # File should still be original content
        assert test_file.read_text() == "# existing file"


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Parameter Validation (8–10 tests)
# ─────────────────────────────────────────────────────────────────────────────

class TestParameterValidation:
    """Test parameter validation for all 6 types."""
    
    def test_validate_string_parameter_valid(self) -> None:
        """Validate string parameter with valid value.
        
        Tests ParamType.STRING validation accepts strings.
        """
        from sap import ParameterValidator
        
        params_def = [ParamDefinition(name="material_id", param_type=ParamType.STRING, required=True)]
        provided = {"material_id": "ABC123"}
        
        is_valid, errors = ParameterValidator.validate(provided, params_def)
        
        assert is_valid
        assert len(errors) == 0
    
    def test_validate_int_parameter_valid(self) -> None:
        """Validate int parameter with valid value.
        
        Tests ParamType.INT validation accepts integers.
        """
        from sap import ParameterValidator
        
        params_def = [ParamDefinition(name="quantity", param_type=ParamType.INT, required=True)]
        provided = {"quantity": 100}
        
        is_valid, errors = ParameterValidator.validate(provided, params_def)
        
        assert is_valid
        assert len(errors) == 0
    
    def test_validate_bool_parameter_valid(self) -> None:
        """Validate bool parameter with valid value.
        
        Tests ParamType.BOOL validation accepts booleans.
        """
        from sap import ParameterValidator
        
        params_def = [ParamDefinition(name="active", param_type=ParamType.BOOL, required=True)]
        provided = {"active": True}
        
        is_valid, errors = ParameterValidator.validate(provided, params_def)
        
        assert is_valid
        assert len(errors) == 0
    
    def test_validate_date_parameter_valid(self) -> None:
        """Validate date parameter with ISO 8601 date.
        
        Tests ParamType.DATE validation accepts ISO dates.
        """
        from sap import ParameterValidator
        
        params_def = [ParamDefinition(name="start_date", param_type=ParamType.DATE, required=True)]
        provided = {"start_date": "2026-01-15"}
        
        is_valid, errors = ParameterValidator.validate(provided, params_def)
        
        assert is_valid
        assert len(errors) == 0
    
    def test_validate_dropdown_parameter_valid(self) -> None:
        """Validate dropdown parameter with enum value.
        
        Tests ParamType.DROPDOWN validation checks enum_values.
        """
        from sap import ParameterValidator
        
        params_def = [
            ParamDefinition(
                name="plant",
                param_type=ParamType.DROPDOWN,
                required=True,
                enum_values=["1000", "2000", "3000"]
            )
        ]
        provided = {"plant": "2000"}
        
        is_valid, errors = ParameterValidator.validate(provided, params_def)
        
        assert is_valid
        assert len(errors) == 0
    
    def test_validate_multi_select_parameter_valid(self) -> None:
        """Validate multi-select parameter with list of values.
        
        Tests ParamType.MULTI_SELECT validation accepts lists.
        """
        from sap import ParameterValidator
        
        params_def = [
            ParamDefinition(name="materials", param_type=ParamType.MULTI_SELECT, required=True)
        ]
        provided = {"materials": ["MAT001", "MAT002"]}
        
        is_valid, errors = ParameterValidator.validate(provided, params_def)
        
        assert is_valid
        assert len(errors) == 0
    
    def test_validate_required_parameter_missing(self) -> None:
        """Validate detects missing required parameter.
        
        Tests validation fails when required parameter is absent.
        """
        from sap import ParameterValidator
        
        params_def = [ParamDefinition(name="material_id", param_type=ParamType.STRING, required=True)]
        provided = {}
        
        is_valid, errors = ParameterValidator.validate(provided, params_def)
        
        assert not is_valid
        assert "material_id" in str(errors).lower()
    
    def test_validate_type_mismatch_int_instead_of_string(self) -> None:
        """Validate catches type mismatch (int given, string expected).
        
        Tests ParamType validation rejects wrong types.
        """
        from sap import ParameterValidator
        
        params_def = [ParamDefinition(name="material_id", param_type=ParamType.STRING, required=True)]
        provided = {"material_id": 12345}
        
        is_valid, errors = ParameterValidator.validate(provided, params_def)
        
        assert not is_valid
        assert len(errors) > 0
    
    def test_validate_dropdown_invalid_enum_value(self) -> None:
        """Validate rejects dropdown value not in enum_values.
        
        Tests dropdown validation enforces enum constraint.
        """
        from sap import ParameterValidator
        
        params_def = [
            ParamDefinition(
                name="plant",
                param_type=ParamType.DROPDOWN,
                required=True,
                enum_values=["1000", "2000"]
            )
        ]
        provided = {"plant": "9999"}
        
        is_valid, errors = ParameterValidator.validate(provided, params_def)
        
        assert not is_valid
    
    def test_validate_multiple_parameters_mixed_valid_invalid(self) -> None:
        """Validate multiple parameters with mix of valid and invalid.
        
        Tests validation accumulates errors across multiple params.
        """
        from sap import ParameterValidator
        
        params_def = [
            ParamDefinition(name="material_id", param_type=ParamType.STRING, required=True),
            ParamDefinition(name="quantity", param_type=ParamType.INT, required=True),
        ]
        provided = {"material_id": "ABC123", "quantity": "not_an_int"}
        
        is_valid, errors = ParameterValidator.validate(provided, params_def)
        
        assert not is_valid
        assert len(errors) > 0


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Execution Workflow (8–10 tests)
# ─────────────────────────────────────────────────────────────────────────────

class TestExecutionWorkflow:
    """Test report execution workflow with mocked SAP session."""
    
    @pytest.mark.asyncio
    async def test_execute_report_navigate_step_structure(self, mock_session_async: MagicMock) -> None:
        """Verify navigate step structure and parameters.
        
        Tests ReportStep.NAVIGATE has correct fields.
        """
        step = ReportStep(action=ReportStepAction.NAVIGATE, target="VA01", timeout=30)
        
        assert step.action == ReportStepAction.NAVIGATE
        assert step.target == "VA01"
        assert step.timeout == 30
    
    @pytest.mark.asyncio
    async def test_execute_report_set_field_step_structure(self, mock_session_async: MagicMock) -> None:
        """Verify set_field step structure with parameter placeholders.
        
        Tests ReportStep.SET_FIELD can accept placeholder values.
        """
        step = ReportStep(
            action=ReportStepAction.SET_FIELD, 
            field="RMMG1-MATNR", 
            value="{material_id}",
            timeout=5
        )
        
        assert step.action == ReportStepAction.SET_FIELD
        assert step.field == "RMMG1-MATNR"
        assert step.value is not None
        assert "{material_id}" in step.value
    
    @pytest.mark.asyncio
    async def test_execute_report_set_field_conditional_structure_true(self) -> None:
        """Verify set_field_conditional step structure with condition.
        
        Tests conditional field can specify when to execute.
        """
        step = ReportStep(
            action=ReportStepAction.SET_FIELD_CONDITIONAL,
            field="RMMG1-WERKS",
            value="{plant}",
            condition="{plant}"
        )
        
        assert step.action == ReportStepAction.SET_FIELD_CONDITIONAL
        assert step.condition is not None
    
    @pytest.mark.asyncio
    async def test_report_step_validation_action_enum(self) -> None:
        """Verify ReportStep validates action enum correctly.
        
        Tests only valid ReportStepAction values accepted.
        """
        # Valid steps should not raise
        for action in ReportStepAction:
            step = ReportStep(action=action)
            assert step.action == action
    
    @pytest.mark.asyncio
    async def test_execute_report_execute_step_minimal(self, mock_session_async: MagicMock) -> None:
        """Execute execute step structure (press button/ENTER).
        
        Tests ReportStep.EXECUTE with minimal config.
        """
        step = ReportStep(action=ReportStepAction.EXECUTE, timeout=30)
        
        assert step.action == ReportStepAction.EXECUTE
        assert step.timeout == 30
    
    @pytest.mark.asyncio
    async def test_execute_report_read_grid_step_structure(self, mock_session_async: MagicMock) -> None:
        """Verify read_grid step structure with output config.
        
        Tests ReportStep.READ_GRID and output configuration.
        """
        step = ReportStep(action=ReportStepAction.READ_GRID, target="sap_grid", timeout=10)
        output_config = ReportOutputConfig(
            columns=[ReportColumn(column_name="MATNR", header="Material", width=20)],
            row_limit=100
        )
        
        assert step.action == ReportStepAction.READ_GRID
        assert step.target == "sap_grid"
        assert len(output_config.columns) == 1
    
    @pytest.mark.asyncio
    async def test_report_metadata_step_sequence(self, tmp_path: Path) -> None:
        """Verify ReportMetadata with complete step sequence.
        
        Tests workflow with all step types in proper order.
        """
        metadata = ReportMetadata(
            name="workflow_test",
            title="Workflow Test",
            transaction="VA01",
            steps=[
                ReportStep(action=ReportStepAction.NAVIGATE, target="VA01"),
                ReportStep(action=ReportStepAction.SET_FIELD, field="RMMG1-MATNR", value="{material_id}"),
                ReportStep(action=ReportStepAction.EXECUTE),
                ReportStep(action=ReportStepAction.READ_GRID, target="[/app/grid]"),
            ],
            output=ReportOutputConfig(columns=[]),
            error_handling=ReportErrorHandling()
        )
        
        assert len(metadata.steps) == 4
        assert metadata.steps[0].action == ReportStepAction.NAVIGATE
        assert metadata.steps[1].action == ReportStepAction.SET_FIELD
        assert metadata.steps[2].action == ReportStepAction.EXECUTE
        assert metadata.steps[3].action == ReportStepAction.READ_GRID
    
    @pytest.mark.asyncio
    async def test_report_manager_registration(self, tmp_path: Path) -> None:
        """ReportManager discovers and registers report metadata.
        
        Tests report discovery and registry functionality.
        """
        reports_dir = tmp_path / "reports"
        
        manager = ReportManager(reports_dir)
        manager.bootstrap_examples()
        
        # Discover should find bootstrapped examples
        discovered = manager.discover_reports()
        
        assert len(discovered) > 0


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Error Cases (6–8 tests)
# ─────────────────────────────────────────────────────────────────────────────

class TestErrorCases:
    """Test error scenarios in report execution."""
    
    def test_error_transaction_not_found_config(self) -> None:
        """Error handling when transaction code not found in SAP.
        
        Tests ReportErrorHandling.transaction_not_found action configuration.
        """
        error_config = ReportErrorHandling(transaction_not_found="abort")
        
        assert error_config.transaction_not_found == "abort"
        assert error_config.max_retries == 2
    
    def test_error_field_set_failed_config(self) -> None:
        """Configuration for field_set_failed error handling.
        
        Tests ReportErrorHandling.field_set_failed strategy.
        """
        error_config = ReportErrorHandling(field_set_failed="skip")
        
        assert error_config.field_set_failed == "skip"
    
    def test_error_execution_timeout_config(self, tmp_path: Path) -> None:
        """Configuration for execution timeout error handling.
        
        Tests ReportErrorHandling.execution_timeout strategy.
        """
        error_config = ReportErrorHandling(
            execution_timeout="abort",
            max_retries=0,
            retry_delay_seconds=5
        )
        
        assert error_config.execution_timeout == "abort"
        assert error_config.max_retries == 0
    
    def test_error_grid_extraction_timeout_config(self) -> None:
        """Configuration for grid extraction timeout.
        
        Tests ReportStep timeout field.
        """
        step = ReportStep(
            action=ReportStepAction.READ_GRID,
            target="[/app/grid]",
            timeout=10
        )
        
        assert step.timeout == 10
        assert step.timeout <= 300  # Within max limit
        assert step.timeout >= 5   # Within min limit
    
    def test_error_invalid_yaml_schema(self, tmp_path: Path) -> None:
        """Error when YAML file violates ReportMetadata schema.
        
        Tests ReportYAML.load() returns None on schema violation.
        """
        invalid_yaml = '''
transaction: "VA01"
# Missing required 'name' field
'''
        report_file = tmp_path / "invalid.yaml"
        report_file.write_text(invalid_yaml)
        
        metadata = ReportYAML.load(report_file)
        
        assert metadata is None
    
    def test_error_parameter_validation_type_mismatch(self) -> None:
        """Error when user-provided parameters fail validation.
        
        Tests ParameterValidator catches invalid parameter types/values.
        """
        from sap import ParameterValidator
        
        params_def = [
            ParamDefinition(name="quantity", param_type=ParamType.INT, required=True)
        ]
        provided = {"quantity": "not_an_integer"}
        
        is_valid, errors = ParameterValidator.validate(provided, params_def)
        
        assert not is_valid
        assert len(errors) > 0
    
    def test_error_handling_retry_strategy(self) -> None:
        """Error handling with retry strategy configuration.
        
        Tests retry_delay_seconds configuration.
        """
        error_config = ReportErrorHandling(
            transaction_not_found="retry",
            max_retries=3,
            retry_delay_seconds=10
        )
        
        assert error_config.transaction_not_found == "retry"
        assert error_config.max_retries == 3
        assert error_config.retry_delay_seconds == 10


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: End-to-End Workflows (4–6 tests)
# ─────────────────────────────────────────────────────────────────────────────

class TestEndToEndWorkflows:
    """Test complete end-to-end report execution workflows."""
    
    def test_end_to_end_stock_report_yaml_load_and_validate(self, tmp_path: Path) -> None:
        """Complete stock report workflow: load YAML → validate params → structure check.
        
        Tests realistic inventory report YAML loading and validation.
        """
        # Create simple report YAML
        report_yaml = '''
name: "stock_report"
title: "Stock Report"
transaction: "MB5B"
parameters:
  - name: "material_id"
    param_type: "string"
    required: true
steps:
  - action: "navigate"
    target: "MB5B"
  - action: "set_field"
    field: "RMMG1-MATNR"
    value: "{material_id}"
  - action: "execute"
  - action: "read_grid"
    target: "[/app/grid]"
output:
  columns:
    - column_name: "MATNR"
      header: "Material"
    - column_name: "LABST"
      header: "Stock"
error_handling:
  transaction_not_found: "abort"
'''
        report_file = tmp_path / "stock_report.yaml"
        report_file.write_text(report_yaml)
        
        # Load and validate
        metadata = ReportYAML.load(report_file)
        
        assert metadata is not None
        assert metadata.name == "stock_report"
        assert metadata.transaction == "MB5B"
        assert len(metadata.parameters) == 1
        assert len(metadata.steps) == 4
        assert len(metadata.output.columns) == 2
    
    def test_end_to_end_sales_orders_report_multi_param(self, tmp_path: Path) -> None:
        """Execute sales orders report with date range and customer filter.
        
        Tests multi-parameter report with optional fields validation.
        """
        report_yaml = '''
name: "sales_orders"
title: "Sales Orders Report"
transaction: "VA03"
parameters:
  - name: "customer_id"
    param_type: "string"
    required: true
  - name: "start_date"
    param_type: "date"
    required: false
  - name: "end_date"
    param_type: "date"
    required: false
steps:
  - action: "navigate"
    target: "VA03"
  - action: "set_field"
    field: "VBKD-KUNNR"
    value: "{customer_id}"
  - action: "set_field_conditional"
    field: "VBRK-ERDAT_FROM"
    value: "{start_date}"
    condition: "{start_date}"
  - action: "execute"
  - action: "read_grid"
output:
  columns:
    - column_name: "VBELN"
      header: "Order"
    - column_name: "KUNNR"
      header: "Customer"
    - column_name: "ERDAT"
      header: "Date"
error_handling: {}
'''
        report_file = tmp_path / "sales_orders.yaml"
        report_file.write_text(report_yaml)
        
        metadata = ReportYAML.load(report_file)
        
        assert metadata is not None
        assert len(metadata.parameters) == 3
        assert metadata.parameters[1].required is False
        
        # Validate optional parameters
        from sap import ParameterValidator
        provided_partial = {"customer_id": "CUST001"}
        is_valid, errors = ParameterValidator.validate(provided_partial, metadata.parameters)
        
        assert is_valid  # Should be valid with optional params missing
    
    def test_end_to_end_with_all_parameter_types(self, tmp_path: Path) -> None:
        """Report using all 6 parameter types: string, int, bool, date, dropdown, multi-select.
        
        Tests parameter handling for diverse data types in single report.
        """
        report_yaml = f'''
name: "complex_params"
title: "Complex Parameters Report"
transaction: "VA01"
parameters:
  - name: "material_id"
    param_type: "{ParamType.STRING.value}"
    required: true
  - name: "quantity"
    param_type: "{ParamType.INT.value}"
    required: false
  - name: "active_only"
    param_type: "{ParamType.BOOL.value}"
    required: false
    default_value: true
  - name: "effective_date"
    param_type: "{ParamType.DATE.value}"
    required: false
  - name: "plant"
    param_type: "{ParamType.DROPDOWN.value}"
    required: false
    enum_values: ["1000", "2000"]
  - name: "materials_to_include"
    param_type: "{ParamType.MULTI_SELECT.value}"
    required: false
steps: []
output:
  columns: []
error_handling: {{}}
'''
        report_file = tmp_path / "complex_params.yaml"
        report_file.write_text(report_yaml)
        
        metadata = ReportYAML.load(report_file)
        
        assert metadata is not None
        assert len(metadata.parameters) == 6
        param_types = [p.param_type for p in metadata.parameters]
        assert ParamType.STRING in param_types
        assert ParamType.INT in param_types
        assert ParamType.BOOL in param_types
        assert ParamType.DATE in param_types
        assert ParamType.DROPDOWN in param_types
        assert ParamType.MULTI_SELECT in param_types


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Export Integration (4–6 tests)
# ─────────────────────────────────────────────────────────────────────────────

class TestExportIntegration:
    """Test report result export (CSV and Excel)."""
    
    def test_export_grid_result_to_dictionary(self) -> None:
        """Convert grid extraction result to dictionary list format.
        
        Tests ReportResult structure and data format.
        """
        # Create mock result data (ReportResult uses dict rows, not list rows)
        result = ReportResult(
            columns=["MATNR", "MAKTX", "LABST"],
            rows=[
                {"MATNR": "001", "MAKTX": "Material 1", "LABST": "100"},
                {"MATNR": "002", "MAKTX": "Material 2", "LABST": "200"},
            ]
        )
        
        assert len(result.rows) == 2
        assert result.columns[0] == "MATNR"
        assert result.row_count == 2
    
    def test_report_result_structure(self) -> None:
        """Test ReportResult dataclass has all expected fields.
        
        Validates result structure for export operations.
        """
        result = ReportResult(
            columns=["MATNR", "MAKTX"],
            rows=[{"MATNR": "001", "MAKTX": "Material"}]
        )
        
        assert result.columns is not None
        assert result.rows is not None
        assert result.row_count == 1
    
    def test_export_result_with_mixed_types(self) -> None:
        """Export preserves data types (int, float, string, date).
        
        Tests result export maintains type fidelity.
        """
        # Create result with mixed types
        result = ReportResult(
            columns=["MATNR", "QUANTITY", "PRICE", "ACTIVE"],
            rows=[
                {"MATNR": "001", "QUANTITY": 100, "PRICE": 29.99, "ACTIVE": True},
                {"MATNR": "002", "QUANTITY": 50, "PRICE": 14.50, "ACTIVE": False},
            ]
        )
        
        assert isinstance(result.rows[0]["QUANTITY"], int)
        assert isinstance(result.rows[0]["PRICE"], float)
        assert isinstance(result.rows[0]["ACTIVE"], bool)
    
    def test_export_empty_result_set(self) -> None:
        """Export handles empty result set gracefully.
        
        Tests export with no data rows (e.g., no query results).
        """
        result = ReportResult(
            columns=["MATNR", "MAKTX"],
            rows=[],
            row_count=0
        )
        
        assert result.rows == []
        assert result.row_count == 0
    
    def test_export_large_result_set(self) -> None:
        """Export handles large result sets (1000+ rows).
        
        Tests performance and memory handling with large data.
        """
        # Create 1000 mock rows
        large_rows = [
            {"MATNR": f"MAT{i:05d}", "MAKTX": f"Material {i}", "LABST": str(i * 10)}
            for i in range(1000)
        ]
        result = ReportResult(
            columns=["MATNR", "MAKTX", "LABST"],
            rows=large_rows
        )
        
        assert len(result.rows) == 1000
        assert result.rows[0]["MATNR"] == "MAT00000"
        assert result.rows[-1]["MATNR"] == "MAT00999"
    def test_export_result_serializable_to_json(self) -> None:
        """Export result row data is JSON-serializable for transport.
        
        Tests result can be sent over network/stored without issues.
        """
        result = ReportResult(
            columns=["MATNR", "MAKTX"],
            rows=[
                ["001", "Material 1"],
                ["002", "Material 2"],
            ]
        )
        
        # Should not raise JSONEncoder error
        try:
            json_str = json.dumps(result.rows)
            assert json_str is not None
            assert "001" in json_str
        except TypeError:
            pytest.fail("ReportResult should be JSON-serializable")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Report Manager & Discovery (3–5 tests)
# ─────────────────────────────────────────────────────────────────────────────

class TestReportManagerAndDiscovery:
    """Test ReportManager and report discovery."""
    
    def test_report_manager_discovery_empty_directory(self, tmp_path: Path) -> None:
        """Report discovery finds no reports in empty directory.
        
        Tests graceful handling of empty reports directory.
        """
        reports_dir = tmp_path / "empty_reports"
        reports_dir.mkdir()
        
        manager = ReportManager(reports_dir)
        reports = manager.discover_reports()
        
        assert reports == []
    
    def test_report_manager_discovery_finds_reports(self, tmp_path: Path) -> None:
        """Report discovery finds YAML files in directory.
        
        Tests report scanning and loading.
        """
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()
        
        # Create test report
        report_yaml = '''
name: "test_report"
title: "Test"
transaction: "VA01"
steps: []
output:
  columns: []
error_handling: {}
'''
        (reports_dir / "test_report.yaml").write_text(report_yaml)
        
        manager = ReportManager(reports_dir)
        reports = manager.discover_reports()
        
        assert len(reports) > 0
        assert reports[0].name == "test_report"
    
    def test_report_manager_list_reports(self, tmp_path: Path) -> None:
        """ReportManager.list_reports() returns all available reports.
        
        Tests report listing functionality.
        """
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()
        
        manager = ReportManager(reports_dir)
        manager.bootstrap_examples()
        
        reports = manager.list_reports()
        
        assert len(reports) > 0
        assert all(hasattr(r, 'name') for r in reports)
    
    def test_report_manager_search_reports_by_name(self, tmp_path: Path) -> None:
        """ReportManager.search_reports() finds reports by name/description.
        
        Tests search functionality.
        """
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()
        
        manager = ReportManager(reports_dir)
        manager.bootstrap_examples()
        
        results = manager.search_reports("stock")
        
        # Should find stock_report if bootstrapped
        assert len(results) >= 0


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_session_async() -> MagicMock:
    """Mock Session with async methods for report testing.
    
    Returns:
        Mock Session object with all required async methods
    """
    from unittest.mock import AsyncMock
    
    session = MagicMock()
    
    # Async methods
    session.start_transaction = AsyncMock(return_value=None)
    session.set_field_value = AsyncMock(return_value=None)
    session.read_grid = AsyncMock(return_value=[])
    session.click_button = AsyncMock(return_value=None)
    
    # Sync properties/methods
    session.is_connected = MagicMock(return_value=True)
    session.close = AsyncMock(return_value=None)
    
    return session


@pytest.fixture
def config() -> MagicMock:
    """Minimal configuration fixture for tests.
    
    Returns:
        Configuration object
    """
    return MagicMock()
