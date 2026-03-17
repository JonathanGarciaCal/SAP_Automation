# Testing Examples & Reference Code

This file contains test authoring reference material for the `testing-qa-engineer` agent (Mode B: Author Tests).

---

## Phase 1: Core Testing Infrastructure

**Module**: `/tests/conftest.py` (Pytest configuration)

```python
import pytest
from unittest.mock import MagicMock, patch
import sys

# Fixtures available to all tests

@pytest.fixture
def mock_sap_session():
    """Mock GuiSession COM object"""
    mock_session = MagicMock()

    # Configure mock behavior
    mock_session.Busy = False
    mock_session.ActiveWindow.ID = "[/app/workbench/window]"

    def find_by_id_side_effect(elem_id: str):
        """Mock FindById behavior"""
        if elem_id in ["[/app/nonexistent]"]:
            return None

        mock_elem = MagicMock()
        mock_elem.ID = elem_id
        mock_elem.Type = "GuiTextField"
        mock_elem.Value = "test_value"
        return mock_elem

    mock_session.FindById.side_effect = find_by_id_side_effect

    return mock_session

@pytest.fixture
def mock_sap_connection(mock_sap_session):
    """Mock SAPConnection object"""
    mock_conn = MagicMock()
    mock_conn.session = mock_sap_session
    return mock_conn

@pytest.fixture
def mock_config():
    """Mock AppConfig object"""
    return {
        "sap": {
            "client": "100",
            "lang": "EN",
        },
        "ui": {
            "port": 8000,
            "host": "127.0.0.1",
        },
        "logging_level": "DEBUG",
    }

@pytest.fixture
def temp_config_file(tmp_path):
    """Create temporary config file"""
    config_yaml = """
sap:
  client: "100"
  lang: "EN"
ui:
  port: 8000
  host: "127.0.0.1"
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_yaml)
    return config_file
```

**Module**: `/tests/test_com_bridge.py`

```python
import pytest
from sap.bridge import SAPComWorkerThread, ComRequest, ComResponse

class TestComBridge:
    """Test COM bridge threading and queue"""

    def test_com_request_creation(self):
        """ComRequest object created with valid schema"""
        req = ComRequest(
            id="test-123",
            method="GuiSession.FindById",
            args=["[/app/button]"],
            kwargs={},
            timeout_sec=30
        )

        assert req.id == "test-123"
        assert req.method == "GuiSession.FindById"

    def test_com_response_creation(self):
        """ComResponse object created and error handling"""
        resp = ComResponse(
            id="test-123",
            result="success",
            error=None,
            elapsed_ms=100
        )

        assert resp.id == "test-123"
        assert resp.result == "success"
        assert resp.error is None

    def test_com_response_with_error(self):
        """ComResponse captures error details"""
        resp = ComResponse(
            id="test-456",
            result=None,
            error={
                "code": "0x80028CA0",
                "message": "SAP server error",
                "traceback": "..."
            },
            elapsed_ms=5000
        )

        assert resp.error is not None
        assert "SAP server error" in resp.error["message"]

    @pytest.mark.asyncio
    async def test_worker_thread_startup(self, mock_sap_session):
        """COM worker thread initializes without error"""
        # (Would use threading fixtures here)
        pass
```

**Module**: `/tests/test_sap_session.py`

