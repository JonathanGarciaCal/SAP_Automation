# openpyxl: Comprehensive AI Agent Documentation Reference

**openpyxl is the dominant Python library for reading, writing, and modifying Excel 2010+ (.xlsx) files — and the single most important tool an AI agent needs for programmatic spreadsheet manipulation.** With **251 million monthly PyPI downloads** and over 7,400 dependent packages, it serves as the default Excel engine for pandas and countless automation workflows. The library handles the full Office Open XML specification — cells, styles, formulas, charts, images, and more — entirely in pure Python with no Excel installation required. For AI agents that must ingest spreadsheet data, produce formatted reports, or modify existing workbooks, openpyxl provides the most complete read-write-modify capability of any Python Excel library.

---

## What openpyxl does and where it fits

openpyxl reads and writes files in the **Office Open XML format**: `.xlsx`, `.xlsm` (macro-enabled), `.xltx`, and `.xltm` (templates). It was created in 2010 to fill Python's gap in native `.xlsx` support, initially inspired by PHPExcel. The library is **100% pure Python** — no compiled extensions, no Excel installation, no platform restrictions.

**Core capabilities** span the full spreadsheet lifecycle. An agent can create workbooks from scratch, load and parse existing files, modify cell values and formatting, insert charts and images, manage named ranges and data validations, and save the result — all programmatically. openpyxl also integrates directly with pandas via `dataframe_to_rows()`, making it the bridge between data analysis and formatted Excel output.

The library sits in a specific niche relative to alternatives. **XlsxWriter** is ~15–40% faster for write-only workloads but cannot read or modify existing files. **xlrd** handles legacy `.xls` files but has deprecated `.xlsx` support. **xlwings** communicates with a running Excel instance for formula recalculation but requires Excel installed. **pandas** uses openpyxl (or XlsxWriter) as its engine under the hood. For AI agents that need read-write-modify capability on `.xlsx` files without platform dependencies, openpyxl is the only complete option.

---

## Core API: Workbook, Worksheet, and Cell

The API is organized around three primary classes that mirror Excel's object hierarchy: a **Workbook** contains **Worksheets**, which contain **Cells**.

### Workbook — the top-level container

```python
from openpyxl import Workbook, load_workbook

# Create new
wb = Workbook()                          # Always has one default sheet
wb = Workbook(write_only=True)           # Optimized for large files

# Load existing
wb = load_workbook('file.xlsx')
wb = load_workbook('file.xlsx', read_only=True, data_only=True)
```

The `load_workbook()` function accepts six parameters that dramatically affect behavior:

| Parameter | Default | Effect |
|-----------|---------|--------|
| `filename` | required | Path string or file-like object (binary mode) |
| `read_only` | `False` | Lazy-loads rows for near-constant memory; returns `ReadOnlyCell` objects |
| `data_only` | `False` | Returns cached formula results instead of formula strings |
| `keep_vba` | `False` | Preserves VBA macros (uneditable) for round-trip `.xlsm` files |
| `keep_links` | `True` | Preserves external workbook link caches |
| `rich_text` | `False` | Preserves rich-text formatting within cells |

Key Workbook properties include **`active`** (returns the active worksheet), **`sheetnames`** (list of sheet name strings), and **`worksheets`** (list of Worksheet objects). Key methods: `save(filename)` writes to disk (overwrites without warning), `create_sheet(title, index)` adds a worksheet at a given position, `remove(worksheet)` deletes a sheet, and `copy_worksheet(from_worksheet)` duplicates a sheet within the same workbook.

### Worksheet — the data grid

Worksheets should never be instantiated directly — always use `wb.create_sheet()` or access via `wb.active` or `wb['SheetName']`. The most important properties and methods for agents:

**Properties:** `title` (get/set sheet name), `max_row` and `max_column` (1-based bounds of data), `min_row` and `min_column`, `dimensions` (e.g., `'A1:M24'`), `values` (generator of row value tuples), `freeze_panes` (set to e.g., `'A2'` to freeze the header row).

**Cell access** uses three patterns — all with **1-based indexing**:

```python
cell = ws['A1']                          # A1 notation
cell = ws.cell(row=1, column=1)          # Numeric (1-based)
ws['A1'] = 42                            # Direct value assignment
```

**Range access** returns tuples of tuples of Cell objects:

```python
cells = ws['A1':'C3']                    # Rectangular range
col_a = ws['A']                          # Entire column
row_5 = ws[5]                            # Entire row
```

**Iteration** is the primary data-extraction mechanism:

```python
# By rows — most common for AI agents
for row in ws.iter_rows(min_row=1, max_col=5, values_only=True):
    print(row)  # Tuple of values: (val1, val2, val3, val4, val5)

# By columns
for col in ws.iter_cols(min_row=1, max_row=100, values_only=True):
    print(col)
```

**Data insertion** uses `append()` for row-by-row writing — the method AI agents will use most:

```python
ws.append(['Name', 'Age', 'City'])       # Header row
ws.append(['Alice', 30, 'NYC'])          # Data rows
ws.append({'A': 'Bob', 'C': 'LA'})       # Dict-based (by column letter)
```

