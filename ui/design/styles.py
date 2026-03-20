"""Reusable Tailwind class strings for NiceGUI .classes() calls.

This module is the single source of truth for all UI styling. Reference these
constants instead of writing inline class strings in components or pages.

Usage pattern:
    ```python
    from ui.design import styles

    with ui.card().classes(styles.Card.BASE):
        ui.label('Title').classes(styles.Text.HEADING)
        ui.label('Body').classes(styles.Text.BODY)

    with ui.card().classes(styles.Card.WARNING):
        ui.label('Alert').classes(styles.Text.WARNING)

    ui.button('Save').props(styles.Button.PRIMARY_PROPS)
    ```

Naming convention:
    Each class groups related elements (Card, Text, Button, Layout, …).
    Constants are UPPER_SNAKE_CASE strings of Tailwind utility classes.
    Props strings (for .props()) are suffixed _PROPS.
"""

from __future__ import annotations


# ─────────────────────────────────────────────────────────────────────────────
# Page layout
# ─────────────────────────────────────────────────────────────────────────────

class Layout:
    """Top-level page structure classes."""
    PAGE        = 'w-full h-full flex flex-col'
    ROW         = 'w-full flex flex-row items-center gap-4'
    ROW_CENTER  = 'w-full flex flex-row items-center justify-center gap-4'
    COLUMN      = 'w-full flex flex-col gap-4'
    CONTENT     = 'flex-grow p-4 overflow-auto'
    DIVIDER     = 'w-full border-t border-gray-200 my-2'


# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────

class Header:
    """Top application header."""
    CONTAINER        = 'bg-blue-700 text-white p-3 shadow-lg'
    TITLE            = 'text-h6 font-bold'
    SUBTITLE         = 'text-subtitle2 text-blue-100'
    STATUS_CONNECTED    = 'text-green-300'
    STATUS_DISCONNECTED = 'text-red-300'
    STATUS_UNKNOWN      = 'text-yellow-300'
    USERNAME         = 'text-white font-semibold'
    ICON_BUTTON_PROPS = 'dense flat color=white'


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar / navigation
# ─────────────────────────────────────────────────────────────────────────────

class Sidebar:
    """Left navigation sidebar."""
    CONTAINER   = 'w-48 bg-gray-100 border-r p-3 gap-2'
    TITLE       = 'text-h6 font-semibold text-gray-800'
    LINK        = 'w-full text-gray-700'
    LINK_ACTIVE = 'font-bold text-blue-600'


# ─────────────────────────────────────────────────────────────────────────────
# Cards
# ─────────────────────────────────────────────────────────────────────────────

class Card:
    """Card containers."""
    BASE    = 'w-full p-4 rounded-lg shadow'
    FLAT    = 'w-full p-4 rounded-lg'
    DENSE   = 'w-full p-2 rounded-lg shadow'

    # Semantic / status accent cards (left-border variant)
    SUCCESS = 'w-full p-4 bg-green-50 border-l-4 border-green-500'
    WARNING = 'w-full p-4 bg-orange-50 border-l-4 border-orange-500'
    ERROR   = 'w-full p-4 bg-red-50 border-l-4 border-red-500'
    INFO    = 'w-full p-4 bg-blue-50 border-l-4 border-blue-500'

    # Full-background tinted cards (for larger blocks)
    SUCCESS_TINTED = 'w-full p-4 rounded-lg bg-green-50'
    WARNING_TINTED = 'w-full p-4 rounded-lg bg-orange-50'
    ERROR_TINTED   = 'w-full p-4 rounded-lg bg-red-50'
    INFO_TINTED    = 'w-full p-4 rounded-lg bg-blue-50'


# ─────────────────────────────────────────────────────────────────────────────
# Typography
# ─────────────────────────────────────────────────────────────────────────────

class Text:
    """Typography class strings."""
    # Hierarchy
    HEADING     = 'text-h6 font-semibold text-gray-800'
    SUBHEADING  = 'text-subtitle2 text-gray-600'
    BODY        = 'text-base text-gray-700'
    SMALL       = 'text-sm text-gray-600'
    LABEL       = 'text-sm font-semibold text-gray-700'    # Form labels, section titles
    CAPTION     = 'text-xs text-gray-500'
    MONO        = 'text-sm font-mono text-gray-800'         # Code / field names

    # Semantic colors
    SUCCESS     = 'text-green-600'
    WARNING     = 'text-orange-600'
    ERROR       = 'text-red-600'
    INFO        = 'text-blue-600'
    MUTED       = 'text-gray-500'
    ON_DARK     = 'text-white'
    ON_DARK_DIM = 'text-blue-100'

    # Status indicator dots (used in header / status badges)
    DOT_SUCCESS = 'text-green-300'
    DOT_WARNING = 'text-yellow-300'
    DOT_ERROR   = 'text-red-300'


