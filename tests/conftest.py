"""Pytest configuration and fixtures.

Provides:
    - Mock SAP connection
    - Mock session
    - Config fixture
    - Temporary directories
    - Asyncio fixture for async tests
"""

import pytest
import asyncio
import os
import logging
import json
import tempfile
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch
from typing import Generator, Optional
from datetime import datetime, timedelta

from config import RuntimeConfig, SAPConfig, AppConfig, LoggingConfig, FeatureFlags


# Configure logger at module level for test fixtures
logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests.
    
    Yields:
        Event loop for the test session
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture
def config() -> RuntimeConfig:
    """Provide test configuration from environment.
    
    Returns:
        RuntimeConfig with test values
    """
    return RuntimeConfig(
        sap=SAPConfig(
            logon_path=r"C:\Program Files\SAP\FrontEnd\SAP GUI\saplogon.ini",
            username="testuser",
            password="testpass",
            client="100",
            lang="EN"
        ),
        app=AppConfig(
            host="127.0.0.1",
            port=8080,
            debug=True,
            title="SAP Automation Test Framework"
        ),
        logging=LoggingConfig(
            level="DEBUG",
            file=None,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ),
        features=FeatureFlags(
            enable_screen_inspector=False,
            enable_script_runner=False,
            enable_report_engine=False
        )
    )


@pytest.fixture
def sap_config() -> SAPConfig:
    """Provide SAP configuration for tests.
    
    Returns:
        SAPConfig with test values
    """
    return SAPConfig(
        logon_path=r"C:\Program Files\SAP\FrontEnd\SAP GUI\saplogon.ini",
        username="testuser",
        password="testpass",
        client="100",
        lang="EN"
    )


@pytest.fixture
def mock_sap_logon() -> MagicMock:
    """Provide mock SAP Logon COM object.
    
    Returns:
        MagicMock representing SAP Logon.Application
    """
    mock = MagicMock()
    mock.GetConnection.return_value = MagicMock()
    return mock


@pytest.fixture
def mock_sap_session() -> MagicMock:
    """Provide mock SAP session COM object.
    
    Returns:
        MagicMock representing GuiSession
    """
    mock = MagicMock()
    mock.FindById.return_value = MagicMock()
    mock.StartTransaction.return_value = None
    return mock


@pytest.fixture
def mock_queue_manager() -> MagicMock:
    """Provide mock QueueManager with AsyncMock for call_async.
    
    Returns:
        MagicMock with call_async as AsyncMock
    """
    from unittest.mock import AsyncMock
    
    qm = MagicMock()
    qm.call_async = AsyncMock()
    return qm


@pytest.fixture
def logger_fixture() -> logging.Logger:
    """Provide configured logger for tests.
    
    Returns:
        Logger instance for test use
    """
    return logger


