"""NiceGUI-based web frontend for SAP automation.

This module provides the browser-based user interface built with NiceGUI
(FastAPI + Vue/Quasar). Communicates with SAP backend via asyncio and WebSocket.

Pages:
    - home: Dashboard and status
    - inspector: Screen inspector and element tree
    - script_runner: Script execution interface
    - reports: Report generation and view

Components:
    - header: Common header bar
    - sidebar: Navigation sidebar
"""