```python
import pytest
from unittest.mock import MagicMock
from sap.session import GuiSession, GuiElement

class TestGuiElement:
    """Test GuiElement wrapper"""

    def test_gui_element_properties(self):
        """GuiElement extracts COM object properties"""
        mock_com = MagicMock()
        mock_com.ID = "/app/button_ok"
        mock_com.Type = "GuiButton"
        mock_com.Text = "OK"

        elem = GuiElement(mock_com)

        assert elem.id == "/app/button_ok"
        assert elem.type == "GuiButton"
        assert elem.text == "OK"

    def test_gui_element_click(self):
        """GuiElement.click() calls Press()"""
        mock_com = MagicMock()
        elem = GuiElement(mock_com)

        elem.click()

        mock_com.Press.assert_called_once()

class TestGuiSession:
    """Test GuiSession wrapper"""

    def test_session_find_by_id(self, mock_sap_session):
        """Session.find_by_id returns GuiElement"""
        session = GuiSession(mock_sap_session)

        elem = session.find_by_id("[/app/button_ok]")

        assert elem is not None
        assert isinstance(elem, GuiElement)
        assert elem.id == "[/app/button_ok]"

    def test_session_find_by_id_not_found(self, mock_sap_session):
        """Session.find_by_id returns None if element not found"""
        # Override side_effect (not return_value) so it takes precedence
        mock_sap_session.FindById.side_effect = lambda elem_id: None

        session = GuiSession(mock_sap_session)
        elem = session.find_by_id("[/app/nonexistent]")

        assert elem is None

    def test_session_wait_for_screen_ready(self, mock_sap_session):
        """Session.wait_for_screen_ready polls until ready"""
        mock_sap_session.Busy = False

        session = GuiSession(mock_sap_session)
        is_ready = session.wait_for_screen_ready(timeout_sec=5)

        assert is_ready
```

**Module**: `/tests/test_config.py`

```python
import pytest
from config import AppConfig, SAPConnectionConfig, UIConfig

class TestConfigModels:
    """Test Pydantic config models"""

    def test_sap_connection_config(self):
        """SAPConnectionConfig validates all fields"""
        config = SAPConnectionConfig(
            sap_logon_path="C:\\SAP\\logon.ini",
            client="100",
            lang="EN"
        )

        assert config.client == "100"
        assert config.lang == "EN"

    def test_app_config_from_dict(self):
        """AppConfig created from dict"""
        data = {
            "sap": {
                "sap_logon_path": "C:\\SAP\\logon.ini",
                "client": "100",
            },
            "ui": {
                "port": 8000,
                "host": "127.0.0.1",
            }
        }

        config = AppConfig(**data)
        assert config.ui.port == 8000

    def test_app_config_from_yaml(self, temp_config_file):
        """AppConfig loaded from YAML file"""
        config = AppConfig.from_yaml(temp_config_file)
        assert config.sap.client == "100"
```

---

## Phase 2+: Continuous Integration

**Module**: `/.github/workflows/tests.yml`

```yaml
name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: windows-latest
    permissions:
      checks: write
      pull-requests: write

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-asyncio

    - name: Run tests
      run: |
        pytest tests/ --cov=sap --cov=ui --cov=config --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        files: ./coverage.xml

    - name: Publish test results
      if: always()
      uses: EnricoMi/publish-unit-test-result-action/windows@v2
      with:
        github_token: ${{ secrets.GITHUB_TOKEN }}
```

---

## Performance Benchmarking

**Module**: `/tests/test_performance.py`

```python
import pytest
import time

class TestPerformance:
    """Performance regression tests"""

    def test_config_load_time(self, temp_config_file):
        """Config load should be <100ms"""
        start = time.time()
        config = AppConfig.from_yaml(temp_config_file)
        elapsed = time.time() - start

        assert elapsed < 0.1, f"Config load took {elapsed}s (expected <0.1s)"

    def test_session_find_by_id_time(self, mock_sap_session):
        """Session.find_by_id should be <10ms"""
        session = GuiSession(mock_sap_session)

        start = time.time()
        for _ in range(100):
            session.find_by_id("[/app/button]")
        elapsed = time.time() - start

        per_call = elapsed / 100
        assert per_call < 0.01, f"find_by_id avg {per_call}s (expected <0.01s)"
```

---

## A.1. Output Format (Author Mode Deliverables)

### Code Deliverables

- **`/tests/conftest.py`**: Shared pytest fixtures (mock SAP, config)
- **`/tests/unit/test_*.py`**: Unit tests for each module (mocked dependencies, per-module coverage targets)
- **`/tests/integration/`**: Integration tests (require real SAP)
- **`/.github/workflows/tests.yml`**: GitHub Actions CI/CD
- **`/pytest.ini`**: Pytest configuration
- **`/scripts/run_tests.ps1`**: Local test runner (PowerShell — Windows environment)

---

## A.2. Quality Standards (Author Mode)

### Success Criteria

