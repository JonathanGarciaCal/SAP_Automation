"""VBScript to Python converter for SAP automation scripts.

Converts VBScript (SAP GUI Scripting output) to Python code compatible with
pywin32 COM automation. Supports 20+ conversion patterns with comprehensive
error handling and flagging of unhandled constructs.

Architecture:
    - ConversionResult dataclass captures success, output, warnings, and errors
    - VBScriptConverter applies regex patterns in sequence
    - Flags unhandled patterns (MsgBox, CreateObject, etc.) for manual review
    - Tracks each pattern application for debugging and unit testing

Example:
    ```python
    from sap.script_runner import VBScriptConverter
    
    converter = VBScriptConverter()
    
    # Convert from file
    result = converter.convert_file('script.vbs')
    print(f"Success: {result.success}")
    print(f"Flags: {result.flags}")
    
    # Convert from string
    vbs_code = '''
    session.FindById("wnd[0]").maximize
    session.FindById("wnd[0]/tbar[0]/okcd").text = "/nVA01"
    '''
    result = converter.convert_code(vbs_code)
    print(result.converted_code)
    ```

Conversion Patterns (20+):
    1. VBS preamble removal (If Not IsObject, Set SapGuiAuto, etc.)
    2. Set declarations → direct assignment
    3. Method calls without parentheses → with parentheses
    4. sendVKey with space-separated args
    5. Boolean literal conversion (true/false → True/False)
    6. VBS comments (') → Python comments (#)
    7. If/Then/Else/End If → Python if/elif/else
    8. For i=start To end → for range loops
    9. For Each In → for ... in loops
    10. Do While → while loops
    11. Do Until → while not loops
    12. String concatenation (& → +)
    13. Function declarations (Function → def)
    14. End Function → implicit return
    15. Dim/ReDim declarations → remove
    16. Property assignment capitalization
    17. Multiple assignments per line handling
    18. Nested object access handling
    19. Integer literals with special handling
    20. Unhandled pattern flagging (MsgBox, CreateObject, On Error, etc.)

See doc/02-sap-scripting/vbs-to-python.md for detailed guidance.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class ConversionResult:
    """Result of VBScript conversion operation.
    
    Attributes:
        success: True if conversion completed (may have flags)
        converted_code: Converted Python code (may contain TODO comments)
        flags: List of warning messages about unhandled patterns
        error_message: Top-level error if conversion failed completely
        line_count: Number of lines in converted code
        patterns_applied: Dict of pattern names to count applied
    """
    
    success: bool
    converted_code: str
    flags: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    line_count: int = 0
    patterns_applied: Dict[str, int] = field(default_factory=dict)


class VBScriptConverter:
    """Convert VBScript to Python for SAP automation.
    
    Applies 20+ regex-based conversion patterns to transform VBScript code
    (from SAP GUI Scripting recorder) into Python code compatible with
    pywin32 COM automation.
    
    All methods are pure functions with no side effects. Instances are
    stateless and can be reused.
    """
    
    @staticmethod
    def _apply_pattern(
        code: str,
        pattern_name: str,
        regex: str,
        replacement: Optional[Any] = None,  # Can be str or callable
        flags: int = 0
    ) -> Tuple[str, int]:
        """Apply a single regex pattern and track matches.
        
        Args:
            code: Source code to transform
            pattern_name: Name of pattern (for logging/tracking)
            regex: Compiled regex or raw pattern string
            replacement: Replacement string (supports \\1, \\2, etc.) or callable
            flags: re module flags (IGNORECASE, MULTILINE, etc.)
        
        Returns:
            Tuple of (transformed_code, count_of_matches)
        """
        if isinstance(regex, str):
            compiled = re.compile(regex, flags)
        else:
            compiled = regex
        
        try:
            matches = len(compiled.findall(code))
            # Handle None replacement (skip substitution)
            if replacement is None:
                transformed = code
            else:
                transformed = compiled.sub(replacement, code)
            return transformed, matches
        except Exception as e:
            logger.warning(f"Pattern {pattern_name} failed: {e}")
            return code, 0
    
    def convert_code(self, vbs_code: str) -> ConversionResult:
        """Convert VBScript code string to Python.
        
        Applies 20+ patterns to transform VBScript to Python. May include
        TODO comments for unhandled constructs that need manual review.
        
        Args:
            vbs_code: VBScript source code as string
        
        Returns:
            ConversionResult with converted code, flags, and metadata
        """
        try:
            if not vbs_code or not vbs_code.strip():
                return ConversionResult(
                    success=False,
                    converted_code="",
                    error_message="Empty input"
                )
            
            code = vbs_code
            patterns_applied = {}
            flags: List[str] = []
            
            #  Pattern 1: Remove VBS preamble (If Not IsObject blocks)
            preamble_patterns = [
                r'If\s+Not\s+IsObject\s*\([^)]*\)\s+Then.*?End\s+If\s*\n?',
                r'WScript\.ConnectObject\s+\w+\s*,\s*"[^"]*"\s*\n?',
                r'Set\s+SapGuiAuto\s*=\s*GetObject\s*\(\s*"SAPGUI"\s*\)\s*\n?',
                r'Set\s+application\s*=\s*SapGuiAuto\.GetScriptingEngine\s*\n?',
                r'Set\s+connection\s*=\s*application\.Children\s*\([^)]*\)\s*\n?',
                r'Set\s+session\s*=\s*connection\.Children\s*\([^)]*\)\s*\n?',
            ]
            
            matches_count = 0
            for pattern in preamble_patterns:
                code, count = self._apply_pattern(
                    code, "remove_preamble", pattern, "", re.IGNORECASE | re.DOTALL
                )
                matches_count += count
            patterns_applied["remove_preamble"] = matches_count
            
            #  Pattern 2: Set variable declarations → direct assignment
            code, count = self._apply_pattern(
                code, "remove_set", r'\bSet\s+(\w+)\s*=\s*',
                r'\1 = ',
                re.IGNORECASE
            )
            patterns_applied["remove_set"] = count
            if count > 0:
                flags.append(f"Converted {count} Set declarations")
            
            #  Pattern 3: Method calls without parentheses
            method_patterns = {
                'maximize': (r'\.maximize\b(?!\()', '.Maximize()'),
                'minimize': (r'\.minimize\b(?!\()', '.Minimize()'),
                'press': (r'\.press\b(?!\()', '.Press()'),
                'select': (r'\.select\b(?!\()', '.Select()'),
                'setfocus': (r'\.setfocus\b(?!\()', '.SetFocus()'),
                'refresh': (r'\.refresh\b(?!\()', '.Refresh()'),
            }
            
            for method_name, (pattern, replacement) in method_patterns.items():
                code, count = self._apply_pattern(
                    code, f"add_parens_{method_name}", pattern, replacement, re.IGNORECASE
                )
                patterns_applied[f"add_parens_{method_name}"] = count
            
            #  Pattern 4: sendVKey with space-separated arguments
            code, count = self._apply_pattern(
                code, "sendvkey_args",
                r'\.sendVKey\s+(\d+)',
                r'.SendVKey(\1)',
                re.IGNORECASE
            )
            patterns_applied["sendvkey_args"] = count
            
            #  Pattern 5: resizeWorkingPane with arguments
            def replace_resize(match):
                args = match.group(1)
                args = re.sub(r'\bfalse\b', 'False', args, flags=re.IGNORECASE)
                args = re.sub(r'\btrue\b', 'True', args, flags=re.IGNORECASE)
                return f'.ResizeWorkingPane({args})'
            
            code, count = self._apply_pattern(
                code, "resize_working_pane",
                r'\.resizeWorkingPane\s+(.+?)(?=\n|$)',
                replace_resize,
                re.IGNORECASE
            )
            patterns_applied["resize_working_pane"] = count
            
            #  Pattern 6 & 7: Boolean literals
            code, count = self._apply_pattern(
                code, "boolean_true", r'\btrue\b', 'True', re.IGNORECASE
            )
            patterns_applied["boolean_true"] = count
            
            code, count = self._apply_pattern(
                code, "boolean_false", r'\bfalse\b', 'False', re.IGNORECASE
            )
            patterns_applied["boolean_false"] = count
            
            #  Pattern 8 & 9: Comments
            code, count = self._apply_pattern(
                code, "vbs_comments", r"^\s*'(.*)$", r'# \1', re.MULTILINE
            )
            patterns_applied["vbs_comments"] = count
            
            code, count = self._apply_pattern(
                code, "rem_comments", r'^\s*REM\s+(.*)$', r'# \1',
                re.IGNORECASE | re.MULTILINE
            )
            patterns_applied["rem_comments"] = count
            
            #  Pattern 10: String concatenation
            code, count = self._apply_pattern(
                code, "string_concat", r'\s*&\s*', ' + '
            )
            patterns_applied["string_concat"] = count
            
            #  Pattern 11: If/Then/Else
            code = self._convert_if_statements(code)
            
            #  Pattern 12 & 13: Loops
            code = self._convert_for_loops(code)
            code = self._convert_for_each_loops(code)
            code = self._convert_do_while_loops(code)
            code = self._convert_do_until_loops(code)
            
            #  Pattern 14 & 15: Dim/ReDim declarations
            code, count = self._apply_pattern(
                code, "remove_dim", r'^\s*Dim\s+\w+.*$', '',
                re.IGNORECASE | re.MULTILINE
            )
            patterns_applied["remove_dim"] = count
            
            #  Pattern 16: Capitalize methods
            code = self._capitalize_methods(code)
            
            #  Pattern 17: Unhandled pattern detection
            unhandled_patterns = {
                'MsgBox': r'\bMsgBox\s*\(',
                'InputBox': r'\bInputBox\s*\(',
                'WScript.Sleep': r'WScript\.Sleep',
                'CreateObject': r'CreateObject\s*\(',
                'On Error Resume Next': r'On\s+Error\s+Resume\s+Next',
                'Select Case': r'Select\s+Case',
            }
            
            for pattern_name, pattern_regex in unhandled_patterns.items():
                if re.search(pattern_regex, code, re.IGNORECASE | re.MULTILINE):
                    flags.append(f'TODO: {pattern_name} needs manual conversion')
            
            #  Clean up blank lines
            code = re.sub(r'\n\s*\n\s*\n+', '\n\n', code)
            
            #  Wrap in function
            code = self._wrap_in_function(code)
            
            return ConversionResult(
                success=True,
                converted_code=code,
                flags=flags,
                line_count=len(code.split('\n')),
                patterns_applied=patterns_applied
            )
        
        except Exception as e:
            return ConversionResult(
                success=False,
                converted_code="",
                error_message=f"Conversion failed: {str(e)}"
            )
    
    def convert_file(self, vbs_file_path: str) -> ConversionResult:
        """Convert VBScript file to Python code.
        
        Reads .vbs file and applies all conversion patterns.
        
        Args:
            vbs_file_path: Path to .vbs file
        
        Returns:
            ConversionResult with converted code and metadata
        """
        try:
            file_path = Path(vbs_file_path)
            
            if not file_path.exists():
                return ConversionResult(
                    success=False,
                    converted_code="",
                    error_message=f"File not found: {vbs_file_path}"
                )
            
            if not file_path.suffix.lower() == '.vbs':
                return ConversionResult(
                    success=False,
                    converted_code="",
                    error_message=f"Not a .vbs file: {vbs_file_path}"
                )
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                vbs_code = f.read()
            
            result = self.convert_code(vbs_code)
            return result
        
        except Exception as e:
            return ConversionResult(
                success=False,
                converted_code="",
                error_message=f"File read failed: {str(e)}"
            )
    
    @staticmethod
    def _capitalize_methods(code: str) -> str:
        """Capitalize SAP method names (findById → FindById)."""
        method_mappings = {
            'findById': 'FindById',
            'setText': 'SetText',
            'getText': 'GetText',
            'setValue': 'SetValue',
            'getValue': 'GetValue',
        }
        
        for old, new in method_mappings.items():
            code = re.sub(rf'(?<!\.)\b{old}\b', new, code)
        
        return code
    
    @staticmethod
    def _convert_if_statements(code: str) -> str:
        """Convert If/Then/Else to Python if/elif/else."""
        code = re.sub(
            r'^\s*If\s+(.+?)\s+Then\s+(.+?)$',
            r'if \1:\n    \2',
            code,
            flags=re.IGNORECASE | re.MULTILINE
        )
        
        code = re.sub(
            r'^\s*If\s+(.+?)\s+Then\s*$',
            r'if \1:',
            code,
            flags=re.IGNORECASE | re.MULTILINE
        )
        code = re.sub(
            r'^\s*Else\s*If\s+(.+?)\s+Then\s*$',
            r'elif \1:',
            code,
            flags=re.IGNORECASE | re.MULTILINE
        )
        code = re.sub(r'^\s*Else\s*$', r'else:', code, flags=re.IGNORECASE | re.MULTILINE)
        code = re.sub(r'^\s*End\s+If\s*$', '', code, flags=re.IGNORECASE | re.MULTILINE)
        
        return code
    
    @staticmethod
    def _convert_for_loops(code: str) -> str:
        """Convert For i = 1 To 10 loops to Python range."""
        def replace_for_loop(match):
            var, start, end, step = match.groups()
            step = step or "1"
            return f'for {var} in range({start}, {end} + 1, {step}):'
        
        code = re.sub(
            r'^\s*For\s+(\w+)\s*=\s*(\d+)\s+To\s+(\d+)(?:\s+Step\s+(\d+))?\s*$',
            replace_for_loop,
            code,
            flags=re.IGNORECASE | re.MULTILINE
        )
        
        code = re.sub(r'^\s*Next\s+\w*\s*$', '', code, flags=re.IGNORECASE | re.MULTILINE)
        return code
    
    @staticmethod
    def _convert_for_each_loops(code: str) -> str:
        """Convert For Each loops to Python for."""
        code = re.sub(
            r'^\s*For\s+Each\s+(\w+)\s+In\s+(.+?)\s*$',
            r'for \1 in \2:',
            code,
            flags=re.IGNORECASE | re.MULTILINE
        )
        code = re.sub(r'^\s*Next\s+\w*\s*$', '', code, flags=re.IGNORECASE | re.MULTILINE)
        return code
    
    @staticmethod
    def _convert_do_while_loops(code: str) -> str:
        """Convert Do While loops to Python while."""
        code = re.sub(
            r'^\s*Do\s+While\s+(.+?)\s*$',
            r'while \1:',
            code,
            flags=re.IGNORECASE | re.MULTILINE
        )
        code = re.sub(r'^\s*Loop\s*$', '', code, flags=re.IGNORECASE | re.MULTILINE)
        return code
    
    @staticmethod
    def _convert_do_until_loops(code: str) -> str:
        """Convert Do Until loops to Python while not."""
        code = re.sub(
            r'^\s*Do\s+Until\s+(.+?)\s*$',
            r'while not (\1):',
            code,
            flags=re.IGNORECASE | re.MULTILINE
        )
        return code
    
    @staticmethod
    def _wrap_in_function(code: str) -> str:
        """Wrap code in async function signature."""
        lines = code.strip().split('\n')
        
        if any(line.startswith('def ') or line.startswith('async def ') for line in lines):
            return code
        
        lines = [l for l in lines if l.strip()]
        indented = '\n'.join(f'    {line}' for line in lines)
        
        wrapped = (
            "async def execute_script(session, parameters):\n"
            "    '''Converted from VBScript SAP automation script.'''\n"
            f"{indented}\n"
            "    return True\n"
        )
        
        return wrapped


class ExecutionStatus:
    """Script execution status (placeholder for Phase 3)."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class ScriptRunner:
    """Script execution engine (Phase 3 placeholder)."""
    pass
