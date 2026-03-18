# Quick Reference — VBScript to Python Conversion

SAP's macro recorder outputs VBScript. Convert to Python using these rules.

## Conversion Rule Summary

| VBScript | Python | Rule |
|----------|--------|------|
| `session.findById(...)` | `session.FindById(...)` | Capitalize (.findById → .FindById) |
| `.text = "value"` | `.Text = "value"` | Capitalize properties |
| `.sendVKey 0` | `.SendVKey(0)` | **Add parentheses** |
| `.press` | `.Press()` | **Add parentheses** |
| `Set x = object` | `x = object` | Remove `Set` keyword |
| `True` / `False` | `True` / `False` | Same (Python capitalizes) |

## Full Example

### Recorded VBScript
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

session.findById("wnd[0]").maximize
session.findById("wnd[0]/tbar[0]/okcd").text = "/nMM01"
session.findById("wnd[0]").sendVKey 0
session.findById("wnd[0]/usr/ctxtMATNR").text = "TEST-001"
session.findById("wnd[0]/tbar[1]/btn[8]").press
```

### Converted Python
```python
import win32com.client

sap_gui = win32com.client.GetObject("SAPGUI")
app = sap_gui.GetScriptingEngine
connection = app.Children(0)
session = connection.Children(0)

session.FindById("wnd[0]").Maximize()
session.FindById("wnd[0]/tbar[0]/okcd").Text = "/nMM01"
session.FindById("wnd[0]").SendVKey(0)
session.FindById("wnd[0]/usr/ctxtMATNR").Text = "TEST-001"
session.FindById("wnd[0]/tbar[1]/btn[8]").Press()
```

## Line-by-Line Conversions

### Navigation & Control

```vbscript
' VBS
session.findById("wnd[0]/tbar[0]/okcd").text = "/nSE16"
session.findById("wnd[0]").sendVKey 0
```

```python
# Python
session.FindById("wnd[0]/tbar[0]/okcd").Text = "/nSE16"
session.FindById("wnd[0]").SendVKey(0)
```

### Field Input

```vbscript
' VBS
session.findById("wnd[0]/usr/ctxtMATNR").text = material
session.findById("wnd[0]/usr/txtQTY").text = "100"
session.findById("wnd[0]/usr/chkFLAG").selected = True
```

```python
# Python
session.FindById("wnd[0]/usr/ctxtMATNR").Text = material
session.FindById("wnd[0]/usr/txtQTY").Text = "100"
session.FindById("wnd[0]/usr/chkFLAG").Selected = True
```

### Buttons & Actions

```vbscript
' VBS
session.findById("wnd[0]/tbar[0]/btn[0]").press     ' Enter
session.findById("wnd[0]/tbar[1]/btn[8]").press     ' Execute
session.findById("wnd[0]/usr/btnSAVE").press         ' Save button
```

```python
# Python
session.FindById("wnd[0]/tbar[0]/btn[0]").Press()    # Enter
session.FindById("wnd[0]/tbar[1]/btn[8]").Press()    # Execute
session.FindById("wnd[0]/usr/btnSAVE").Press()        # Save button
```

### Window Operations

```vbscript
' VBS
session.findById("wnd[0]").maximize
session.findById("wnd[0]").iconify
session.findById("wnd[0]").close
```

```python
# Python
session.FindById("wnd[0]").Maximize()
session.FindById("wnd[0]").Iconify()
session.FindById("wnd[0]").Close()
```

## Common Patterns to Skip

These VBScript lines can be deleted or converted to passes:

```vbscript
' Skip these — they're preamble
If Not IsObject(application) Then ...
Set SapGuiAuto = GetObject("SAPGUI")
End If
WScript.ConnectObject ...

' These are performance-irrelevant in SAP GUI (skip them):
session.findById("wnd[0]").resizeWorkingPane 173, 36, false
session.findById("wnd[0]/tbar[0]/okcd").caretPosition = 5
```

## Property Name Capitalization

**Important:** SAP COM is case-insensitive for API calls, but Python conventions prefer CamelCase.

```python
# All equivalent (SAP COM is case-insensitive)
session.findById("wnd[0]/usr/ctxtMATNR").text = "TEST"
session.FindById("wnd[0]/usr/ctxtMATNR").Text = "TEST"
session.FINDBYID("wnd[0]/usr/ctxtMATNR").TEXT = "TEST"  # Unusual

# Recommended: Use PascalCase for methods, properties
session.FindById("wnd[0]/usr/ctxtMATNR").Text = "TEST"
```

## Methods Requiring Parentheses

Any method call needs parentheses in Python (unlike VBScript):

```python
# VBScript — parens optional
session.findById("wnd[0]").maximize          ' No parens

# Python — parens required
session.FindById("wnd[0]").Maximize()        # Parens required

# Methods with arguments
session.FindById("wnd[0]/usr/ctxtMATNR").SetFocus()
session.FindById("wnd[0]").SendVKey(0)
```

---

See also: [Object Model Reference](../00-foundation/01-object-model.md), [Virtual Key Codes](virtual-keys.md)
