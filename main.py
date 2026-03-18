"""SAP Automation Framework - Main Entry Point.

Initializes configuration, SAP connection, and starts NiceGUI server with all registered pages.

Usage:
    python main.py
    
    Or with custom config file:
    python main.py --config /path/to/config.yaml
    
Environment Variables (override config.yaml):
    SAP_USERNAME: SAP username
    SAP_PASSWORD: SAP password
    SAP_CLIENT: SAP client number
    APP_PORT: Web server port
    APP_DEBUG: Debug mode
    LOG_LEVEL: Logging level

Pages registered:
    / — Home (Dashboard)
    /inspector — Screen Inspector (Phase 2)
    /script-runner — Script Runner (Phase 3)
    /reports — Reports & Exports (Phase 4)

See config.example.yaml and .env.example for configuration.
"""

import sys
import logging
from pathlib import Path
from typing import Optional

try:
    from config import initialize_config
    from ui.app import create_app
    from sap.connection import SAPConnection
    from loguru import logger
except ImportError as e:
    print(f"ERROR: Failed to import required modules: {e}")
    print("Install dependencies with: pip install -r requirements.txt")
    sys.exit(1)


def setup_logging(config) -> None:
    """Configure logging with loguru.
    
    Args:
        config: RuntimeConfig instance with logging configuration
    """
    log_level = config.logging.level
    
    # Remove default handler
    logger.remove()
    
    # Console output
    logger.add(
        sys.stderr,
        format="<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=log_level
    )
    
    # File output (if configured)
    if config.logging.file:
        log_path = Path(config.logging.file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_path,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level=log_level,
            rotation="10 MB",
            retention="7 days"
        )
    
    # Redirect standard logging to loguru
    logging.basicConfig(
        handlers=[logging.StreamHandler()],
        level=getattr(logging, log_level)
    )


def main(config_path: Optional[Path] = None) -> None:
    """Run the SAP Automation Framework with NiceGUI server.
    
    Initializes configuration, sets up logging, creates the NiceGUI app with all
    registered pages (Home, Inspector, Script Runner, Reports), and starts the server.
    
    Args:
        config_path: Optional path to config.yaml file. If not provided, looks for
                    config.yaml in the current directory.
        
    Raises:
        FileNotFoundError: If config file not found
        Exception: If startup fails
    """
    try:
        # Initialize configuration
        print("[*] Loading configuration...")
        if config_path is None:
            if Path("config.yaml").exists():
                config_path = Path("config.yaml")
        
        config = initialize_config(config_path)
        print("[+] Configuration loaded successfully")
        
        # Setup logging
        setup_logging(config)
        logger.info("Logging configured")
        logger.info(f"Log level: {config.logging.level}")
        
        # Bootstrap example scripts (Task 4)
        print("[*] Bootstrapping example scripts...")
        try:
            from sap import ScriptManager
            script_manager = ScriptManager(scripts_dir="scripts")
            results = script_manager.bootstrap_examples(overwrite=False)
            created_count = sum(1 for v in results.values() if v)
            logger.info(f"Bootstrap complete: {created_count} example scripts initialized")
            print(f"[+] Examples initialized ({created_count} files)")
        except Exception as e:
            logger.warning(f"Bootstrap examples failed (non-fatal): {e}")
            print(f"[!] Warning: Example scripts bootstrap failed: {e}")
        
        # Create NiceGUI app with all pages
        print("[*] Initializing NiceGUI application...")
        print("[*] Registering pages:")
        print("    - / (Home)")
        print("    - /inspector (Screen Inspector)")
        print("    - /script-runner (Script Runner)")
        print("    - /reports (Reports & Exports)")
        
        # Initialize SAP connection before creating app (Phase 1)
        print("[*] Initializing SAP connection...")
        try:
            sap_connection = SAPConnection(config.sap)
            logger.info("SAP connection initialized (SSO-only mode)")
            print("[+] SAP connection initialized")
        except ValueError as e:
            logger.error(f"Failed to initialize SAP connection: {e}")
            print(f"[!] Error: {e}")
            print("[!] Check that SAP configuration (logon_path, client, lang) is properly set in config.yaml")
            sys.exit(1)
        except Exception as e:
            logger.exception(f"Unexpected error initializing SAP connection: {e}")
            print(f"[!] Error: {e}")
            sys.exit(1)
        
        # Create app with initialized connection
        create_app(config, connection=sap_connection, session=None)
        
        logger.info("NiceGUI application initialized with 4 pages")
        
        # Start server
        print(f"[*] Starting server on {config.app.host}:{config.app.port}")
        print(f"[+] Open browser to http://{config.app.host}:{config.app.port}")
        logger.info(f"Starting server on {config.app.host}:{config.app.port}")
        
        # Run NiceGUI (blocking)
        from nicegui import ui as nicegui_ui
        # Note: NiceGUI doesn't support 'debug' parameter in ui.run()
        # Debug mode can be set via environment variables or app config if needed
        nicegui_ui.run(
            host=config.app.host,
            port=config.app.port,
            title=config.app.title,
            reload=False,  # Disable watchfiles file-watcher (eliminates page load delay)
            show=False,    # Don't auto-open browser (user opens manually)
        )
        
    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        print(f"ERROR: {e}")
        print("Create a config.yaml file or copy config.example.yaml")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Failed to start application: {e}")
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ in {"__main__", "__mp_main__"}:
    import argparse
    
    parser = argparse.ArgumentParser(
        description="SAP Automation Framework - NiceGUI-based SAP GUI Bridge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python main.py                                    # Use config.yaml in current dir
  python main.py --config /path/to/config.yaml     # Use custom config
  SAP_PASSWORD=mypass python main.py                # Override via env var
        """
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to config.yaml file (default: config.yaml in current directory)"
    )
    parser.add_argument(
        "--version",
        action="version",
        version="SAP Automation Framework v0.1.0 (Phase 1 Foundation)"
    )
    
    args = parser.parse_args()
    main(args.config)