# ─────────────────────────────────────────────────────────────────────────────
# Buttons
# ─────────────────────────────────────────────────────────────────────────────

class Button:
    """Quasar prop strings for common button variants.

    These go into .props(), not .classes().

    Example:
        ui.button('Save').props(Button.PRIMARY_PROPS)
        ui.button('Cancel').props(Button.GHOST_PROPS)
    """
    PRIMARY_PROPS   = 'color=primary unelevated'
    SECONDARY_PROPS = 'color=secondary outline'
    DANGER_PROPS    = 'color=negative unelevated'
    GHOST_PROPS     = 'flat color=primary'
    GHOST_DARK_PROPS = 'flat color=white'
    ICON_DENSE_PROPS = 'dense flat'
    OUTLINE_PROPS   = 'outline'


# ─────────────────────────────────────────────────────────────────────────────
# Form elements
# ─────────────────────────────────────────────────────────────────────────────

class Form:
    """Input and form layout helpers."""
    CONTAINER   = 'w-full flex flex-col gap-3'
    FIELD       = 'w-full'
    FIELD_ROW   = 'w-full flex flex-row gap-3 items-end'
    SECTION     = 'w-full flex flex-col gap-2'
    FOOTER      = 'w-full flex flex-row gap-2 justify-end pt-2'
    PARAMS_AREA = 'w-full gap-2 p-3 bg-gray-50 rounded'   # Parameter form background tray


# ─────────────────────────────────────────────────────────────────────────────
# Modals / dialogs
# ─────────────────────────────────────────────────────────────────────────────

class Modal:
    """Dialog card structure."""
    CONTAINER   = 'w-96 gap-0'
    CONTAINER_LG = 'w-full h-screen gap-0 p-0'

    # Header bands (color-coded per semantic role)
    HEADER_BASE    = 'w-full gap-3 p-4 rounded-t'
    HEADER_SUCCESS = 'w-full gap-3 p-4 bg-green-50 rounded-t'
    HEADER_WARNING = 'w-full gap-3 p-4 bg-amber-50 rounded-t'
    HEADER_ERROR   = 'w-full gap-3 p-4 bg-red-50 rounded-t'
    HEADER_INFO    = 'w-full gap-3 p-4 bg-blue-50 rounded-t'
    HEADER_NEUTRAL = 'w-full p-4 bg-gray-100 border-b'

    CONTENT        = 'gap-3 p-4'
    FOOTER         = 'w-full gap-2 p-4 justify-end bg-gray-50'
    FOOTER_BORDER  = 'w-full gap-2 p-4 bg-gray-50 border-t justify-end'


# ─────────────────────────────────────────────────────────────────────────────
# Status badges / chips
# ─────────────────────────────────────────────────────────────────────────────

class Badge:
    """Inline status badge / chip class strings."""
    BASE        = 'px-2 py-0.5 rounded-full text-xs font-semibold'
    SUCCESS     = 'px-2 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-700'
    WARNING     = 'px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-700'
    ERROR       = 'px-2 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-700'
    INFO        = 'px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-700'
    NEUTRAL     = 'px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-600'


# ─────────────────────────────────────────────────────────────────────────────
# Icons (Material icon names used in the app)
# ─────────────────────────────────────────────────────────────────────────────

class Icons:
    """Material icon name constants — use in ui.icon() or button icon= parameter."""
    # Navigation
    HOME          = 'home'
    INSPECTOR     = 'search'
    SCRIPT_RUNNER = 'play_circle'
    REPORTS       = 'assessment'

    # Actions
    CONNECT       = 'link'
    DISCONNECT    = 'link_off'
    REFRESH       = 'refresh'
    SETTINGS      = 'settings'
    LOGOUT        = 'logout'
    UPLOAD        = 'upload_file'
    DOWNLOAD      = 'download'
    COPY          = 'content_copy'
    CLOSE         = 'close'
    CHECK         = 'check_circle'
    INFO          = 'info'
    WARNING       = 'warning'
    ERROR         = 'error'

    # SAP-specific
    SAP_CONNECTION = 'cloud_off'
    SAP_TIMEOUT    = 'schedule'
    SAP_SESSION    = 'logout'
    SAP_FIELD      = 'edit_off'
    SAP_PERMISSION = 'lock'
    SAP_AUTH       = 'password'
    SAP_GRID       = 'grid_on'


# ─────────────────────────────────────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────────────────────────────────────

def join(*parts: str) -> str:
    """Merge multiple class strings, stripping extra whitespace.

    Useful for composing base styles with conditional modifiers.

    Example:
        classes = styles.join(styles.Card.BASE, 'border-2 border-blue-500')
        element.classes(classes)
    """
    return ' '.join(p.strip() for p in parts if p.strip())
