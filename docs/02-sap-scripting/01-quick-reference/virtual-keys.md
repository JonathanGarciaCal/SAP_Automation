# Quick Reference — Virtual Key Codes (SendVKey)

The `SendVKey(code)` method simulates keyboard input. Map the code number to the actual keyboard shortcut.

## Common Keys

| Code | Key | Typical SAP Action |
|------|-----|-------------------|
| **0** | **Enter** | ✓ Confirm / Continue / Execute |
| **1** | F1 | Help / Info |
| **2** | F2 | Double-click equivalent |
| **3** | F3 | ← Back / Previous screen |
| **4** | F4 | ↓ Search help / Dropdown |
| **5** | F5 | ↑ Top of list |
| **6** | F6 | ↓ End of list |
| **7** | F7 | More options (F7) |
| **8** | F8 | ⚙ Execute / Run |
| **9** | F9 | Select all |
| **10** | F10 | Menu bar |
| **11** | Ctrl+S | 💾 Save |
| **12** | Esc / F12 | ✕ Cancel / Exit |

## Extended Keys (Ctrl+Fn)

| Code | Key | Typical Use |
|------|-----|-------------|
| **13**–**23** | Ctrl+F1–F11 | Function-specific |
| **24** | Ctrl+F12 | Copy / Export |
| **25**–**35** | Ctrl+F1–F11 | Vary by transaction |

## Shift+Fn Keys  

| Code | Key |
|------|-----|
| **36**–**47** | Shift+F1–F12 |

## Ctrl+Shift+Fn Keys

| Code | Key |
|------|-----|
| **70** | Ctrl+Shift+F10 (Context menu) |
| **71**–**82** | Ctrl+Shift+F1–F12 |

## Usage

```python
import time

# Press Enter to confirm transaction
session.FindById("wnd[0]").SendVKey(0)
time.sleep(0.5)

# Press F3 to go back
session.FindById("wnd[0]").SendVKey(3)

# Press F8 to execute
session.FindById("wnd[0]").SendVKey(8)

# Press Ctrl+S to save
session.FindById("wnd[0]").SendVKey(11)

# Dismiss a modal dialog (press Enter)
session.FindById("wnd[1]").SendVKey(0)
```

## Finding the Right Code

Use **Scripting Tracker** to discover key codes:
1. Download: https://tracker.stschnell.de/
2. Click on buttons in SAP GUI
3. Scripting Tracker shows the VKey code in output

Or record a macro in SAP (Customize Local Layout → Record) — the output shows SendVKey for each button press.

---

See also: [Object Model Reference](../00-foundation/01-object-model.md#controls)