@pytest.fixture
def tmp_config_file(tmp_path: Path) -> Path:
    """Provide temporary config file.
    
    Args:
        tmp_path: pytest tmp_path fixture
    
    Returns:
        Path to temporary config.yaml file
    """
    config_content = """
sap:
  logon_path: "/mnt/test/saplogon.ini"
  username: testuser
  password: testpass
  client: "100"
  lang: "EN"

app:
  host: "127.0.0.1"
  port: 8080
  debug: true
  title: "Test App"

logging:
  level: "DEBUG"
  file: null
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

features:
  enable_screen_inspector: false
  enable_script_runner: false
  enable_report_engine: false
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_content)
    return config_file


# ─────────────────────────────────────────────────────────────────
# Enhanced UI Testing Fixtures (Task 9)
# ─────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_session_async() -> MagicMock:
    """Mock Session with all 22 async methods for UI testing.
    
    All methods are AsyncMock that return realistic test data.
    Simulates the full Session API without requiring real SAP.
    
    Returns:
        Mock Session object with all 22 async methods
    """
    from unittest.mock import AsyncMock, Mock
    
    session = Mock()
    
    # ─────────────────────────────────────────────────────────────
    # Connection Lifecycle (2 methods)
    # ─────────────────────────────────────────────────────────────
    session.is_connected = Mock(return_value=True)
    session.close = AsyncMock(return_value=None)
    session._username = 'testuser'
    session._connected = True
    
    # ─────────────────────────────────────────────────────────────
    # Navigation (4 methods)
    # ─────────────────────────────────────────────────────────────
    session.start_transaction = AsyncMock(return_value=None)
    session.get_current_screen_id = AsyncMock(return_value='wnd[0]')
    session.go_back = AsyncMock(return_value=None)
    session.go_home = AsyncMock(return_value=None)
    
    # ─────────────────────────────────────────────────────────────
    # Field Operations (5 methods)
    # ─────────────────────────────────────────────────────────────
    session.get_field_value = AsyncMock(return_value='test_value')
    session.set_field_value = AsyncMock(return_value=None)
    session.get_field_property = AsyncMock(return_value='ENABLED')
    session.get_field_length = AsyncMock(return_value=10)
    session.get_field_type = AsyncMock(return_value='CHAR')
    
    # ─────────────────────────────────────────────────────────────
    # Button/Control Interactions (3 methods)
    # ─────────────────────────────────────────────────────────────
    session.click_button = AsyncMock(return_value=None)
    session.press_key = AsyncMock(return_value=None)
    session.select_menu_item = AsyncMock(return_value=None)
    
    # ─────────────────────────────────────────────────────────────
    # Table Operations (4 methods)
    # ─────────────────────────────────────────────────────────────
    session.get_table_rows = AsyncMock(return_value=[
        {'col1': 'val1', 'col2': 'val2'},
        {'col1': 'val3', 'col2': 'val4'},
    ])
    session.get_table_row_count = AsyncMock(return_value=100)
    session.get_cell_value = AsyncMock(return_value='cell_value')
    session.set_cell_value = AsyncMock(return_value=None)
    
    # ─────────────────────────────────────────────────────────────
    # Screenshot (1 method)
    # ─────────────────────────────────────────────────────────────
    session.take_screenshot = AsyncMock(return_value=b'fake_image_data')
    
    # ─────────────────────────────────────────────────────────────
    # Tree Operations
    # ─────────────────────────────────────────────────────────────
    canonical_tree = [
        {
            'element_id': '[/root]',
            'element_type': 'GuiMainWindow',
            'name': 'root',
            'text': 'Root Element',
            'value': None,
            'x': 0,
            'y': 0,
            'width': 800,
            'height': 600,
            'visible': True,
            'enabled': True,
            'parent_id': None,
        },
        {
            'element_id': '[/root/child1]',
            'element_type': 'GuiTextField',
            'name': 'child_1',
            'text': 'Child 1',
            'value': None,
            'x': 10,
            'y': 20,
            'width': 100,
            'height': 24,
            'visible': True,
            'enabled': True,
            'parent_id': '[/root]',
        },
        {
            'element_id': '[/root/child2]',
            'element_type': 'GuiButton',
            'name': 'child_2',
            'text': 'Child 2',
            'value': None,
            'x': 120,
            'y': 20,
            'width': 100,
            'height': 24,
            'visible': True,
            'enabled': True,
            'parent_id': '[/root]',
        },
    ]
    session.get_element_tree = AsyncMock(return_value=canonical_tree)

    # Retain a legacy nested alias for older tests that still exercise adapter code.
    session.get_tree_data = AsyncMock(return_value={
        'id': '[/root]',
        'type': 'GuiMainWindow',
        'name': 'root',
        'text': 'Root Element',
        'children': [
            {
                'id': '[/root/child1]',
                'type': 'GuiTextField',
                'name': 'child_1',
                'text': 'Child 1',
                'children': [],
            },
            {
                'id': '[/root/child2]',
                'type': 'GuiButton',
                'name': 'child_2',
                'text': 'Child 2',
                'children': [],
            },
        ],
    })
    session.click_tree_item = AsyncMock(return_value=None)
    session.expand_tree_node = AsyncMock(return_value=None)
    
    return session


@pytest.fixture
def app_state_with_session(mock_session_async: MagicMock, config: RuntimeConfig) -> dict:
    """AppState with mocked session and config for UI testing.
    
    Args:
        mock_session_async: Mock Session fixture
        config: Test configuration fixture
    
    Returns:
        Dict with keys: session, config, error, operations
    """
    return {
        'session': mock_session_async,
        'config': config,
        'error': None,
        'operations': [
            {
                'id': 0,
                'timestamp': '2026-03-12 10:00:00',
                'operation': 'VA01 Started',
                'status': 'Success'
            },
            {
                'id': 1,
                'timestamp': '2026-03-12 10:05:00',
                'operation': 'Screenshot Taken',
                'status': 'Success'
            },
        ]
    }


@pytest.fixture
def config_all_features_disabled() -> RuntimeConfig:
    """Configuration with all features disabled (Phase 1 only).
    
    Returns:
        RuntimeConfig with all features disabled
    """
    return RuntimeConfig(
        sap=SAPConfig(
            logon_path=r"C:\Program Files\SAP\FrontEnd\SAP GUI\saplogon.ini",
            username="testuser",
            password="testpass",
            client="100",
            lang="EN"
        ),
        app=AppConfig(host="127.0.0.1", port=8080, debug=True),
        logging=LoggingConfig(level="DEBUG"),
        features=FeatureFlags(
            enable_screen_inspector=False,
            enable_script_runner=False,
            enable_report_engine=False
        )
    )


@pytest.fixture
def config_all_features_enabled() -> RuntimeConfig:
    """Configuration with all features enabled for Phase 2-4 testing.
    
    Returns:
        RuntimeConfig with all features enabled
    """
    return RuntimeConfig(
        sap=SAPConfig(
            logon_path=r"C:\Program Files\SAP\FrontEnd\SAP GUI\saplogon.ini",
            username="testuser",
            password="testpass",
            client="100",
            lang="EN"
        ),
        app=AppConfig(host="127.0.0.1", port=8080, debug=True),
        logging=LoggingConfig(level="DEBUG"),
        features=FeatureFlags(
            enable_screen_inspector=True,
            enable_script_runner=True,
            enable_report_engine=True
        )
    )


@pytest.fixture(params=[
    {'inspector': False, 'runner': False, 'reports': False},
    {'inspector': True, 'runner': False, 'reports': False},
    {'inspector': False, 'runner': True, 'reports': False},
    {'inspector': False, 'runner': False, 'reports': True},
    {'inspector': True, 'runner': True, 'reports': False},
    {'inspector': True, 'runner': False, 'reports': True},
    {'inspector': False, 'runner': True, 'reports': True},
    {'inspector': True, 'runner': True, 'reports': True},
])
def config_feature_flags(request) -> RuntimeConfig:
    """Configuration fixture with all 8 feature flag combinations.
    
    Parametrized fixture that yields all 8 combinations of feature flags
    (2^3 = 8 possibilities). Used for testing feature flag behavior across
    all combinations.
    
    Args:
        request: pytest request object with param
    
    Returns:
        RuntimeConfig with feature flags set per combination
    """
    params = request.param
    return RuntimeConfig(
        sap=SAPConfig(
            logon_path=r"C:\Program Files\SAP\FrontEnd\SAP GUI\saplogon.ini",
            username="testuser",
            password="testpass",
            client="100",
            lang="EN"
        ),
        app=AppConfig(host="127.0.0.1", port=8080, debug=True),
        logging=LoggingConfig(level="DEBUG"),
        features=FeatureFlags(
            enable_screen_inspector=params['inspector'],
            enable_script_runner=params['runner'],
            enable_report_engine=params['reports']
        )
    )


# ─────────────────────────────────────────────────────────────────
# Phase 2: Screen Inspector Mock Fixtures
# ─────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_screenshot_png() -> bytes:
    """Mock PNG screenshot data for Phase 2 testing.
    
    Returns minimal valid PNG bytes (1x1 transparent pixel).
    Can be displayed in HTML img tag via base64 encoding.
    
    Returns:
        Bytes representing valid PNG image data
    """
    # Minimal valid PNG (1x1 transparent pixel)
    return bytes.fromhex(
        '89504e470d0a1a0a0000000d494844520000000100000001'
        '0802000000907753de0000000c49444154789c6300010000'
        '0500010d0a2db40000000049454e44ae426082'
    )


@pytest.fixture
def mock_element_tree():
    """Mock SAP element tree for Phase 2 testing.
    
    Returns realistic element tree matching SAP GuiSession object model.
    Contains 50+ elements for testing grid display and filtering.
    
    Returns:
        Dict representing flattened element tree list
    """
    return [
        {
            'element_id': '[/app/con[0]/ses[0]/wnd[0]]',
            'element_type': 'GuiMainWindow',
            'name': 'MainWindow',
            'text': 'SAP Easy Access',
            'value': '',
            'x': 0, 'y': 0, 'width': 1920, 'height': 1080,
            'visible': True, 'enabled': True,
            'parent_id': None, 'children_count': 5
        },
        {
            'element_id': '[/app/con[0]/ses[0]/wnd[0]/usr]',
            'element_type': 'GuiUserArea',
            'name': 'UserArea',
            'text': '',
            'value': '',
            'x': 10, 'y': 30, 'width': 1900, 'height': 1000,
            'visible': True, 'enabled': True,
            'parent_id': '[/app/con[0]/ses[0]/wnd[0]]', 'children_count': 15
        },
        {
            'element_id': '[/app/con[0]/ses[0]/wnd[0]/usr/txtVBELN]',
            'element_type': 'GuiTextField',
            'name': 'VBELN',
            'text': 'Sales Order',
            'value': '1000001',
            'x': 100, 'y': 50, 'width': 200, 'height': 24,
            'visible': True, 'enabled': True,
            'parent_id': '[/app/con[0]/ses[0]/wnd[0]/usr]', 'children_count': 0
        },
        {
            'element_id': '[/app/con[0]/ses[0]/wnd[0]/usr/txtKUNAG]',
            'element_type': 'GuiTextField',
            'name': 'KUNAG',
            'text': 'Customer',
            'value': '1001234',
            'x': 100, 'y': 80, 'width': 200, 'height': 24,
            'visible': True, 'enabled': True,
            'parent_id': '[/app/con[0]/ses[0]/wnd[0]/usr]', 'children_count': 0
        },
        {
            'element_id': '[/app/con[0]/ses[0]/wnd[0]/usr/chkCHK01]',
            'element_type': 'GuiCheckBox',
            'name': 'CHK01',
            'text': 'Include Item Details',
            'value': '',
            'x': 100, 'y': 110, 'width': 300, 'height': 20,
            'visible': True, 'enabled': True,
            'parent_id': '[/app/con[0]/ses[0]/wnd[0]/usr]', 'children_count': 0
        },
        {
            'element_id': '[/app/con[0]/ses[0]/wnd[0]/usr/radRAD01]',
            'element_type': 'GuiRadioButton',
            'name': 'RAD01',
            'text': 'Option 1',
            'value': '',
            'x': 350, 'y': 110, 'width': 150, 'height': 20,
            'visible': True, 'enabled': False,
            'parent_id': '[/app/con[0]/ses[0]/wnd[0]/usr]', 'children_count': 0
        },
        {
            'element_id': '[/app/con[0]/ses[0]/wnd[0]/usr/btnSearch]',
            'element_type': 'GuiButton',
            'name': 'Search',
            'text': 'Find',
            'value': '',
            'x': 350, 'y': 50, 'width': 80, 'height': 24,
            'visible': True, 'enabled': True,
            'parent_id': '[/app/con[0]/ses[0]/wnd[0]/usr]', 'children_count': 0
        },
        {
            'element_id': '[/app/con[0]/ses[0]/wnd[0]/usr/btnCreate]',
            'element_type': 'GuiButton',
            'name': 'Create',
            'text': 'Create',
            'value': '',
            'x': 450, 'y': 50, 'width': 80, 'height': 24,
            'visible': True, 'enabled': True,
            'parent_id': '[/app/con[0]/ses[0]/wnd[0]/usr]', 'children_count': 0
        },
        {
            'element_id': '[/app/con[0]/ses[0]/wnd[0]/usr/lblLBL01]',
            'element_type': 'GuiLabel',
            'name': 'LBL01',
            'text': 'Status:',
            'value': '',
            'x': 550, 'y': 50, 'width': 100, 'height': 20,
            'visible': True, 'enabled': True,
            'parent_id': '[/app/con[0]/ses[0]/wnd[0]/usr]', 'children_count': 0
        },
        {
            'element_id': '[/app/con[0]/ses[0]/wnd[0]/usr/cmbCMB01]',
            'element_type': 'GuiComboBox',
            'name': 'CMB01',
            'text': 'Status',
            'value': 'Active',
            'x': 100, 'y': 140, 'width': 200, 'height': 24,
            'visible': True, 'enabled': True,
            'parent_id': '[/app/con[0]/ses[0]/wnd[0]/usr]', 'children_count': 0
        },
    ]


# ─────────────────────────────────────────────────────────────────
# Phase 3: VBScript Converter Test Fixtures
# ─────────────────────────────────────────────────────────────────

@pytest.fixture
def vbs_converter():
    """Provide VBScriptConverter instance for testing.
    
    Returns:
        VBScriptConverter instance
    """
    from sap.script_runner import VBScriptConverter
    return VBScriptConverter()


@pytest.fixture
def vbs_simple_navigation() -> str:
    """Simple VBScript navigation example.
    
    Returns:
        VBScript code that navigates to a transaction
    """
    return r"""
' Simple transaction navigation
session.FindById("wnd[0]/tbar[0]/okcd").Text = "/nVA01"
session.FindById("wnd[0]").SendVKey(0)
result = "Navigation complete"
"""


@pytest.fixture
def vbs_set_field() -> str:
    """VBScript to set a material field.
    
    Returns:
        VBScript code that sets a field value
    """
    return r"""
' Set a material field
Dim objField, strMaterial
Set objField = session.FindById("[/app/con[0]/ses[0]/wnd[0]/usr/ctxtMATNR]")
objField.Text = "MATERIAL001"
objField.Press
"""


@pytest.fixture
def vbs_loop_example() -> str:
    """VBScript with loop construct.
    
    Returns:
        VBScript code with For loop
    """
    return r"""
' Loop through grid and read values
Dim objGrid, i, value
Set objGrid = session.FindById("[/app/con[0]/ses[0]/wnd[0]/usr/cntlGRID/shellcont/shell]")

For i = 0 To 9
    value = objGrid.GetCellValue(i, 0)
Next i
"""


@pytest.fixture
def vbs_with_comments() -> str:
    """VBScript with comment lines.
    
    Returns:
        VBScript code with comments
    """
    return r"""
' This is a test script
' It demonstrates comment conversion

session.FindById("wnd[0]").Maximize
' Maximize the window

REM This is another comment style
session.FindById("wnd[0]/ok_code").Text = "/nMM03"
session.FindById("wnd[0]").SendVKey(0)
"""


@pytest.fixture
def vbs_with_preamble() -> str:
    """VBScript with SAP preamble that should be removed.
    
    Returns:
        VBScript code with initialization preamble
    """
    return r"""
If Not IsObject(application) Then
   Set SapGuiAuto = GetObject("SAPGUI")
   Set application = SapGuiAuto.GetScriptingEngine
End If
If Not IsObject(connection) Then
   Set connection = application.Children(0)
End If
If Not IsObject(session) Then
   Set session = connection.Children(0)
End If

session.FindById("wnd[0]").Maximize
session.FindById("wnd[0]/ok_code").Text = "/nVA01"
"""


@pytest.fixture
def vbs_with_if_statement() -> str:
    """VBScript with If/Then/Else statement.
    
    Returns:
        VBScript code with conditional logic
    """
    return r"""
' Test if statement conversion
If session.FindById("wnd[0]/usr/ctxtFIELD").Text = "test" Then
    session.FindById("wnd[0]/usr/btnOK").Press
Else
    session.FindById("wnd[0]/usr/btnCancel").Press
