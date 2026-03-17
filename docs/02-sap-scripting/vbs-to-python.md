# VBScript → Python Conversion Guide

## Why Conversion Is Needed

SAP's built-in script recorder outputs VBScript (`.vbs`). Our bridge runs Python. The good news: the conversion is mostly mechanical — add parentheses, remove `Set`, and adjust a few patterns.

## Conversion Rules

### 1. Connection Preamble

**VBScript** (recorded preamble — replace entirely):
```vbscript
If Not IsObject(application) Then
   Set SapGuiAuto = GetObject("SAPGUI")
   Set application = SapGuiAuto.GetScriptingEngine
End If
If Not IsObject(connection) Then
   Set connection = application.Children(0)
End If
If Not IsObject(session) Then
   Set session = connection.Children(0)
End If
If IsObject(WScript) Then
   WScript.ConnectObject session, "on"
   WScript.ConnectObject application, "on"
End If
```

**Python** (replacement — 2 lines):
```python
import win32com.client
SapGui = win32com.client.GetObject("SAPGUI").GetScriptingEngine
session = SapGui.FindById("ses[0]")
```

Or for the bridge pattern (session already held by COM thread):
```python
# session is already available from the COM worker thread
```

### 2. Statement-by-Statement Conversion

| VBScript | Python | Rule |
|----------|--------|------|
| `session.findById("...").text = "value"` | `session.FindById("...").Text = "value"` | Capitalize property names (optional but conventional) |
| `.sendVKey 0` | `.SendVKey(0)` | **Add parentheses** to all method calls |
| `.press` | `.Press()` | **Add parentheses** |
| `.select` | `.Select()` | **Add parentheses** |
| `.setFocus` | `.SetFocus()` | **Add parentheses** |
| `.caretPosition = 5` | `.CaretPosition = 5` | Direct assignment — same syntax |
| `.maximize` | `.Maximize()` | **Add parentheses** |
| `.resizeWorkingPane 173, 36, false` | `.ResizeWorkingPane(173, 36, False)` | Add parens + Python `False` |
| `Set x = obj.something` | `x = obj.Something` | Remove `Set` keyword |
| `True` / `False` | `True` / `False` | Same (but VBS is case-insensitive) |

### 3. Complete Conversion Example

**Recorded VBScript**:
```vbscript
session.findById("wnd[0]").maximize
session.findById("wnd[0]/tbar[0]/okcd").text = "/nSE16"
session.findById("wnd[0]").sendVKey 0
session.findById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME").text = "MARA"
session.findById("wnd[0]").sendVKey 0
session.findById("wnd[0]/usr/txtMAX_SEL").text = "100"
session.findById("wnd[0]/tbar[1]/btn[8]").press
```

**Converted Python**:
```python
session.FindById("wnd[0]").Maximize()
session.FindById("wnd[0]/tbar[0]/okcd").Text = "/nSE16"
session.FindById("wnd[0]").SendVKey(0)
session.FindById("wnd[0]/usr/ctxtDATABROWSE-TABLENAME").Text = "MARA"
session.FindById("wnd[0]").SendVKey(0)
session.FindById("wnd[0]/usr/txtMAX_SEL").Text = "100"
session.FindById("wnd[0]/tbar[1]/btn[8]").Press()
```

### 4. Patterns That Need More Thought

#### Menu navigation
```vbscript
' VBS
session.findById("wnd[0]/mbar/menu[0]/menu[3]").select
```
```python
# Python
session.FindById("wnd[0]/mbar/menu[0]/menu[3]").Select()
```

#### Handling variables in field values
```vbscript
' VBS
session.findById("wnd[0]/usr/ctxtMATNR").text = material_number
```
```python
# Python — use f-strings or direct variable
session.FindById("wnd[0]/usr/ctxtMATNR").Text = material_number
```

#### Multiple sessions
```vbscript
' VBS — accessing second session
Set session = connection.Children(1)
```
```python
# Python
session = connection.Children(1)
```

## Automated Conversion Script Concept

A regex-based converter can handle ~80% of recorded scripts:

```python
import re

def convert_vbs_to_python(vbs_code: str) -> str:
    lines = vbs_code.strip().split('\n')
    python_lines = []

    for line in lines:
        line = line.strip()

        # Skip VBS preamble
        if any(skip in line for skip in ['If Not IsObject', 'Set SapGuiAuto',
               'Set application', 'Set connection', 'Set session',
               'WScript.ConnectObject', 'End If']):
            continue

        # Remove 'Set ' prefix
        line = re.sub(r'^Set\s+', '', line)

        # Convert .sendVKey N → .SendVKey(N)
        line = re.sub(r'\.sendVKey\s+(\d+)', r'.SendVKey(\1)', line)

        # Convert .press → .Press()
        line = re.sub(r'\.press\b(?!\()', '.Press()', line)

        # Convert .select → .Select()
        line = re.sub(r'\.select\b(?!\()', '.Select()', line)

        # Convert .setFocus → .SetFocus()
        line = re.sub(r'\.setFocus\b(?!\()', '.SetFocus()', line)

        # Convert .maximize → .Maximize()
        line = re.sub(r'\.maximize\b(?!\()', '.Maximize()', line)

        # Convert .iconify → .Iconify()
        line = re.sub(r'\.iconify\b(?!\()', '.Iconify()', line)

        # Convert method calls with space-separated args:
        # .resizeWorkingPane 173, 36, false → .ResizeWorkingPane(173, 36, False)
        line = re.sub(
            r'\.resizeWorkingPane\s+(.+)',
            lambda m: f'.ResizeWorkingPane({m.group(1).replace("false","False").replace("true","True")})',
            line
        )

        # Convert VBS booleans
        line = line.replace(' false', ' False').replace(' true', ' True')

        # Convert VBS comments ' → #
        line = re.sub(r"^'(.*)$", r'#\1', line)

        if line and not line.startswith('#'):
            python_lines.append(line)

    return '\n'.join(python_lines)
```

## Things the Converter Cannot Handle

- Complex VBS control flow (`For Each`, `Do While`, `Select Case`) — needs manual rewrite
- Error handling (`On Error Resume Next`) — replace with Python try/except
- VBS-specific functions (`MsgBox`, `InputBox`, `WScript.Sleep`) — replace with Python equivalents
- Late-bound COM object creation (`CreateObject`) — use `win32com.client.Dispatch`
- String concatenation with `&` — replace with `+` or f-strings