1. **Coverage**: >80% of code covered by tests
2. **Test Execution**: All tests pass locally and in CI/CD
3. **CI/CD Performance**: Test suite completes in <5 minutes
4. **Mock Fidelity**: Mock SAP objects behave realistically
5. **Regression Detection**: Performance tests flag >10% degradation
6. **Documentation**: Every test has docstring explaining its purpose

### Test Categories

**Unit Tests**: Fast, no dependencies
- Mock all external dependencies (SAP, filesystem)
- Run in <30s total
- Focus on logic correctness

**Integration Tests**: Medium speed, adjacent modules
- Test Module A + Module B interaction
- Use mock SAP session layer
- Run in <2 min total

**End-to-End Tests**: Slow, require real SAP
- Full workflow: config load → SAP connect → execute → shutdown
- Run on-demand (separate CI job)
- Run in <10 min total

**Performance Tests**: Regression detection
- Benchmark critical paths
- Alert if >10% slowdown detected
- Run with each commit

---

## A.3. Canonical Example (Author Mode)

### Example: Test Suite Structure

```
tests/
  conftest.py                    # Shared fixtures (all test categories)
  unit/
    test_com_bridge.py           # COM bridge tests
    test_sap_session.py          # Session wrapper tests
    test_config.py               # Config validation tests
    test_ui_pages.py             # UI page tests
  integration/
    test_bridge_session.py       # Bridge + Session integration
    test_ui_sap_full.py          # UI + SAP full stack (requires real SAP)
  test_performance.py            # Benchmarks (root level — run separately)
```

### Example: Running Tests Locally

```bash
# Run unit tests with coverage
pytest tests/unit/ --cov=sap --cov=config --cov=ui --cov=main --cov-report=html -v

# Run integration tests
pytest tests/integration/ -v

# Run performance benchmarks
pytest tests/test_performance.py -v

# Run single test
pytest tests/test_config.py::TestConfigModels::test_app_config_from_dict -v
```

### Example: Creating a Test File (Mode B)

**Input from Orchestrator**: "Write tests for the bridge.py module"

**Agent process**:
1. Read CONTEXT.md (confirm test conventions)
2. Read `/sap/bridge.py` (understand what to test)
3. Read `/tests/test_com_bridge.py` if it exists (check for existing coverage)
4. **Generate test code** (write Python)
5. **Use `editFiles` tool to CREATE the file**:
   ```
   Path: /tests/test_new_bridge_functionality.py
   Content: [full Python test code here, 200+ lines]
   ```
6. Verify the file meets pytest discovery rules (do NOT use terminal commands):
   - File name matches `test_*.py` ✅
   - Classes named `Test*` ✅
   - Methods named `test_*` ✅
7. Return success message with file path and list of test class/method names authored

✅ **CORRECT**: Use `editFiles` tool to create the file.
❌ **WRONG**: Use terminal `cat > file << EOF` (fails on Windows PowerShell).

---

## A.4. Edge Cases & Testing Challenges

### A. Testing COM Threading

**Challenge**: Worker thread runs independently; hard to test
- Solution: Use `threading.Event()` to synchronize test with worker

### B. Mock Accuracy

**Challenge**: Mock SAP session might not behave exactly like real SAP
- Solution: Periodically run integration tests against real SAP to catch divergence

### C. Large Data Performance

**Challenge**: Test reading 100k-row grid can be slow
- Solution: Mock grid data; only test real SAP occasionally (separate CI job)

### D. Flaky Tests

**Challenge**: Timing-dependent tests fail intermittently
- Solution: Use deterministic fixtures; avoid time.sleep() in tests

---

## A.5. Critical Reminders (Author Mode)

1. **Test < Code Ratio**: Aim for 1:1 to 2:1 test:code ratio
2. **Mock Thoroughly**: Unit tests should not touch SAP
3. **Document Test Purposes**: Every test docstring explains why it exists
4. **Fail Fast**: First failure should provide clear insight
5. **CI/CD Gating**: No code merges without passing tests
6. **Performance Regression**: Flag any >10% slowdown
7. **Coverage Reports**: Publish to track improvements
8. **Coordinate with All Agents**: Ensure your test fixtures match their module APIs
