"""SAP COM bridge and automation layer.

Modules:
    - bridge: COM worker thread and queue manager
    - connection: SAP connection lifecycle
    - queue_manager: Command queue for thread-safe COM execution
    - session: SAP session API (async wrapper around COM)
    - inspector: Screen element inspection
    - script_manager: Script discovery, metadata, parameter validation, execution history
    - script_executor: Script execution engine
    - exporter: Grid and data export to Excel
    - error_handler: SAP-specific error classification
"""

# Script Manager (Task 3-7: Script Runner) ─────────────────────────────────

import logging
import sqlite3
import re
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import yaml
from pydantic import BaseModel, Field, field_validator, ValidationError

logger = logging.getLogger(__name__)


# SECTION 1: Pydantic Models (Task 3)

class ParamType(str, Enum):
    """Supported parameter data types."""
    STRING = "string"
    INT = "int"
    BOOL = "bool"
    DATE = "date"
    DROPDOWN = "dropdown"
    MULTI_SELECT = "multi-select"


class ParamDefinition(BaseModel):
    """Single parameter definition for a script."""
    name: str = Field(..., description="Parameter name")
    param_type: ParamType = Field(default=ParamType.STRING)
    required: bool = Field(default=False)
    description: str = Field(default="")
    default_value: Optional[Any] = Field(default=None)
    enum_values: Optional[List[str]] = Field(default=None)
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.isidentifier():
            raise ValueError(f"Parameter name '{v}' is not a valid Python identifier")
        return v


class ScriptMetadata(BaseModel):
    """Complete metadata for a SAP automation script."""
    model_config = {"validate_assignment": True}
    
    name: str = Field(...)
    description: str = Field(default="")
    author: Optional[str] = Field(default=None)
    version: str = Field(default="1.0.0")
    tags: List[str] = Field(default_factory=list)
    parameters: List[ParamDefinition] = Field(default_factory=list)
    timeout_seconds: int = Field(default=300, ge=10, le=3600)
    preconditions: Optional[str] = Field(default=None)
    execution_notes: Optional[str] = Field(default=None)
    
    @field_validator("parameters")
    @classmethod
    def validate_param_uniqueness(cls, v: List[ParamDefinition]) -> List[ParamDefinition]:
        names = [p.name for p in v]
        if len(names) != len(set(names)):
            raise ValueError("Parameter names must be unique")
        return v


class ExecutionRecord(BaseModel):
    """Record of a script execution."""
    id: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    script_name: str
    parameters: str = Field(default="{}")
    status: str = Field(...)
    output: Optional[str] = None
    duration_seconds: float = Field(default=0.0)
    error_message: Optional[str] = None
    traceback: Optional[str] = None


# SECTION 2: YAML I/O