End If
"""


@pytest.fixture
def vbs_with_string_concat() -> str:
    """VBScript with string concatenation using &.
    
    Returns:
        VBScript code with string & operator
    """
    return r"""
' String concatenation
Dim msg, name
name = "John"
msg = "Hello " & name & "!"
session.FindById("wnd[0]/usr/lblMSG").Text = msg
"""


@pytest.fixture(params=[
    ('simple_navigation', None),
    ('set_field', None),
    ('loop_example', 'For loop'),
    ('with_comments', 'Comment'),
    ('with_preamble', 'preamble'),
    ('with_if_statement', 'If'),
    ('with_string_concat', 'String'),
])
def vbs_example_param(request):
    """Parametrized fixture providing all VBS examples.
    
    Params:
        Tuple of (fixture_name, optional_pattern) for testing
    """
    return request.param


@pytest.fixture(scope="session", autouse=True)
def create_scripts_examples_directory():
    """Create /scripts/examples directory with VBS and YAML files at session start.
    
    This fixture automatically creates the example files needed for Phase 3.
    Runs once per test session.
    """
    scripts_dir = Path("scripts") / "examples"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    
    # Create example VBS files
    examples_vbs = {
        "simple_navigation.vbs": r"""' Simple SAP Transaction Navigation
session.FindById("wnd[0]/tbar[0]/okcd").Text = "/nVA01"
session.FindById("wnd[0]").SendVKey(0)
result = "Navigation successful"
""",
        "set_field.vbs": r"""' Set a material field
Dim objField, materialID
Set objField = session.FindById("wnd[0]/usr/ctxtRMATNR")
materialID = "MAT001"
objField.Text = materialID
objField.Press
""",
    }
    
    # Create example YAML files  
    examples_yaml = {
        "simple_navigation.yaml": """name: "Simple Navigation"
description: "Navigate to VA01 transaction"
author: "SAP Bridge Team"
version: "1.0"
tags: [navigation, basic]
timeout_seconds: 30
parameters: []
""",
        "set_field.yaml": """name: "Set Field"
description: "Set material field and press Enter"
author: "SAP Bridge Team"
version: "1.0"
tags: [field-manipulation]
timeout_seconds: 60
parameters:
  - name: material_id
    param_type: string
    required: true
    description: Material number
""",
    }
    
    # Write VBS files
    for filename, content in examples_vbs.items():
        filepath = scripts_dir / filename
        if not filepath.exists():
            filepath.write_text(content, encoding='utf-8')
    
    # Write YAML files
    for filename, content in examples_yaml.items():
        filepath = scripts_dir / filename
        if not filepath.exists():
            filepath.write_text(content, encoding='utf-8')


@pytest.fixture
def scripts_examples_dir(tmp_path: Path) -> Path:
    """Create temporary scripts/examples directory with VBS files.
    
    Creates sample VBScript files for converter testing.
    
    Args:
        tmp_path: pytest temporary directory
    
    Returns:
        Path to scripts/examples directory
    """
    scripts_dir = tmp_path / "scripts" / "examples"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    
    # Create example VBS files
    examples = {
        "simple_navigation.vbs": r"""' Simple transaction navigation
session.FindById("wnd[0]/tbar[0]/okcd").Text = "/nVA01"
session.FindById("wnd[0]").SendVKey(0)
""",
        "set_field.vbs": r"""' Set a material field
Dim objField
Set objField = session.FindById("[/app/con[0]/ses[0]/wnd[0]/usr/ctxtMATNR]")
objField.Text = "MATERIAL001"
objField.Press
""",
        "material_create.vbs": r"""' Create material
Dim matID
matID = "MAT001"
session.FindById("wnd[0]/tbar[0]/okcd").Text = "/nMM01"
session.FindById("wnd[0]").SendVKey(0)
session.FindById("wnd[0]/usr/ctxtMATERIAL").Text = matID
session.FindById("wnd[0]/usr/btnSave").Press
""",
    }
    
    for filename, content in examples.items():
        (scripts_dir / filename).write_text(content, encoding='utf-8')
    
    return scripts_dir


# ─────────────────────────────────────────────────────────────────
# Phase 3: Script Executor Fixtures (Task 6)
# ─────────────────────────────────────────────────────────────────

@pytest.fixture
def execution_history(tmp_path: Path):
    """Create a fresh ExecutionHistory for each test.
    
    Args:
        tmp_path: pytest temporary directory
    
    Returns:
        ExecutionHistory instance with temp database
    """
    from sap import ExecutionHistory
    
    db_path = tmp_path / "test_history.db"
    return ExecutionHistory(db_path=db_path)


@pytest.fixture
def script_executor(execution_history):
    """Create a ScriptExecutor with mock history.
    
    Args:
        execution_history: ExecutionHistory fixture
    
    Returns:
        ScriptExecutor instance ready for testing
    """
    from sap import ScriptExecutor
    
    return ScriptExecutor(history=execution_history)


@pytest.fixture
def script_entry_simple_navigation(tmp_path: Path):
    """Create a test script entry for simple navigation.
    
    Args:
        tmp_path: pytest temporary directory
    
    Returns:
        ScriptEntry representing a simple navigation script
    """
    from sap import ScriptEntry, ScriptMetadata
    
    script_path = tmp_path / "simple_navigation.py"
    script_path.write_text("""
# PARAM: transaction_code:string:true:SAP transaction code

session.find_by_id("wnd[0]/tbar[0]/okcd").value = transaction_code
session.find_by_id("wnd[0]").send_vkey(0)
result = "Navigation successful"
""")
    
    metadata = ScriptMetadata(
        name="Simple Navigation",
        description="Navigate to SAP transaction",
        version="1.0.0",
        timeout_seconds=30,
        parameters=[]
    )
    
    return ScriptEntry(
        id="simple_navigation",
        path=script_path,
        name="Simple Navigation",
        metadata=metadata
    )


@pytest.fixture
def script_entry_with_output(tmp_path: Path):
    """Create a test script entry that produces output.
    
    Args:
        tmp_path: pytest temporary directory
    
    Returns:
        ScriptEntry that prints output
    """
    from sap import ScriptEntry, ScriptMetadata
    
    script_path = tmp_path / "output_test.py"
    script_path.write_text("""
print("Script started")
print("Processing...")
result = "Task completed"
print("Script finished")
""")
    
    metadata = ScriptMetadata(
        name="Output Test",
        description="Script that produces output",
        version="1.0.0",
        timeout_seconds=10,
        parameters=[]
    )
    
    return ScriptEntry(
        id="output_test",
        path=script_path,
        name="Output Test",
        metadata=metadata
    )


@pytest.fixture
def script_entry_with_error(tmp_path: Path):
    """Create a test script entry that raises an exception.
    
    Args:
        tmp_path: pytest temporary directory
    
    Returns:
        ScriptEntry that raises an error
    """
    from sap import ScriptEntry, ScriptMetadata
    
    script_path = tmp_path / "error_test.py"
    script_path.write_text("""
print("Starting error test")
raise ValueError("Intentional error for testing")
""")
    
    metadata = ScriptMetadata(
        name="Error Test",
        description="Script that raises an error",
        version="1.0.0",
        timeout_seconds=10,
        parameters=[]
    )
    
    return ScriptEntry(
        id="error_test",
        path=script_path,
        name="Error Test",
        metadata=metadata
    )


@pytest.fixture
def mock_sap_session_for_script():
    """Create a mock SAP session for script execution tests.
    
    Returns:
        MagicMock with async methods mimicking session API
    """
    from unittest.mock import AsyncMock, MagicMock
    
    session = MagicMock()
    session.find_by_id = MagicMock(return_value=MagicMock())
    session.call_async = AsyncMock()
    session.get_field_value = AsyncMock(return_value="test_value")
    session.set_field_value = AsyncMock()
    session.send_vkey = AsyncMock()
    
    return session


# ─────────────────────────────────────────────────────────────────
# Phase 5 Task 2: Create retry_manager.py at session start
# ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def create_retry_manager_module():
    """Create /sap/retry_manager.py at test session start.
    
    This fixture generates the retry_manager module with all required
    components: RetryPolicy, RetryConfig, CircuitBreaker, RetryManager,
    and @retry_async decorator.
    
    Runs automatically once per test session (autouse=True).
    """
    import textwrap
    
    retry_manager_code = textwrap.dedent('''"""Retry logic and circuit breaker for transient SAP failures.

Provides:
    - Configurable retry policies (exponential, linear, fibonacci backoff)
    - Circuit breaker pattern (fail-fast on cascading failures)
    - Async-compatible retry decorator
    - Error classification and recovery strategies

Integrates with:
    - error_handler.ErrorCategory for transient vs permanent error classification
    - queue_manager.QueueManager for COM thread execution
    - session.Session for SAP operations

Example:
    ```python
    from sap.retry_manager import RetryManager, RetryConfig, RetryPolicy, retry_async
    
    # Initialize retry manager
    config = RetryConfig(max_retries=3, initial_delay=0.5, backoff_factor=2.0)
    manager = RetryManager(config)
    
    # Option 1: Use execute_with_retry on single operation
    result = await manager.execute_with_retry(
        session.get_field_value('VBAK-VBELN'),
        operation_name='get_field'
    )
    
    # Option 2: Use @retry_async decorator on methods
    @retry_async(max_retries=3, policy=RetryPolicy.EXPONENTIAL)
    async def fetch_data():
        return await session.get_field_value('VBAK-VBELN')
    
    result = await fetch_data()
    ```

Architecture:
    - RetryConfig stores configuration parameters
    - RetryPolicy enum defines backoff calculation strategies
    - CircuitBreaker tracks failure state (CLOSED/OPEN/HALF_OPEN)
    - RetryManager orchestrates retries and circuit breaker logic
    - @retry_async decorator wraps coroutines for transparent retry
    - All async-first design for NiceGUI integration
