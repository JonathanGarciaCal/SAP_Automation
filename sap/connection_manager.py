"""
SAP Connection Manager — Smart connection detection and launch.

Provides intelligent connection logic:
- Detect if SAP GUI is running
- Open SAP GUI programmatically
- Find or create sessions with retries
- Smart connection with exponential backoff
"""

import win32com.client
import subprocess
import psutil
import os
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SAPConnectionManager:
    """
    Production-ready SAP connection manager.
    
    Features:
    - Smart connection detection
    - Auto-launch SAP GUI if needed
    - Retry logic with exponential backoff
    - Session timeout handling
    - Multi-system support
    
    Example:
        config = {'saplogon_path': r'C:\\Program Files (x86)\\SAP\\...\\saplogon.exe'}
        mgr = SAPConnectionManager(config)
        session = mgr.connect("PRD", client="100", auto_launch=True)
    """
    
    def __init__(self, config: Optional[dict] = None):
        """
        Initialize connection manager.
        
        Args:
            config: Optional dict with:
                - saplogon_path: Full path to saplogon.exe
                - wait_timeout: Max seconds to wait for launches (default: 30)
                - retry_attempts: Max connection retries (default: 3)
        """
        
        self.config = config or {}
        self.logger = logger
        
        self.saplogon_path = self.config.get('saplogon_path')
        self.wait_timeout = self.config.get('wait_timeout', 30)
        self.retry_attempts = self.config.get('retry_attempts', 3)
    
    def find_sap_path(self) -> Optional[str]:
        """
        Locate SAP GUI executable.
        
        Searches config path, then common installation locations.
        
        Returns:
            Full path to saplogon.exe or None if not found
        """
        
        # Try configured path first
        if self.saplogon_path and os.path.exists(self.saplogon_path):
            self.logger.debug(f"Using configured SAP path: {self.saplogon_path}")
            return self.saplogon_path
        
        # Common installation locations
        common_paths = [
            r"C:\Program Files (x86)\SAP\FrontEnd\SAPgui\saplogon.exe",
            r"C:\Program Files\SAP\FrontEnd\SAPgui\saplogon.exe",
            r"C:\SAP\FrontEnd\SAPgui\saplogon.exe",
            r"C:\Program Files (x86)\SAP\Frontpac\saplogon.exe",
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                self.logger.debug(f"Found SAP at: {path}")
                return path
        
        self.logger.error("SAP GUI executable not found in standard locations")
        return None
    
    def is_sap_gui_running(self) -> bool:
        """
        Check if SAP GUI process is currently running.
        
        Returns:
            True if saplogon or saplgpad process found
        """
        
        try:
            for proc in psutil.process_iter(['name']):
                try:
                    name = proc.info['name'].lower()
                    if 'saplogon' in name or 'saplgpad' in name:
                        self.logger.debug(f"✓ SAP GUI found: {proc.info['name']}")
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        
        except ImportError:
            self.logger.warning(
                "psutil not installed. Install via: pip install psutil"
            )
            return False
        except Exception as e:
            self.logger.warning(f"Error checking SAP process: {e}")
            return False
        
        self.logger.debug("✗ SAP GUI not running")
        return False
    
    def is_sap_com_available(self) -> bool:
        """
        Check if SAP COM scripting interface is accessible.
        
        Returns:
            True if SAPGUI COM object can be accessed
        """
        
        try:
            sap_gui = win32com.client.GetObject("SAPGUI")
            return sap_gui is not None
        
        except Exception as e:
            self.logger.debug(f"SAP COM not available: {e}")
            return False
    
    def launch_sap(self, system: Optional[str] = None) -> bool:
        """
        Launch SAP GUI application.
        
        Args:
            system: Optional system ID to pass to SAP (e.g., "PRD", "DEV")
        
        Returns:
            True if launched successfully
        """
        
        sap_path = self.find_sap_path()
        if not sap_path:
            raise Exception(
                "SAP GUI not found. Install SAP GUI or set config['saplogon_path']"
            )
        
        try:
            if system:
                cmd = f'"{sap_path}" "{system}"'
            else:
                cmd = f'"{sap_path}"'
            
            self.logger.info(f"Launching SAP GUI: {cmd}")
            subprocess.Popen(cmd)
            
            self.logger.info(
                f"Waiting {self.wait_timeout} seconds for SAP startup..."
            )
            time.sleep(self.wait_timeout)
            
            if self.is_sap_gui_running():
                self.logger.info("✓ SAP GUI started successfully")
                return True
            else:
                self.logger.error("✗ SAP GUI did not start in time")
                return False
        
        except Exception as e:
            self.logger.error(f"Failed to launch SAP: {e}")
            raise
    
    def get_session(
        self,
        system: str,
        client: Optional[str] = None,
        transaction: Optional[str] = None,
        timeout: int = 10
    ) -> Optional[object]:
        """
        Get session with retry logic.
        
        Args:
            system: System ID
            client: Optional client number
            transaction: Optional transaction code (default: SESSION_MANAGER)
            timeout: Max seconds to search
        
        Returns:
            GuiSession object or None
        """
        
        if transaction is None:
            transaction = "SESSION_MANAGER"
        
        start = time.time()
        attempt = 0
        
        while time.time() - start < timeout:
            try:
                sap_gui = win32com.client.GetObject("SAPGUI")
                app = sap_gui.GetScriptingEngine
                
                # Search for matching session
                for ci in range(app.Children.Count):
                    conn = app.Children(ci)
                    for si in range(conn.Children.Count):
                        sess = conn.Children(si)
                        
                        if sess.Info.SystemName != system:
                            continue
                        
                        if client and sess.Info.Client != client:
                            continue
                        
                        if transaction and sess.Info.Transaction != transaction:
                            continue
                        
                        self.logger.debug(
                            f"✓ Found session: {system}/{client} ({transaction})"
                        )
                        return sess
            
            except Exception as e:
                self.logger.debug(f"Error searching sessions (attempt {attempt}): {e}")
            
            if time.time() - start < timeout:
                # Exponential backoff: 1s, 2s, 4s, ...
                wait_time = min(2 ** attempt, 4)
                time.sleep(wait_time)
                attempt += 1
        
        self.logger.warning(f"✗ Session not found after {timeout}s: {system}/{client}")
        return None
    
    def connect(
        self,
        system: str,
        client: Optional[str] = None,
        auto_launch: bool = True,
        timeout: int = 30
    ) -> object:
        """
        Smart connection with auto-launch and retry.
        
        Logic:
        1. Check if session already open
        2. If not and auto_launch=True, launch SAP
        3. Retry with exponential backoff
        4. Return session or raise exception
        
        Args:
            system: System ID (PRD, DEV, QAS)
            client: Optional client number (default: infer from open connection)
            auto_launch: If True, launch SAP if not running
            timeout: Max seconds to wait for connection
        
        Returns:
            GuiSession object
        
        Raises:
            Exception: If connection fails
        """
        
        self.logger.info(f"Attempting to connect to {system}")
        
        # Step 1: Try to find existing session
        session = self.get_session(system, client, timeout=5)
        if session:
            self.logger.info(f"✓ Connected to existing session: {system}")
            return session
        
        # Step 2: Auto-launch if needed
        if not self.is_sap_gui_running() and auto_launch:
            self.logger.info("SAP not running; launching...")
            try:
                self.launch_sap(system)
                time.sleep(5)
            except Exception as e:
                raise Exception(f"Failed to launch SAP: {e}")
        
        # Step 3: Retry with backoff
        for attempt in range(self.retry_attempts):
            session = self.get_session(system, client, timeout=5)
            
            if session:
                self.logger.info(
                    f"✓ Connected to {system} after {attempt} attempt(s)"
                )
                return session
            
            if attempt < self.retry_attempts - 1:
                wait_time = 2 ** attempt
                self.logger.info(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)
        
        raise Exception(
            f"Could not connect to {system}/{client} after "
            f"{self.retry_attempts} attempts"
        )


# Convenience function
def smart_connect(
    system: str,
    client: Optional[str] = None,
    auto_launch: bool = True
) -> object:
    """
    Quick smart connection.
    
    Args:
        system: System ID
        client: Optional client number
        auto_launch: If True, launch SAP if not running
    
    Returns:
        GuiSession object
    """
    
    mgr = SAPConnectionManager()
    return mgr.connect(system, client, auto_launch)
