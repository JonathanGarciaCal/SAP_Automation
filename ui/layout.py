"""Common UI layout components and wrappers.

Provides reusable page layout containers with header, sidebar, and main content area.
Handles error display, responsive layout, and consistent styling across all pages.

Example:
    ```python
    from ui.layout import create_page_layout
    
    with create_page_layout(title='Home'):
        ui.label('Welcome to SAP Automation')
        ui.button('Start')
    ```
"""

import logging
from contextlib import contextmanager
from typing import Generator, Optional

from nicegui import ui

from config import RuntimeConfig
from ui.app import get_app_state
from ui.design import styles

logger = logging.getLogger(__name__)


@contextmanager
def create_page_layout(
    title: str,
    show_sidebar: bool = True,
    show_header: bool = True
) -> Generator:
    """Create standard page layout with header, sidebar, and main content area.
    
    Yields a column container for page-specific content. Automatically wraps
    all page content with consistent header, sidebar, and error display.
    
    Layout structure:
        ┌─ Header ─────────────────────────────────┐
        │ App Icon | Title | Status | User | Logout│
        ├────────┬──────────────────────────────────┤
        │ Sidebar│ Content Area                     │
        │        │ [Error Banner if error]          │
        │        │                                  │
        │        │ [Page Content - Yield Here]      │
        │        │                                  │
        └────────┴──────────────────────────────────┘
    
    Args:
        title: Page title to display in header and sidebar indicator
        show_sidebar: Show left navigation sidebar (default: True)
        show_header: Show top header bar (default: True)
        
    Yields:
        Column UI element containing page content area
        
    Example:
        ```python
        with create_page_layout(title='Home', show_sidebar=True):
            ui.label('Page specific content')
            ui.button('Click me')
        ```
    """
    
    logger.debug("Creating page layout: title=%s, sidebar=%s, header=%s", 
                 title, show_sidebar, show_header)
    
    # Get global app state
    app_state = get_app_state()
    config: Optional[RuntimeConfig] = app_state.get('config')
    
    # ─────────────────────────────────────────────────────────
    # Header (if enabled) - MUST BE TOP-LEVEL, not nested
    # ─────────────────────────────────────────────────────────
    if show_header:
        from ui.components import header
        header.render(title=title, session=app_state.get('session'), config=config)
    
    # ─────────────────────────────────────────────────────────
    # Main content area with sidebar and content column
    # ─────────────────────────────────────────────────────────
    with ui.row().classes('w-full flex-grow gap-0'):
        
        # Sidebar (if enabled)
        if show_sidebar:
            from ui.components import sidebar
            sidebar.render(current_route=title.lower(), config=config)
        
        # Main content column
        with ui.column().classes('flex-grow gap-4 p-4') as main_content:
            
            # Error banner (shows if app_state['error'] is set)
            error_label = ui.label().classes(styles.Text.ERROR + ' text-sm')
            error_label.visible = False
            
            def update_error_display():
                """Update error display when app state changes."""
                if app_state.get('error'):
                    error_label.text = f"⚠️ {app_state['error']}"
                    error_label.visible = True
                else:
                    error_label.visible = False
            
            # Check for errors initially
            update_error_display()
            
            # Yield content area to caller
            yield main_content


def create_card(title: str, **classes_dict) -> None:
    """Create a styled card container for content sections.
    
    Args:
        title: Card title/heading
        **classes_dict: Additional CSS classes to apply (e.g., classes='gap-4')
        
    Example:
        ```python
        with create_card('Connection Status'):
            ui.label('Status: Connected')
        ```
    """
    card_classes = styles.Card.BASE
    if 'classes' in classes_dict:
        card_classes = styles.join(card_classes, classes_dict['classes'])

    with ui.card().classes(card_classes):
        ui.label(title).classes(styles.Text.HEADING)


class PageSection:
    """Helper for creating consistent page sections with title and content."""
    
    def __init__(self, title: str, description: Optional[str] = None):
        """Initialize page section.
        
        Args:
            title: Section title
            description: Optional description text
        """
        self.title = title
        self.description = description
    
    def __enter__(self):
        """Enter section context (create card and title)."""
        self.container = ui.column().classes('w-full gap-2')
        self.container.__enter__()
        
        ui.label(self.title).classes(styles.Text.HEADING)
        if self.description:
            ui.label(self.description).classes(styles.Text.SUBHEADING)
        
        # Content container within section
        self.content = ui.column().classes('w-full gap-3')
        self.content.__enter__()
        return self.content
    
    def __exit__(self, *args):
        """Exit section context."""
        self.content.__exit__(*args)
        self.container.__exit__(*args)


def show_error_banner(message: str) -> None:
    """Show error message in banner style.
    
    Args:
        message: Error message to display
    """
    with ui.row().classes(styles.Card.ERROR):
        ui.icon('error').classes(styles.Text.ERROR)
        ui.label(message).classes(styles.Text.ERROR + ' flex-grow')