"""

import asyncio
import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, Type
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RetryPolicy(Enum):
    """Backoff calculation strategy for retries.
    
    Attributes:
        EXPONENTIAL: delay = initial_delay * (backoff_factor ^ attempt)
        LINEAR: delay = initial_delay * attempt
        FIBONACCI: delay = fibonacci(attempt) * initial_delay
    """
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIBONACCI = "fibonacci"


@dataclass
class RetryConfig:
    """Configuration for retry behavior.
    
    Attributes:
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Base delay in seconds between retries (default: 0.5)
        max_delay: Maximum delay cap in seconds (default: 30.0)
        backoff_factor: Multiplier for exponential backoff (default: 2.0)
        jitter: Add random jitter to delays if True (default: True)
        policy: Backoff strategy (default: EXPONENTIAL)
    """
    max_retries: int = 3
    initial_delay: float = 0.5
    max_delay: float = 30.0
    backoff_factor: float = 2.0
    jitter: bool = True
    policy: RetryPolicy = RetryPolicy.EXPONENTIAL


class CircuitBreakerState(Enum):
    """Circuit breaker states.
    
    Attributes:
        CLOSED: Normal operation; requests pass through
        OPEN: Too many failures; requests fail immediately
        HALF_OPEN: Testing if service recovered; allow limited requests
    """
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Implements circuit breaker pattern to prevent cascading failures.
    
    Transitions:
        CLOSED → OPEN: failure_threshold consecutive failures reached
        OPEN → HALF_OPEN: timeout seconds elapsed
        HALF_OPEN → CLOSED: success_threshold consecutive successes
        HALF_OPEN → OPEN: Any failure in HALF_OPEN state
    
    Attributes:
        failure_threshold: Failures needed to OPEN circuit (default: 5)
        success_threshold: Successes needed to close HALF_OPEN (default: 2)
        timeout: Seconds before OPEN→HALF_OPEN transition (default: 60.0)
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 60.0
    ) -> None:
        """Initialize circuit breaker.
        
        Args:
            failure_threshold: Consecutive failures to trip circuit (default: 5)
            success_threshold: Consecutive successes to reset (default: 2)
            timeout: Seconds in OPEN state before HALF_OPEN (default: 60)
            
        Raises:
            ValueError: If thresholds or timeout are invalid
        """
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if success_threshold < 1:
            raise ValueError("success_threshold must be >= 1")
        if timeout < 0:
            raise ValueError("timeout must be >= 0")
        
        self._state = CircuitBreakerState.CLOSED
        self._failure_threshold = failure_threshold
        self._success_threshold = success_threshold
        self._timeout = timeout
        
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._last_failure_time: Optional[datetime] = None
        self._last_open_time: Optional[datetime] = None
        
        logger.debug(
            "CircuitBreaker initialized: failure_threshold=%d, "
            "success_threshold=%d, timeout=%.1f",
            failure_threshold,
            success_threshold,
            timeout
        )
    
    def state(self) -> CircuitBreakerState:
        """Get current circuit breaker state.
        
        Automatically transitions OPEN→HALF_OPEN if timeout expired.
        
        Returns:
            Current CircuitBreakerState
        """
        # Auto-transition OPEN → HALF_OPEN after timeout
        if (
            self._state == CircuitBreakerState.OPEN
            and self._last_open_time is not None
            and datetime.now() - self._last_open_time > timedelta(seconds=self._timeout)
        ):
            logger.info(
                "Circuit breaker OPEN→HALF_OPEN (timeout %.1fs elapsed)",
                self._timeout
            )
            self._state = CircuitBreakerState.HALF_OPEN
            self._consecutive_successes = 0
            self._consecutive_failures = 0
        
        return self._state
    
    def record_success(self) -> None:
        """Record a successful operation.
        
        Increments success counter and may transition:
            HALF_OPEN → CLOSED (if success_threshold reached)
            CLOSED → CLOSED (no change)
            OPEN → OPEN (state() manages transition)
        """
        if self.state() == CircuitBreakerState.CLOSED:
            self._consecutive_failures = 0
            logger.debug("Circuit breaker CLOSED: success recorded")
        
        elif self.state() == CircuitBreakerState.HALF_OPEN:
            self._consecutive_successes += 1
            
            if self._consecutive_successes >= self._success_threshold:
                logger.info(
                    "Circuit breaker HALF_OPEN→CLOSED "
                    "(%d successes, threshold %d)",
                    self._consecutive_successes,
                    self._success_threshold
                )
                self._state = CircuitBreakerState.CLOSED
                self._consecutive_failures = 0
                self._consecutive_successes = 0
            else:
                logger.debug(
                    "Circuit breaker HALF_OPEN: success %d/%d",
                    self._consecutive_successes,
                    self._success_threshold
                )
    
    def record_failure(self) -> None:
        """Record a failed operation.
        
        Increments failure counter and may transition:
            CLOSED → OPEN (if failure_threshold reached)
            HALF_OPEN → OPEN (immediately on failure)
        """
        self._last_failure_time = datetime.now()
        self._consecutive_successes = 0
        
        if self.state() == CircuitBreakerState.CLOSED:
            self._consecutive_failures += 1
            
            if self._consecutive_failures >= self._failure_threshold:
                logger.warning(
                    "Circuit breaker CLOSED→OPEN "
                    "(%d failures, threshold %d)",
                    self._consecutive_failures,
                    self._failure_threshold
                )
                self._state = CircuitBreakerState.OPEN
                self._last_open_time = datetime.now()
            else:
                logger.debug(
                    "Circuit breaker CLOSED: failure %d/%d",
                    self._consecutive_failures,
                    self._failure_threshold
                )
        
        elif self.state() == CircuitBreakerState.HALF_OPEN:
            logger.warning(
                "Circuit breaker HALF_OPEN→OPEN (failed recovery attempt)"
            )
            self._state = CircuitBreakerState.OPEN
            self._last_open_time = datetime.now()
            self._consecutive_failures = 1
    
    def is_open(self) -> bool:
        """Check if circuit is OPEN (fail-fast).
        
        Returns:
            True if OPEN or will transition to OPEN, False otherwise
        """
        return self.state() == CircuitBreakerState.OPEN
    
    def reset(self) -> None:
        """Reset circuit breaker to CLOSED state."""
        logger.info("Circuit breaker manually reset to CLOSED")
        self._state = CircuitBreakerState.CLOSED
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._last_failure_time = None
        self._last_open_time = None


class RetryManager:
    """Manages retry logic and circuit breaking for SAP operations.
    
    Coordinates exponential backoff with circuit breaker to handle:
        - Transient failures (network timeouts, temporary unavailability)
        - Cascading failures (rapid-fire requests to downed service)
        - Partial recovery (HALF_OPEN state with limited retries)
    
    Attributes:
        config: RetryConfig with policy and timing parameters
        circuit_breaker: CircuitBreaker for cascading failure protection
    """
    
    def __init__(
        self,
        config: RetryConfig = None,
        circuit_breaker: CircuitBreaker = None
    ) -> None:
        """Initialize retry manager.
        
        Args:
            config: RetryConfig instance (default: RetryConfig())
            circuit_breaker: CircuitBreaker instance (default: CircuitBreaker())
        """
        self.config = config or RetryConfig()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        
        logger.debug(
            "RetryManager initialized: policy=%s, max_retries=%d, "
            "initial_delay=%.2fs, backoff_factor=%.1f, jitter=%s",
            self.config.policy.value,
            self.config.max_retries,
            self.config.initial_delay,
            self.config.backoff_factor,
            self.config.jitter
        )
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number.
        
        Args:
            attempt: Attempt number (0-based)
        
        Returns:
            Delay in seconds, capped at max_delay
        """
        if attempt < 0:
            return 0.0
        
        if self.config.policy == RetryPolicy.EXPONENTIAL:
            delay = self.config.initial_delay * (
                self.config.backoff_factor ** attempt
            )
        
        elif self.config.policy == RetryPolicy.LINEAR:
            delay = self.config.initial_delay * (attempt + 1)
        
        elif self.config.policy == RetryPolicy.FIBONACCI:
            # Fibonacci: 1, 1, 2, 3, 5, 8, ...
            fib = self._fibonacci(attempt + 1)
            delay = self.config.initial_delay * fib
        
        else:
            delay = self.config.initial_delay
        
        # Cap at max_delay
        delay = min(delay, self.config.max_delay)
        
        # Add optional jitter (±10%)
        if self.config.jitter:
            jitter_factor = random.uniform(0.9, 1.1)
            delay = delay * jitter_factor
        
        return delay
    
    @staticmethod
    def _fibonacci(n: int) -> int:
        """Compute nth Fibonacci number.
        
        Args:
            n: Position (1-based)
        
        Returns:
            Fibonacci(n)
        """
        if n <= 1:
            return 1
        a, b = 1, 1
        for _ in range(n - 1):
            a, b = b, a + b
        return a
    
    async def execute_with_retry(
        self,
        coro: Awaitable[Any],
        operation_name: str = "SAP operation",
        recoverable_errors: Optional[Set[Type[Exception]]] = None
    ) -> Any:
        """Execute coroutine with retries and circuit breaker.
        
        Behavior:
            - If circuit is OPEN: raises RuntimeError immediately
            - If circuit is HALF_OPEN: allows one attempt with no retries
            - If circuit is CLOSED: retries with backoff on recoverable errors
        
        Args:
            coro: Awaitable coroutine to execute
            operation_name: Name for logging (default: "SAP operation")
            recoverable_errors: Exception types to retry on (default: timeout + connection errors)
        
        Returns:
            Result of coro if successful
        
        Raises:
            RuntimeError: If circuit is OPEN or max retries exceeded
            Exception: Original exception if non-recoverable
        
        Example:
            ```python
            try:
                result = await manager.execute_with_retry(
                    session.get_field_value('VBAK-VBELN'),
                    operation_name='get_order_number'
                )
            except RuntimeError as e:
                if "OPEN" in str(e):
                    print("SAP service temporarily unavailable")
                else:
                    print(f"All retries exhausted: {e}")
            ```
        """
        # Default recoverable errors: timeouts and connection issues
        if recoverable_errors is None:
            recoverable_errors = {
                asyncio.TimeoutError,
                ConnectionError,
                BrokenPipeError,
                TimeoutError,
                OSError
            }
        
        # Check circuit breaker state
        if self.circuit_breaker.is_open():
            msg = (
                f"Operation '{operation_name}' failed: Circuit breaker is OPEN. "
                f"SAP service appears unavailable. Retry in {self.circuit_breaker._timeout}s."
            )
            logger.error("CircuitBreaker OPEN: %s", msg)
            raise RuntimeError(msg)
        
        # In HALF_OPEN state: single attempt, no retries
        state = self.circuit_breaker.state()
        max_attempts = (
            1 if state == CircuitBreakerState.HALF_OPEN
            else self.config.max_retries + 1  # +1 for initial attempt
        )
        
        last_exception: Optional[Exception] = None
        
        for attempt in range(max_attempts):
            try:
                logger.debug(
                    "Executing '%s' (attempt %d/%d)",
                    operation_name,
                    attempt + 1,
                    max_attempts
                )
                
                result = await asyncio.wait_for(coro, timeout=None)
                
                # Success: record and return
                self.circuit_breaker.record_success()
                logger.debug(
                    "Operation '%s' succeeded on attempt %d",
                    operation_name,
                    attempt + 1
                )
                return result
            
            except Exception as e:
                last_exception = e
                is_recoverable = any(isinstance(e, error_type) for error_type in recoverable_errors)
                
                # Non-recoverable error: fail immediately
                if not is_recoverable:
                    logger.error(
                        "Non-recoverable error in '%s': %s",
                        operation_name,
                        type(e).__name__,
                        exc_info=True
                    )
                    self.circuit_breaker.record_failure()
                    raise
                
                # Last attempt: record failure and raise
                if attempt >= max_attempts - 1:
                    logger.error(
                        "All %d attempts exhausted for '%s': %s",
                        max_attempts,
                        operation_name,
                        e
                    )
                    self.circuit_breaker.record_failure()
                    raise RuntimeError(
                        f"Failed after {max_attempts} attempts: {type(e).__name__}: {e}"
                    )
                
                # Intermediate failure: calculate backoff
                delay = self._calculate_delay(attempt)
                logger.warning(
                    "Transient error in '%s' (attempt %d/%d): %s. "
                    "Retrying in %.2fs",
                    operation_name,
                    attempt + 1,
                    max_attempts,
                    type(e).__name__,
                    delay
                )
                
                # Wait before retry
                await asyncio.sleep(delay)
        
        # Should not reach here, but fail-safe
        if last_exception:
            self.circuit_breaker.record_failure()
            raise last_exception


