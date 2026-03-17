"""Tests for structured logging system.

Comprehensive unit tests covering:
    - Logger initialization and configuration
    - JSON formatter output and validity
    - Rotating file handler (file creation, rotation, backup counts)
    - All log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - Context enrichment (transaction, field, session_id, attempt, step)
    - Error logging with traceback
    - UI handler and log entry buffering
    - Convenience functions (get_logger, get_ui_log_entries)
"""

import pytest
import logging
import json
import sys
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Import the module under test
from sap.logging_config import (
    JSONFormatter,
    LogContext,
    UILogHandler,
    setup_logging_json,
    get_logger,
    get_ui_log_entries,
    clear_ui_log_entries,
    _context_transaction,
    _context_field_name,
    _context_session_id,
    _context_attempt,
    _context_step,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_log_dir():
    """Create a temporary directory for log files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture(autouse=True)
def reset_logging_state():
    """Reset global logging state between tests to prevent file locking."""
    # Store original handlers/config
    original_handlers = logging.root.handlers[:]
    original_level = logging.root.level
    
    yield
    
    # Clean up after test: remove all handlers and reset state
    # IMPORTANT: Close ALL handlers to release file locks before next test
    for handler in logging.root.handlers[:]:
        try:
            # Flush to ensure all data is written
            if hasattr(handler, 'flush'):
                handler.flush()
            # Close to release file handles
            if hasattr(handler, 'close'):
                handler.close()
        except Exception:
            pass  # Ignore errors during cleanup
        
        try:
            logging.root.removeHandler(handler)
        except Exception:
            pass  # Handler might already be removed
    
    # Reset global UI log handler to prevent state leakage
    import sap.logging_config as logging_config
    logging_config._ui_log_handler = None
    
    # Reset context variables (thread-local storage)
    try:
        _context_transaction.set(None)
        _context_field_name.set(None)
        _context_session_id.set(None)
        _context_attempt.set(None)
        _context_step.set(None)
    except Exception:
        pass  # Context vars might not be accessible
    
    # Force garbage collection to release resources
    import gc
    gc.collect()
    
    # Restore original state
    logging.root.setLevel(original_level)
    for handler in original_handlers:
        if handler not in logging.root.handlers:
            try:
                logging.root.addHandler(handler)
            except Exception:
                pass  # Handler might be invalid after cleanup


@pytest.fixture
def json_formatter():
    """Create a JSON formatter for testing."""
    return JSONFormatter()


@pytest.fixture
def sample_log_record():
    """Create a sample log record for testing."""
    record = logging.LogRecord(
        name='test.module',
        level=logging.INFO,
        pathname='/path/to/module.py',
        lineno=42,
        msg='Test message',
        args=(),
        exc_info=None,
        func='test_function',
    )
    return record


# ============================================================================
# JSON Formatter Tests
# ============================================================================

def test_json_formatter_basic_format(json_formatter, sample_log_record):
    """Test JSON formatter produces valid JSON with required fields."""
    result = json_formatter.format(sample_log_record)
    
    # Should be valid JSON
    log_entry = json.loads(result)
    
    # Check required fields
    assert 'timestamp' in log_entry
    assert 'level' in log_entry
    assert 'logger' in log_entry
    assert 'message' in log_entry
    assert 'module' in log_entry
    assert 'line' in log_entry
    assert 'function' in log_entry
    
    # Check values
    assert log_entry['level'] == 'INFO'
    assert log_entry['message'] == 'Test message'
    assert log_entry['line'] == 42
    assert log_entry['function'] == 'test_function'


def test_json_formatter_timestamp_format(json_formatter, sample_log_record):
    """Test JSON formatter produces ISO format timestamps."""
    result = json_formatter.format(sample_log_record)
    log_entry = json.loads(result)
    
    # Check timestamp is ISO format with Z suffix
    assert log_entry['timestamp'].endswith('Z')
    
    # Should be parseable as ISO datetime
    timestamp_str = log_entry['timestamp'].rstrip('Z')
    try:
        datetime.fromisoformat(timestamp_str)
    except ValueError:
        pytest.fail("Timestamp is not ISO format")


def test_json_formatter_with_context(json_formatter):
    """Test JSON formatter includes context variables in output."""
    # Set context variables
    _context_transaction.set('VA01')
    _context_field_name.set('P_MATNR')
    _context_session_id.set('session-123')
    
    try:
        record = logging.LogRecord(
            name='test.session',
            level=logging.INFO,
            pathname='/path/to/session.py',
            lineno=100,
            msg='Set field',
            args=(),
            exc_info=None,
            func='set_field',
        )
        
        result = json_formatter.format(record)
        log_entry = json.loads(result)
        
        # Check context is included
        assert 'context' in log_entry
        assert log_entry['context']['transaction'] == 'VA01'
        assert log_entry['context']['field_name'] == 'P_MATNR'
        assert log_entry['context']['session_id'] == 'session-123'
    finally:
        # Reset context
        _context_transaction.set(None)
        _context_field_name.set(None)
        _context_session_id.set(None)


def test_json_formatter_with_exception(json_formatter):
    """Test JSON formatter includes exception details."""
    try:
        raise ValueError("Test error message")
    except ValueError:
        record = logging.LogRecord(
            name='test.error',
            level=logging.ERROR,
            pathname='/path/to/error.py',
            lineno=50,
            msg='An error occurred',
            args=(),
            exc_info=sys.exc_info(),
            func='error_func',
        )
        
        result = json_formatter.format(record)
        log_entry = json.loads(result)
        
        # Check exception is included
        assert 'exception' in log_entry
        assert log_entry['exception']['type'] == 'ValueError'
        assert log_entry['exception']['message'] == 'Test error message'
        assert 'traceback' in log_entry['exception']


def test_json_formatter_with_extra_fields(json_formatter):
    """Test JSON formatter includes extra fields in output."""
    record = logging.LogRecord(
        name='test.extra',
        level=logging.INFO,
        pathname='/path/to/extra.py',
        lineno=75,
        msg='With extra data',
        args=(),
        exc_info=None,
        func='extra_func',
    )
    
    # Add extra fields
    record.request_id = 'req-12345'
    record.operation = 'read_grid'
    
    result = json_formatter.format(record)
    log_entry = json.loads(result)
    
    # Check extra fields are included
    assert 'extra' in log_entry
    assert log_entry['extra']['request_id'] == 'req-12345'
    assert log_entry['extra']['operation'] == 'read_grid'


# ============================================================================
# LogContext Tests
# ============================================================================

def test_log_context_sets_variables():
    """Test LogContext sets context variables."""
    # Ensure clean state
    assert _context_transaction.get() is None
    
    with LogContext(transaction='VA01', session_id='sess-1'):
        # Within context, variables should be set
        assert _context_transaction.get() == 'VA01'
        assert _context_session_id.get() == 'sess-1'
    
    # After context, variables should be None
    assert _context_transaction.get() is None
    assert _context_session_id.get() is None


def test_log_context_restores_previous_values():
    """Test LogContext restores previous values after exiting."""
    _context_transaction.set('TX01')
    
    with LogContext(transaction='VA01'):
        assert _context_transaction.get() == 'VA01'
    
    # Previous value restored
    assert _context_transaction.get() == 'TX01'


def test_log_context_nested_contexts():
    """Test nested LogContext contexts work correctly."""
    with LogContext(transaction='TX01'):
        assert _context_transaction.get() == 'TX01'
        
        with LogContext(field_name='FIELD1'):
            assert _context_transaction.get() == 'TX01'
            assert _context_field_name.get() == 'FIELD1'
        
        assert _context_transaction.get() == 'TX01'
        assert _context_field_name.get() is None


def test_log_context_all_fields():
    """Test LogContext with all available fields."""
    with LogContext(
        transaction='VA01',
        field_name='P_MATNR',
        session_id='session-123',
        step='read_grid',
        attempt=2,
    ):
        assert _context_transaction.get() == 'VA01'
        assert _context_field_name.get() == 'P_MATNR'
        assert _context_session_id.get() == 'session-123'
        assert _context_step.get() == 'read_grid'
        assert _context_attempt.get() == 2


# ============================================================================
# UILogHandler Tests
# ============================================================================

def test_ui_log_handler_buffers_entries():
    """Test UILogHandler buffers log entries."""
    handler = UILogHandler(max_entries=50)
    
    record1 = logging.LogRecord(
        name='test', level=logging.INFO,
        pathname='test.py', lineno=1,
        msg='Message 1', args=(), exc_info=None, func='fn1'
    )
    
    record2 = logging.LogRecord(
        name='test', level=logging.WARNING,
        pathname='test.py', lineno=2,
        msg='Message 2', args=(), exc_info=None, func='fn2'
    )
    
    handler.emit(record1)
    handler.emit(record2)
    
    entries = handler.get_entries()
    assert len(entries) == 2
    assert entries[0]['level'] == 'INFO'
    assert entries[1]['level'] == 'WARNING'


def test_ui_log_handler_respects_max_entries():
    """Test UILogHandler respects max_entries limit."""
    handler = UILogHandler(max_entries=3)
    
    # Add 5 entries
    for i in range(5):
        record = logging.LogRecord(
            name='test', level=logging.INFO,
            pathname='test.py', lineno=i,
            msg=f'Message {i}', args=(), exc_info=None, func='fn'
        )
        handler.emit(record)
    
    entries = handler.get_entries()
    assert len(entries) == 3  # Only last 3 entries


def test_ui_log_handler_clear_entries():
    """Test UILogHandler can clear entries."""
    handler = UILogHandler(max_entries=50)
    
    record = logging.LogRecord(
        name='test', level=logging.INFO,
        pathname='test.py', lineno=1,
        msg='Message', args=(), exc_info=None, func='fn'
    )
    
    handler.emit(record)
    assert len(handler.get_entries()) == 1
    
    handler.clear_entries()
    assert len(handler.get_entries()) == 0


def test_ui_log_handler_with_callback():
    """Test UILogHandler calls callback when provided."""
    callback_called = []
    
    def mock_callback(msg, level):
        callback_called.append((msg, level))
    
    handler = UILogHandler(callback=mock_callback)
    
    record = logging.LogRecord(
        name='test', level=logging.ERROR,
        pathname='test.py', lineno=1,
        msg='Error message', args=(), exc_info=None, func='fn'
    )
    
    handler.emit(record)
    
    assert len(callback_called) == 1
    assert 'Error message' in callback_called[0][0]
    assert callback_called[0][1] == 'ERROR'


def test_ui_log_handler_respects_level():
    """Test UILogHandler respects minimum log level."""
    handler = UILogHandler(level=logging.WARNING)
    
    # INFO should be ignored
    info_record = logging.LogRecord(
        name='test', level=logging.INFO,
        pathname='test.py', lineno=1,
        msg='Info', args=(), exc_info=None, func='fn'
    )
    
    # WARNING should be recorded
    warning_record = logging.LogRecord(
        name='test', level=logging.WARNING,
        pathname='test.py', lineno=2,
        msg='Warning', args=(), exc_info=None, func='fn'
    )
    
    handler.emit(info_record)
    handler.emit(warning_record)
    
    entries = handler.get_entries()
    assert len(entries) == 1
    assert entries[0]['level'] == 'WARNING'


# ============================================================================
# Logger Initialization Tests
# ============================================================================

@pytest.mark.serial
def test_setup_logging_json_creates_log_dir(temp_log_dir):
    """Test setup_logging_json creates log directory if missing."""
    log_dir = os.path.join(temp_log_dir, 'new_logs', 'subdir')
    assert not os.path.exists(log_dir)
    
    ui_handler = setup_logging_json(log_dir=log_dir)
    
    assert os.path.exists(log_dir)
    assert ui_handler is not None


@pytest.mark.serial
def test_setup_logging_json_creates_log_file(temp_log_dir):
    """Test setup_logging_json creates rotating log file."""
    ui_handler = setup_logging_json(log_dir=temp_log_dir)
    
    logger = logging.getLogger('test.setup')
    logger.debug("Test message")
    
    log_file = Path(temp_log_dir) / 'sap_bridge.log'
    assert log_file.exists()
    
    # Log file should contain JSON lines
    with open(log_file, 'r') as f:
        for line in f:
            if line.strip():
                json_entry = json.loads(line)
                assert 'timestamp' in json_entry
                assert 'level' in json_entry


def test_setup_logging_json_invalid_level():
    """Test setup_logging_json raises ValueError for invalid level."""
    with pytest.raises(ValueError, match="Invalid log level"):
        setup_logging_json(log_level='INVALID')


@pytest.mark.serial
def test_setup_logging_json_rotation_parameters(temp_log_dir):
    """Test setup_logging_json respects rotation parameters."""
    max_bytes = 1000  # Small size for testing rotation
    backup_count = 3
    
    ui_handler = setup_logging_json(
        log_dir=temp_log_dir,
        max_bytes=max_bytes,
        backup_count=backup_count,
    )
    
    logger = logging.getLogger('test.rotation')
    
    # Write enough to trigger rotation
    large_message = "X" * 500
    for i in range(5):
        logger.critical(f"Message {i}: {large_message}")
    
    log_dir = Path(temp_log_dir)
    log_files = list(log_dir.glob('sap_bridge.log*'))
    
    # Should have rotated files (main + backups)
    assert len(log_files) > 1
    assert len(log_files) <= backup_count + 1  # +1 for main file


# ============================================================================
# Log Level Tests
# ============================================================================

@pytest.mark.serial
def test_all_log_levels(temp_log_dir):
    """Test all log levels work correctly."""
    setup_logging_json(log_dir=temp_log_dir, log_level='DEBUG')
    
    logger = logging.getLogger('test.levels')
    
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    logger.critical("Critical message")
    
    log_file = Path(temp_log_dir) / 'sap_bridge.log'
    
    levels_found = set()
    with open(log_file, 'r') as f:
        for line in f:
            if line.strip():
                json_entry = json.loads(line)
                levels_found.add(json_entry['level'])
    
    expected_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
    assert levels_found == expected_levels


# ============================================================================
# Convenience Function Tests
# ============================================================================

@pytest.mark.serial
def test_get_logger(temp_log_dir):
    """Test get_logger returns configured logger."""
    setup_logging_json(log_dir=temp_log_dir)
    
    logger = get_logger('sap.session')
    
    assert logger.name == 'sap.session'
    assert isinstance(logger, logging.Logger)


@pytest.mark.serial
def test_get_ui_log_entries(temp_log_dir):
    """Test get_ui_log_entries returns buffered entries."""
    setup_logging_json(log_dir=temp_log_dir)
    
    logger = get_logger('test.ui_entries')
    logger.info("Message 1")
    logger.warning("Message 2")
    
    entries = get_ui_log_entries()
    
    assert len(entries) >= 2
    assert any(e['level'] == 'INFO' for e in entries)
    assert any(e['level'] == 'WARNING' for e in entries)


@pytest.mark.serial
def test_get_ui_log_entries_max_count(temp_log_dir):
    """Test get_ui_log_entries respects max_count parameter."""
    setup_logging_json(log_dir=temp_log_dir)
    
    logger = get_logger('test.max_entries')
    for i in range(10):
        logger.info(f"Message {i}")
    
    entries = get_ui_log_entries(max_count=3)
    
    assert len(entries) == 3


@pytest.mark.serial
def test_clear_ui_log_entries(temp_log_dir):
    """Test clear_ui_log_entries clears buffered entries."""
    setup_logging_json(log_dir=temp_log_dir)
    
    logger = get_logger('test.clear')
    logger.info("Message 1")
    
    assert len(get_ui_log_entries()) > 0
    
    clear_ui_log_entries()
    
    assert len(get_ui_log_entries()) == 0


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.serial
def test_logging_with_context_integration(temp_log_dir):
    """Test logging system works with context enrichment."""
    setup_logging_json(log_dir=temp_log_dir)
    
    logger = get_logger('test.integration')
    
    with LogContext(transaction='VA01', session_id='session-123', attempt=2):
        logger.info("Operation starting")
        logger.error("Operation failed")
    
    log_file = Path(temp_log_dir) / 'sap_bridge.log'
    entries_in_context = []
    
    with open(log_file, 'r') as f:
        for line in f:
            if line.strip():
                json_entry = json.loads(line)
                if json_entry['message'] in ['Operation starting', 'Operation failed']:
                    entries_in_context.append(json_entry)
    
    assert len(entries_in_context) == 2
    
    for entry in entries_in_context:
        assert entry['context']['transaction'] == 'VA01'
        assert entry['context']['session_id'] == 'session-123'
        assert entry['context']['attempt'] == 2


@pytest.mark.serial
def test_exception_logging_integration(temp_log_dir):
    """Test exception logging with traceback."""
    setup_logging_json(log_dir=temp_log_dir)
    
    logger = get_logger('test.exception')
    
    try:
        raise RuntimeError("Test exception for logging")
    except RuntimeError:
        logger.error("Caught exception", exc_info=True)
    
    log_file = Path(temp_log_dir) / 'sap_bridge.log'
    
    found = False
    with open(log_file, 'r') as f:
        for line in f:
            if line.strip():
                json_entry = json.loads(line)
                if 'Caught exception' in json_entry['message']:
                    assert 'exception' in json_entry
                    assert json_entry['exception']['type'] == 'RuntimeError'
                    assert 'Test exception for logging' in json_entry['exception']['message']
                    found = True
    
    assert found


@pytest.mark.serial
def test_multiple_loggers(temp_log_dir):
    """Test multiple loggers can coexist."""
    setup_logging_json(log_dir=temp_log_dir)
    
    logger1 = get_logger('module1')
    logger2 = get_logger('module2')
    logger3 = get_logger('module1.submodule')
    
    logger1.info("From module1")
    logger2.warning("From module2")
    logger3.debug("From module1.submodule")
    
    log_file = Path(temp_log_dir) / 'sap_bridge.log'
    loggers_found = set()
    
    with open(log_file, 'r') as f:
        for line in f:
            if line.strip():
                json_entry = json.loads(line)
                if 'From' in json_entry['message']:
                    loggers_found.add(json_entry['logger'])
    
    assert 'module1' in loggers_found
    assert 'module2' in loggers_found
    assert 'module1.submodule' in loggers_found
