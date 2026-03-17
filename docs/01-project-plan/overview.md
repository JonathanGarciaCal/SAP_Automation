# Project Overview

## What We're Building

A standalone NiceGUI web application that acts as a bridge between a user's browser and a running SAP GUI session on the same Windows machine. The server runs in Python, connects to the open SAP session through `win32com` / SAP GUI Scripting, and exposes a browser-based interface.

## Core Capabilities

1. **Inspect SAP data** — Browse screen elements, read tables (ALV grids, classic tables), view report output, and explore transaction screens through a tree-based inspector.

2. **Execute scripts & macros** — Run pre-recorded SAP GUI scripts (converted from VBScript to Python) with configurable parameters, from a web-based script library.

3. **Trigger reports** — Define standard SAP reports (transaction + selection parameters + output format), trigger them on demand, and route output to configurable local folders.

4. **Export data** — Download or export information from SAP screens to CSV, Excel, or text files on the local filesystem.

5. **Monitor connection** — Real-time connection status, session heartbeat, and automatic reconnection handling.

## What This Is NOT

- **Not a replacement for SAP GUI** — The user still needs SAP GUI installed and a session logged in. This tool automates and simplifies interaction with that session.
- **Not an RFC/API gateway** — It drives the GUI, not the application server directly (though PyRFC can complement it later).
- **Not multi-user out of the box** — It's designed to run on a single Windows machine for a single user. Network-exposed multi-user scenarios require added authentication.
- **Not a data warehouse** — It extracts data on demand; it doesn't store historical data (though that could be added).

## Target Users

- SAP power users who run repetitive transactions and reports
- Business analysts who need regular data exports from SAP
- IT teams who maintain SAP automation scripts
- Anyone who wants a friendlier interface for SAP data extraction

## Constraints

- **Windows only** — SAP GUI for Windows and `win32com` are Windows-specific
- **Same machine** — The Python server must run on the machine where SAP GUI is installed (COM is local)
- **SAP Basis cooperation required** — GUI Scripting must be enabled server-side
- **Session must be logged in** — The bridge attaches to an existing session; it does not handle login