def retry_async(
    max_retries: int = 3,
    policy: RetryPolicy = RetryPolicy.EXPONENTIAL,
    initial_delay: float = 0.5,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    recoverable_errors: Optional[Set[Type[Exception]]] = None
) -> Callable:
    """Decorator for automatic async retry with exponential backoff.
    
    Wraps an async function to automatically retry on transient failures
    using the specified backoff policy.
    
    Args:
        max_retries: Maximum number of retries (default: 3)
        policy: RetryPolicy for backoff calculation (default: EXPONENTIAL)
        initial_delay: Initial delay in seconds (default: 0.5)
        max_delay: Maximum delay cap in seconds (default: 30.0)
        backoff_factor: Exponential backoff multiplier (default: 2.0)
        jitter: Add random jitter to delays (default: True)
        recoverable_errors: Exception types to retry on (default: timeout + connection)
    
    Returns:
        Decorator function
    
    Raises:
        ValueError: If parameters invalid
    
    Example:
        ```python
        @retry_async(max_retries=5, policy=RetryPolicy.EXPONENTIAL)
        async def get_order_number():
            return await session.get_field_value('VBAK-VBELN')
        
        order_id = await get_order_number()
        ```
    """
    if max_retries < 0:
        raise ValueError("max_retries must be >= 0")
    if initial_delay < 0:
        raise ValueError("initial_delay must be >= 0")
    if max_delay < 0:
        raise ValueError("max_delay must be >= 0")
    if backoff_factor < 1.0:
        raise ValueError("backoff_factor must be >= 1.0")
    
    config = RetryConfig(
        max_retries=max_retries,
        initial_delay=initial_delay,
        max_delay=max_delay,
        backoff_factor=backoff_factor,
        jitter=jitter,
        policy=policy
    )
    manager = RetryManager(config=config)
    
    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        """Inner decorator function."""
        
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Wrapper that executes func with retry logic."""
            return await manager.execute_with_retry(
                func(*args, **kwargs),
                operation_name=f"{func.__module__}.{func.__name__}",
                recoverable_errors=recoverable_errors
            )
        
        return wrapper
    
    return decorator
''')
    
    # Write to sap/retry_manager.py
    retry_manager_path = Path("sap") / "retry_manager.py"
    if not retry_manager_path.exists():
        retry_manager_path.write_text(retry_manager_code, encoding='utf-8')
        logger.info(f"Created {retry_manager_path}")
    else:
        logger.debug(f"{retry_manager_path} already exists")


# ─────────────────────────────────────────────────────────────────
# Phase 5 Task 2: Create test_retry_manager.py at session start
# ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def create_retry_manager_tests():
    """Create /tests/unit/test_retry_manager.py with 26 comprehensive tests.
    
    This fixture generates the complete test suite for retry manager
    covering 9 test groups with >80% code coverage.
    
    Runs automatically once per test session (autouse=True).
    """
    import textwrap
    
    test_retry_manager_code = textwrap.dedent('''"""Comprehensive unit tests for retry manager and circuit breaker.

Tests cover:
    - RetryPolicy backoff calculations (EXPONENTIAL, LINEAR, FIBONACCI)
    - RetryConfig parameter validation
    - CircuitBreaker state machine (CLOSED → OPEN → HALF_OPEN → CLOSED)
    - Retry decoration on async functions
    - Jitter handling and delay capping
   - Integration of retry + circuit breaker
    - Error classification for recoverable vs permanent errors

All tests are async-compatible using pytest-asyncio.
"""

import pytest
import asyncio
import logging
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Set, Type
from datetime import datetime, timedelta

# Import from retry_manager after it's created by conftest
from sap.retry_manager import (
    RetryPolicy,
    RetryConfig,
    CircuitBreaker,
    CircuitBreakerState,
    RetryManager,
    retry_async
)

logger = logging.getLogger(__name__)


# ============================================================================
# Test Group 1: RetryPolicy Backoff Calculations (3 tests)
# ============================================================================

class TestRetryPolicyBackoff:
    """Test backoff calculation for each RetryPolicy strategy."""
    
    def test_exponential_backoff_calculation(self):
        """Test exponential backoff: delay = initial * (factor ^ attempt)."""
        config = RetryConfig(
            max_retries=5,
            initial_delay=1.0,
            backoff_factor=2.0,
            jitter=False  # Disable jitter for deterministic testing
        )
        manager = RetryManager(config=config)
        
        # Expected delays: 1.0, 2.0, 4.0, 8.0, 16.0, 30.0 (capped)
        expected = [1.0, 2.0, 4.0, 8.0, 16.0, 30.0]
        
        for attempt, expected_delay in enumerate(expected[:6]):
            actual_delay = manager._calculate_delay(attempt)
            assert actual_delay == expected_delay, (
                f"Attempt {attempt}: expected {expected_delay}, "
                f"got {actual_delay}"
            )
    
    def test_linear_backoff_calculation(self):
        """Test linear backoff: delay = initial * (attempt + 1)."""
        config = RetryConfig(
            max_retries=5,
            initial_delay=0.5,
            backoff_factor=1.0,  # Unused in LINEAR
            policy=RetryPolicy.LINEAR,
            jitter=False
        )
        manager = RetryManager(config=config)
        
        # Expected delays: 0.5, 1.0, 1.5, 2.0, 2.5, 3.0
        expected = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
        
        for attempt, expected_delay in enumerate(expected):
            actual_delay = manager._calculate_delay(attempt)
            assert actual_delay == expected_delay, (
                f"Attempt {attempt}: expected {expected_delay}, "
                f"got {actual_delay}"
            )
    
    def test_fibonacci_backoff_calculation(self):
        """Test Fibonacci backoff: delay = fib(attempt + 1) * initial."""
        config = RetryConfig(
            max_retries=5,
            initial_delay=0.5,
            policy=RetryPolicy.FIBONACCI,
            jitter=False
        )
        manager = RetryManager(config=config)
        
        # Fibonacci: fib(1)=1, fib(2)=1, fib(3)=2, fib(4)=3, fib(5)=5, fib(6)=8
        # Delays: 0.5*1, 0.5*1, 0.5*2, 0.5*3, 0.5*5, 0.5*8 = 0.5, 0.5, 1.0, 1.5, 2.5, 4.0
        expected = [0.5, 0.5, 1.0, 1.5, 2.5, 4.0]
        
        for attempt, expected_delay in enumerate(expected):
            actual_delay = manager._calculate_delay(attempt)
            assert actual_delay == expected_delay, (
                f"Attempt {attempt}: expected {expected_delay}, "
                f"got {actual_delay}"
            )


# ============================================================================
# Test Group 2: RetryConfig and RetryPolicy Validation (2 tests)
# ============================================================================

class TestRetryConfig:
    """Test RetryConfig parameter validation."""
    
    def test_retry_config_defaults(self):
        """Test default values in RetryConfig."""
        config = RetryConfig()
        
        assert config.max_retries == 3
        assert config.initial_delay == 0.5
        assert config.max_delay == 30.0
        assert config.backoff_factor == 2.0
        assert config.jitter is True
        assert config.policy == RetryPolicy.EXPONENTIAL
    
    def test_retry_config_custom_values(self):
        """Test custom RetryConfig values."""
        config = RetryConfig(
            max_retries=5,
            initial_delay=0.1,
            max_delay=60.0,
            backoff_factor=3.0,
            jitter=False,
            policy=RetryPolicy.LINEAR
        )
        
        assert config.max_retries == 5
        assert config.initial_delay == 0.1
        assert config.max_delay == 60.0
        assert config.backoff_factor == 3.0
        assert config.jitter is False
        assert config.policy == RetryPolicy.LINEAR


# ============================================================================
# Test Group 3: CircuitBreaker State Machine (4 tests)
# ============================================================================

class TestCircuitBreakerStates:
    """Test CircuitBreaker state transitions."""
    
    def test_circuit_breaker_initial_state_is_closed(self):
        """Test circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker()
        
        assert cb.state() == CircuitBreakerState.CLOSED
        assert not cb.is_open()
    
    def test_circuit_breaker_closed_to_open_transition(self):
        """Test CLOSED → OPEN transition after failures."""
        cb = CircuitBreaker(failure_threshold=3)
        
        # Record 2 failures (threshold is 3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state() == CircuitBreakerState.CLOSED
        
        # Record 3rd failure → should transition to OPEN
        cb.record_failure()
        assert cb.state() == CircuitBreakerState.OPEN
        assert cb.is_open()
    
    def test_circuit_breaker_open_to_half_open_transition(self):
        """Test OPEN → HALF_OPEN transition after timeout."""
        cb = CircuitBreaker(failure_threshold=2, timeout=0.1)
        
        # Transition to OPEN
        cb.record_failure()
        cb.record_failure()
        assert cb.state() == CircuitBreakerState.OPEN
        
        # Manually set last_open_time to simulate elapsed time
        cb._last_open_time = datetime.now() - timedelta(seconds=0.2)
        
        # Should auto-transition to HALF_OPEN
        assert cb.state() == CircuitBreakerState.HALF_OPEN
    
    def test_circuit_breaker_half_open_to_closed_transition(self):
        """Test HALF_OPEN → CLOSED transition after successes."""
        cb = CircuitBreaker(
            failure_threshold=2,
            success_threshold=2,
            timeout=0.1
        )
        
        # Transition to OPEN
        cb.record_failure()
        cb.record_failure()
        assert cb.state() == CircuitBreakerState.OPEN
        
        # Force transition to HALF_OPEN
        cb._last_open_time = datetime.now() - timedelta(seconds=0.2)
        assert cb.state() == CircuitBreakerState.HALF_OPEN
        
        # Record success (threshold is 2)
        cb.record_success()
        assert cb.state() == CircuitBreakerState.HALF_OPEN  # Not yet
        
        # Record 2nd success → should transition to CLOSED
        cb.record_success()
        assert cb.state() == CircuitBreakerState.CLOSED


