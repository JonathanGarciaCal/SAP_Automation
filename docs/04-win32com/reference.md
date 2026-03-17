# win32com / COM Threading Reference

## Official Sources
- pywin32 GitHub: `https://github.com/mhammond/pywin32`
- Quick Start Guide: `https://timgolden.me.uk/pywin32-docs/html/com/win32com/HTML/QuickStartClientCom.html`
- PyPI: `https://pypi.org/project/pywin32/`

---

## Core Concepts

### GetObject vs Dispatch

| Method | When to Use | SAP Context |
|--------|-------------|-------------|
| `win32com.client.GetObject("SAPGUI")` | Attach to an already-running COM server | ★ **Always use this** — SAP GUI must be running |
| `win32com.client.Dispatch("Sapgui.ScriptingCtrl.1")` | Create a new COM instance | Can launch SAP GUI, but less common |

### Dynamic vs Static Dispatch

- **Dynamic dispatch** (default): Python discovers methods/properties at runtime. Slower but requires no setup.
- **Static dispatch** (via `makepy`): Pre-generates Python wrappers from COM type library. Faster, with autocomplete.

For SAP GUI Scripting, dynamic dispatch works fine. If you want static dispatch:
```bash
# Generate early-binding wrappers
python -m win32com.client.makepy "SAP GUI Scripting"
```

---

## COM Threading Model

### The Apartment Model

COM objects live in "apartments" — execution contexts with threading rules.

- **STA (Single-Threaded Apartment)**: Object can only be called from the thread that created it. This is what SAP GUI Scripting uses.
- **MTA (Multi-Threaded Apartment)**: Object can be called from any thread.

`pythoncom.CoInitialize()` initializes an STA. Every thread that uses COM must call this.

### Rules for Our Architecture

