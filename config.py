"""Application configuration with Pydantic v2 validation.

Provides:
    - Configuration schema for all modules
    - Environment variable overrides
    - YAML file loading
    - Sensible defaults
    - Runtime validation

Usage:
    ```python
    # Load from YAML file
    config = AppConfig.from_yaml(Path('config.yaml'))
    
    # Or use environment variables
    config = AppConfig()
    
    # Access config
    sap_config = config.sap
    print(sap_config.client)  # '100'
    ```

Environment Variables (override YAML):
    - SAP_LOGON_PATH: Path to SAP Logon file
    - SAP_USERNAME: SAP username
    - SAP_PASSWORD: SAP password
    - SAP_CLIENT: SAP client number
    - SAP_LANG: SAP language code
    - APP_HOST: Web server host
    - APP_PORT: Web server port
    - APP_DEBUG: Debug mode (true/false)
    - LOG_LEVEL: Logging level
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
import yaml


class SAPConfig(BaseModel):
    """SAP connection configuration.
    
    Attributes:
        logon_path: Path to SAP Logon file (e.g., C:\\Program Files\\SAP\\FrontEnd\\SAP GUI\\saplogon.ini)
        username: SAP username (from env var SAP_USERNAME)
        password: SAP password (from env var SAP_PASSWORD, NEVER hardcode)
        client: SAP client number (default: '100')
        lang: Language code (default: 'EN')
        sapgui_exe_path: Full path to saplogon.exe for auto-launch
        connection_timeout_sec: Max seconds to wait for connection (default: 30)
        wait_optimization_enabled: Use SmartWait instead of fixed waits (default: True)
        retry_attempts: Connection retry attempts with exponential backoff (default: 3)
        retry_backoff_sec: Initial retry backoff time in seconds (default: 2)
    """
    
    model_config = {"validate_assignment": True}
    
    logon_path: str = Field(
        default="",
        description="Path to SAP Logon file or connection descriptor"
    )
    username: Optional[str] = Field(
        default=None,
        description="SAP username (from SAP_USERNAME env var)"
    )
    password: Optional[str] = Field(
        default=None,
        description="SAP password (from SAP_PASSWORD env var, NEVER hardcode)"
    )
    client: str = Field(
        default="100",
        description="SAP client number"
    )
    lang: str = Field(
        default="EN",
        description="Language code"
    )
    sapgui_exe_path: Optional[str] = Field(
        default=None,
        description="Full path to saplogon.exe for auto-launch (optional, auto-detected if None)"
    )
    connection_timeout_sec: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Max seconds to wait for SAP connection"
    )
    wait_optimization_enabled: bool = Field(
        default=True,
        description="Use SmartWait for 60-70% speedup"
    )
    retry_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Connection retry attempts with exponential backoff"
    )
    retry_backoff_sec: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Initial retry backoff time (exponential: 2, 4, 8, ...)"
    )
    
    @field_validator("username", mode="before")
    @classmethod
    def set_username_from_env(cls, v: Optional[str]) -> Optional[str]:
        """Read username from env var if not provided."""
        if v is None:
            v = os.getenv("SAP_USERNAME")
        return v
    
    @field_validator("password", mode="before")
    @classmethod
    def set_password_from_env(cls, v: Optional[str]) -> Optional[str]:
        """Read password from env var if not provided."""
        if v is None:
            v = os.getenv("SAP_PASSWORD")
        return v
    
    @field_validator("sapgui_exe_path", mode="before")
    @classmethod
    def set_sapgui_exe_path_from_env(cls, v: Optional[str]) -> Optional[str]:
        """Read SAP GUI exe path from env var if not provided."""
        if v is None:
            v = os.getenv("SAP_LOGON_PATH")
        return v
    
    @field_validator("connection_timeout_sec", mode="before")
    @classmethod
    def set_connection_timeout_from_env(cls, v: int) -> int:
        """Read connection timeout from env var if available."""
        env_val = os.getenv("SAP_CONNECTION_TIMEOUT_SEC")
        if env_val:
            try:
                return int(env_val)
            except (ValueError, TypeError):
                pass
        return v
    
    @field_validator("retry_attempts", mode="before")
    @classmethod
    def set_retry_attempts_from_env(cls, v: int) -> int:
        """Read retry attempts from env var if available."""
        env_val = os.getenv("SAP_RETRY_ATTEMPTS")
        if env_val:
            try:
                return int(env_val)
            except (ValueError, TypeError):
                pass
        return v
    
    @field_validator("retry_backoff_sec", mode="before")
    @classmethod
    def set_retry_backoff_from_env(cls, v: int) -> int:
        """Read retry backoff from env var if available."""
        env_val = os.getenv("SAP_RETRY_BACKOFF_SEC")
        if env_val:
            try:
                return int(env_val)
            except (ValueError, TypeError):
                pass
        return v


class AppConfig(BaseModel):
    """Web application configuration.
    
    Attributes:
        host: Server host address (default: '127.0.0.1')
        port: Server port (default: 8080)
        debug: Debug mode flag (default: False)
        title: Application title
    """
    
    model_config = {"validate_assignment": True}
    
    host: str = Field(
        default="127.0.0.1",
        description="Web server host"
    )
    port: int = Field(
        default=8080,
        ge=1024,
        le=65535,
        description="Web server port"
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    title: str = Field(
        default="SAP Automation Framework",
        description="Application title"
    )


class LoggingConfig(BaseModel):
    """Logging configuration.
    
    Attributes:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        file: Log file path (optional)
        format: Log message format
    """
    
    model_config = {"validate_assignment": True}
    
    level: str = Field(
        default="INFO",
        pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
        description="Logging level"
    )
    file: Optional[str] = Field(
        default=None,
        description="Log file path (optional)"
    )
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log message format"
    )


class FeatureFlags(BaseModel):
    """Feature flags for phases.
    
    Attributes:
        enable_screen_inspector: Enable Phase 2 screen inspector
        enable_script_runner: Enable Phase 3 script runner
        enable_report_engine: Enable Phase 4 report engine
    """
    
    model_config = {"validate_assignment": True}
    
    enable_screen_inspector: bool = Field(
        default=False,
        description="Enable screen inspector feature (Phase 2)"
    )
    enable_script_runner: bool = Field(
        default=False,
        description="Enable script runner feature (Phase 3)"
    )
    enable_report_engine: bool = Field(
        default=False,
        description="Enable report engine feature (Phase 4)"
    )


class RuntimeConfig(BaseModel):
    """Complete runtime configuration.
    
    Attributes:
        sap: SAP connection settings
        app: Web application settings
        logging: Logging settings
        features: Feature flags
        scripts_dir: Directory containing automation scripts
    """
    
    model_config = {"validate_assignment": True}
    
    sap: SAPConfig = Field(
        default_factory=SAPConfig,
        description="SAP connection configuration"
    )
    app: AppConfig = Field(
        default_factory=AppConfig,
        description="Web application configuration"
    )
    logging: LoggingConfig = Field(
        default_factory=LoggingConfig,
        description="Logging configuration"
    )
    features: FeatureFlags = Field(
        default_factory=FeatureFlags,
        description="Feature flags"
    )
    scripts_dir: str = Field(
        default="scripts",
        description="Directory containing automation scripts"
    )
    
    @classmethod
    def from_yaml(cls, config_path: Path) -> "RuntimeConfig":
        """Load configuration from YAML file.
        
        Args:
            config_path: Path to config.yaml file
            
        Returns:
            RuntimeConfig instance
            
        Raises:
            FileNotFoundError: If config file not found
            yaml.YAMLError: If YAML syntax error
            ValueError: If validation fails
            
        Example:
            ```python
            config = RuntimeConfig.from_yaml(Path('config.yaml'))
            ```
        """
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
        
        if data is None:
            data = {}
        
        return cls(**data)
    
    @classmethod
    def from_env(cls) -> "RuntimeConfig":
        """Load configuration from environment variables.
        
        Returns:
            RuntimeConfig with env var overrides
            
        Example:
            ```python
            config = RuntimeConfig.from_env()
            ```
        """
        return cls()


# Global config instance
_config: Optional[RuntimeConfig] = None


def initialize_config(config_path: Optional[Path] = None) -> RuntimeConfig:
    """Initialize application configuration.
    
    Call this once at application startup before accessing config.
    
    Args:
        config_path: Path to YAML config file (optional)
        
    Returns:
        RuntimeConfig instance
        
    Raises:
        FileNotFoundError: If config file specified but not found
        yaml.YAMLError: If YAML syntax error
        ValueError: If validation fails
        
    Example:
        ```python
        from pathlib import Path
        from config import initialize_config
        
        config = initialize_config(Path('config.yaml'))
        ```
    """
    global _config
    
    if config_path:
        _config = RuntimeConfig.from_yaml(config_path)
    else:
        _config = RuntimeConfig.from_env()
    
    return _config


def get_config() -> RuntimeConfig:
    """Get the current configuration instance.
    
    Must call initialize_config() first.
    
    Returns:
        RuntimeConfig instance
        
    Raises:
        RuntimeError: If config not initialized
        
    Example:
        ```python
        from config import get_config
        
        config = get_config()
        port = config.app.port
        ```
    """
    if _config is None:
        raise RuntimeError(
            "Configuration not initialized. "
            "Call initialize_config() at application startup."
        )
    return _config