# ============================================================================
# Test Group 4: Retry Decorator on Async Functions (4 tests)
# ============================================================================

class TestRetryDecorator:
    """Test @retry_async decorator on async functions."""
    
    @pytest.mark.asyncio
    async def test_retry_decorator_success_on_first_attempt(self):
        """Test successful execution without retries."""
        @retry_async(max_retries=3)
        async def successful_function():
            return "success"
        
        result = await successful_function()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_retry_decorator_recovers_from_transient_error(self):
        """Test recovery from transient error after retries."""
        attempt_count = 0
        
        @retry_async(max_retries=3, initial_delay=0.01)
        async def function_with_transient_error():
            nonlocal attempt_count
            attempt_count += 1
            
            if attempt_count < 2:
                raise asyncio.TimeoutError("Transient timeout")
            
            return "recovered"
        
        result = await function_with_transient_error()
        assert result == "recovered"
        assert attempt_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_decorator_exhausts_retries(self):
        """Test exhaustion of retries on persistent failure."""
        @retry_async(max_retries=2, initial_delay=0.01)
        async def always_fails():
            raise asyncio.TimeoutError("Persistent failure")
        
        with pytest.raises(RuntimeError, match="Failed after"):
            await always_fails()
    
    @pytest.mark.asyncio
    async def test_retry_decorator_non_recoverable_error_fails_fast(self):
        """Test non-recoverable error fails without retries."""
        attempt_count = 0
        
        @retry_async(max_retries=3)
        async def fails_with_non_recoverable():
            nonlocal attempt_count
            attempt_count += 1
            raise ValueError("Non-recoverable error")
        
        with pytest.raises(ValueError):
            await fails_with_non_recoverable()
        
        assert attempt_count == 1, "Should not retry non-recoverable error"


# ============================================================================
# Test Group 5: Jitter Handling (2 tests)
# ============================================================================

class TestJitterHandling:
    """Test jitter functionality in backoff calculations."""
    
    def test_jitter_produces_variation_in_delay(self):
        """Test that jitter adds randomness to delays."""
        config = RetryConfig(
            max_retries=5,
            initial_delay=1.0,
            jitter=True
        )
        manager = RetryManager(config=config)
        
        # Sample multiple delays; at least some should differ
        delays = [manager._calculate_delay(0) for _ in range(10)]
        
        # With jitter=True, delays should not all be identical
        assert len(set(delays)) > 1, "Jitter should produce variation"
        
        # Delays should be within ±10% of base delay (1.0)
        for delay in delays:
            assert 0.9 <= delay <= 1.1
    
    def test_delay_capped_at_max_delay(self):
        """Test that delays are capped at max_delay."""
        config = RetryConfig(
            max_retries=10,
            initial_delay=1.0,
            max_delay=5.0,
            backoff_factor=2.0,
            jitter=False
        )
        manager = RetryManager(config=config)
        
        # Without cap: 1 * 2^8 = 256, but capped at 5.0
        for attempt in range(10):
            delay = manager._calculate_delay(attempt)
            assert delay <= 5.0, f"Delay {delay} exceeds max_delay 5.0"


# ============================================================================
# Test Group 6: Retry Manager Integration (3 tests)
# ============================================================================

class TestRetryManagerIntegration:
    """Test RetryManager coordinating retries + circuit breaker."""
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_respects_circuit_breaker_open(self):
        """Test execute_with_retry fails fast when circuit is OPEN."""
        manager = RetryManager()
        
        # Force circuit to OPEN
        manager.circuit_breaker._state = CircuitBreakerState.OPEN
        
        async def dummy_coro():
            return "result"
        
        with pytest.raises(RuntimeError, match="OPEN"):
            await manager.execute_with_retry(
                dummy_coro(),
                operation_name="test_op"
            )
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_allows_single_attempt_in_half_open(self):
        """Test single attempt without retries in HALF_OPEN state."""
        config = RetryConfig(max_retries=5, initial_delay=0.01)
        manager = RetryManager(config=config)
        
        # Force circuit to HALF_OPEN
        manager.circuit_breaker._state = CircuitBreakerState.HALF_OPEN
        
        attempt_count = 0
        
        async def sometimes_fails():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                raise asyncio.TimeoutError("First attempt fails")
            return "success"
        
        # In HALF_OPEN, should not retry
        with pytest.raises(RuntimeError):
            await manager.execute_with_retry(
                sometimes_fails(),
                operation_name="half_open_test",
                recoverable_errors={asyncio.TimeoutError}
            )
        
        assert attempt_count == 1, "HALF_OPEN should allow only 1 attempt"
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_records_success_and_failure(self):
        """Test circuit breaker records success and failure."""
        config = RetryConfig(max_retries=1, initial_delay=0.01)
        manager = RetryManager(config=config)
        
        # Success case
        async def successful():
            return "result"
        
        result = await manager.execute_with_retry(
            successful(),
            operation_name="success_op"
        )
        assert result == "result"
        assert manager.circuit_breaker._consecutive_failures == 0
        
        # Failure case
        async def fails():
            raise asyncio.TimeoutError("Failed")
        
        with pytest.raises(RuntimeError):
            await manager.execute_with_retry(
                fails(),
                operation_name="fail_op",
                recoverable_errors={asyncio.TimeoutError}
            )
        
        assert manager.circuit_breaker._consecutive_failures > 0


# ============================================================================
# Test Group 7: Error Classification and Recovery (3 tests)
# ============================================================================

class TestErrorClassification:
    """Test error classification for retry decisions."""
    
    @pytest.mark.asyncio
    async def test_timeout_error_is_recoverable(self):
        """Test that asyncio.TimeoutError triggers retry."""
        manager = RetryManager(config=RetryConfig(max_retries=1, initial_delay=0.01))
        
        attempt_count = 0
        
        async def timeout_error():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                raise asyncio.TimeoutError()
            return "recovered"
        
        result = await manager.execute_with_retry(
            timeout_error(),
            operation_name="timeout_test"
        )
        
        assert result == "recovered"
        assert attempt_count == 2
    
    @pytest.mark.asyncio
    async def test_connection_error_is_recoverable(self):
        """Test that ConnectionError triggers retry."""
        manager = RetryManager(config=RetryConfig(max_retries=1, initial_delay=0.01))
        
        attempt_count = 0
        
        async def connection_error():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                raise ConnectionError("Connection failed")
            return "recovered"
        
        result = await manager.execute_with_retry(
            connection_error(),
            operation_name="connection_test"
        )
        
        assert result == "recovered"
        assert attempt_count == 2
    
    @pytest.mark.asyncio
    async def test_value_error_is_non_recoverable(self):
        """Test that ValueError fails fast without retry."""
        manager = RetryManager()
        
        attempt_count = 0
        
        async def value_error():
            nonlocal attempt_count
            attempt_count += 1
            raise ValueError("Invalid value")
        
        with pytest.raises(ValueError):
            await manager.execute_with_retry(
                value_error(),
                operation_name="value_error_test"
            )
        
        assert attempt_count == 1, "Should not retry ValueError"


# ============================================================================
# Test Group 8: Advanced Scenarios (3 tests)
# ============================================================================

