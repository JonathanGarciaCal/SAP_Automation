"""Configuration loading and validation tests.

Tests for RuntimeConfig, including scripts_dir field and other core configuration options.
"""

import pytest
from pathlib import Path
from config import RuntimeConfig, SAPConfig, AppConfig, LoggingConfig, FeatureFlags


def test_config_loads():
    """Test that config loads without error."""
    config = RuntimeConfig()
    assert config is not None
    assert isinstance(config.sap, SAPConfig)
    assert isinstance(config.app, AppConfig)
    assert isinstance(config.logging, LoggingConfig)
    assert isinstance(config.features, FeatureFlags)


def test_config_validation():
    """Test that config validates required fields."""
    config = RuntimeConfig()
    assert config.app.port >= 1024
    assert config.app.port <= 65535
    assert config.logging.level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def test_scripts_dir_has_default_value():
    """Test that scripts_dir field has sensible default."""
    config = RuntimeConfig()
    assert config.scripts_dir == "scripts"
    assert isinstance(config.scripts_dir, str)


def test_scripts_dir_can_be_customized():
    """Test that scripts_dir field can be set to custom value."""
    config = RuntimeConfig(scripts_dir="custom_scripts")
    assert config.scripts_dir == "custom_scripts"


def test_scripts_dir_absolute_path():
    """Test that scripts_dir can accept absolute paths."""
    custom_path = str(Path("c:/temp/scripts").resolve())
    config = RuntimeConfig(scripts_dir=custom_path)
    assert config.scripts_dir == custom_path


def test_scripts_dir_in_docstring():
    """Test that scripts_dir is documented in class docstring."""
    doc = RuntimeConfig.__doc__
    assert doc is not None
    assert "scripts_dir" in doc
    assert "automation scripts" in doc.lower()
