"""Design tokens — raw values for colors, spacing, and typography.

Use these when you need exact hex values in .style() calls or custom CSS.
For Tailwind class strings (the common case), use ui.design.styles instead.

Example:
    ```python
    from ui.design.tokens import Colors, Quasar, Spacing

    # Hex color in a custom style call
    element.style(f'color: {Colors.PRIMARY}')

    # Quasar color name in a .props() call
    button.props(f'color={Quasar.PRIMARY}')

    # Spacing constant in a gap utility
    row.classes(f'gap-{Spacing.MD}')
    ```
"""

from __future__ import annotations


# ─────────────────────────────────────────────────────────────────────────────
# Raw hex palette
# ─────────────────────────────────────────────────────────────────────────────

class Colors:
    """Hex color values — use in .style() or wherever CSS strings are needed."""

    # ── Brand ─────────────────────────────────────────────────────────────────
    PRIMARY        = '#1976d2'   # Blue 700  — main brand / interactive
    PRIMARY_DARK   = '#1565c0'   # Blue 800  — hover / pressed state
    PRIMARY_LIGHT  = '#bbdefb'   # Blue 100  — tinted backgrounds
    SECONDARY      = '#26a69a'   # Teal 400  — secondary actions
    ACCENT         = '#9c27b0'   # Purple 500 — highlights / badges

    # ── Neutrals ──────────────────────────────────────────────────────────────
    WHITE          = '#ffffff'
    GRAY_50        = '#f9fafb'
    GRAY_100       = '#f3f4f6'
    GRAY_200       = '#e5e7eb'
    GRAY_300       = '#d1d5db'
    GRAY_500       = '#6b7280'
    GRAY_600       = '#4b5563'
    GRAY_700       = '#374151'
    GRAY_800       = '#1f2937'
    GRAY_900       = '#111827'
    BLACK          = '#000000'

    # ── Semantic / status ─────────────────────────────────────────────────────
    SUCCESS        = '#16a34a'   # Green 600
    SUCCESS_BG     = '#f0fdf4'   # Green 50
    SUCCESS_BORDER = '#22c55e'   # Green 500

    WARNING        = '#d97706'   # Amber 600
    WARNING_BG     = '#fffbeb'   # Amber 50
    WARNING_BORDER = '#f59e0b'   # Amber 500

    ERROR          = '#dc2626'   # Red 600
    ERROR_BG       = '#fef2f2'   # Red 50
    ERROR_BORDER   = '#ef4444'   # Red 500

    INFO           = '#2563eb'   # Blue 600
    INFO_BG        = '#eff6ff'   # Blue 50
    INFO_BORDER    = '#3b82f6'   # Blue 500


# ─────────────────────────────────────────────────────────────────────────────
# Quasar / NiceGUI named colors
# ─────────────────────────────────────────────────────────────────────────────

class Quasar:
    """Quasar color names for NiceGUI .props('color=X') calls.

    These are the string names that Quasar understands — not hex values.

    Example:
        button.props(f'color={Quasar.PRIMARY}')
        button.props(f'color={Quasar.NEGATIVE}')
    """
    PRIMARY   = 'primary'
    SECONDARY = 'secondary'
    ACCENT    = 'accent'
    POSITIVE  = 'positive'    # success / green
    NEGATIVE  = 'negative'    # error / red
    WARNING   = 'warning'
    INFO      = 'info'
    WHITE     = 'white'
    DARK      = 'dark'


# ─────────────────────────────────────────────────────────────────────────────
# Spacing scale  (maps to Tailwind numeric suffixes: gap-X, p-X, m-X)
# ─────────────────────────────────────────────────────────────────────────────

class Spacing:
    """Tailwind spacing scale indices — use as gap-{X}, p-{X}, m-{X}."""
    XS  = 1    # 4 px
    SM  = 2    # 8 px
    MD  = 4    # 16 px
    LG  = 6    # 24 px
    XL  = 8    # 32 px
    XXL = 12   # 48 px


# ─────────────────────────────────────────────────────────────────────────────
# Typography scale (Tailwind / Quasar class fragments)
# ─────────────────────────────────────────────────────────────────────────────

class FontSize:
    """Tailwind text-size class names."""
    XS   = 'text-xs'    # 12 px
    SM   = 'text-sm'    # 14 px
    BASE = 'text-base'  # 16 px
    LG   = 'text-lg'    # 18 px
    XL   = 'text-xl'    # 20 px
    H6   = 'text-h6'    # Quasar heading 6 (≈ 20 px)
    H5   = 'text-h5'    # Quasar heading 5 (≈ 24 px)


class FontWeight:
    """Tailwind font-weight class names."""
    NORMAL    = 'font-normal'
    MEDIUM    = 'font-medium'
    SEMIBOLD  = 'font-semibold'
    BOLD      = 'font-bold'


# ─────────────────────────────────────────────────────────────────────────────
# Elevation / shadow
# ─────────────────────────────────────────────────────────────────────────────

class Shadow:
    """Tailwind shadow class names."""
    NONE   = 'shadow-none'
    SM     = 'shadow-sm'
    BASE   = 'shadow'
    MD     = 'shadow-md'
    LG     = 'shadow-lg'
    XL     = 'shadow-xl'


# ─────────────────────────────────────────────────────────────────────────────
# Border radius
# ─────────────────────────────────────────────────────────────────────────────

class Radius:
    """Tailwind border-radius class names."""
    NONE   = 'rounded-none'
    SM     = 'rounded-sm'
    BASE   = 'rounded'
    MD     = 'rounded-md'
    LG     = 'rounded-lg'
    XL     = 'rounded-xl'
    FULL   = 'rounded-full'