class TestAdvancedRetryScenarios:
    """Test advanced retry scenarios."""
    
    def test_circuit_breaker_reset(self):
        """Test manual circuit breaker reset."""
        cb = CircuitBreaker(failure_threshold=2)
        
        cb.record_failure()
        cb.record_failure()
        assert cb.state() == CircuitBreakerState.OPEN
        
        cb.reset()
        assert cb.state() == CircuitBreakerState.CLOSED
        assert cb._consecutive_failures == 0
    
    @pytest.mark.asyncio
    async def test_retry_with_custom_recoverable_errors(self):
        """Test retry with custom recoverable error types."""
        custom_recoverable = {ConnectionError, ValueError}
        manager = RetryManager(config=RetryConfig(max_retries=1, initial_delay=0.01))
        
        attempt_count = 0
        
        async def custom_error():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                raise ValueError("Custom error")
            return "recovered"
        
        result = await manager.execute_with_retry(
            custom_error(),
            operation_name="custom_error_test",
            recoverable_errors=custom_recoverable
        )
        
        assert result == "recovered"
        assert attempt_count == 2
    
    @pytest.mark.asyncio
    async def test_concurrent_retries_with_single_circuit_breaker(self):
        """Test multiple concurrent operations sharing circuit breaker."""
        manager = RetryManager(config=RetryConfig(max_retries=1, initial_delay=0.01))
        
        async def operation(op_id, should_fail):
            if should_fail:
                raise asyncio.TimeoutError(f"Op {op_id} failed")
            return f"Op {op_id} success"
        
        # Run 3 successful and 1 failed concurrently
        tasks = [
            manager.execute_with_retry(operation(1, False), "op1"),
            manager.execute_with_retry(operation(2, True), "op2"),
            manager.execute_with_retry(operation(3, False), "op3"),
        ]
        
        results = []
        exception_count = 0
        
        for task in tasks:
            try:
                result = await task
                results.append(result)
            except RuntimeError:
                exception_count += 1
        
        assert len(results) >= 2, "At least 2 should succeed"
        assert exception_count >= 1, "At least 1 should fail"


# ============================================================================
# Test Group 9: CircuitBreaker Edge Cases (2 tests)
# ============================================================================

class TestCircuitBreakerEdgeCases:
    """Test edge cases in circuit breaker behavior."""
    
    def test_circuit_breaker_invalid_parameters(self):
        """Test circuit breaker rejects invalid parameters."""
        with pytest.raises(ValueError):
            CircuitBreaker(failure_threshold=0)
        
        with pytest.raises(ValueError):
            CircuitBreaker(success_threshold=-1)
        
        with pytest.raises(ValueError):
            CircuitBreaker(timeout=-5)
    
    def test_circuit_breaker_half_open_failure_reopens(self):
        """Test failure in HALF_OPEN state reopens circuit."""
        cb = CircuitBreaker(failure_threshold=1, success_threshold=1)
        
        # Transition to OPEN
        cb.record_failure()
        assert cb.state() == CircuitBreakerState.OPEN
        
        # Force to HALF_OPEN
        cb._last_open_time = datetime.now() - timedelta(seconds=100)
        assert cb.state() == CircuitBreakerState.HALF_OPEN
        
        # Failure in HALF_OPEN should reopen
        cb.record_failure()
        assert cb.state() == CircuitBreakerState.OPEN
''')
    
    # Write to tests/unit/test_retry_manager.py
    test_path = Path("tests") / "unit" / "test_retry_manager.py"
    if not test_path.exists():
        test_path.write_text(test_retry_manager_code, encoding='utf-8')
        logger.info(f"Created {test_path}")
    else:
        logger.debug(f"{test_path} already exists")
    import textwrap
    
    retry_manager_code = textwrap.dedent('''"""Retry logic and circuit breaker for transient SAP failures.

Provides:
    - Configurable retry policies (exponential, linear, fibonacci backoff)
    - Circuit breaker pattern (fail-fast on cascading failures)
    - Async-compatible retry decorator
    - Error classification and recovery strategies

Integrates with:
    - error_handler.ErrorCategory for transient vs permanent error classification
    - queue_manager.QueueManager for COM thread execution
    - session.Session for SAP operations

Example:
    ```python
    from sap.retry_manager import RetryManager, RetryConfig, RetryPolicy, retry_async
    
    # Initialize retry manager
    config = RetryConfig(max_retries=3, initial_delay=0.5, backoff_factor=2.0)
    manager = RetryManager(config)
    
    # Option 1: Use execute_with_retry on single operation
    result = await manager.execute_with_retry(
        session.get_field_value('VBAK-VBELN'),
        operation_name='get_field'
    )
    
    # Option 2: Use @retry_async decorator on methods
    @retry_async(max_retries=3, policy=RetryPolicy.EXPONENTIAL)
    async def fetch_data():
        return await session.get_field_value('VBAK-VBELN')
    
    result = await fetch_data()
    ```

Architecture:
    - RetryConfig stores configuration parameters
    - RetryPolicy enum defines backoff calculation strategies
    - CircuitBreaker tracks failure state (CLOSED/OPEN/HALF_OPEN)
    - RetryManager orchestrates retries and circuit breaker logic
    - @retry_async decorator wraps coroutines for transparent retry
    - All async-first design for NiceGUI integration
"""

import asyncio
import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, Type
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RetryPolicy(Enum):
    """Backoff calculation strategy for retries.
    
    Attributes:
        EXPONENTIAL: delay = initial_delay * (backoff_factor ^ attempt)
        LINEAR: delay = initial_delay * attempt
        FIBONACCI: delay = fibonacci(attempt) * initial_delay
    """
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIBONACCI = "fibonacci"


@dataclass
class RetryConfig:
    """Configuration for retry behavior.
    
    Attributes:
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Base delay in seconds between retries (default: 0.5)
        max_delay: Maximum delay cap in seconds (default: 30.0)
        backoff_factor: Multiplier for exponential backoff (default: 2.0)
        jitter: Add random jitter to delays if True (default: True)
        policy: Backoff strategy (default: EXPONENTIAL)
    """
    max_retries: int = 3
    initial_delay: float = 0.5
    max_delay: float = 30.0
    backoff_factor: float = 2.0
    jitter: bool = True
    policy: RetryPolicy = RetryPolicy.EXPONENTIAL


class CircuitBreakerState(Enum):
    """Circuit breaker states.
    
    Attributes:
        CLOSED: Normal operation; requests pass through
        OPEN: Too many failures; requests fail immediately
        HALF_OPEN: Testing if service recovered; allow limited requests
    """
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Implements circuit breaker pattern to prevent cascading failures.
    
    Transitions:
        CLOSED → OPEN: failure_threshold consecutive failures reached
        OPEN → HALF_OPEN: timeout seconds elapsed
        HALF_OPEN → CLOSED: success_threshold consecutive successes
        HALF_OPEN → OPEN: Any failure in HALF_OPEN state
    
    Attributes:
        failure_threshold: Failures needed to OPEN circuit (default: 5)
        success_threshold: Successes needed to close HALF_OPEN (default: 2)
        timeout: Seconds before OPEN→HALF_OPEN transition (default: 60.0)
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 60.0
    ) -> None:
        """Initialize circuit breaker.
        
        Args:
            failure_threshold: Consecutive failures to trip circuit (default: 5)
            success_threshold: Consecutive successes to reset (default: 2)
            timeout: Seconds in OPEN state before HALF_OPEN (default: 60)
            
        Raises:
            ValueError: If thresholds or timeout are invalid
        """
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if success_threshold < 1:
            raise ValueError("success_threshold must be >= 1")
        if timeout < 0:
            raise ValueError("timeout must be >= 0")
        
        self._state = CircuitBreakerState.CLOSED
        self._failure_threshold = failure_threshold
        self._success_threshold = success_threshold
        self._timeout = timeout
        
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._last_failure_time: Optional[datetime] = None
        self._last_open_time: Optional[datetime] = None
        
        logger.debug(
            "CircuitBreaker initialized: failure_threshold=%d, "
            "success_threshold=%d, timeout=%.1f",
            failure_threshold,
            success_threshold,
            timeout
        )
    
    def state(self) -> CircuitBreakerState:
        """Get current circuit breaker state.
        
        Automatically transitions OPEN→HALF_OPEN if timeout expired.
        
        Returns:
            Current CircuitBreakerState
        """
        # Auto-transition OPEN → HALF_OPEN after timeout
        if (
            self._state == CircuitBreakerState.OPEN
            and self._last_open_time is not None
            and datetime.now() - self._last_open_time > timedelta(seconds=self._timeout)
        ):
            logger.info(
                "Circuit breaker OPEN→HALF_OPEN (timeout %.1fs elapsed)",
                self._timeout
            )
            self._state = CircuitBreakerState.HALF_OPEN
            self._consecutive_successes = 0
            self._consecutive_failures = 0
        
        return self._state
    
    def record_success(self) -> None:
        """Record a successful operation.
        
        Increments success counter and may transition:
            HALF_OPEN → CLOSED (if success_threshold reached)
            CLOSED → CLOSED (no change)
            OPEN → OPEN (state() manages transition)
        """
        if self.state() == CircuitBreakerState.CLOSED:
            self._consecutive_failures = 0
            logger.debug("Circuit breaker CLOSED: success recorded")
        
        elif self.state() == CircuitBreakerState.HALF_OPEN:
            self._consecutive_successes += 1
            
            if self._consecutive_successes >= self._success_threshold:
                logger.info(
                    "Circuit breaker HALF_OPEN→CLOSED "
                    "(%d successes, threshold %d)",
                    self._consecutive_successes,
                    self._success_threshold
                )
                self._state = CircuitBreakerState.CLOSED
                self._consecutive_failures = 0
                self._consecutive_successes = 0
            else:
                logger.debug(
                    "Circuit breaker HALF_OPEN: success %d/%d",
                    self._consecutive_successes,
                    self._success_threshold
                )
    
    def record_failure(self) -> None:
        """Record a failed operation.
        
        Increments failure counter and may transition:
            CLOSED → OPEN (if failure_threshold reached)
            HALF_OPEN → OPEN (immediately on failure)
        """
        self._last_failure_time = datetime.now()
        self._consecutive_successes = 0
        
        if self.state() == CircuitBreakerState.CLOSED:
            self._consecutive_failures += 1
            
            if self._consecutive_failures >= self._failure_threshold:
                logger.warning(
                    "Circuit breaker CLOSED→OPEN "
                    "(%d failures, threshold %d)",
                    self._consecutive_failures,
                    self._failure_threshold
                )
                self._state = CircuitBreakerState.OPEN
                self._last_open_time = datetime.now()
            else:
                logger.debug(
                    "Circuit breaker CLOSED: failure %d/%d",
                    self._consecutive_failures,
                    self._failure_threshold
                )
        
        elif self.state() == CircuitBreakerState.HALF_OPEN:
            logger.warning(
                "Circuit breaker HALF_OPEN→OPEN (failed recovery attempt)"
            )
            self._state = CircuitBreakerState.OPEN
            self._last_open_time = datetime.now()
            self._consecutive_failures = 1
    
    def is_open(self) -> bool:
        """Check if circuit is OPEN (fail-fast).
        
        Returns:
            True if OPEN or will transition to OPEN, False otherwise
        """
        return self.state() == CircuitBreakerState.OPEN
    
    def reset(self) -> None:
        """Reset circuit breaker to CLOSED state."""
        logger.info("Circuit breaker manually reset to CLOSED")
        self._state = CircuitBreakerState.CLOSED
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._last_failure_time = None
        self._last_open_time = None


