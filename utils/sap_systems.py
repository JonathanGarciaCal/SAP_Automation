"""Utilities for reading SAP system configuration from saplogon.ini.

Provides functions to enumerate available SAP systems from the SAP Logon
configuration file (saplogon.ini) on Windows.
"""

import logging
import os
from typing import List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


def get_sap_systems() -> List[Dict[str, str]]:
    """Get list of available SAP systems from saplogon.ini.
    
    Reads the SAP Logon configuration file and extracts system IDs (SIDs)
    with their connection details. Falls back gracefully if saplogon.ini
    cannot be found.
    
    Returns:
        List of dicts with keys:
        - 'sid': System ID (e.g., 'D00', 'P00')
        - 'name': Display name (e.g., 'Development', 'Production')
        - 'application_server': Server hostname/IP
        - 'system_number': System number
        
        Empty list if saplogon.ini not found or cannot be read.
        
    Example:
        ```python
        systems = get_sap_systems()
        for system in systems:
            print(f"{system['sid']}: {system['name']} ({system['application_server']})")
        ```
    """
    systems = []
    
    # Common paths for saplogon.ini on Windows
    possible_paths = [
        Path.home() / "AppData" / "Roaming" / "SAP" / "Common" / "saplogon.ini",
        Path("C:/Program Files/SAP/FrontEnd/app/saplogon.ini"),
        Path("C:/Program Files (x86)/SAP/FrontEnd/app/saplogon.ini"),
        Path.home() / ".saplogon.ini",
    ]
    
    saplogon_path = None
    for path in possible_paths:
        if path.exists():
            saplogon_path = path
            break
    
    if not saplogon_path:
        logger.debug("saplogon.ini not found in common locations")
        return systems
    
    try:
        logger.debug("Reading saplogon.ini from %s", saplogon_path)
        
        with open(saplogon_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse INI format
        # Format: [SID]
        #         DESCRIPTION=...
        #         APPSERVER=...
        #         SYSNR=00
        # etc.
        
        current_sid = None
        current_section = {}
        
        for line in content.split('\n'):
            line = line.strip()
            
            # Section header: [SID]
            if line.startswith('[') and line.endswith(']'):
                # Save previous section if it has APPSERVER
                if current_sid and 'APPSERVER' in current_section:
                    systems.append({
                        'sid': current_sid,
                        'name': current_section.get('DESCRIPTION', current_sid),
                        'application_server': current_section.get('APPSERVER', ''),
                        'system_number': current_section.get('SYSNR', '00'),
                    })
                
                current_sid = line[1:-1]  # Remove brackets
                current_section = {}
            
            # Property: KEY=VALUE
            elif '=' in line and current_sid:
                key, value = line.split('=', 1)
                current_section[key.strip().upper()] = value.strip()
        
        # Don't forget the last section
        if current_sid and 'APPSERVER' in current_section:
            systems.append({
                'sid': current_sid,
                'name': current_section.get('DESCRIPTION', current_sid),
                'application_server': current_section.get('APPSERVER', ''),
                'system_number': current_section.get('SYSNR', '00'),
            })
        
        logger.info("Found %d SAP systems in saplogon.ini", len(systems))
        
    except Exception as e:
        logger.error("Error reading saplogon.ini: %s", e)
    
    return systems
