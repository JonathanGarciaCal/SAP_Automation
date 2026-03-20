"""Navigation sidebar component for all pages.

Displays feature-aware navigation menu with links to all available pages.
Highlights the current page. Shows/hides pages based on feature flags.

Example:
    ```python
    from ui.components import sidebar
    from config import RuntimeConfig
    
    sidebar.render(current_route='home', config=my_config)
    ```
"""

import logging
from typing import Optional

from nicegui import ui

from config import RuntimeConfig
from ui.design import styles

logger = logging.getLogger(__name__)


def render(
    current_route: str = 'home',
    config: Optional[RuntimeConfig] = None
) -> None:
    """Render navigation sidebar with feature-aware menu items.
    
    Displays navigation links for all available pages:
    - Home (always shown)
    - Inspector (/inspector) — shown if config.features.enable_screen_inspector
    - Script Runner (/script-runner) — shown if config.features.enable_script_runner
    - Reports (/reports) — shown if config.features.enable_report_engine
    
    Highlights the current page with bold text.
    
    Args:
        current_route: Current page name for highlighting (e.g., 'home', 'inspector')
        config: Application configuration with feature flags
        
    Example:
        >>> render(current_route='inspector', config=config)
        # Shows sidebar with Inspector link highlighted if feature enabled
    """
    
    logger.debug("Rendering sidebar: current_route=%s", current_route)
    
    # Normalize route for comparison
    current_route_lower = current_route.lower() if current_route else 'home'
    
    with ui.column().classes(styles.Sidebar.CONTAINER):

        ui.label('Navigation').classes(styles.Sidebar.TITLE)

        # Home link (always shown)
        home_link = ui.link('Home', '/').classes(styles.Sidebar.LINK)

        if current_route_lower == 'home':
            home_link.classes(styles.Sidebar.LINK_ACTIVE)

        # Inspector link (feature-flagged)
        if config and config.features.enable_screen_inspector:
            inspector_link = ui.link('Screen Inspector', '/inspector').classes(styles.Sidebar.LINK)

            if current_route_lower == 'inspector':
                inspector_link.classes(styles.Sidebar.LINK_ACTIVE)

        # Script Runner link (feature-flagged)
        if config and config.features.enable_script_runner:
            script_runner_link = ui.link('Script Runner', '/script-runner').classes(styles.Sidebar.LINK)

            if current_route_lower == 'script runner' or current_route_lower == 'script-runner':
                script_runner_link.classes(styles.Sidebar.LINK_ACTIVE)

        # Reports link (feature-flagged)
        if config and config.features.enable_report_engine:
            reports_link = ui.link('Reports', '/reports').classes(styles.Sidebar.LINK)

            if current_route_lower == 'reports':
                reports_link.classes(styles.Sidebar.LINK_ACTIVE)
