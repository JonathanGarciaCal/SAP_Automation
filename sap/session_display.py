"""
SAP Session Display — Display and export session information.

Provides utilities for:
- Pretty-print session information
- Export sessions to CSV, Excel
- Real-time session monitoring
- Session metadata formatting
"""

import win32com.client
from typing import List, Dict, Optional
import csv
import logging

logger = logging.getLogger(__name__)


class SessionDisplayManager:
    """
    Display and export SAP session information.
    
    Example:
        manager = SessionDisplayManager()
        print(manager.get_sessions_ascii_table())
        manager.export_sessions_csv("sessions.csv")
    """
    
    def __init__(self):
        """Initialize display manager."""
        self.logger = logger
    
    def get_all_sessions(self) -> List[Dict]:
        """
        Get all open SAP sessions with metadata.
        
        Returns:
            List of dicts with session info
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
                            'program': sess.Info.Program,
                            'server': sess.Info.ApplicationServer,
                        })
                    except Exception as e:
                        self.logger.warning(
                            f"Error reading session[{ci}][{si}]: {e}"
                        )
        
        except Exception as e:
            self.logger.error(f"Error getting sessions: {e}")
        
        return sessions
    
    def get_sessions_ascii_table(self) -> str:
        """
        Get sessions formatted as ASCII table.
        
        Returns:
            Formatted table string
        """
        
        sessions = self.get_all_sessions()
        
        if not sessions:
            return "No sessions open"
        
        lines = []
        lines.append("\n" + "=" * 100)
        lines.append("OPEN SAP SESSIONS")
        lines.append("=" * 100)
        
        # Header
        lines.append(
            f"{'#':<3} | {'System':<6} | {'Client':<6} | {'User':<10} | "
            f"{'Transaction':<15} | {'Program':<20}"
        )
        lines.append("-" * 100)
        
        # Rows
        for i, s in enumerate(sessions):
            lines.append(
                f"{i:<3} | {s['system']:<6} | {s['client']:<6} | "
                f"{s['user']:<10} | {s['transaction']:<15} | {s['program']:<20}"
            )
        
        lines.append("=" * 100 + "\n")
        
        return "\n".join(lines)
    
    def get_sessions_detailed(self) -> str:
        """
        Get sessions with detailed information.
        
        Returns:
            Formatted detailed view
        """
        
        sessions = self.get_all_sessions()
        
        if not sessions:
            return "No sessions open"
        
        lines = []
        
        for i, s in enumerate(sessions):
            lines.append(f"\n[Session {i}]")
            lines.append(f"  System:        {s['system']}")
            lines.append(f"  Client:        {s['client']}")
            lines.append(f"  User:          {s['user']}")
            lines.append(f"  Transaction:   {s['transaction']}")
            lines.append(f"  Language:      {s['language']}")
            lines.append(f"  Program:       {s['program']}")
            lines.append(f"  Server:        {s['server']}")
        
        lines.append("\n")
        
        return "\n".join(lines)
    
    def export_sessions_csv(self, filepath: str) -> bool:
        """
        Export sessions to CSV file.
        
        Args:
            filepath: Output CSV file path
        
        Returns:
            True if successful, False otherwise
        """
        
        sessions = self.get_all_sessions()
        
        if not sessions:
            self.logger.warning("No sessions to export")
            return False
        
        try:
            with open(filepath, 'w', newline='') as csvfile:
                fieldnames = [
                    'system', 'client', 'user', 'transaction',
                    'language', 'program', 'server',
                ]
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                writer.writerows(sessions)
            
            self.logger.info(f"✓ Exported {len(sessions)} sessions to {filepath}")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to export CSV: {e}")
            return False
    
    def get_session_count_by_system(self) -> Dict[str, int]:
        """
        Get session count grouped by system.
        
        Returns:
            Dict with system → session count
        """
        
        sessions = self.get_all_sessions()
        counts = {}
        
        for s in sessions:
            system = s['system']
            counts[system] = counts.get(system, 0) + 1
        
        return counts
    
    def get_session_summary(self) -> str:
        """
        Get summary statistics.
        
        Returns:
            Summary string
        """
        
        sessions = self.get_all_sessions()
        counts = self.get_session_count_by_system()
        
        lines = []
        lines.append("\n" + "=" * 60)
        lines.append("SESSION SUMMARY")
        lines.append("=" * 60)
        lines.append(f"Total Sessions: {len(sessions)}")
        lines.append(f"Total Systems:  {len(counts)}")
        
        for system, count in sorted(counts.items()):
            lines.append(f"  {system}: {count} session(s)")
        
        if len(sessions) > 0:
            users = set(s['user'] for s in sessions)
            lines.append(f"\nActive Users: {len(users)}")
            for user in sorted(users):
                lines.append(f"  {user}")
        
        lines.append("=" * 60 + "\n")
        
        return "\n".join(lines)


# Convenience functions
def display_sessions():
    """Display all sessions to console."""
    
    manager = SessionDisplayManager()
    print(manager.get_sessions_ascii_table())
    print(manager.get_session_summary())


def export_sessions(filepath: str):
    """Export all sessions to CSV."""
    
    manager = SessionDisplayManager()
    return manager.export_sessions_csv(filepath)