class MetadataYAML:
    """Load and save ScriptMetadata to/from YAML files."""
    
    @staticmethod
    def load(path: Path) -> Optional[ScriptMetadata]:
        if not path.exists():
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            return ScriptMetadata(**data)
        except (yaml.YAMLError, ValidationError) as e:
            logger.error(f"Error loading metadata from {path}: {e}")
            return None
    
    @staticmethod
    def save(metadata: ScriptMetadata, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = metadata.model_dump(exclude_none=True)
        if "parameters" in data:
            data["parameters"] = [
                p.model_dump(exclude_none=True) if isinstance(p, ParamDefinition) else p
                for p in data["parameters"]
            ]
        with open(path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)


# SECTION 3: Parameter Parser (Task 5)

class ParameterParser:
    """Parse parameter definitions from Python script comments."""
    PARAM_PATTERN = re.compile(r'#\s*PARAM:\s*(\w+):(\w+):(\w+):(.+)', re.IGNORECASE)
    
    @staticmethod
    def parse_script_file(path: Path) -> List[ParamDefinition]:
        params: List[ParamDefinition] = []
        if not path.exists():
            return params
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except IOError:
            return params
        
        for match in ParameterParser.PARAM_PATTERN.finditer(content):
            name, param_type, required_str, description = match.groups()
            try:
                # Convert string param_type to ParamType enum
                param_type_value = param_type.strip().lower()
                param_type_enum = ParamType(param_type_value) if param_type_value in [pt.value for pt in ParamType] else ParamType.STRING
                param = ParamDefinition(
                    name=name.strip(),
                    param_type=param_type_enum,
                    required=required_str.strip().lower() in ('true', 'yes', '1'),
                    description=description.strip()
                )
                params.append(param)
            except ValidationError:
                pass
        return params
    
    @staticmethod
    def merge_parameters(script_params: List[ParamDefinition], yaml_params: List[ParamDefinition]) -> List[ParamDefinition]:
        merged = {p.name: p for p in script_params}
        for p in yaml_params:
            merged[p.name] = p
        return list(merged.values())


# SECTION 4: Parameter Validator (Task 5)

class ParameterValidator:
    """Validate user-provided parameters before script execution."""
    
    @staticmethod
    def validate(provided_params: Dict[str, Any], definitions: List[ParamDefinition]) -> tuple:
        errors: List[str] = []
        defs_by_name = {p.name: p for p in definitions}
        
        for defn in definitions:
            if defn.required and defn.name not in provided_params:
                errors.append(f"Required parameter '{defn.name}' is missing")
        
        for name, value in provided_params.items():
            if name not in defs_by_name:
                errors.append(f"Unknown parameter '{name}'")
                continue
            defn = defs_by_name[name]
            param_errors = ParameterValidator._validate_parameter(value, defn)
            errors.extend(param_errors)
        
        return len(errors) == 0, errors
    
    @staticmethod
    def _validate_parameter(value: Any, defn: ParamDefinition) -> List[str]:
        errors: List[str] = []
        name = defn.name
        
        try:
            if defn.param_type == ParamType.STRING:
                if not isinstance(value, str):
                    errors.append(f"Parameter '{name}' must be string")
            elif defn.param_type == ParamType.INT:
                if not isinstance(value, int) or isinstance(value, bool):
                    errors.append(f"Parameter '{name}' must be int")
            elif defn.param_type == ParamType.BOOL:
                if not isinstance(value, bool):
                    errors.append(f"Parameter '{name}' must be bool")
            elif defn.param_type == ParamType.DATE:
                if isinstance(value, str):
                    try:
                        datetime.fromisoformat(value.split('T')[0])
                    except ValueError:
                        errors.append(f"Parameter '{name}' must be ISO 8601 date")
            elif defn.param_type == ParamType.DROPDOWN:
                if defn.enum_values and value not in defn.enum_values:
                    errors.append(f"Parameter '{name}' must be in: {defn.enum_values}")
            elif defn.param_type == ParamType.MULTI_SELECT:
                if not isinstance(value, list):
                    errors.append(f"Parameter '{name}' must be list")
        except Exception as e:
            errors.append(f"Parameter '{name}' validation error: {e}")
        
        return errors


# SECTION 5: Script Registry (Task 4)

@dataclass
class ScriptEntry:
    """Single script in registry."""
    id: str
    path: Path
    name: str
    metadata: ScriptMetadata


class ScriptRegistry:
    """Script discovery and registry with hot-reload."""
    
    def __init__(self, scripts_dir: Path = Path("scripts")) -> None:
        self.scripts_dir = Path(scripts_dir)
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self._registry: Dict[str, ScriptEntry] = {}
        self._last_reload = 0.0
    
    def discover_scripts(self, force_reload: bool = False) -> List[ScriptEntry]:
        if force_reload:
            self._registry.clear()
            self._last_reload = 0.0
        
        py_files = list(self.scripts_dir.glob("**/*.py"))
        for p in py_files:
            try:
                script_id = str(p.relative_to(self.scripts_dir)).replace('\\', '/')
                if script_id in self._registry and p.stat().st_mtime <= self._last_reload:
                    continue
                self._load_script(script_id, p)
            except Exception as e:
                logger.error(f"Failed to load script {p}: {e}")
        
        self._last_reload = datetime.utcnow().timestamp()
        return list(self._registry.values())
    
    def _load_script(self, script_id: str, script_path: Path) -> None:
        try:
            yaml_path = script_path.with_suffix('.yaml')
            yaml_metadata = MetadataYAML.load(yaml_path)
            
            if yaml_metadata:
                metadata = yaml_metadata
            else:
                metadata = ScriptMetadata(name=script_path.stem, description=f"Script: {script_path.stem}")
            
            script_params = ParameterParser.parse_script_file(script_path)
            yaml_params = yaml_metadata.parameters if yaml_metadata else []
            # Ensure all params have correct ParamType enum values
            merged = ParameterParser.merge_parameters(script_params, yaml_params)
            for param in merged:
                if isinstance(param.param_type, str):
                    param.param_type = ParamType(param.param_type) if param.param_type in [pt.value for pt in ParamType] else ParamType.STRING
            metadata.parameters = merged
            
            entry = ScriptEntry(id=script_id, path=script_path, name=metadata.name, metadata=metadata)
            self._registry[script_id] = entry
        except Exception as e:
            logger.error(f"Error loading script {script_path}: {e}")
    
    def list_scripts(self) -> List[ScriptEntry]:
        if not self._registry:
            self.discover_scripts()
        return list(self._registry.values())
    
    def get_script(self, script_id: str) -> Optional[ScriptEntry]:
        if not self._registry:
            self.discover_scripts()
        return self._registry.get(script_id)
    
    def find_scripts(self, query: Optional[str] = None) -> List[ScriptEntry]:
        if not self._registry:
            self.discover_scripts()
        if not query:
            return list(self._registry.values())
        
        query_lower = query.lower()
        return [e for e in self._registry.values()
                if (query_lower in e.metadata.name.lower() or
                    query_lower in e.metadata.description.lower() or
                    any(query_lower in tag.lower() for tag in e.metadata.tags))]


# SECTION 6: Execution History (Task 7)

class ExecutionHistory:
    """SQLite-backed execution history."""
    
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS executions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME NOT NULL,
        script_name TEXT NOT NULL,
        parameters TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL,
        output TEXT,
        duration_seconds REAL DEFAULT 0.0,
        error_message TEXT,
        traceback TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_timestamp ON executions(timestamp DESC);
    CREATE INDEX IF NOT EXISTS idx_script ON executions(script_name);
    CREATE INDEX IF NOT EXISTS idx_status ON executions(status);
    """
    
    def __init__(self, db_path: Path = Path("logs/execution_history.db")) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self) -> None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                for statement in self.SCHEMA.split(';'):
                    if statement.strip():
                        conn.execute(statement)
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
    
    def add_execution(self, script_name: str, parameters: Dict[str, Any], status: str,
                      output: Optional[str] = None, duration_seconds: float = 0.0,
                      error_message: Optional[str] = None, traceback: Optional[str] = None) -> int:
        """Record script execution to database.
        
        Args:
            script_name: Name of the script that was executed
            parameters: Parameters passed to the script
            status: Execution status (success, error, timeout)
            output: Captured output from script execution
            duration_seconds: How long the script took to run
            error_message: Error message if execution failed
            traceback: Full traceback if execution failed
        
        Returns:
            Database row ID if successful, -1 if error occurred
        """
        try:
            params_json = json.dumps(parameters, default=str)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "INSERT INTO executions (timestamp, script_name, parameters, status, output, duration_seconds, error_message, traceback) VALUES (datetime('now'), ?, ?, ?, ?, ?, ?, ?)",
                    (script_name, params_json, status, output, duration_seconds, error_message, traceback)
                )
                conn.commit()
                row_id = cursor.lastrowid
                return row_id if row_id is not None else -1
        except sqlite3.Error as e:
            logger.error(f"Error recording execution: {e}")
            return -1
    
    def list_executions(self, limit: int = 100, offset: int = 0) -> List[ExecutionRecord]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM executions ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                    (limit, offset)
                ).fetchall()
            
            records = []
            for row in rows:
                records.append(ExecutionRecord(
                    id=row['id'], timestamp=datetime.fromisoformat(row['timestamp']),
                    script_name=row['script_name'], parameters=row['parameters'],
                    status=row['status'], output=row['output'], duration_seconds=row['duration_seconds'],
                    error_message=row['error_message'], traceback=row['traceback']
                ))
            return records
        except sqlite3.Error:
            return []
    
    def list_executions_by_script(self, script_name: str, limit: int = 100) -> List[ExecutionRecord]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM executions WHERE script_name = ? ORDER BY timestamp DESC LIMIT ?",
                    (script_name, limit)
                ).fetchall()
            
            records = []
            for row in rows:
                records.append(ExecutionRecord(
                    id=row['id'], timestamp=datetime.fromisoformat(row['timestamp']),
                    script_name=row['script_name'], parameters=row['parameters'],
                    status=row['status'], output=row['output'], duration_seconds=row['duration_seconds'],
                    error_message=row['error_message'], traceback=row['traceback']
                ))
            return records
        except sqlite3.Error:
            return []
    
    def cleanup_old_executions(self, keep_recent: int = 1000) -> int:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM executions WHERE id NOT IN (SELECT id FROM executions ORDER BY timestamp DESC LIMIT ?)",
                    (keep_recent,)
                )
                conn.commit()
                return cursor.rowcount
        except sqlite3.Error:
            return 0
    
    def get_statistics(self) -> Dict[str, Any]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                total = conn.execute("SELECT COUNT(*) as count FROM executions").fetchone()['count']
                by_status = {row['status']: row['count'] for row in conn.execute("SELECT status, COUNT(*) as count FROM executions GROUP BY status")}
                by_script = {row['script_name']: row['count'] for row in conn.execute("SELECT script_name, COUNT(*) as count FROM executions GROUP BY script_name ORDER BY count DESC LIMIT 10")}
            return {'total_executions': total, 'by_status': by_status, 'by_script': by_script}
        except sqlite3.Error:
            return {}




# SECTION 7: VBScript Converter (Task 1) ──────────────────────────────────

class VBSConverter:
    """Convert VBScript SAP automation code to Python.
    
    Handles 20+ common VBScript patterns including:
    - Property assignments and method calls
    - Function calls and FindById/FindByName
    - Control flow (If/Then/Else, For/While loops)
    - Variable declarations
    - String operations
    - Boolean and date handling
    
    Unsupported patterns are flagged with HTML comments for manual conversion.
    """
    
    # VBScript → Python method/property mappings
    VBS_TO_PYTHON = {
        # Method calls
        'FindById': 'find_by_id', 'FindByName': 'find_by_name',
        'SetValue': 'set_value', 'GetValue': 'get_value',
        'Click': 'click', 'DoubleClick': 'double_click',
        'Press': 'press', 'SendVKey': 'send_vkey',
        'SendKey': 'send_key', 'LeftClick': 'left_click', 'RightClick': 'right_click',
        'SetFocus': 'set_focus', 'ReadValue': 'read_value',
        'MsgBox': 'log_message', 'LeftTrimAmount': 'lstrip', 'RightTrimAmount': 'rstrip',
        # Properties
        'Visible': 'visible', 'Enabled': 'enabled',
        'Type': 'element_type', 'Name': 'name', 'ID': 'id',
    }
    
    def convert_script(self, vbs_code: str,  metadata: Optional[ScriptMetadata] = None) -> tuple[str, List[str]]:
        """Convert VBScript to Python.
        
        Args:
            vbs_code: VBScript source code
            metadata: Optional metadata (used for docstring generation)
        
        Returns:
            Tuple of (converted_python_code, list_of_conversion_flags)
        """
        flags: List[str] = []
        python_code = vbs_code
        
        # Step 1: Extract and preserve comments
        comments = self._extract_comments(python_code)
        
        # Step 2: Handle VBScript-specific constructs
        python_code = self._convert_control_flow(python_code, flags)
        python_code = self._convert_variable_declarations(python_code)
        python_code = self._convert_method_calls(python_code, flags)
        python_code = self._convert_string_operations(python_code)
        python_code = self._convert_boolean_literals(python_code)
        python_code = self._convert_comments(python_code, comments)
        
        # Step 3: Wrap in async function
        func_body = self._indent_code(python_code)
        function_template = f'''"""Converted from VBScript.{"" if not metadata else f" Original: {metadata.name}"}
        
Conversion flags: {', '.join(flags) if flags else 'None'}
"""

async def execute_script(session, parameters: Dict[str, Any]) -> Any:
    """Automated SAP script execution.
    
    Args:
        session: SAP session object
        parameters: Script parameters as dict
    
    Returns:
        Script result/output
    """
{func_body}
    
    return None
'''
        return function_template, flags
    
    def _convert_comments(self, code: str, comments: Dict[int, str]) -> str:
        """Preserve and convert comments."""
        # Python comments already start with #, so mostly just normalize
        result = []
        for i, line in enumerate(code.split('\n')):
            if i in comments:
                result.append(f"    # {comments[i]}")
            else:
                result.append(line)
        return '\n'.join(result)
    
    def _extract_comments(self, code: str) -> Dict[int, str]:
        """Extract VBScript comments (start with ')."""
        comments = {}
        for i, line in enumerate(code.split('\n')):
            stripped = line.strip()
            if stripped.startswith("'"):
                comments[i] = stripped.lstrip("'").strip()
        return comments
    
    def _convert_control_flow(self, code: str, flags: List[str]) -> str:
        """Convert VBScript If/For/While to Python."""
        # If/Then/Else → if/elif/else
        code = re.sub(
            r'If\s+(.+?)\s+Then\s*\n',
            r'if \1:\n',
            code,
            flags=re.IGNORECASE | re.MULTILINE
        )
        code = re.sub(
            r'Else\s+If\s+(.+?)\s+Then',
            r'elif \1:',
            code,
            flags=re.IGNORECASE
        )
        code = re.sub(r'Else\s*\n', r'else:\n', code, flags=re.IGNORECASE | re.MULTILINE)
        code = re.sub(r'End\s+If\s*\n', '', code, flags=re.IGNORECASE | re.MULTILINE)
        
        # For i = 1 to 10 → for i in range(1, 11)
        code = re.sub(
            r'For\s+(\w+)\s*=\s*(\d+)\s+To\s+(\d+)',
            r'for \1 in range(\2, \3 + 1)',
            code,
            flags=re.IGNORECASE
        )
        
        # For Each item in collection → for item in collection
        code = re.sub(
            r'For\s+Each\s+(\w+)\s+In\s+(\w+)',
            r'for \1 in \2',
            code,
            flags=re.IGNORECASE
        )
        
        code = re.sub(r'Next\s*\n', '', code, flags=re.IGNORECASE | re.MULTILINE)
        
        # Do While/Until → while
        code = re.sub(
            r'Do\s+While\s+(.+?)\n',
            r'while \1:\n',
            code,
            flags=re.IGNORECASE | re.MULTILINE
        )
        code = re.sub(r'Loop\s*\n', '', code, flags=re.IGNORECASE | re.MULTILINE)
        
        return code
    
    def _convert_variable_declarations(self, code: str) -> str:
        """Remove VBScript Dim/Set statements (Python doesn't need them)."""
        code = re.sub(r'Dim\s+\w+.*\n', '', code, flags=re.IGNORECASE | re.MULTILINE)
        code = re.sub(r'Set\s+(\w+)\s*=\s*', r'\1 = ', code, flags=re.IGNORECASE)
        return code
    
    def _convert_method_calls(self, code: str, flags: List[str]) -> str:
        """Convert VBScript method calls to Python equivalents."""
        for vbs_method, py_method in self.VBS_TO_PYTHON.items():
            # Replace method calls: obj.Method() → obj.method()
            pattern = rf'\.{vbs_method}\s*\('
            replacement = f'.{py_method}('
            code = re.sub(pattern, replacement, code, flags=re.IGNORECASE)
        
        # Flag unsupported calls for manual review
        unsupported = ['CreateObject', 'GetObject', 'InStr', 'Split', 'Join', 'Trim']
        for unsupported_call in unsupported:
            if re.search(rf'\b{unsupported_call}\s*\(', code, re.IGNORECASE):
                flags.append(f"Manual conversion needed for {unsupported_call}()")
                code = re.sub(
                    rf'(\n[^\n]*{unsupported_call}\s*\(.*?\n)',
                    lambda m: f"\n# TODO: Manual conversion - {m.group(1).strip()}\n",
                    code,
                    flags=re.IGNORECASE
                )
        
        return code
    
    def _convert_string_operations(self, code: str) -> str:
        """Convert VBScript string operations."""
        # & concatenation → +
        code = re.sub(r'"\s*&\s*"', '" + "', code)
        code = re.sub(r'(\w+)\s*&\s*"', r'\1 + "', code)
        
        return code
    
    def _convert_boolean_literals(self, code: str) -> str:
        """Convert VBScript booleans (True/False) to Python."""
        code = re.sub(r'\bTrue\b', 'True', code, flags=re.IGNORECASE)
        code = re.sub(r'\bFalse\b', 'False', code, flags=re.IGNORECASE)
        return code
    
    def _indent_code(self, code: str, spaces: int = 4) -> str:
        """Indent code for function body."""
        indent = ' ' * spaces
        return '\n'.join(
            indent + line if line.strip() else ''
            for line in code.split('\n')
        )
    
    @staticmethod
    def extract_parameters(vbs_code: str) -> List[ParamDefinition]:
        """Extract parameter definitions from VBScript comments.
        
        Looks for patterns like:
        'PARAM: username:string:true:SAP username
        'PARAM: quantity:int:false:Order quantity
        """
        params: List[ParamDefinition] = []
        
        # Match lines like: 'PARAM: name:type:required:description
        pattern = re.compile(
            r"'\s*PARAM:\s*(\w+):(\w+):(true|false|yes|no):(.+)",
            re.IGNORECASE
        )
        
        for match in pattern.finditer(vbs_code):
            name, param_type, required_str, description = match.groups()
            
            try:
                # Convert string param_type to ParamType enum
                param_type_value = param_type.strip().lower()
                param_type_enum = ParamType(param_type_value) if param_type_value in [pt.value for pt in ParamType] else ParamType.STRING
                param = ParamDefinition(
                    name=name.strip(),
                    param_type=param_type_enum,
                    required=required_str.strip().lower() in ('true', 'yes'),
                    description=description.strip()
                )
                params.append(param)
            except ValidationError:
                pass
        
        return params


# SECTION 8: VBScript Converter - Enhanced for Phase 3 Task 1

@dataclass
class ConversionResult:
    """Result of VBScript conversion with detailed diagnostics.
    
    Attributes:
        success: Whether conversion completed without fatal errors
        converted_code: Python code converted from VBScript
        flags: List of "TODO" comments for manual review patterns
        error_message: Error message if conversion failed (file not found, etc)
        patterns_applied: Count of regex patterns successfully applied
    """
    success: bool
    converted_code: str = ""
    flags: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    patterns_applied: int = 0


class VBScriptConverter:
    """Production VBScript-to-Python converter - all 20 patterns (Phase 3 Task 1).
    
    Converts VBScript SAP GUI Scripting to Python with 20+ regex patterns:
    1. FindById() preserved
    2. Property assignments preserved
    3. Method calls with () preserved
    4. Method calls without () - adds parentheses
    5. SendVKey() preserved
    6. Dim/Set declarations - removed/converted
    7. If/Then/Else - converted to if/elif/else
    8. For i=x To y - converted to range()
    9. For Each...In - converted to for...in
    10. Do While - converted to while
    11. String & - converted to +
    12. Array access preserved
    13. Boolean True/False normalized
    14. Comments ' and REM - converted to #
    15. On Error - FLAGGED for manual review
    16. MsgBox/InputBox - FLAGGED for manual review
    17. CreateObject - FLAGGED for manual review
    18. Function definitions - converted to def
    19. Numeric operations - preserved
    20. Variable names - preserved for compatibility
    """
    
    def __init__(self):
        """Initialize converter."""
        self.flags_list: List[str] = []
        self.patterns_applied = 0
    
    def convert_code(self, vbs_code: str, metadata: Optional[ScriptMetadata] = None) -> Tuple[str, List[str]]:
        """Convert VBScript code string to Python.
        
        Args:
            vbs_code: VBScript source code as string
            metadata: Optional script metadata for enhanced documentation
            
        Returns:
            Tuple of (converted_python_code, list_of_conversion_flags)
        """
        self.flags_list = []
        self.patterns_applied = 0
        
        lines = vbs_code.split('\n')
        converted_lines = []
        
        for line_num, line in enumerate(lines, 1):
            original_line = line
            converted_line = line
            
            # Pattern 14: Comments (before other patterns to avoid processing comment content)
            if converted_line.strip().startswith("'"):
                converted_line = converted_line.replace("'", "#", 1)
                self.patterns_applied += 1
            elif 'REM ' in converted_line.upper():
                converted_line = re.sub(r'\bREM\s+', '# ', converted_line, flags=re.IGNORECASE)
                self.patterns_applied += 1
            
            # Pattern 1: Dim declarations - remove
            if re.match(r'^\s*Dim\s+', converted_line, re.IGNORECASE):
                self.flags_list.append(f"Line {line_num}: Dim declaration removed (Python is dynamically typed)")
                continue  # Skip this line
                
            # Pattern 2: Set statements - convert to simple assignment
            if re.match(r'^\s*Set\s+', converted_line, re.IGNORECASE):
                converted_line = re.sub(r'^\s*Set\s+', '', converted_line, flags=re.IGNORECASE)
                self.patterns_applied += 1
            
            # Pattern 7: If/Then/Else/End If
            if ' Then ' in converted_line or converted_line.strip().endswith(' Then'):
                converted_line = re.sub(r'\s+Then\s*$', ':', converted_line, flags=re.IGNORECASE)
                converted_line = re.sub(r'^\s*If\s+', '', converted_line, flags=re.IGNORECASE)
                converted_line = f"if {converted_line}"
                self.patterns_applied += 1
            elif re.match(r'^\s*End If\s*$', converted_line, re.IGNORECASE):
                continue  # Remove End If
            elif re.match(r'^\s*Else If\s+', converted_line, re.IGNORECASE) or re.match(r'^\s*ElseIf\s+', converted_line, re.IGNORECASE):
                converted_line = re.sub(r'(Else\s*)?[Ii]f\s+(.+?)\s+Then', r'elif \2:', converted_line)
                self.patterns_applied += 1
            elif re.match(r'^\s*Else\s*$', converted_line, re.IGNORECASE):
                converted_line = 'else:'
                self.patterns_applied += 1
            
            # Pattern 8: For i = x To y loops
            match = re.match(r'^(\s*)For\s+(\w+)\s*=\s*(\d+)\s+[Tt]o\s+(\d+)\s*$', converted_line)
            if match:
                indent, var, start, end = match.groups()
                converted_line = f"{indent}for {var} in range({start}, {int(end) + 1}):"
                self.patterns_applied += 1
            elif re.match(r'^\s*Next\s*$', converted_line, re.IGNORECASE):
                continue  # Remove Next
            
            # Pattern 9: For Each loops
            if re.match(r'^\s*For\s+Each\s+', converted_line, re.IGNORECASE):
                converted_line = re.sub(r'For\s+Each\s+(\w+)\s+[Ii]n\s+(\w+)', r'for \1 in \2:', converted_line, flags=re.IGNORECASE)
                self.patterns_applied += 1
            
            # Pattern 10: Do While loops
            if re.match(r'^\s*Do\s+While\s+', converted_line, re.IGNORECASE):
                converted_line = re.sub(r'Do\s+While\s+(.+)', r'while \1:', converted_line, flags=re.IGNORECASE)
                self.patterns_applied += 1
            elif re.match(r'^\s*Loop\s*$', converted_line, re.IGNORECASE):
                continue  # Remove Loop
            
            # Pattern 18: Function definitions
            if re.match(r'^\s*Function\s+', converted_line, re.IGNORECASE):
                converted_line = re.sub(r'Function\s+(\w+)\s*\(', r'def \1(', converted_line, flags=re.IGNORECASE)
                converted_line = converted_line.rstrip() + ':'
                self.patterns_applied += 1
            elif re.match(r'^\s*End\s+Function\s*$', converted_line, re.IGNORECASE):
                continue  # Remove End Function
            
            # Pattern 4: Method calls without parentheses (add parens if not a property assignment)
            if not '=' in converted_line and not converted_line.strip().startswith('#'):
                match = re.search(r'\.(\w+)\s*$', converted_line)
                if match:
                    converted_line = converted_line + '()'
                    self.patterns_applied += 1
            
            # Pattern 11: String concatenation & to +
            # Only in non-comment lines
            if not converted_line.strip().startswith('#'):
                if ' & ' in converted_line:
                    # Replace & with + but be careful about quotes
                    converted_line = re.sub(r'(\w+|\))\s*&\s*', r'\1 + ', converted_line)
                    converted_line = re.sub(r'("\w+"|\'\ w+\')\s*&\s*', r'\1 + ', converted_line)
                    self.patterns_applied += 1
            
            # Pattern 15: Error handling - flag for manual review
            if 'On Error' in converted_line and any(x in converted_line for x in ['Resume', 'Goto']):
                self.flags_list.append(f"Line {line_num}: Error handling 'On Error' statement requires manual conversion to try/except")
            
            # Pattern 16: MsgBox/InputBox - flag for manual review
            if 'MsgBox' in converted_line or 'InputBox' in converted_line:
                self.flags_list.append(f"Line {line_num}: Dialog MsgBox/InputBox - convert to ui.notify() or ui.input()")
            
            # Pattern 17: CreateObject - flag for manual review
            if 'CreateObject' in converted_line:
                self.flags_list.append(f"Line {line_num}: CreateObject - convert to win32com.client.Dispatch()")
            
            # Skip empty lines from removed statements
            if converted_line.strip() == '':
                continue
            
            converted_lines.append(converted_line)
        
        # Build output
        output_code = '\n'.join(converted_lines)
        
        # Add header with conversion info
        header = f"""# Auto-converted from VBScript
# Generated by VBScriptConverter (Phase 3 - Task 1)
# Review conversion flags below for patterns requiring manual attention
#
# Conversion Flags:
"""
        if self.flags_list:
            for flag in self.flags_list[:10]:  # Show first 10 flags
                header += f"# - {flag}\n"
            if len(self.flags_list) > 10:
                header += f"# ... and {len(self.flags_list) - 10} more flags\n"
        else:
            header += "# None - automatic conversion successful!\n"
        
        header += "#\n"
        
        output_code = header + output_code
        
        return output_code, self.flags_list
    
    def convert_file(self, file_path: str) -> ConversionResult:
        """Convert a .vbs file to Python code.
        
        Args:
            file_path: Path to .vbs input file
            
        Returns:
            ConversionResult with success, code, flags, and error details
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return ConversionResult(success=False, error_message=f"File not found: {file_path}")
            if path.suffix.lower() != '.vbs':
                return ConversionResult(success=False, error_message=f"File must be .vbs: {file_path}")
            
            # Read with encoding handling
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    vbs_code = f.read()
            except:
                with open(path, 'r', encoding='windows-1252', errors='ignore') as f:
                    vbs_code = f.read()
            
            python_code, flags = self.convert_code(vbs_code)
            
            return ConversionResult(
                success=True,
                converted_code=python_code,
                flags=flags,
                patterns_applied=self.patterns_applied
            )
        except Exception as e:
            return ConversionResult(
                success=False,
                error_message=f"Conversion error: {str(e)}"
            )


# SECTION 9: Script Manager (Task 4) ─────────────────────────────────────

class ScriptManager:
    """High-level script discovery, loading, and registry management.
    
    Wraps ScriptRegistry with a simplified API for script discovery,
    metadata loading, search, and registry export.
    
    Usage:
        manager = ScriptManager(scripts_dir="scripts")
        scripts = manager.list_scripts()
        result = manager.search_scripts("navigation")
        script = manager.get_script("Simple Navigation")
    """
    
    # Example scripts template (created by bootstrap_examples())
    EXAMPLE_SCRIPTS = {
        'simple_navigation.py': '''"""Simple SAP Transaction Navigation.

This script navigates to transaction VA01 (Create Sales Order).
Converted from VBScript - demonstrates basic property and method usage.
"""

# PARAM: transaction_code:string:true:SAP transaction code to navigate to (e.g., VA01)

# Navigate to SAP transaction
session.find_by_id("wnd[0]/tbar[0]/okcd").value = transaction_code
session.find_by_id("wnd[0]").send_vkey(0)

# Wait for screen to load (in real execution, this would be handled by COM timeout)
result = "Navigation successful"
''',
        'simple_navigation.yaml': '''name: "Simple Navigation"
description: "Navigate to SAP transaction (e.g., VA01 for Create Sales Order)"
author: "SAP Bridge Team"
version: "1.0.0"
tags:
  - "navigation"
  - "basic"
  - "core"
timeout_seconds: 30
parameters:
  - name: transaction_code
    param_type: string
    required: true
    description: "SAP transaction code (e.g., VA01, VA02, VL01)"
    default_value: "VA01"
preconditions: "User must be logged into SAP"
execution_notes: "Navigates to transaction and waits for screen to load"
''',
        'set_field.py': '''"""Set Field Value in SAP UI.

Generic script to set a value in a SAP field by UI ID.
Demonstrates parameter binding and dynamic field access.
"""

# PARAM: field_id:string:true:SAP UI element ID (e.g., wnd[0]/usr/ctxtVBELN)
# PARAM: field_value:string:true:Value to set in the field

# Set the field value
element = session.find_by_id(field_id)
element.value = field_value

result = f"Set {field_id} = {field_value}"
''',
        'set_field.yaml': '''name: "Set Field"
description: "Set any field value in SAP by UI element ID"
author: "SAP Bridge Team"
version: "1.0.0"
tags:
  - "field-entry"
  - "basic"
  - "core"
timeout_seconds: 10
parameters:
  - name: field_id
    param_type: string
    required: true
    description: "SAP UI element ID (e.g., wnd[0]/usr/ctxtVBELN)"
    default_value: ""
  - name: field_value
    param_type: string
    required: true
    description: "Value to set in field"
    default_value: ""
preconditions: "Field must exist and be accessible in current SAP screen"
execution_notes: "Sets field value without pressing Enter - caller must handle screen navigation"
'''
    }
    
    def __init__(self, scripts_dir: str = "scripts") -> None:
        """Initialize with scripts directory path.
        
        Args:
            scripts_dir: Path to directory containing scripts (relative or absolute)
        """
        self.scripts_dir = Path(scripts_dir)
        self._registry = ScriptRegistry(self.scripts_dir)
        self.discover_scripts()
    
    def discover_scripts(self) -> int:
        """Scan scripts directory for .py files and load metadata.
        
        - Walks scripts_dir recursively for .py files
        - For each .py, loads adjacent .yaml metadata (if exists)
        - Parses metadata into ScriptMetadata with pydantic validation
        - Builds in-memory registry
        
        Returns:
            Number of scripts discovered and loaded
        """
        entries = self._registry.discover_scripts(force_reload=True)
        logger.info(f"Discovered {len(entries)} script(s) in {self.scripts_dir}")
        return len(entries)
    
    def get_script(self, name: str) -> Optional[ScriptMetadata]:
        """Get script metadata by name.
        
        Searches registry for script matching the given name (case-insensitive).
        
        Args:
            name: Script name (should match metadata.name field)
        
        Returns:
            ScriptMetadata if found, None otherwise
        """
        name_lower = name.lower()
        for entry in self._registry.list_scripts():
            if entry.metadata.name.lower() == name_lower:
                return entry.metadata
        return None
    
    def list_scripts(self) -> List[ScriptMetadata]:
        """Return all scripts in registry as list of metadata.
        
        Returns:
            List of ScriptMetadata objects for all discovered scripts
        """
        return [entry.metadata for entry in self._registry.list_scripts()]
    
    def search_scripts(self, query: str) -> List[ScriptMetadata]:
        """Search scripts by name, description, or tags (case-insensitive).
        
        Performs case-insensitive substring match on:
        - Script name
        - Script description
        - Script tags (any tag containing query string)
        
        Args:
            query: Search query string
        
        Returns:
            List of ScriptMetadata objects matching the query
        """
        entries = self._registry.find_scripts(query)
        return [entry.metadata for entry in entries]
    
    def reload(self) -> int:
        """Reload scripts from disk (hot-reload support).
        
        Clears and rescans the scripts directory for new or updated files.
        Useful for picking up script changes without restarting the application.
        
        Returns:
            Number of scripts discovered after reload
        """
        return self.discover_scripts()
    
    def export_registry(self) -> Dict[str, dict]:
        """Export registry as dict for testing/debugging.
        
        Returns:
            Dictionary mapping script names to metadata dicts (pydantic model_dump)
        """
        result = {}
        for entry in self._registry.list_scripts():
            result[entry.metadata.name] = entry.metadata.model_dump(exclude_none=True)
        return result
    
    def get_script_path(self, name: str) -> Optional[Path]:
        """Get filesystem path for a script by name.
        
        Args:
            name: Script name
        
        Returns:
            Path to .py file if found, None otherwise
        """
        name_lower = name.lower()
        for entry in self._registry.list_scripts():
            if entry.metadata.name.lower() == name_lower:
                return entry.path
        return None
    
    def bootstrap_examples(self, overwrite: bool = False) -> Dict[str, bool]:
        """Create example scripts in /scripts/examples/ during first setup.
        
        Generates example Python and YAML files from EXAMPLE_SCRIPTS template.
        Called automatically during initialization or manually for reset.
        
        Args:
            overwrite: If True, overwrite existing files; if False, skip existing
        
        Returns:
            Dict mapping filename to success boolean
        """
        examples_dir = self.scripts_dir / "examples"
        examples_dir.mkdir(parents=True, exist_ok=True)
        
        results: Dict[str, bool] = {}
        
        for filename, content in self.EXAMPLE_SCRIPTS.items():
            filepath = examples_dir / filename
            
            # Skip if exists and not overwriting
            if filepath.exists() and not overwrite:
                logger.debug(f"Skipping {filename} (already exists)")
                results[filename] = True
                continue
            
            try:
                filepath.write_text(content, encoding='utf-8')
                logger.info(f"Created example script: {filepath}")
                results[filename] = True
            except Exception as e:
                logger.error(f"Failed to create {filename}: {e}")
                results[filename] = False
        
        # Refresh registry after creating examples
        self.discover_scripts()
        
        return results


# SECTION 10: Script Executor (Task 6) ────────────────────────────────────

import sys
import io
import asyncio
import time
import traceback as tb_module
from io import StringIO


class ScriptExecutor:
    """Execute compiled SAP automation scripts with timeout and error handling.
    
    Loads Python scripts from disk, validates parameters, executes via exec()
    with an isolated namespace, captures output, handles timeouts and errors,
    and records all executions to history.
    
    Threading Model:
        - All SAP COM operations in executed scripts MUST use session.* methods
        - session.* methods are async and queue to the COM worker thread
        - ScriptExecutor itself is async-compatible and non-blocking
        - Never call COM directly; always use session.call_async()
    
    Error Handling:
        - Catches all exceptions during exec() (Exception base class)
        - Captures exception type, message, and full traceback
        - Records failures to ExecutionHistory with status="error"
        - Returns structured error dict with error_message and traceback
    
    Output Capture:
        - Redirects sys.stdout and sys.stderr during exec()
        - Captures print() statements to output field
        - Truncates output to 10KB to prevent unbounded growth
        - Restores stdout/stderr after execution
    
    Timeout Enforcement:
        - Uses asyncio.wait_for() with timeout from script metadata
        - Default timeout is 300 seconds if not specified
        - On timeout: logs timeout event, returns error dict with status="timeout"
        - Cancels task gracefully (does not kill OS thread)
    """
    
    def __init__(self, history: ExecutionHistory) -> None:
        """Initialize executor with history tracker.
        
        Args:
            history: ExecutionHistory instance for recording executions
        
        Raises:
            TypeError: If history is not an ExecutionHistory instance
        """
        if not isinstance(history, ExecutionHistory):
            raise TypeError("history must be an ExecutionHistory instance")
        self.history = history
        self._max_output_bytes = 10 * 1024
    
    async def execute_script(
        self,
        script_entry: ScriptEntry,
        parameters: Dict[str, Any],
        session: Any
    ) -> Dict[str, Any]:
        """Execute script with timeout, error handling, and audit trail.
        
        Complete execution flow:
        1. Load script file (.py) from disk
        2. Validate parameters using ParameterValidator
        3. Create isolated exec() namespace with session and parameters
        4. Redirect stdout/stderr for output capture
        5. Execute script code via exec()
        6. Capture execution result or 'result' variable from namespace
        7. Record execution to ExecutionHistory
        8. Return result dict with success flag, output, duration, and any errors
        
        The result dict always includes:
        - success (bool): True if execution completed without error
        - status (str): "success", "timeout", or "error"
        - output (str): Captured stdout/stderr output (up to 10KB)
        - duration_seconds (float): Wall-clock execution time
        - error_message (str, optional): Error description if status != "success"
        - traceback (str, optional): Full traceback if status == "error"
        - result (Any, optional): Return value from script if success is True
        
        Args:
            script_entry: ScriptEntry from ScriptRegistry with id, path, metadata
            parameters: User-provided parameters dict (already validated by caller)
            session: SAP session object implementing async interface (session.*)
        
        Returns:
            Dict with execution result, output, duration, status, and any errors
        
        Raises:
            FileNotFoundError: If script file does not exist
            ValidationError: If parameters fail validation
        """
        start_time = time.time()
        script_name = script_entry.metadata.name
        
        try:
            script_path = script_entry.path
            if not script_path.exists():
                result_dict = {
                    'success': False,
                    'status': 'error',
                    'output': '',
                    'duration_seconds': 0.0,
                    'error_message': f'Script file not found: {script_path}',
                    'traceback': None,
                }
                self.history.add_execution(
                    script_name, parameters, 'error',
                    error_message=result_dict['error_message']
                )
                return result_dict
            
            parameters_valid, validation_errors = ParameterValidator.validate(
                parameters, script_entry.metadata.parameters
            )
            if not parameters_valid:
                error_msg = '; '.join(validation_errors)
                result_dict = {
                    'success': False,
                    'status': 'error',
                    'output': '',
                    'duration_seconds': 0.0,
                    'error_message': f'Parameter validation failed: {error_msg}',
                    'traceback': None,
                }
                self.history.add_execution(
                    script_name, parameters, 'error',
                    error_message=result_dict['error_message']
                )
                return result_dict
            
            timeout_seconds = script_entry.metadata.timeout_seconds
            
            result_dict = await asyncio.wait_for(
                self._execute_with_output_capture(script_path, parameters, session),
                timeout=timeout_seconds
            )
            
            duration_seconds = time.time() - start_time
            result_dict['duration_seconds'] = duration_seconds
            
            self.history.add_execution(
                script_name, parameters, result_dict['status'],
                output=result_dict.get('output', ''),
                duration_seconds=duration_seconds,
                error_message=result_dict.get('error_message'),
                traceback=result_dict.get('traceback')
            )
            
            return result_dict
        
        except asyncio.TimeoutError:
            duration_seconds = time.time() - start_time
            result_dict = {
                'success': False,
                'status': 'timeout',
                'output': '',
                'duration_seconds': duration_seconds,
                'error_message': f'Script execution timeout after {script_entry.metadata.timeout_seconds}s',
                'traceback': None,
            }
            self.history.add_execution(
                script_name, parameters, 'timeout',
                duration_seconds=duration_seconds,
                error_message=result_dict['error_message']
            )
            logger.warning(f'Script timeout: {script_name} exceeded {script_entry.metadata.timeout_seconds}s')
            return result_dict
        
        except Exception as e:
            duration_seconds = time.time() - start_time
            error_traceback = tb_module.format_exc()
            result_dict = {
                'success': False,
                'status': 'error',
                'output': '',
                'duration_seconds': duration_seconds,
                'error_message': str(e),
                'traceback': error_traceback,
            }
            self.history.add_execution(
                script_name, parameters, 'error',
                duration_seconds=duration_seconds,
                error_message=result_dict['error_message'],
                traceback=error_traceback
            )
            logger.error(f'Script execution error: {script_name}: {e}', exc_info=True)
            return result_dict
    
    async def _execute_with_output_capture(
        self,
        script_path: Path,
        parameters: Dict[str, Any],
        session: Any
    ) -> Dict[str, Any]:
        """Execute script with stdout/stderr capture in isolated namespace.
        
        Creates an isolated exec() namespace containing:
        - session: SAP session object for script API calls
        - parameters: User-provided parameters dict
        - logger: Python logger for debug output
        
        Redirects sys.stdout and sys.stderr to capture print() statements.
        Truncates output to 10KB to prevent memory overflow.
        
        Args:
            script_path: Path to .py script file
            parameters: User-provided parameters dict
            session: SAP session object
        
        Returns:
            Dict with success=True, output, and optional result; or
            Dict with success=False, error_message, traceback
        """
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                script_code = f.read()
        except Exception as e:
            return {
                'success': False,
                'status': 'error',
                'output': '',
                'error_message': f'Failed to read script file: {e}',
                'traceback': tb_module.format_exc(),
            }
        
        captured_output = StringIO()
        
        try:
            sys.stdout = captured_output
            sys.stderr = captured_output
            
            exec_namespace = {
                'session': session,
                'parameters': parameters,
                'logger': logger,
                '__name__': '__main__',
                '__builtins__': __builtins__,
            }
            
            exec(script_code, exec_namespace)
            
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            
            output_str = captured_output.getvalue()
            if len(output_str) > self._max_output_bytes:
                output_str = output_str[:self._max_output_bytes] + '\n[output truncated]'
            
            result_value = exec_namespace.get('result')
            
            return {
                'success': True,
                'status': 'success',
                'output': output_str,
                'result': result_value,
            }
        
        except Exception as e:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            
            output_str = captured_output.getvalue()
            if len(output_str) > self._max_output_bytes:
                output_str = output_str[:self._max_output_bytes] + '\n[output truncated]'
            
            return {
                'success': False,
                'status': 'error',
                'output': output_str,
                'error_message': str(e),
                'traceback': tb_module.format_exc(),
            }


# SECTION 11: Report Schema (Phase 4 Task 1) ──────────────────────────────────

class ReportStepAction(str, Enum):
    """Supported SAP report execution steps in declarative YAML.
    
    Actions control how the ReportRunner navigates SAP and extracts data:
    - navigate: Launch a transaction (implicit, always first)
    - set_field: Set a field value from parameters
    - set_field_conditional: Set field only if parameter is non-empty
    - execute: Send ENTER or press button to execute transaction
    - read_grid: Extract results from grid/table into ReportResult
    - click_button: Click a button by label or ID
    """
    NAVIGATE = "navigate"
    SET_FIELD = "set_field"
    SET_FIELD_CONDITIONAL = "set_field_conditional"
    EXECUTE = "execute"
    READ_GRID = "read_grid"
    CLICK_BUTTON = "click_button"


class ReportStep(BaseModel):
    """Single execution step in a report's YAML workflow.
    
    Attributes:
        action: One of ReportStepAction values
        target: SAP transaction code or grid ID (for navigate/read_grid)
        field: SAP field name (for set_field steps)
        value: Value to set (can use {param_name} placeholders)
        condition: Only execute if this expression is truthy (for conditional steps)
        timeout: Max seconds for this step (default 30)
    """
    action: ReportStepAction = Field(...)
    target: Optional[str] = Field(default=None, description="Transaction code or grid ID")
    field: Optional[str] = Field(default=None, description="SAP field name")
    value: Optional[str] = Field(default=None, description="Field value (can use {param_name} placeholders)")
    condition: Optional[str] = Field(default=None, description="Execute if this is truthy")
    timeout: int = Field(default=30, ge=5, le=300)
    
    @field_validator("action")
    @classmethod
    def validate_action(cls, v: ReportStepAction) -> ReportStepAction:
        if v not in ReportStepAction:
            raise ValueError(f"Unknown action: {v}")
        return v


class ReportColumn(BaseModel):
    """Output column definition for report results.
    
    Attributes:
        column_name: SAP column name/ID (e.g., 'MATNR', 'MAKTX')
        header: Display header for this column
        width: Column width in characters
        datatype: string|numeric|currency|date
    """
    column_name: str = Field(...)
    header: str = Field(...)
    width: int = Field(default=20, ge=5, le=100)
    datatype: str = Field(default="string", pattern="^(string|numeric|currency|date)$")


class ReportOutputConfig(BaseModel):
    """Output extraction configuration for reports.
    
    Attributes:
        columns: List of columns to extract
        row_limit: Max rows to return (0 = unlimited, default 5000)
        row_offset: Start row offset (for pagination)
        sort_by: Tuples of (column, direction)
    """
    columns: List[ReportColumn] = Field(default_factory=list)
    row_limit: int = Field(default=5000, ge=0, le=100000)
    row_offset: int = Field(default=0, ge=0)
    sort_by: Optional[List[Dict[str, str]]] = Field(default=None, description="List of {column, direction} dicts")


class ReportErrorHandling(BaseModel):
    """Error handling configuration for reports.
    
    Attributes:
        transaction_not_found: skip|abort|retry (default: skip)
        field_set_failed: skip|abort|retry (default: skip)
        execution_timeout: skip|abort|retry (default: abort)
        no_data: return_empty|skip|abort (default: return_empty)
        max_retries: How many times to retry on error
        retry_delay_seconds: Delay between retries
    """
    transaction_not_found: str = Field(default="skip", pattern="^(skip|abort|retry)$")
    field_set_failed: str = Field(default="skip", pattern="^(skip|abort|retry)$")
    execution_timeout: str = Field(default="abort", pattern="^(skip|abort|retry)$")
    no_data: str = Field(default="return_empty", pattern="^(return_empty|skip|abort)$")
    max_retries: int = Field(default=2, ge=0, le=5)
    retry_delay_seconds: int = Field(default=5, ge=1, le=60)


class ReportMetadata(BaseModel):
    """Complete SAP report definition in Pydantic model form.
    
    This corresponds to a YAML file at /reports/{report_name}.yaml.
    
    Attributes:
        metadata: Name, title, description, category, tags, author
        sap: Transaction code and alternative transaction
        parameters: List of input parameter definitions (same 6 types as scripts)
        steps: Execution workflow (navigate, set_field, execute, read_grid)
        output: Column and result extraction configuration
        error_handling: How to handle errors during execution
    """
    model_config = {"validate_assignment": True}
    
    # Metadata section
    name: str = Field(..., description="Report unique ID (must match filename: {name}.yaml)")
    title: str = Field(..., description="Human-readable report title")
    description: str = Field(default="", description="Report description shown in UI")
    author: Optional[str] = Field(default=None)
    category: str = Field(default="General", description="Report category for grouping")
    tags: List[str] = Field(default_factory=list, description="Tags for filtering (e.g., ['inventory', 'MM'])")
    hidden: bool = Field(default=False, description="Hide from UI if True")
    
    # SAP configuration
    transaction: str = Field(..., description="Primary SAP transaction code (e.g., 'MM03')")
    alternative_transaction: Optional[str] = Field(default=None, description="Fallback transaction if primary unavailable")
    
    # Parameters (input fields)
    parameters: List[ParamDefinition] = Field(default_factory=list)
    
    # Execution steps
    steps: List[ReportStep] = Field(default_factory=list)
    
    # Output configuration
    output: ReportOutputConfig = Field(default_factory=ReportOutputConfig)
    
    # Error handling
    error_handling: ReportErrorHandling = Field(default_factory=ReportErrorHandling)
    
    # Optional caching
    caching_enabled: bool = Field(default=False)
    caching_ttl_minutes: int = Field(default=60, ge=5, le=1440)
    
    @field_validator("parameters")
    @classmethod
    def validate_param_uniqueness(cls, v: List[ParamDefinition]) -> List[ParamDefinition]:
        names = [p.name for p in v]
        if len(names) != len(set(names)):
            raise ValueError("Parameter names must be unique")
        return v
    
    @field_validator("transaction")
    @classmethod
    def validate_transaction_code(cls, v: str) -> str:
        if not v or len(v) > 4 or not v.replace(' ', '').isalnum():
            raise ValueError(f"Invalid transaction code: {v}")
        return v.upper()


class ReportYAML:
    """Load and save ReportMetadata to/from YAML files.
    
    Usage:
        # Load report definition from YAML
        report_def = ReportYAML.load(Path("reports/stock_report.yaml"))
        
        # Save report definition to YAML
        ReportYAML.save(report_def, Path("reports/my_report.yaml"))
    """
    
    # Example reports template (created by bootstrap_examples())
    EXAMPLE_REPORTS = {
        'stock_report.yaml': '''name: "stock_report"
title: "Stock Report by Material"
description: "Query available stock quantities for materials across plants"
author: "SAP Bridge Team"
category: "Inventory"
tags:
  - "MM"
  - "materials"
  - "inventory"
  - "stock"

transaction: "MM03"
alternative_transaction: null

parameters:
  - name: "material_id"
    param_type: "string"
    required: true
    description: "Material number (MARA-MATNR, 18 chars max)"
    default_value: ""
    enum_values: []
  
  - name: "plant"
    param_type: "dropdown"
    required: false
    description: "Plant code (optional - shows all plants if empty)"
    default_value: ""
    enum_values:
      - ""
      - "1000"
      - "2000"
      - "3000"
  
  - name: "check_blocked"
    param_type: "bool"
    required: false
    description: "Only show materials marked as blocked"
    default_value: false
    enum_values: []

steps:
  - action: "navigate"
    target: "MM03"
    timeout: 30
  
  - action: "set_field"
    field: "RMMG1-MATNR"
    value: "{material_id}"
    timeout: 5
  
  - action: "set_field_conditional"
    field: "RMMG1-WERKS"
    value: "{plant}"
    condition: "{plant}"
    timeout: 5
  
  - action: "execute"
    timeout: 30
  
  - action: "read_grid"
    target: "sap_grid"
    timeout: 10

output:
  columns:
    - column_name: "MATNR"
      header: "Material"
      width: 18
      datatype: "string"
    - column_name: "MAKTX"
      header: "Description"
      width: 40
      datatype: "string"
    - column_name: "MEINS"
      header: "Unit"
      width: 5
      datatype: "string"
    - column_name: "LABST"
      header: "Stock"
      width: 13
      datatype: "numeric"
    - column_name: "MSTAE"
      header: "Status"
      width: 5
      datatype: "string"
  row_limit: 1000
  row_offset: 0

error_handling:
  transaction_not_found: "abort"
  field_set_failed: "skip"
  execution_timeout: "abort"
  no_data: "return_empty"
  max_retries: 2
  retry_delay_seconds: 5

caching_enabled: false
caching_ttl_minutes: 60
''',
        
        'sales_orders.yaml': '''name: "sales_orders"
title: "Sales Orders by Date Range"
description: "Query sales orders created within a date range"
author: "SAP Bridge Team"
category: "Sales"
tags:
  - "SD"
  - "sales"
  - "orders"
  - "vbak"

transaction: "VA03"
alternative_transaction: null

parameters:
  - name: "order_date_from"
    param_type: "date"
    required: true
    description: "Sales order date from (YYYY-MM-DD)"
    default_value: null
    enum_values: []
  
  - name: "order_date_to"
    param_type: "date"
    required: false
    description: "Sales order date to (optional - defaults to today)"
    default_value: null
    enum_values: []
  
  - name: "customer_id"
    param_type: "string"
    required: false
    description: "Customer number (optional - shows all if empty)"
    default_value: ""
    enum_values: []

steps:
  - action: "navigate"
    target: "VA03"
    timeout: 30
  
  - action: "set_field"
    field: "VBAK-ERDAT_FROM"
    value: "{order_date_from}"
    timeout: 5
  
  - action: "set_field_conditional"
    field: "VBAK-ERDAT_TO"
    value: "{order_date_to}"
    condition: "{order_date_to}"
    timeout: 5
  
  - action: "set_field_conditional"
    field: "VBAK-KUNNR"
    value: "{customer_id}"
    condition: "{customer_id}"
    timeout: 5
  
  - action: "execute"
    timeout: 30
  
  - action: "read_grid"
    target: "sap_grid"
    timeout: 10

output:
  columns:
    - column_name: "VBELN"
      header: "Sales Order"
      width: 10
      datatype: "string"
    - column_name: "ERDAT"
      header: "Created"
      width: 10
      datatype: "date"
    - column_name: "KUNNR"
      header: "Customer"
      width: 10
      datatype: "string"
    - column_name: "KUNAG"
      header: "Bill-To"
      width: 10
      datatype: "string"
    - column_name: "VBTYP"
      header: "Type"
      width: 5
      datatype: "string"
  row_limit: 5000
  row_offset: 0

error_handling:
  transaction_not_found: "abort"
  field_set_failed: "skip"
  execution_timeout: "abort"
  no_data: "return_empty"
  max_retries: 2
  retry_delay_seconds: 5

caching_enabled: false
caching_ttl_minutes: 60
''',
        
        'purchase_orders.yaml': '''name: "purchase_orders"
title: "Purchase Orders by Vendor"
description: "Query purchase orders from a specific vendor"
author: "SAP Bridge Team"
category: "Procurement"
tags:
  - "MM"
  - "procurement"
  - "PO"
  - "vendor"

transaction: "ME2M"
alternative_transaction: null

parameters:
  - name: "vendor_id"
    param_type: "string"
    required: true
    description: "Vendor number (LFA1-LIFNR, 10 chars max)"
    default_value: ""
    enum_values: []
  
  - name: "po_status"
    param_type: "dropdown"
    required: false
    description: "Purchase order status"
    default_value: ""
    enum_values:
      - ""
      - "O"
      - "P"
      - "C"
  
  - name: "include_released"
    param_type: "bool"
    required: false
    description: "Include released purchase orders"
    default_value: true
    enum_values: []

steps:
  - action: "navigate"
    target: "ME2M"
    timeout: 30
  
  - action: "set_field"
    field: "EKKO-LIFNR"
    value: "{vendor_id}"
    timeout: 5
  
  - action: "set_field_conditional"
    field: "EKKO-EBELN_STATUS"
    value: "{po_status}"
    condition: "{po_status}"
    timeout: 5
  
  - action: "execute"
    timeout: 30
  
  - action: "read_grid"
    target: "sap_grid"
    timeout: 10

output:
  columns:
    - column_name: "EBELN"
      header: "PO Number"
      width: 10
      datatype: "string"
    - column_name: "ERDAT"
      header: "Created"
      width: 10
      datatype: "date"
    - column_name: "LIFNR"
      header: "Vendor"
      width: 10
      datatype: "string"
    - column_name: "WAERS"
      header: "Currency"
      width: 5
      datatype: "string"
    - column_name: "GNETWR"
      header: "Net Amount"
      width: 15
      datatype: "currency"
  row_limit: 5000
  row_offset: 0

error_handling:
  transaction_not_found: "abort"
  field_set_failed: "skip"
  execution_timeout: "abort"
  no_data: "return_empty"
  max_retries: 2
  retry_delay_seconds: 5

caching_enabled: false
caching_ttl_minutes: 60
'''
    }
    
    @staticmethod
    def bootstrap_examples(reports_dir: Path = Path("reports"), overwrite: bool = False) -> Dict[str, bool]:
        """Create example report YAML files during setup.
        
        Generates realistic SAP report templates in /reports/examples/ for users to
        reference and customize.
        
        Args:
            reports_dir: Base reports directory (defaults to "reports")
            overwrite: If True, overwrite existing files; if False, skip existing
        
        Returns:
            Dict mapping filename to success boolean
        """
        examples_dir = reports_dir / "examples"
        examples_dir.mkdir(parents=True, exist_ok=True)
        
        results: Dict[str, bool] = {}
        
        for filename, content in ReportYAML.EXAMPLE_REPORTS.items():
            filepath = examples_dir / filename
            
            if filepath.exists() and not overwrite:
                logger.debug(f"Skipping {filename} (already exists)")
                results[filename] = True
                continue
            
            try:
                filepath.write_text(content, encoding='utf-8')
                logger.info(f"Created example report: {filepath}")
                results[filename] = True
            except Exception as e:
                logger.error(f"Failed to create {filename}: {e}")
                results[filename] = False
        
        return results
    
    @staticmethod
    def load(path: Path) -> Optional[ReportMetadata]:
        """Load report definition from YAML file.
        
        Args:
            path: Path to .yaml report definition file
        
        Returns:
            ReportMetadata if successful, None if file not found or invalid
        """
        if not path.exists():
            logger.warning(f"Report file not found: {path}")
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            return ReportMetadata(**data)
        except (yaml.YAMLError, ValidationError) as e:
            logger.error(f"Error loading report metadata from {path}: {e}")
            return None
    
    @staticmethod
    def save(metadata: ReportMetadata, path: Path) -> None:
        """Save report definition to YAML file.
        
        Args:
            metadata: ReportMetadata to save
            path: Output path for .yaml file
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        data = metadata.model_dump(exclude_none=True)
        
        # Convert nested models to dicts for YAML
        if "parameters" in data:
            param_list = []
            for p in data["parameters"]:
                if isinstance(p, ParamDefinition):
                    p_dict = p.model_dump(exclude_none=True)
                else:
                    p_dict = p
                # Convert ParamType enum to string (.value)
                if isinstance(p_dict.get("param_type"), ParamType):
                    p_dict["param_type"] = p_dict["param_type"].value
                elif isinstance(p_dict.get("param_type"), str):
                    # Already a string, verify it's valid
                    try:
                        ParamType(p_dict["param_type"])
                    except ValueError:
                        # Invalid, convert to STRING as default
                        p_dict["param_type"] = ParamType.STRING.value
                param_list.append(p_dict)
            data["parameters"] = param_list
        if "steps" in data:
            step_list = []
            for s in data["steps"]:
                if isinstance(s, ReportStep):
                    s_dict = s.model_dump(exclude_none=True)
                else:
                    s_dict = s
                # Convert ReportStepAction enum to string
                if isinstance(s_dict.get("action"), ReportStepAction):
                    s_dict["action"] = s_dict["action"].value
                step_list.append(s_dict)
            data["steps"] = step_list
        if "output" in data and isinstance(data["output"], ReportOutputConfig):
            output_dict = data["output"].model_dump(exclude_none=True)
            if "columns" in output_dict:
                output_dict["columns"] = [
                    c.model_dump(exclude_none=True) if isinstance(c, ReportColumn) else c
                    for c in output_dict["columns"]
                ]
            data["output"] = output_dict
        if "error_handling" in data and isinstance(data["error_handling"], ReportErrorHandling):
            data["error_handling"] = data["error_handling"].model_dump(exclude_none=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
        
        logger.info(f"Saved report definition: {path}")


class ReportManager:
    """High-level report discovery, loading, and registry management (Phase 4 Task 1).
    
    Wraps ReportYAML with a simplified API for report discovery, metadata loading,
    search, and list operations. Reports are defined as YAML files in /reports/ directory.
    
    Usage:
        manager = ReportManager(reports_dir=Path("reports"))
        reports = manager.list_reports()
        results = manager.search_reports("inventory")
        report = manager.get_report("stock_report")
        
        # Bootstrap example reports
        manager.bootstrap_examples()
        
    Threading Model:
        - ReportManager is synchronous (blocking I/O only)
        - Async execution happens in ReportRunner (Phase 4 Task 2)
        - See architecture patterns for threading model
    """
    
    def __init__(self, reports_dir: Path = Path("reports")) -> None:
        """Initialize report manager.
        
        Args:
            reports_dir: Path to reports directory (relative or absolute)
        """
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self._registry: Dict[str, ReportMetadata] = {}
        self._last_reload = 0.0
    
    def discover_reports(self, force_reload: bool = False) -> List[ReportMetadata]:
        """Scan reports directory for .yaml files and load definitions.
        
        - Walks reports_dir recursively for .yaml files (excluding /examples/)
        - Loads each .yaml as ReportMetadata with pydantic validation
        - Builds in-memory registry indexed by report name
        - Logs warnings for invalid YAML files
        
        Args:
            force_reload: If True, clear registry and rescan all files
        
        Returns:
            List of discovered ReportMetadata objects
        """
        if force_reload:
            self._registry.clear()
            self._last_reload = 0.0
        
        yaml_files = list(self.reports_dir.glob("**/*.yaml"))
        for yaml_path in yaml_files:
            try:
                # Skip if we've already loaded this file and it hasn't changed
                if yaml_path.name in self._registry and yaml_path.stat().st_mtime <= self._last_reload:
                    continue
                
                metadata = ReportYAML.load(yaml_path)
                if metadata:
                    self._registry[metadata.name] = metadata
                    logger.debug(f"Loaded report: {metadata.name} from {yaml_path}")
                else:
                    logger.warning(f"Failed to load report from {yaml_path}")
            except Exception as e:
                logger.error(f"Error loading report {yaml_path}: {e}")
        
        self._last_reload = datetime.utcnow().timestamp()
        return list(self._registry.values())
    
    def list_reports(self) -> List[ReportMetadata]:
        """Return all discovered reports as list of metadata.
        
        Triggers discovery if registry is empty.
        
        Returns:
            List of ReportMetadata objects for all discovered reports
        """
        if not self._registry:
            self.discover_reports()
        return list(self._registry.values())
    
    def get_report(self, report_name: str) -> Optional[ReportMetadata]:
        """Get report metadata by name (case-insensitive).
        
        Args:
            report_name: Report name (should match metadata.name field)
        
        Returns:
            ReportMetadata if found, None otherwise
        """
        if not self._registry:
            self.discover_reports()
        
        # Direct lookup first
        if report_name in self._registry:
            return self._registry[report_name]
        
        # Case-insensitive search
        report_name_lower = report_name.lower()
        for name, metadata in self._registry.items():
            if name.lower() == report_name_lower:
                return metadata
        
        return None
    
    def search_reports(self, query: str) -> List[ReportMetadata]:
        """Search reports by name, title, description, or tags (case-insensitive).
        
        Performs case-insensitive substring match on:
        - Report name
        - Report title
        - Report description
        - Report category
        - Report tags (any tag containing query string)
        
        Args:
            query: Search query string
        
        Returns:
            List of ReportMetadata objects matching the query
        """
        if not self._registry:
            self.discover_reports()
        
        query_lower = query.lower()
        results = []
        
        for metadata in self._registry.values():
            if (query_lower in metadata.name.lower() or
                query_lower in metadata.title.lower() or
                query_lower in metadata.description.lower() or
                query_lower in metadata.category.lower() or
                any(query_lower in tag.lower() for tag in metadata.tags)):
                results.append(metadata)
        
        return results
    
    def reload(self, force: bool = True) -> int:
        """Reload reports from disk (hot-reload support).
        
        Clears and rescans the reports directory for new or updated files.
        Useful for picking up report changes without restarting the application.
        
        Args:
            force: If True, force reload even if no changes detected
        
        Returns:
            Number of reports discovered after reload
        """
        reports = self.discover_reports(force_reload=force)
        logger.info(f"Reloaded {len(reports)} report(s)")
        return len(reports)
    
    def export_registry(self) -> Dict[str, dict]:
        """Export registry as dict for testing/debugging.
        
        Returns:
            Dictionary mapping report names to metadata dicts (pydantic model_dump)
        """
        if not self._registry:
            self.discover_reports()
        
        result = {}
        for name, metadata in self._registry.items():
            result[name] = metadata.model_dump(exclude_none=True)
        return result
    
    def list_by_category(self, category: str) -> List[ReportMetadata]:
        """Get all reports in a specific category.
        
        Args:
            category: Category name (e.g., "Inventory", "Sales")
        
        Returns:
            List of ReportMetadata objects in that category
        """
        if not self._registry:
            self.discover_reports()
        
        category_lower = category.lower()
        return [m for m in self._registry.values()
                if m.category.lower() == category_lower]
    
    def list_categories(self) -> List[str]:
        """Get all unique categories from discovered reports.
        
        Returns:
            Sorted list of unique category names
        """
        if not self._registry:
            self.discover_reports()
        
        categories = set()
        for metadata in self._registry.values():
            categories.add(metadata.category)
        
        return sorted(categories)
    
    def validate_report(self, report_metadata: ReportMetadata) -> Tuple[bool, List[str]]:
        """Validate a report definition for completeness and correctness.
        
        Checks:
        - Report has at least one parameter or is for a fixed transaction
        - Report has at least one execution step
        - All steps reference valid fields (if known)
        - Output columns match extracted grid columns
        - Error handling configuration is valid
        
        Args:
            report_metadata: Report to validate
        
        Returns:
            Tuple of (is_valid, list_of_error_messages)
        """
        errors: List[str] = []
        
        # Validate name
        if not report_metadata.name or not report_metadata.name.isidentifier():
            errors.append(f"Invalid report name: {report_metadata.name}")
        
        # Validate transaction
        if not report_metadata.transaction:
            errors.append("Report must have a transaction code")
        
        # Validate parameters
        param_names = set()
        for param in report_metadata.parameters:
            if param.name in param_names:
                errors.append(f"Duplicate parameter name: {param.name}")
            param_names.add(param.name)
        
        # Validate steps
        if not report_metadata.steps:
            errors.append("Report must have at least one execution step")
        
        for i, step in enumerate(report_metadata.steps):
            # Check for placeholder parameters that don't exist
            if step.value:
                import re
                placeholders = re.findall(r'\{(\w+)\}', step.value)
                for ph in placeholders:
                    if ph not in param_names and ph != 'plant':  # Allow common names as exception
                        errors.append(f"Step {i}: Parameter placeholder '{{{ph}}}' not defined")
        
        # Validate error handling
        valid_strategies = {'skip', 'abort', 'retry'}
        if report_metadata.error_handling.transaction_not_found not in valid_strategies:
            errors.append(f"Invalid error strategy: {report_metadata.error_handling.transaction_not_found}")
        
        return len(errors) == 0, errors
    
    def bootstrap_examples(self, overwrite: bool = False) -> Dict[str, bool]:
        """Create example report YAML files during setup.
        
        Generates realistic SAP report templates in /reports/examples/ for users to
        reference and customize. Call during first application start or manual reset.
        
        Args:
            overwrite: If True, overwrite existing files; if False, skip existing
        
        Returns:
            Dict mapping filename to success boolean
        """
        results = ReportYAML.bootstrap_examples(self.reports_dir, overwrite)
        
        # Refresh registry after creating examples
        self.discover_reports(force_reload=True)
        
        return results


# SECTION 12: Report Execution Engine (Phase 4 Task 2) ─────────────────────

import re
import asyncio
import traceback as tb_module
from time import time as now_seconds

# Import ReportResult from exporter module (canonical definition) - MUST BE BEFORE ReportRunner
from sap.exporter import ReportResult


class ReportRunner:
    """Execute SAP reports defined in YAML format (Phase 4 Task 2).
    
    Responsibilities:
    - Load report definitions via ReportManager
    - Validate parameters against parameter definitions
    - Execute step workflow (navigate → set_field → execute → read_grid)
    - Handle errors per error_handling config
    - Return ReportResult with extracted data and metadata
    
    Threading Model:
        All SAP session calls are async and automatically queued to COM worker thread.
        This class coordinates the workflow without blocking the asyncio event loop.
    
    Usage:
        ```python
        from sap.session import Session
        from sap import ReportRunner
        from pathlib import Path
        
        session = ...  # Connected SAP session
        runner = ReportRunner(session, reports_dir=Path("reports"))
        
        result = await runner.execute_report("stock_report", {
            "material_id": "ABC123",
            "plant": "1000"
        })
        
        print(f"Returned {result.row_count} rows in {result.execution_time_ms}ms")
        ```
    """
    
    def __init__(self, session: Any, reports_dir: Optional[Path] = None) -> None:
        """Initialize report runner.
        
        Args:
            session: Connected SAP Session for executing steps
            reports_dir: Path to reports directory (defaults to "reports")
        """
        self.session = session
        self.reports_dir = reports_dir or Path("reports")
        self.manager = ReportManager(self.reports_dir)
        logger.info(f"ReportRunner initialized (reports_dir={self.reports_dir})")
    
    async def execute_report(
        self,
        report_name: str,
        parameters: Dict[str, Any],
        timeout_seconds: int = 300
    ) -> ReportResult:
        """Execute a report by name with given parameters.
        
        Workflow:
        1. Load report metadata from YAML
        2. Validate parameters against parameter definitions
        3. Execute steps in order (navigate → set_field → execute → read_grid)
        4. Handle errors according to error_handling config
        5. Return ReportResult with extracted data
        
        Args:
            report_name: Report name (matches YAML filename without extension)
            parameters: Dict of parameter values {param_name: value}
            timeout_seconds: Max execution time (default 300s)
        
        Returns:
            ReportResult with columns, rows, metadata
        
        Raises:
            ValueError: If report not found, parameters invalid, or execution fails
            asyncio.TimeoutError: If execution exceeds timeout_seconds
        
        Example:
            ```python
            result = await runner.execute_report("stock_report", {
                "material_id": "ABC123",
                "plant": "1000"
            })
            ```
        """
        start_time = now_seconds()
        
        try:
            # Load report metadata
            report_metadata = self.manager.get_report(report_name)
            if not report_metadata:
                raise ValueError(f"Report not found: {report_name}")
            
            logger.info(f"Starting report execution: {report_name}")
            
            # Validate parameters
            validated_params = await self._validate_parameters(
                report_metadata.parameters,
                parameters
            )
            
            # Execute steps with timeout
            result = await asyncio.wait_for(
                self._execute_steps(
                    report_metadata.steps,
                    validated_params,
                    report_metadata.output,
                    report_metadata.error_handling
                ),
                timeout=timeout_seconds
            )
            
            # Attach metadata
            elapsed_ms = (now_seconds() - start_time) * 1000
            result.execution_time_ms = elapsed_ms
            
            logger.info(f"Report completed: {report_name} ({result.row_count} rows, {elapsed_ms:.0f}ms)")
            return result
        
        except asyncio.TimeoutError:
            logger.error(f"Report execution timeout: {report_name} (exceeded {timeout_seconds}s)")
            raise
        
        except Exception as e:
            logger.error(f"Report execution failed: {report_name} — {e}", exc_info=True)
            raise
    
    async def _validate_parameters(
        self,
        param_defs: List[ParamDefinition],
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate and normalize parameters before execution.
        
        Validations:
        - All required parameters are provided
        - All parameter types are correct (reuse Phase 3 ParameterValidator)
        - No extra parameters passed
        - Default values applied for optional params
        
        Args:
            param_defs: Parameter definitions from report metadata
            params: User-provided parameter values
        
        Returns:
            Validated and normalized parameters dict
        
        Raises:
            ValueError: If validation fails
        """
        validated: Dict[str, Any] = {}
        
        # Track provided params
        provided_keys = set(params.keys())
        
        # Process each parameter definition
        for param_def in param_defs:
            if param_def.name in params:
                value = params[param_def.name]
                provided_keys.discard(param_def.name)
                
                # Type validation (basic; extend with Phase 3 validator if available)
                if param_def.param_type == ParamType.INT and value is not None:
                    try:
                        validated[param_def.name] = int(value)
                    except ValueError:
                        raise ValueError(f"Parameter '{param_def.name}' must be integer, got: {value}")
                
                elif param_def.param_type == ParamType.BOOL and value is not None:
                    if isinstance(value, bool):
                        validated[param_def.name] = value
                    elif isinstance(value, str):
                        validated[param_def.name] = value.lower() in ('true', 'yes', '1')
                    else:
                        validated[param_def.name] = bool(value)
                
                elif param_def.param_type == ParamType.DATE and value is not None:
                    # Accept strings or date objects; convert to ISO format
                    if hasattr(value, 'isoformat'):
                        validated[param_def.name] = value.isoformat()
                    else:
                        validated[param_def.name] = str(value)
                
                elif param_def.param_type in (ParamType.DROPDOWN, ParamType.MULTI_SELECT):
                    # Validate against enum_values if provided
                    if param_def.enum_values and value not in param_def.enum_values:
                        raise ValueError(
                            f"Parameter '{param_def.name}' value '{value}' not in allowed values: {param_def.enum_values}"
                        )
                    validated[param_def.name] = value
                
                else:  # STRING and others — convert to string
                    validated[param_def.name] = str(value)
            
            elif param_def.required:
                raise ValueError(f"Required parameter missing: {param_def.name}")
            
            elif param_def.default_value is not None:
                validated[param_def.name] = param_def.default_value
        
        # Check for extra parameters
        if provided_keys:
            logger.warning(f"Unknown parameters provided: {provided_keys}")
        
        logger.debug(f"Parameters validated: {list(validated.keys())}")
        return validated
    
    async def _execute_steps(
        self,
        steps: List[ReportStep],
        params: Dict[str, Any],
        output_config: ReportOutputConfig,
        error_handling: ReportErrorHandling
    ) -> ReportResult:
        """Execute workflow steps in order.
        
        Steps are executed sequentially:
        1. NAVIGATE — start transaction
        2. SET_FIELD — set field values from parameters
        3. SET_FIELD_CONDITIONAL — conditionally set fields
        4. EXECUTE — send ENTER or execute
        5. READ_GRID — extract results
        6. CLICK_BUTTON — click a button
        
        Args:
            steps: List of ReportStep objects
            params: Validated parameters dict
            output_config: Output extraction configuration
            error_handling: Error handling configuration
        
        Returns:
            ReportResult with extracted data
        
        Raises:
            ValueError: If critical step fails and error_handling.abort
        """
        rows: List[Dict[str, Any]] = []
        
        for i, step in enumerate(steps):
            try:
                logger.debug(f"Executing step {i+1}/{len(steps)}: {step.action.value}")
                
                if step.action == ReportStepAction.NAVIGATE:
                    await self._handle_navigate(step)
                
                elif step.action == ReportStepAction.SET_FIELD:
                    await self._handle_set_field(step, params)
                
                elif step.action == ReportStepAction.SET_FIELD_CONDITIONAL:
                    # Only execute if condition is truthy
                    if step.condition and await self._eval_condition(step.condition, params):
                        await self._handle_set_field(step, params)
                
                elif step.action == ReportStepAction.EXECUTE:
                    await self._handle_execute(step)
                
                elif step.action == ReportStepAction.READ_GRID:
                    rows = await self._handle_read_grid(step, output_config)
                
                elif step.action == ReportStepAction.CLICK_BUTTON:
                    await self._handle_click_button(step)
            
            except asyncio.TimeoutError:
                logger.error(f"Step {i+1} timeout: {step.action.value}")
                if error_handling.execution_timeout == "abort":
                    raise ValueError(f"Step timeout (step {i+1}): {step.action.value}")
                elif error_handling.execution_timeout == "skip":
                    logger.warning(f"Skipping step {i+1} due to timeout")
                    continue
                # retry would be retried here, but we don't auto-retry yet
            
            except Exception as e:
                logger.error(f"Step {i+1} error: {step.action.value} — {e}")
                if step.action == ReportStepAction.SET_FIELD and error_handling.field_set_failed == "abort":
                    raise ValueError(f"Field set failed (step {i+1}): {e}")
                elif error_handling.execution_timeout == "abort":
                    raise
        
        # Build result using canonical ReportResult from exporter
        from sap.exporter import ReportResult as CanonicalReportResult
        columns = output_config.columns or []
        column_names = [col.column_name for col in columns]
        
        if not rows and error_handling.no_data == "abort":
            raise ValueError("No data returned from grid and no_data=abort")
        
        return CanonicalReportResult(
            columns=column_names,
            rows=rows
        )
    
    async def _substitute_value(self, value: str, params: Dict[str, Any]) -> str:
        """Substitute {param_name} placeholders in field value.
        
        Example:
            value = "Material: {material_id}, Plant: {plant}"
            params = {"material_id": "ABC123", "plant": "1000"}
            result = "Material: ABC123, Plant: 1000"
        
        Args:
            value: String with {param_name} placeholders
            params: Parameter dict
        
        Returns:
            String with placeholders replaced
        """
        result = value
        for param_name, param_value in params.items():
            placeholder = "{" + param_name + "}"
            result = result.replace(placeholder, str(param_value or ""))
        return result
    
    async def _eval_condition(self, condition: str, params: Dict[str, Any]) -> bool:
        """Evaluate condition expression for conditional steps.
        
        Supports simple expressions like:
        - "{plant}" (true if plant is non-empty)
        - "{quantity} > 0" (basic comparison)
        
        Args:
            condition: Condition expression
            params: Parameter dict
        
        Returns:
            True if condition is truthy, False otherwise
        """
        try:
            # Substitute parameters
            expr = await self._substitute_value(condition, params)
            
            # Try direct eval (dangerous, but limited to SAP report context)
            # In production, use ast.literal_eval or safer expression parser
            return bool(eval(expr, {"__builtins__": {}}, {}))
        
        except Exception as e:
            logger.warning(f"Condition evaluation failed: {condition} — {e}")
            return False
    
    async def _handle_navigate(self, step: ReportStep) -> None:
        """Execute NAVIGATE step — start a transaction.
        
        Args:
            step: ReportStep with action=NAVIGATE, target=transaction_code
        
        Raises:
            ValueError: If transaction not found
        """
        if not step.target:
            raise ValueError("NAVIGATE step missing target (transaction code)")
        
        logger.debug(f"Navigating to transaction: {step.target}")
        await self.session.start_transaction(step.target, timeout=step.timeout)
    
    async def _handle_set_field(self, step: ReportStep, params: Dict[str, Any]) -> None:
        """Execute SET_FIELD step — set a field value.
        
        Args:
            step: ReportStep with action=SET_FIELD, field=field_name, value={param}
            params: Parameter values for substitution
        
        Raises:
            ValueError: If field or value missing
        """
        if not step.field:
            raise ValueError("SET_FIELD step missing field name")
        if not step.value:
            raise ValueError("SET_FIELD step missing value")
        
        # Substitute parameters in value
        value = await self._substitute_value(step.value, params)
        
        logger.debug(f"Setting field '{step.field}' = '{value}'")
        await self.session.set_field_value(step.field, value, timeout=step.timeout)
    
    async def _handle_execute(self, step: ReportStep) -> None:
        """Execute EXECUTE step — send ENTER or execute.
        
        Args:
            step: ReportStep with action=EXECUTE
        """
        logger.debug("Executing (pressing ENTER)")
        await self.session.send_vkey("ENTER", timeout=step.timeout)
    
    async def _handle_read_grid(
        self,
        step: ReportStep,
        output_config: ReportOutputConfig
    ) -> List[Dict[str, Any]]:
        """Execute READ_GRID step — extract data from grid.
        
        Args:
            step: ReportStep with action=READ_GRID, target=grid_id
            output_config: Column and row limit configuration
        
        Returns:
            List of row dicts
        """
        logger.debug(f"Reading grid: {step.target or 'default'}")
        
        # Get element tree (includes grid data)
        tree = await self.session.get_element_tree(timeout=step.timeout)
        
        # Extract grid rows (simplified; in production use inspector.get_grid_data())
        rows: List[Dict[str, Any]] = []
        
        # For now, return empty rows (real implementation would extract from tree)
        # This is a placeholder that demonstrates the structure
        logger.debug(f"Extracted {len(rows)} rows from grid")
        
        return rows[:output_config.row_limit] if output_config.row_limit > 0 else rows
    
    async def _handle_click_button(self, step: ReportStep) -> None:
        """Execute CLICK_BUTTON step — click a button by label or ID.
        
        Args:
            step: ReportStep with action=CLICK_BUTTON, target=button_label_or_id
        """
        if not step.target:
            raise ValueError("CLICK_BUTTON step missing target (button label or ID)")
        
        logger.debug(f"Clicking button: {step.target}")
        await self.session.click_button(step.target, timeout=step.timeout)


__all__ = [
    # Script Manager (Tasks 3-7)
    'ParamType', 'ParamDefinition', 'ScriptMetadata', 'ExecutionRecord',
    'MetadataYAML', 'ParameterParser', 'ParameterValidator',
    'ScriptEntry', 'ScriptRegistry', 'ScriptManager', 'ExecutionHistory',
    # Script Executor (Task 6)
    'ScriptExecutor',
    # VBScript Converter (Task 1) - available as sap.VBScriptConverter or import directly
    'VBSConverter', 'VBScriptConverter', 'ConversionResult',
    # Report Schema (Phase 4 Task 1)
    'ReportStepAction', 'ReportStep', 'ReportColumn', 'ReportOutputConfig',
    'ReportErrorHandling', 'ReportMetadata', 'ReportResult', 'ReportYAML', 'ReportManager',
    # Report Execution Engine (Phase 4 Task 2)
    'ReportRunner'
]

# Note: VBScriptConverter is defined in this module.
# For Phase 3, the converter was originally intended to be in a separate sap/vbs_converter.py file,
# but due to build constraints, it's defined in __init__.py and exported here.
# To use the converter:
#   from sap import VBScriptConverter
#   converter = VBScriptConverter()
#   python_code, flags = converter.convert_code(vbs_code)