Other critical methods: `insert_rows(idx, amount)`, `delete_rows(idx, amount)`, `insert_cols(idx, amount)`, `delete_cols(idx, amount)`, `merge_cells('A1:D1')`, `unmerge_cells('A1:D1')`, `add_chart(chart, anchor)`, and `add_image(img, anchor)`.

### Cell — the atomic data unit

Each Cell exposes **`value`** (the Python-typed content), **`data_type`** (one of `'s'`, `'n'`, `'b'`, `'f'`, `'e'` for string/number/boolean/formula/error), **`coordinate`** (e.g., `'B5'`), **`row`** and **`column`** (1-based integers), **`column_letter`**, **`number_format`** (string like `'#,##0.00'`), **`comment`**, and **`hyperlink`**.

Python types map automatically: `str` → string, `int`/`float` → number, `datetime.datetime` → date (with default format `'yyyy-mm-dd h:mm:ss'`), `bool` → boolean, strings starting with `=` → formula, `None` → empty.

### Essential utility functions

```python
from openpyxl.utils import get_column_letter, column_index_from_string

get_column_letter(3)              # → 'C'
get_column_letter(27)             # → 'AA'
column_index_from_string('AA')    # → 27
```

---

## Common operations with code patterns

### Formatting: fonts, fills, borders, alignment

All style objects are imported from `openpyxl.styles` and are **immutable once assigned to a cell** — to modify a style, create a new object and reassign it.

```python
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment, NamedStyle

# Font
ws['A1'].font = Font(name='Calibri', size=14, bold=True, color='FF0000')

# Fill
ws['A1'].fill = PatternFill('solid', fgColor='FFFF00')

# Border
thin = Side(border_style='thin', color='000000')
ws['A1'].border = Border(left=thin, right=thin, top=thin, bottom=thin)

# Alignment
ws['A1'].alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

# Number format
ws['B1'].number_format = '#,##0.00'
ws['C1'].number_format = '0.00%'
```

**Named styles** act as reusable templates: define once with `NamedStyle(name='highlight')`, register with `wb.add_named_style(style)`, apply with `ws['A1'].style = 'highlight'`. This is significantly more efficient than creating individual style objects per cell.

### Formulas, charts, and images

**Formulas** are written as strings starting with `=`. openpyxl **never evaluates formulas** — it stores them verbatim. Function names must be in English with comma separators. When reading, `data_only=True` returns the last value Excel cached; without it, you get the formula string.

```python
ws['A1'] = '=SUM(B1:B10)'
ws['A2'] = '=VLOOKUP(C2,Sheet2!A:B,2,FALSE)'
```

**Charts** support bar, line, pie, scatter, area, bubble, radar, stock, surface, and doughnut types plus 3D variants. The pattern is consistent: create a chart object, define data with `Reference`, add data to the chart, and anchor it to a cell.

```python
from openpyxl.chart import BarChart, Reference

chart = BarChart()
chart.title = "Sales Report"
data = Reference(ws, min_col=2, min_row=1, max_row=7, max_col=3)
cats = Reference(ws, min_col=1, min_row=2, max_row=7)
chart.add_data(data, titles_from_data=True)
chart.set_categories(cats)
ws.add_chart(chart, 'E1')
```

**Images** require `pillow` installed. The API is straightforward:

```python
from openpyxl.drawing.image import Image
img = Image('logo.png')
img.width, img.height = 300, 200
ws.add_image(img, 'B2')
```

### Named ranges and data management

Named ranges use the `DefinedName` class. They require absolute references and quoted sheet names:

```python
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.utils import quote_sheetname, absolute_coordinate

ref = f"{quote_sheetname(ws.title)}!{absolute_coordinate('A1:A100')}"
defn = DefinedName("data_range", attr_text=ref)
wb.defined_names["data_range"] = defn
```

**Auto-filters** can be configured but are only applied when the file is opened in Excel — openpyxl writes the filter instructions without actually hiding rows: `ws.auto_filter.ref = "A1:D100"`.

---

## How AI agents should use openpyxl

AI agents interact with openpyxl in three primary patterns: **reading data for analysis**, **writing structured output**, and **modifying existing files**. Each has distinct best practices.

### Reading spreadsheet data into agent context

The most common agent task is extracting data from a user-provided `.xlsx` file. The optimal pattern uses `iter_rows(values_only=True)` for clean tuple output, with `read_only=True` for large files to avoid memory exhaustion:

```python
from openpyxl import load_workbook

wb = load_workbook('input.xlsx', read_only=True, data_only=True)
ws = wb.active

headers = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
data = []
for row in ws.iter_rows(min_row=2, values_only=True):
    data.append(dict(zip(headers, row)))

wb.close()  # Critical in read_only mode
```

Agents should **always use `data_only=True`** when they need computed values rather than formula strings. However, agents must be aware that if the file was never opened in Excel, formula cells return `None` — a frequent source of agent confusion.

### Writing structured output

When agents produce tabular results — analysis summaries, extracted entities, generated reports — the pattern combines `append()` for data with formatting for readability:

```python
wb = Workbook()
ws = wb.active
ws.title = "Analysis Results"

# Header with formatting
headers = ['Entity', 'Category', 'Confidence', 'Source']
ws.append(headers)
for cell in ws[1]:
    cell.font = Font(bold=True)
    cell.fill = PatternFill('solid', fgColor='4472C4')
    cell.font = Font(bold=True, color='FFFFFF')

# Data rows
for result in agent_results:
    ws.append([result.entity, result.category, result.confidence, result.source])

# Auto-width columns (common agent utility)
for col in ws.columns:
    max_len = max(len(str(cell.value or '')) for cell in col)
    ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)

wb.save('output.xlsx')
```

For large outputs exceeding tens of thousands of rows, agents should use **write-only mode** (`Workbook(write_only=True)`) to maintain constant memory. In this mode, only `ws.append()` works — no random cell access. Metadata like `freeze_panes` must be set before appending any data.

### Modifying existing files

Agents frequently need to update specific cells, add sheets to existing workbooks, or annotate data. The key risk is **data loss on round-trip** — openpyxl silently drops unsupported elements (shapes, some drawings, certain XML extensions) when saving. Agents should always save to a new filename:

```python
wb = load_workbook('original.xlsx')
ws = wb.active
ws['E1'] = 'Agent Notes'
for row_idx in range(2, ws.max_row + 1):
    ws.cell(row=row_idx, column=5, value='Reviewed')
wb.save('original_annotated.xlsx')  # Never overwrite the original
```

For macro-enabled files, agents must use `keep_vba=True` when loading and save with the `.xlsm` extension — failing to do so produces a corrupted file.

---

## Critical limitations and gotchas agents must handle

Several openpyxl behaviors are non-obvious and cause frequent agent failures:

- **No formula evaluation.** openpyxl cannot compute `=SUM(A1:A10)`. The `data_only=True` flag only retrieves values Excel previously cached. Files created by openpyxl (never opened in Excel) will have `None` for all formula cells when read with `data_only=True`. Agents needing computed values must calculate them in Python.

- **Memory scales at ~50× file size.** A 50 MB Excel file consumes roughly **2.5 GB of RAM** in normal mode. Agents processing user-uploaded files must use `read_only=True` for any file over a few MB, and `write_only=True` when generating large outputs.

- **1-based indexing throughout.** Both `row` and `column` parameters are 1-based, unlike Python conventions. `ws.cell(row=0, column=0)` raises an error.

- **Shapes and objects silently dropped.** Opening and re-saving a file strips shapes, SmartArt, embedded objects, and other elements openpyxl doesn't model. This is the most dangerous pitfall for modify-and-save workflows.

- **Not thread-safe.** Workbook objects cannot be shared across threads. Agents running concurrent operations must use separate processes or external locks.

- **No `.xls` support.** Legacy binary Excel files require `xlrd`. The `.xlsb` binary format requires `pyxlsb`. Agents must check file extensions before attempting to load.

- **No pivot table creation.** Existing pivot tables can be preserved on round-trip, but agents cannot create new ones programmatically.

- **Accessing empty cells creates them.** Iterating over `ws['A1':'Z1000']` instantiates all cells in memory even if they're empty, potentially bloating the workbook.

---

## Version, compatibility, and security posture

**Current stable version: 3.1.5** (released June 28, 2024). No new releases have been published in over 18 months, though the project's maintenance status is classified as "Sustainable" by Snyk with **no known security vulnerabilities** in the current version. The library requires **Python ≥ 3.8** (Python 3.6 and 3.7 were dropped in v3.1.4). Its sole hard dependency is `et-xmlfile`; optional dependencies include `pillow` (images), `lxml` (performance), `defusedxml` (security), and `pandas` (DataFrame integration).

**Security is a critical concern for agents processing untrusted files.** By default, openpyxl does not guard against XML billion-laughs or quadratic-blowup attacks. Installing `defusedxml` mitigates this — agents operating in production environments where users upload Excel files **must** have `defusedxml` installed. A historical CVE (CVE-2017-5992) for XML external entity attacks was fixed in v2.4.1 and does not affect current versions.

The project is hosted on Heptapod (a Mercurial-based GitLab instance) at `foss.heptapod.net/openpyxl/openpyxl`, maintained primarily by a single lead developer (Charlie Clark), with fewer than 10 total contributors. Despite the small team, openpyxl's position as the default pandas Excel engine ensures its long-term relevance — it is deeply embedded in the Python data ecosystem.

## Conclusion

For AI agents, openpyxl's value lies in three strengths: it is the **only Python library that can read, write, and modify `.xlsx` files**; it maps naturally to agent workflows (ingest data → process → output formatted results); and its pure-Python architecture runs anywhere without platform dependencies. The critical patterns agents need are `load_workbook(read_only=True, data_only=True)` for extraction, `ws.append()` loops with formatting for output, and strict discipline around saving to new filenames to prevent data loss. The library's two most dangerous gaps — no formula evaluation and silent dropping of unsupported elements — must be explicitly handled in agent logic. With `defusedxml` installed for security and `lxml` for performance, openpyxl provides a robust, production-ready Excel interface for any AI agent operating on structured spreadsheet data.
