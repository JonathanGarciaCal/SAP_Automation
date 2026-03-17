"""Utility modules.

Provides:
    - VBScript converter (vbs_converter)
    - File/path utilities
    - Logging helpers
    - Configuration helpers

Example:
    ```python
    from utils.vbs_converter import convert_vbs_to_python
    
    result = convert_vbs_to_python(vbs_code)
    python_code = result.python_code
    ```
"""

try:
    from .vbs_converter import convert_vbs_to_python, ConversionResult
    __all__ = ['convert_vbs_to_python', 'ConversionResult']
except ImportError:
    # vbs_converter not yet created
    __all__ = []