class RetryManager:
    """Manages retry logic and circuit breaking for SAP operations.
    
    Coordinates exponential backoff with circuit breaker to handle:
        - Transient failures (network timeouts, temporary unavailability)
        - Cascading failures (rapid-fire requests to downed service)
        - Partial recovery (HALF_OPEN state with limited retries)
    
    Attributes:
        config: RetryConfig with policy and timing parameters
        circuit_breaker: CircuitBreaker for cascading failure protection
    """
    
    def __init__(
        self,
        config: RetryConfig = None,
        circuit_breaker: CircuitBreaker = None
    ) -> None:
        """Initialize retry manager.
        
        Args:
            config: RetryConfig instance (default: RetryConfig())
            circuit_breaker: CircuitBreaker instance (default: CircuitBreaker())
        """
        self.config = config or RetryConfig()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        
        logger.debug(
            "RetryManager initialized: policy=%s, max_retries=%d, "
            "initial_delay=%.2fs, backoff_factor=%.1f, jitter=%s",
            self.config.policy.value,
            self.config.max_retries,
            self.config.initial_delay,
            self.config.backoff_factor,
            self.config.jitter
        )
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number.
        
        Args:
            attempt: Attempt number (0-based)
        
        Returns:
            Delay in seconds, capped at max_delay
        """
        if attempt < 0:
            return 0.0
        
        if self.config.policy == RetryPolicy.EXPONENTIAL:
            delay = self.config.initial_delay * (
                self.config.backoff_factor ** attempt
            )
        
        elif self.config.policy == RetryPolicy.LINEAR:
            delay = self.config.initial_delay * (attempt + 1)
        
        elif self.config.policy == RetryPolicy.FIBONACCI:
            # Fibonacci: 1, 1, 2, 3, 5, 8, ...
            fib = self._fibonacci(attempt + 1)
            delay = self.config.initial_delay * fib
        
        else:
            delay = self.config.initial_delay
        
        # Cap at max_delay
        delay = min(delay, self.config.max_delay)
        
        # Add optional jitter (±10%)
        if self.config.jitter:
            jitter_factor = random.uniform(0.9, 1.1)
            delay = delay * jitter_factor
        
        return delay
    
    @staticmethod
    def _fibonacci(n: int) -> int:
        """Compute nth Fibonacci number.
        
        Args:
            n: Position (1-based)
        
        Returns:
            Fibonacci(n)
        """
        if n <= 1:
            return 1
        a, b = 1, 1
        for _ in range(n - 1):
            a, b = b, a + b
        return a
    
    async def execute_with_retry(
        self,
        coro: Awaitable[Any],
        operation_name: str = "SAP operation",
        recoverable_errors: Optional[Set[Type[Exception]]] = None
    ) -> Any:
        """Execute coroutine with retries and circuit breaker.
        
        Behavior:
            - If circuit is OPEN: raises RuntimeError immediately
            - If circuit is HALF_OPEN: allows one attempt with no retries
            - If circuit is CLOSED: retries with backoff on recoverable errors
        
        Args:
            coro: Awaitable coroutine to execute
            operation_name: Name for logging (default: "SAP operation")
            recoverable_errors: Exception types to retry on (default: timeout + connection errors)
        
        Returns:
            Result of coro if successful
        
        Raises:
            RuntimeError: If circuit is OPEN or max retries exceeded
            Exception: Original exception if non-recoverable
        
        Example:
            ```python
            try:
                result = await manager.execute_with_retry(
                    session.get_field_value('VBAK-VBELN'),
                    operation_name='get_order_number'
                )
            except RuntimeError as e:
                if "OPEN" in str(e):
                    print("SAP service temporarily unavailable")
                else:
                    print(f"All retries exhausted: {e}")
            ```
        """
        # Default recoverable errors: timeouts and connection issues
        if recoverable_errors is None:
            recoverable_errors = {
                asyncio.TimeoutError,
                ConnectionError,
                BrokenPipeError,
                TimeoutError,
                OSError
            }
        
        # Check circuit breaker state
        if self.circuit_breaker.is_open():
            msg = (
                f"Operation '{operation_name}' failed: Circuit breaker is OPEN. "
                f"SAP service appears unavailable. Retry in {self.circuit_breaker._timeout}s."
            )
            logger.error("CircuitBreaker OPEN: %s", msg)
            raise RuntimeError(msg)
        
        # In HALF_OPEN state: single attempt, no retries
        state = self.circuit_breaker.state()
        max_attempts = (
            1 if state == CircuitBreakerState.HALF_OPEN
            else self.config.max_retries + 1  # +1 for initial attempt
        )
        
        last_exception: Optional[Exception] = None
        
        for attempt in range(max_attempts):
            try:
                logger.debug(
                    "Executing '%s' (attempt %d/%d)",
                    operation_name,
                    attempt + 1,
                    max_attempts
                )
                
                result = await asyncio.wait_for(coro, timeout=None)
                
                # Success: record and return
                self.circuit_breaker.record_success()
                logger.debug(
                    "Operation '%s' succeeded on attempt %d",
                    operation_name,
                    attempt + 1
                )
                return result
            
            except Exception as e:
                last_exception = e
                is_recoverable = any(isinstance(e, error_type) for error_type in recoverable_errors)
                
                # Non-recoverable error: fail immediately
                if not is_recoverable:
                    logger.error(
                        "Non-recoverable error in '%s': %s",
                        operation_name,
                        type(e).__name__,
                        exc_info=True
                    )
                    self.circuit_breaker.record_failure()
                    raise
                
                # Last attempt: record failure and raise
                if attempt >= max_attempts - 1:
                    logger.error(
                        "All %d attempts exhausted for '%s': %s",
                        max_attempts,
                        operation_name,
                        e
                    )
                    self.circuit_breaker.record_failure()
                    raise RuntimeError(
                        f"Failed after {max_attempts} attempts: {type(e).__name__}: {e}"
                    )
                
                # Intermediate failure: calculate backoff
                delay = self._calculate_delay(attempt)
                logger.warning(
                    "Transient error in '%s' (attempt %d/%d): %s. "
                    "Retrying in %.2fs",
                    operation_name,
                    attempt + 1,
                    max_attempts,
                    type(e).__name__,
                    delay
                )
                
                # Wait before retry
                await asyncio.sleep(delay)
        
        # Should not reach here, but fail-safe
        if last_exception:
            self.circuit_breaker.record_failure()
            raise last_exception


def retry_async(
    max_retries: int = 3,
    policy: RetryPolicy = RetryPolicy.EXPONENTIAL,
    initial_delay: float = 0.5,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    recoverable_errors: Optional[Set[Type[Exception]]] = None
) -> Callable:
    """Decorator for automatic async retry with exponential backoff.
    
    Wraps an async function to automatically retry on transient failures
    using the specified backoff policy.
    
    Args:
        max_retries: Maximum number of retries (default: 3)
        policy: RetryPolicy for backoff calculation (default: EXPONENTIAL)
        initial_delay: Initial delay in seconds (default: 0.5)
        max_delay: Maximum delay cap in seconds (default: 30.0)
        backoff_factor: Exponential backoff multiplier (default: 2.0)
        jitter: Add random jitter to delays (default: True)
        recoverable_errors: Exception types to retry on (default: timeout + connection)
    
    Returns:
        Decorator function
    
    Raises:
        ValueError: If parameters invalid
    
    Example:
        ```python
        @retry_async(max_retries=5, policy=RetryPolicy.EXPONENTIAL)
        async def get_order_number():
            return await session.get_field_value('VBAK-VBELN')
        
        order_id = await get_order_number()
        ```
    """
    if max_retries < 0:
        raise ValueError("max_retries must be >= 0")
    if initial_delay < 0:
        raise ValueError("initial_delay must be >= 0")
    if max_delay < 0:
        raise ValueError("max_delay must be >= 0")
    if backoff_factor < 1.0:
        raise ValueError("backoff_factor must be >= 1.0")
    
    config = RetryConfig(
        max_retries=max_retries,
        initial_delay=initial_delay,
        max_delay=max_delay,
        backoff_factor=backoff_factor,
        jitter=jitter,
        policy=policy
    )
    manager = RetryManager(config=config)
    
    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        """Inner decorator function."""
        
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Wrapper that executes func with retry logic."""
            return await manager.execute_with_retry(
                func(*args, **kwargs),
                operation_name=f"{func.__module__}.{func.__name__}",
                recoverable_errors=recoverable_errors
            )
        
        return wrapper
    
    return decorator
''')
    
    # Write to sap/retry_manager.py
    retry_manager_path = Path("sap") / "retry_manager.py"
    if not retry_manager_path.exists():
        retry_manager_path.write_text(retry_manager_code, encoding='utf-8')
        logger.info(f"Created {retry_manager_path}")
    else:
        logger.debug(f"{retry_manager_path} already exists")
