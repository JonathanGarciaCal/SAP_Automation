"""Compatibility wrapper for the ParameterForm component.

The full ParameterForm implementation currently lives in the
ui.components package initializer. This module preserves the import path used
by page modules and tests until the component is fully refactored.
"""

from ui.components import FormFieldState, ParameterForm

__all__ = ["ParameterForm", "FormFieldState"]