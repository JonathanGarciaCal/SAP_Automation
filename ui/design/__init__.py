"""UI Design Library — centralized design tokens and style constants.

This package is the single source of truth for all visual styling in the app.
Import from here instead of writing inline Tailwind strings in components.

Quick reference:
    from ui.design import styles, tokens

    # Tailwind class strings  → element.classes(...)
    styles.Card.BASE
    styles.Card.WARNING
    styles.Text.HEADING
    styles.Text.ERROR
    styles.Header.CONTAINER
    styles.Sidebar.CONTAINER
    styles.Modal.HEADER_ERROR
    styles.Badge.SUCCESS
    styles.Button.PRIMARY_PROPS     # → element.props(...)
    styles.Icons.LOGOUT             # → ui.icon(styles.Icons.LOGOUT)
    styles.join(a, b)               # merge class strings

    # Raw hex values / Quasar names  → element.style(...) / element.props(...)
    tokens.Colors.PRIMARY
    tokens.Colors.ERROR
    tokens.Quasar.NEGATIVE
    tokens.Spacing.MD
    tokens.FontSize.H6
    tokens.Shadow.LG

Modules:
    styles  — Tailwind class-string constants grouped by component type
    tokens  — Raw design tokens (hex colors, Quasar color names, spacing scale)
"""

from ui.design import styles, tokens
from ui.design.styles import join

__all__ = ['styles', 'tokens', 'join']
