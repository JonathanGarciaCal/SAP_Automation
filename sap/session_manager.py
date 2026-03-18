"""
SAP Session Manager — Multi-session orchestration and lookup.

Provides utilities for finding, validating, and managing multiple SAP sessions across
different systems and landscapes (PRD, DEV, QAS, etc.).
"""

import win32com.client
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)


class SAP_Session_Manager:
    """
    Manage multiple SAP sessions across systems.
    
    Features:
    - Find sessions by system/client/transaction
    - Session validation and health checks
    - List all open sessions with metadata
    - Session pooling support
    
    Example:
        manager = SAP_Session_Manager()
        session = manager.get_session_by_system_client("PRD", "100")
        if session:
            session.StartTransaction("MM01")
    """
    
    def __init__(self):
        """Initialize session manager."""
        self.logger = logger
    
    def get_session_by_system_client(
        self,
        system_name: str,
        client_code: str,
        require_session_manager: bool = True
    ) -> Optional[object]:
        """
        Find session matching system and client.
        
        Args:
            system_name: System ID (e.g., "PRD", "DEV", "QAS")
            client_code: Client number (e.g., "100")
            require_session_manager: If True, prefer SESSION_MANAGER (main menu)
        
        Returns:
            GuiSession object or None if not found
            
        Raises:
            Exception: If SAP COM not available
        """
        
        try:
            sap_gui = win32com.client.GetObject("SAPGUI")
            app = sap_gui.GetScriptingEngine
            
            # First loop: Look for SESSION_MANAGER (preferred)
            if require_session_manager:
                for ci in range(app.Children.Count):
                    conn = app.Children(ci)
                    
                    # Get first session to check system/client
                    if conn.Children.Count > 0:
                        first_sess = conn.Children(0)
                        
                        if (first_sess.Info.SystemName == system_name and
                            first_sess.Info.Client == client_code):
                            
                            # Find SESSION_MANAGER in this connection
                            for si in range(conn.Children.Count):
                                sess = conn.Children(si)
                                if sess.Info.Transaction == "SESSION_MANAGER":
                                    self.logger.debug(
                                        f"✓ Found SESSION_MANAGER: {system_name}/{client_code}"
                                    )
                                    return sess
            
            # Second loop: Any session in system/client
            for ci in range(app.Children.Count):
                conn = app.Children(ci)
                for si in range(conn.Children.Count):
                    sess = conn.Children(si)
                    
                    if (sess.Info.SystemName == system_name and
                        sess.Info.Client == client_code):
                        
                        self.logger.debug(
                            f"✓ Found session in {system_name}/{client_code}: "
                            f"{sess.Info.Transaction}"
                        )
                        return sess
            
            self.logger.warning(f"✗ Session not found: {system_name}/{client_code}")
            return None
        
        except Exception as e:
            self.logger.error(f"Error finding session: {e}")
            return None
    
    def get_session_by_transaction(self, transaction_code: str) -> Optional[object]:
        """
        Find session currently in specific transaction.
        
        Args:
            transaction_code: Transaction code (e.g., "MM01", "VA01", "SESSION_MANAGER")
        
        Returns:
            GuiSession object or None if not found
        """
        
        try:
            sap_gui = win32com.client.GetObject("SAPGUI")
            app = sap_gui.GetScriptingEngine
            
            for ci in range(app.Children.Count):
                conn = app.Children(ci)
                for si in range(conn.Children.Count):
                    sess = conn.Children(si)
                    
                    if sess.Info.Transaction == transaction_code:
                        self.logger.debug(f"✓ Found {transaction_code} session")
                        return sess
            
            self.logger.warning(f"✗ No session in transaction: {transaction_code}")
            return None
        
        except Exception as e:
            self.logger.error(f"Error finding transaction session: {e}")
            return None
    
    def get_all_sessions(self) -> List[Dict]:
        """
        Get list of all open SAP sessions.
        
        Returns:
            List of dicts with session metadata:
            {
                'system': str,           # System name (PRD, DEV, QAS)
                'client': str,           # Client number
                'user': str,             # Logged-in user
                'transaction': str,      # Current transaction code
                'language': str,         # Login language
                'conn_idx': int,         # Connection index
                'sess_idx': int,         # Session index
                'session': object,       # GuiSession COM object
            }
        """
        
        sessions = []
        
        try:
            sap_gui = win32com.client.GetObject("SAPGUI")
            app = sap_gui.GetScriptingEngine
            
            for ci in range(app.Children.Count):
                conn = app.Children(ci)
                
                for si in range(conn.Children.Count):
                    sess = conn.Children(si)
                    
                    try:
                        sessions.append({
                            'system': sess.Info.SystemName,
                            'client': sess.Info.Client,
                            'user': sess.Info.User,
                            'transaction': sess.Info.Transaction,
                            'language': sess.Info.Language,
                            'conn_idx': ci,
                            'sess_idx': si,
                            'session': sess,
                        })
                    except Exception as e:
                        self.logger.warning(
                            f"Error reading session[{ci}][{si}]: {e}"
                        )
        
        except Exception as e:
            self.logger.error(f"Error listing all sessions: {e}")
        
        return sessions
    
    def validate_session(self, session: object) -> bool:
        """
        Check if session is still alive and responsive.
        
        Args:
            session: GuiSession object to validate
        
        Returns:
            True if session is valid, False if closed or unresponsive
        """
        
        try:
            # Try to access basic info
            _ = session.Info.SystemName
            _ = session.Info.Client
            
            self.logger.debug(
                f"✓ Session valid: {session.Info.SystemName}/"
                f"{session.Info.Client}"
            )
            return True
        
        except:
            self.logger.warning("✗ Session is dead or unresponsive")
            return False
    
    def close_session(self, system: str, client: str) -> bool:
        """
        Close session for given system/client.
        
        Args:
            system: System ID
            client: Client number
        
        Returns:
            True if closed, False if not found
        """
        
        try:
            sess = self.get_session_by_system_client(system, client)
            if sess:
                sess.EndTransaction()
                self.logger.info(f"✓ Closed session: {system}/{client}")
                return True
        
        except Exception as e:
            self.logger.error(f"Error closing session: {e}")
        
        return False
    
    def format_sessions_table(self, sessions: List[Dict]) -> str:
        """
        Format session list as ASCII table.
        
        Args:
            sessions: List from get_all_sessions()
        
        Returns:
            Formatted table string
        """
        
        if not sessions:
            return "No sessions open"
        
        lines = ["\n" + "=" * 80]
        lines.append("OPEN SAP SESSIONS")
        lines.append("=" * 80)
        
        for i, s in enumerate(sessions):
            lines.append(
                f"\n[{i}] {s['system']}/{s['client']} ({s['transaction']})"
            )
            lines.append(f"    User: {s['user']}")
            lines.append(f"    Language: {s['language']}")
        
        lines.append("\n" + "=" * 80 + "\n")
        
        return "\n".join(lines)
    
    def list_all_sessions_formatted(self) -> str:
        """
        Get pretty-printed session list.
        
        Returns:
            Formatted session list string
        """
        
        sessions = self.get_all_sessions()
        return self.format_sessions_table(sessions)


# Convenience function
def get_session(system: str, client: str) -> Optional[object]:
    """
    Quick lookup for session.
    
    Args:
        system: System ID
        client: Client number
    
    Returns:
        GuiSession object or None
    """
    
    manager = SAP_Session_Manager()
    return manager.get_session_by_system_client(system, client)
