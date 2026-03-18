# Quick Reference — Security, Tools & Setup

## SAP Security & Authorization

### Server Parameters (RZ11/RZ10)

| Parameter | Default | Recommended | Effect |
|-----------|---------|-------------|--------|
| `sapgui/user_scripting` | FALSE | **TRUE** | Enable scripting API |
| `sapgui/user_scripting_per_user` | FALSE | TRUE | Restrict to authorized users |
| `sapgui/user_scripting_disable_recording` | FALSE | FALSE | Allow recording |
| `sapgui/user_scripting_set_readonly` | FALSE | FALSE | Allow read-write scripting |
| `sapgui/user_scripting_force_notification` | TRUE | **FALSE** | Suppress pop-ups during automation |

**How to set (RZ10 - permanent):**
- Transaction `RZ10`
- Select instance → Extended Maintenance
- Parameter: `sapgui/user_scripting_force_notification`
- Value: `FALSE`
- Save & request system restart

### Authorization Object `S_SCR`

When `sapgui/user_scripting_per_user = TRUE`, users need authorization object `S_SCR`:

- Assign via role configuration (SE16 → T100S)
- Without it: scripting blocked even if enabled server-wide

### Client Options (SAP GUI)

Path: **Options** → **Accessibility and Scripting** → **Scripting**

Checkboxes to configure:
- ✓ **Enable Scripting** (must be checked)
- ☐ "Notify when script attaches to SAP GUI" (uncheck for automation)
- ☐ "Notify when script opens connection" (uncheck for automation)

---

## Development Tools

### Scripting Tracker (Recommended)

- **Download**: https://tracker.stschnell.de/ (extract, no install)
- **Versions**: 32-bit & 64-bit available
- **Status**: Mature/stable (SAP will not update)

**Key Features:**
- **Analyzer**: Browse SAP GUI object tree, see element IDs & properties
  - Click any element → Right-click → Copy ID
  - Red border highlights element in SAP
- **Recorder**: Records automation sequences in Python/VBScript/PowerShell
- **Comparator**: Diff two screens to find changed elements
- **Help**: Built-in reference of all SAP scripting objects

**Download & run:**
```bash
# Extract Tracker_654_x64.zip
# Double-click Tracker.exe
# Connect to running SAP GUI automatically
```

### SAP Built-in Recorder  

Path: **Customize Local Layout** → **Script Recording and Playback**

- **Output**: VBScript (`.vbs` files)
- **Good for**: Quick prototyping
- **Limitations**: Lower quality than Scripting Tracker, cannot inspect grid cells

### Type Library Browser

The SAP COM type library is at:
```
C:\Program Files\SAP\FrontEnd\SAPgui\sapfewse.ocx
```

Load into:
- **Excel**: VBA Tools → References → Browse → select `.ocx` → gains IntelliSense
- **Python**: Use `comtypes.gen` to auto-generate stubs

---

## Element ID Patterns

### Path Structure

```
wnd[0]/usr/ctxtFIELD-NAME
│      │    │
│      │    └─ Type prefix + field name
│      └─ User area
└─ Window index
```

### Common Prefixes

| Prefix | Control Type | Example |
|--------|---|---|
| `txt` | Text (read-only) | `wnd[0]/usr/txtMATPO` |
| `ctxt` | Text with F4 search | `wnd[0]/usr/ctxtMATNR` |
| `pwd` | Password field | `wnd[0]/usr/pwdPASSWORD` |
| `chk` | Checkbox | `wnd[0]/usr/chkFLAG` |
| `rad` | Radio button | `wnd[0]/usr/radOPTION[0]` |
| `btn` | Button | `wnd[0]/usr/btnBUTTON` |
| `cmb` | Dropdown | `wnd[0]/usr/cmbCLIENT` |
| `lbl` | Label (static text) | `wnd[0]/usr/lblLABEL` |
| `tbl` | Table control | `wnd[0]/usr/tblLINE_ITEMS` |
| `okcd` | OK code field | `wnd[0]/tbar[0]/okcd` |
| `btn[N]` | Toolbar button | `wnd[0]/tbar[0]/btn[0]` (Enter) |
| `cntl.../shell` | Grid/Tree | `wnd[0]/usr/cntl.../shellcont/shell` |

### Toolbar Buttons

| Index | Typical Action |
|-------|---|
| `btn[0]` | ✓ Enter |
| `btn[1]` | ? Info |
| `btn[2]` | ≡ Menu |
| `btn[3]` | ← Back |
| `btn[8]` (tbar[1]) | ⚙ Execute (F8) |

---

## Troubleshooting

| Issue | Check | Solution |
|-------|-------|----------|
| "Could not be found by id" | Element timing | Add `time.sleep(0.5)` before access |
| Scripting not working | Server param | RZ11: `sapgui/user_scripting = TRUE` |
| Scripts are slow | Wait strategy | Use adaptive waits (see Performance guide) |
| Different element IDs each time | Screen changes | Use Scripting Tracker to verify IDs on each screen |

---

See also:
- [Object Model](../00-foundation/01-object-model.md)
- [Performance Optimization](../03-production-patterns/performance-optimization.md)
