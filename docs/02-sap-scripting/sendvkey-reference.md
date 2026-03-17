# SendVKey Reference

The `SendVKey(n)` method on `GuiMainWindow` and `GuiModalWindow` simulates keyboard input. The number maps to a virtual key.

## Common Keys

| VKey | Keyboard | Typical SAP Action |
|------|----------|--------------------|
| 0 | Enter | Confirm / Continue / Execute |
| 1 | F1 | Help |
| 2 | F2 | Double-click equivalent |
| 3 | F3 (Back) | Go back one screen |
| 4 | F4 | Search help / value list |
| 5 | F5 | Top of list |
| 6 | F6 | End of list |
| 7 | F7 | Table contents button (SE16) |
| 8 | F8 | Execute / Run |
| 9 | F9 | Select all |
| 10 | F10 | Menu bar activation |
| 11 | Ctrl+S | Save |
| 12 | F12 / Esc | Cancel |

## Extended Keys (Ctrl+Fn)

| VKey | Keyboard | Typical SAP Action |
|------|----------|--------------------|
| 24 | Ctrl+F12 | Often mapped to Copy/Export |
| 25 | Ctrl+F1 | |
| 26 | Ctrl+F2 | |
| 27 | Ctrl+F3 | |
| 28 | Ctrl+F4 | Close window |
| 29 | Ctrl+F5 | |
| 30 | Ctrl+F6 | |
| 31 | Ctrl+F7 | |
| 32 | Ctrl+F8 | |
| 33 | Ctrl+F9 | |
| 34 | Ctrl+F10 | |
| 35 | Ctrl+F11 | |

## Shift+Fn Keys

| VKey | Keyboard |
|------|----------|
| 36–47 | Shift+F1 through Shift+F12 |

## Ctrl+Shift+Fn Keys

| VKey | Keyboard |
|------|----------|
| 70 | Ctrl+Shift+F10 (Context menu) |
| 71–82 | Ctrl+Shift+F1 through Ctrl+Shift+F12 |

## Usage in Python

```python
# Press Enter
session.FindById("wnd[0]").SendVKey(0)

# Press F8 (Execute)
session.FindById("wnd[0]").SendVKey(8)

# Press Back (F3)
session.FindById("wnd[0]").SendVKey(3)

# Press Save (Ctrl+S)
session.FindById("wnd[0]").SendVKey(11)

# Press Cancel (F12)
session.FindById("wnd[0]").SendVKey(12)

# Dismiss a modal popup (press Enter on it)
session.FindById("wnd[1]").SendVKey(0)
```

## Discovering VKey Mappings

When you record a macro in SAP, button presses appear as `sendVKey n`. To find what a specific key does:

1. Use `session.FindById("wnd[0]").GetVKeyDescription(n)` — returns human-readable text
2. Check the application toolbar button tooltips in Scripting Tracker
3. The mapping can vary by transaction — the same VKey number may trigger different functions in different screens
