"""NiceGUI reusable components.

This module provides reusable UI components for the SAP Bridge application.

Note: The ParameterForm component is defined here. In production, it should be
refactored into a separate parameter_form.py module for better organization.

Modules:
    - parameter_form: Dynamic form generation from ParamDefinition objects
"""

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
from datetime import date

from nicegui import ui

from sap import ParamDefinition, ParamType, ParameterValidator

logger = logging.getLogger(__name__)


@dataclass
class FormFieldState:
    """Track validation and runtime state for a single parameter field.
    
    Attributes:
        param_id: Unique identifier for the parameter
        param_name: Display name of the parameter
        value: Current value of the parameter field
        is_valid: Whether current value passes validation
        error_message: Validation error message (if any)
        ui_element: Reference to the NiceGUI input element
        error_label: Reference to the error display label
    """
    
    param_id: str
    param_name: str
    value: Any
    is_valid: bool = True
    error_message: str = ""
    ui_element: Optional[ui.element] = None
    error_label: Optional[ui.label] = None


class ParameterForm:
    """Dynamically render NiceGUI fields from ParamDefinition list.
    
    Supports all 6 parameter types: STRING, INT, BOOL, DATE, DROPDOWN, MULTI_SELECT.
    Integrates with ParameterValidator for real-time field validation.
    
    Attributes:
        parameters: List of ParamDefinition objects defining form structure.
        field_state: Dict mapping param names to FormFieldState objects.
        on_change_callback: Optional callback invoked after field changes.
    
    Example:
        ```python
        from ui.components import ParameterForm
        from sap import ParamDefinition, ParamType
        
        parameters = [
            ParamDefinition(
                name="transaction",
                param_type=ParamType.STRING,
                required=True,
                description="SAP transaction code"
            ),
            ParamDefinition(
                name="quantity",
                param_type=ParamType.INT,
                default_value=1,
                description="Number of items"
            ),
            ParamDefinition(
                name="status",
                param_type=ParamType.DROPDOWN,
                enum_values=["Active", "Inactive", "Pending"],
                default_value="Active",
            ),
        ]
        
        form = ParameterForm(parameters)
        
        with ui.column() as form_container:
            form.render(form_container)
        
        if form.is_valid():
            values = form.get_values()
            await execute_script(script_id, values)
        else:
            errors = form.get_errors()
            ui.notify(f"Validation errors: {errors}", type='negative')
        ```
    """
    
    def __init__(self, parameters: List[ParamDefinition]) -> None:
        """Initialize form with parameter definitions.
        
        Args:
            parameters: List of ParamDefinition objects defining form structure.
            
        Raises:
            ValueError: If parameters list is empty or contains duplicates.
        """
        if not parameters:
            raise ValueError("parameters list cannot be empty")
        
        param_names = [p.name for p in parameters]
        if len(param_names) != len(set(param_names)):
            raise ValueError("Parameter names must be unique")
        
        self.parameters = parameters
        self.field_state: Dict[str, FormFieldState] = {}
        self.on_change_callback: Optional[Callable] = None
        self._container: Optional[ui.element] = None
        
        # Initialize field state for each parameter with default values
        for param in parameters:
            default_val = param.default_value if param.default_value is not None else ""
            self.field_state[param.name] = FormFieldState(
                param_id=param.name,
                param_name=param.name,
                value=default_val,
                is_valid=not param.required or param.default_value is not None,
                error_message="",
            )
    
    def render(self, container: ui.element) -> None:
        """Render all form fields into the given container.
        
        Creates NiceGUI input elements for each parameter, applying appropriate
        field types, validation, styling, and error display.
        
        Args:
            container: NiceGUI element (column, card, etc.) to render fields into.
        """
        self._container = container
        
        for param in self.parameters:
            with container:
                self._render_field(param)
    
    def _render_field(self, param: ParamDefinition) -> None:
        """Render a single parameter field based on its type.
        
        Args:
            param: ParamDefinition describing the field to render.
        """
        with ui.column().classes("gap-2 mb-4 w-full"):
            # Render field label with optional required asterisk
            label_text = param.name
            if param.required:
                label_text += " *"
            
            ui.label(label_text).classes("text-sm font-semibold")
            
            # Render field-type-specific input element
            state = self.field_state[param.name]
            
            if param.param_type == ParamType.STRING:
                self._render_string_field(param, state)
            elif param.param_type == ParamType.INT:
                self._render_int_field(param, state)
            elif param.param_type == ParamType.BOOL:
                self._render_bool_field(param, state)
            elif param.param_type == ParamType.DATE:
                self._render_date_field(param, state)
            elif param.param_type == ParamType.DROPDOWN:
                self._render_dropdown_field(param, state)
            elif param.param_type == ParamType.MULTI_SELECT:
                self._render_multi_select_field(param, state)
            else:
                ui.label(f"Unknown type: {param.param_type}").classes("text-red-500")
            
            # Render help text if available
            if param.description:
                ui.label(param.description).classes("text-xs text-gray-500 italic")
            
            # Render error message label (initially hidden)
            error_label = ui.label("").classes("text-xs text-red-600 mt-1")
            error_label.visible = False
            state.error_label = error_label
    
    def _render_string_field(self, param: ParamDefinition, state: FormFieldState) -> None:
        """Render a STRING parameter as text input.
        
        Args:
            param: ParamDefinition for the string field.
            state: FormFieldState tracking this field's state.
        """
        def on_value_change(new_val: str) -> None:
            state.value = new_val
            self._validate_field(param, state, new_val)
            if self.on_change_callback:
                self.on_change_callback()
        
        field_elem = ui.input(
            label="",
            placeholder=f"Enter {param.name}",
            value=str(state.value) if state.value else "",
            on_change=lambda val: on_value_change(val.value),
        ).classes("w-full")
        
        state.ui_element = field_elem
    
    def _render_int_field(self, param: ParamDefinition, state: FormFieldState) -> None:
        """Render an INT parameter as number input.
        
        Args:
            param: ParamDefinition for the integer field.
            state: FormFieldState tracking this field's state.
        """
        def on_value_change(new_val: float) -> None:
            state.value = int(new_val) if new_val is not None else 0
            self._validate_field(param, state, state.value)
            if self.on_change_callback:
                self.on_change_callback()
        
        initial_val = state.value if state.value else 0
        field_elem = ui.number(
            label="",
            value=float(initial_val),
            on_change=lambda val: on_value_change(val.value),
        ).classes("w-full")
        
        state.ui_element = field_elem
    
    def _render_bool_field(self, param: ParamDefinition, state: FormFieldState) -> None:
        """Render a BOOL parameter as checkbox.
        
        Args:
            param: ParamDefinition for the boolean field.
            state: FormFieldState tracking this field's state.
        """
        def on_value_change(new_val: bool) -> None:
            state.value = new_val
            self._validate_field(param, state, state.value)
            if self.on_change_callback:
                self.on_change_callback()
        
        initial_val = bool(state.value) if state.value is not None else False
        field_elem = ui.checkbox(
            text=f"Enable {param.name}",
            value=initial_val,
            on_change=lambda val: on_value_change(val.value),
        ).classes("w-full")
        
        state.ui_element = field_elem
    
    def _render_date_field(self, param: ParamDefinition, state: FormFieldState) -> None:
        """Render a DATE parameter as date picker.
        
        Args:
            param: ParamDefinition for the date field.
            state: FormFieldState tracking this field's state.
        """
        def on_value_change(new_val: str) -> None:
            state.value = new_val
            self._validate_field(param, state, state.value)
            if self.on_change_callback:
                self.on_change_callback()
        
        initial_val = state.value if state.value else date.today().isoformat()
        field_elem = ui.date(
            label="",
            value=initial_val,
            on_change=lambda val: on_value_change(val.value),
        ).classes("w-full")
        
        state.ui_element = field_elem
    
    def _render_dropdown_field(self, param: ParamDefinition, state: FormFieldState) -> None:
        """Render a DROPDOWN parameter as select.
        
        Args:
            param: ParamDefinition for the dropdown field.
            state: FormFieldState tracking this field's state.
        """
        if not param.enum_values:
            raise ValueError(
                f"ParamDefinition '{param.name}' type=DROPDOWN requires enum_values list"
            )
        
        def on_value_change(new_val: str) -> None:
            state.value = new_val
            self._validate_field(param, state, state.value)
            if self.on_change_callback:
                self.on_change_callback()
        
        initial_val = (
            str(state.value) if state.value and state.value in param.enum_values
            else (param.enum_values[0] if param.enum_values else "")
        )
        
        field_elem = ui.select(
            options=param.enum_values,
            label="",
            value=initial_val,
            on_change=lambda val: on_value_change(val.value),
        ).classes("w-full")
        
        state.ui_element = field_elem
    
    def _render_multi_select_field(
        self, param: ParamDefinition, state: FormFieldState
    ) -> None:
        """Render a MULTI_SELECT parameter as multiple checkboxes.
        
        Args:
            param: ParamDefinition for the multi-select field.
            state: FormFieldState tracking this field's state.
        """
        if not param.enum_values:
            raise ValueError(
                f"ParamDefinition '{param.name}' type=MULTI_SELECT requires enum_values list"
            )
        
        if not isinstance(state.value, list):
            state.value = state.value if isinstance(state.value, list) else []
        
        checkbox_values: Dict[str, bool] = {}
        
        def update_state() -> None:
            state.value = [opt for opt, checked in checkbox_values.items() if checked]
            self._validate_field(param, state, state.value)
            if self.on_change_callback:
                self.on_change_callback()
        
        for opt_val in param.enum_values:
            is_checked = opt_val in (state.value if isinstance(state.value, list) else [])
            checkbox_values[opt_val] = is_checked
            ui.checkbox(
                text=opt_val,
                value=is_checked,
                on_change=lambda val, opt=opt_val: (
                    checkbox_values.update({opt: val.value}),
                    update_state(),
                ),
            ).classes("w-full")
        
        state.ui_element = None
        state.value = [opt for opt, checked in checkbox_values.items() if checked]
    
    def _validate_field(
        self, param: ParamDefinition, state: FormFieldState, value: Any
    ) -> None:
        """Validate a single field and update UI state accordingly.
        
        Calls ParameterValidator._validate_parameter() for type/constraint checking.
        Updates error state and visual styling on the field.
        
        Args:
            param: ParamDefinition describing the field.
            state: FormFieldState to update with validation results.
            value: Current value of the field.
        """
        errors = ParameterValidator._validate_parameter(value, param)
        
        state.is_valid = len(errors) == 0
        state.error_message = errors[0] if errors else ""
        
        if state.error_label:
            if state.is_valid:
                state.error_label.visible = False
                state.error_label.text = ""
            else:
                state.error_label.visible = True
                state.error_label.text = state.error_message
        
        if state.ui_element:
            if state.is_valid:
                state.ui_element.classes(
                    remove="border-red-500 bg-red-50", add="border-gray-300"
                )
            else:
                state.ui_element.classes(
                    remove="border-gray-300", add="border-red-500 bg-red-50"
                )
    
    def get_values(self) -> Dict[str, Any]:
        """Return current form values as {param_name: value}.
        
        Collects current values from all form fields.
        
        Returns:
            Dictionary mapping parameter names to their current values.
            For MULTI_SELECT, values are lists. For other types, values
            match their Python types (str, int, bool, ISO 8601 date string, etc).
        """
        return {name: state.value for name, state in self.field_state.items()}
    
    def is_valid(self) -> bool:
        """Check if all required fields have valid values.
        
        Performs full validation sweep: checks required field presence,
        type correctness, and constraint satisfaction (enum, etc).
        
        Returns:
            True if all fields pass validation, False otherwise.
        """
        for param in self.parameters:
            state = self.field_state[param.name]
            
            # Required field check
            if param.required and not state.value:
                return False
            
            # Type validation
            if state.value:
                errors = ParameterValidator._validate_parameter(state.value, param)
                if errors:
                    return False
        
        return True
    
    def get_errors(self) -> Dict[str, str]:
        """Return {param_name: error_message} for failed validations.
        
        Re-validates all fields and accumulates errors. Useful for
        bulk error reporting to the user.
        
        Returns:
            Dictionary mapping parameter names to their validation error messages.
            Empty dict if all fields valid.
        """
        errors = {}
        
        for param in self.parameters:
            state = self.field_state[param.name]
            param_errors = []
            
            # Required check
            if param.required and not state.value:
                param_errors.append(f"Required parameter '{param.name}' is missing")
            
            # Type validation
            if state.value:
                type_errors = ParameterValidator._validate_parameter(state.value, param)
                param_errors.extend(type_errors)
            
            if param_errors:
                errors[param.name] = param_errors[0]
        
        return errors
    
    def reset_to_defaults(self) -> None:
        """Reset all fields to their default values.
        
        Restores initial state and clears validation errors for all fields.
        Updates NiceGUI elements to display default values.
        """
        for param in self.parameters:
            state = self.field_state[param.name]
            
            # Reset state
            default_val = param.default_value if param.default_value is not None else ""
            state.value = default_val
            state.is_valid = not param.required or param.default_value is not None
            state.error_message = ""
            
            # Update UI element if present
            if state.ui_element:
                if param.param_type == ParamType.STRING:
                    state.ui_element.value = str(default_val) if default_val else ""
                elif param.param_type == ParamType.INT:
                    state.ui_element.value = float(default_val) if default_val else 0.0
                elif param.param_type == ParamType.BOOL:
                    state.ui_element.value = bool(default_val) if default_val else False
                elif param.param_type == ParamType.DATE:
                    state.ui_element.value = (
                        str(default_val) if default_val else date.today().isoformat()
                    )
                elif param.param_type == ParamType.DROPDOWN:
                    if param.enum_values:
                        state.ui_element.value = (
                            str(default_val)
                            if default_val and str(default_val) in param.enum_values
                            else param.enum_values[0]
                        )
            
            # Clear error display
            if state.error_label:
                state.error_label.visible = False
                state.error_label.text = ""


__all__ = ["ParameterForm", "FormFieldState"]