1. **Rule 1**: Call `pythoncom.CoInitialize()` at the start of any thread that uses COM objects.
2. **Rule 2**: Call `pythoncom.CoUninitialize()` when the thread is done with COM.
3. **Rule 3**: Never pass COM object references between threads. The COM proxy is tied to the creating thread.
4. **Rule 4**: If you need to access the same COM object from another thread, use inter-thread marshalling (complex) — or better, use a command queue so only one thread touches COM.
5. **Rule 5**: The main thread (NiceGUI's async loop) must not touch COM objects directly.

### Worker Thread Pattern

```python
import pythoncom
import win32com.client
import threading
import queue
import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional

@dataclass
class SAPCommand:
    method: str
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    future: Optional[asyncio.Future] = None

class SAPWorkerThread:
    def __init__(self):
        self._queue = queue.Queue()
        self._thread = None
        self._loop = None
        self._session = None
        self._alive = False

    def start(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        self._thread = threading.Thread(target=self._run, daemon=True, name='SAP-COM-Worker')
        self._thread.start()

    def _run(self):
        """Main loop of the COM worker thread"""
        pythoncom.CoInitialize()
        try:
            self._connect()
            while True:
                try:
                    cmd = self._queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                if cmd.method == '__stop__':
                    break

                try:
                    handler = getattr(self, f'_cmd_{cmd.method}', None)
                    if handler:
                        result = handler(*cmd.args, **cmd.kwargs)
                    else:
                        raise ValueError(f'Unknown command: {cmd.method}')

                    if cmd.future:
                        self._loop.call_soon_threadsafe(cmd.future.set_result, result)
                except Exception as e:
                    if cmd.future:
                        self._loop.call_soon_threadsafe(cmd.future.set_exception, e)
        finally:
            pythoncom.CoUninitialize()

    def _connect(self):
        """Establish COM connection to SAP GUI"""
        sap_gui = win32com.client.GetObject("SAPGUI")
        engine = sap_gui.GetScriptingEngine
        connection = engine.Children(0)
        self._session = connection.Children(0)
        self._alive = True

    async def execute(self, method: str, *args, **kwargs) -> Any:
        """Submit a command and await the result (called from async context)"""
        future = self._loop.create_future()
        self._queue.put(SAPCommand(method=method, args=args, kwargs=kwargs, future=future))
        return await future

    def stop(self):
        self._queue.put(SAPCommand(method='__stop__'))
        if self._thread:
            self._thread.join(timeout=5.0)

    # --- Command handlers (run on COM thread) ---

    def _cmd_get_status(self):
        try:
            info = self._session.Info
            return {
                'alive': True,
                'system': info.SystemName,
                'client': info.Client,
                'user': info.User,
                'transaction': info.Transaction,
            }
        except Exception:
            self._alive = False
            return {'alive': False}

    def _cmd_read_field(self, field_id):
        element = self._session.FindById(field_id)
        return element.Text

    def _cmd_set_field(self, field_id, value):
        element = self._session.FindById(field_id)
        element.Text = value

    def _cmd_start_transaction(self, tcode):
        self._session.StartTransaction(tcode)

    def _cmd_send_vkey(self, key):
        self._session.FindById("wnd[0]").SendVKey(key)

    def _cmd_press_button(self, button_id):
        self._session.FindById(button_id).Press()
```

---

## Error Handling

### COM Error Structure

```python
import pywintypes

try:
    element = session.FindById("wnd[0]/usr/txtNONEXISTENT")
except pywintypes.com_error as e:
    hresult = e.args[0]          # HRESULT code (e.g., -2147352567)
    description = e.args[1]       # "Exception occurred."
    exc_info = e.args[2]          # Tuple: (source, helpfile, helpcontext, scode, ...)
    if exc_info:
        source = exc_info[0]      # e.g., "saplogon"
        help_file = exc_info[1]
        scode = exc_info[5]       # SAP-specific error code
```

### Common Error Codes

| HRESULT / scode | Meaning | Recovery |
|----------------|---------|----------|
| -2147352567 | Generic "Exception occurred" | Check inner `scode` for details |
| scode 619 (393215) | "Control could not be found by id" | Element doesn't exist — wrong screen or bad ID |
| scode 614 | "Element not found in collection" | Index out of range |
| scode 605 | "Component could not be instantiated" | COM component not registered — bitness mismatch? |
| -2147221005 | "Invalid class string" | `GetObject` target not found — SAP GUI not running |
| -2147221008 | "CoInitialize has not been called" | Forgot `pythoncom.CoInitialize()` on this thread |
| -2147418111 | "Call was rejected by callee" | COM object busy or disconnected |

### Error Wrapper Pattern
```python
import pywintypes

class SAPError(Exception):
    def __init__(self, message, com_error=None):
        super().__init__(message)
        self.com_error = com_error

def safe_com_call(func, *args, **kwargs):
    """Wrap any COM call with friendly error handling"""
    try:
        return func(*args, **kwargs)
    except pywintypes.com_error as e:
        scode = e.args[2][5] if e.args[2] and len(e.args[2]) > 5 else None

        if scode == 619 or scode == 393215:
            raise SAPError(f"Element not found on current screen", e)
        elif e.args[0] == -2147418111:
            raise SAPError("SAP session disconnected", e)
        elif e.args[0] == -2147221008:
            raise SAPError("COM not initialized — call CoInitialize() first", e)
        else:
            raise SAPError(f"SAP COM error: {e.args[1]}", e)
```

---

## 32-bit vs 64-bit

| SAP GUI Version | Bitness | Compatible Python |
|----------------|---------|-------------------|
| SAP GUI ≤ 7.70 | 32-bit only | 32-bit Python |
| SAP GUI 8.00+ | 32-bit or 64-bit (choose during install) | Must match: 32→32, 64→64 |

### Validation Script (run first!)
```python
import sys
import win32com.client

print(f"Python: {sys.version}")
print(f"Python bitness: {'64-bit' if sys.maxsize > 2**32 else '32-bit'}")

try:
    sap = win32com.client.GetObject("SAPGUI")
    engine = sap.GetScriptingEngine
    print(f"SAP GUI version: {engine.Children(0).Children(0).Info.ApplicationServer}")
    print("SUCCESS: COM connection works!")
except Exception as e:
    print(f"FAILED: {e}")
    print("Try the other Python bitness, or check if SAP GUI is running.")
```
