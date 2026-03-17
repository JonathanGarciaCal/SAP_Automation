from nicegui import ui

# Material‑UI colour palette (blue primary, pink secondary, etc.)
# These values come from the default MUI theme (v5).
PALETTE = {
    'primary': "#19d232",
    'primary_dark': "#369311",
    'primary_light': '#63a4ff',
    'secondary': '#dc004e',
    'secondary_dark': '#9a0036',
    'secondary_light': '#ff5c8d',
    'error': '#d32f2f',
    'warning': '#ed6c02',
    'info': '#0288d1',
    'success': '#2e7d32',
    'background': '#fafafa',
    'surface': '#ffffff',
    'on_primary': '#ffffff',
    'on_secondary': '#ffffff',
}


def apply():
    """Configure the NiceGUI theme to look like Material‑UI.

    Call this once at the start of your app (before creating most components).
    It sets colours, injects fonts/icons, and adds the CSS overrides.
    """
    # set colours
    ui.colors(
        primary=PALETTE['primary'],
        accent=PALETTE['secondary'],
        dark=PALETTE['background'],
    )

    # load Roboto font and Material Icons
    ui.add_head_html('''
<link href="https://fonts.googleapis.com/css?family=Roboto:300,400,500,700&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
<style>body{font-family:Roboto,sans-serif;}</style>
''')

    # inject the contents of material.css so we don't need a separate static route
    try:
        with open('material.css', 'r', encoding='utf-8') as f:
            ui.add_css(f.read())
    except FileNotFoundError:
        # if the CSS file is missing just skip it
        pass


# helper wrappers -----------------------------------------------------------

def button(*args, **kwargs):
    """Material-style button."""
    # `unelevated` is a raised button, `ripple` gives the ripple effect.
    b = ui.button(*args, **kwargs)
    b.props('unelevated ripple')
    b.classes('mui-button')
    return b


def outlined_button(*args, **kwargs):
    # outlined variant of the button
    b = ui.button(*args, **kwargs)
    b.props('outlined ripple')
    b.classes('mui-outlined-button')
    return b


def card(*args, **kwargs):
    """Card container matching MUI card spacing/radius."""
    c = ui.card(*args, **kwargs)
    c.props('outlined')
    c.classes('mui-card')
    return c


def text_input(*args, **kwargs):
    """Text input with Material look."""
    inp = ui.input(*args, **kwargs)
    inp.props('outlined')
    inp.classes('mui-input')
    return inp


def select(*args, **kwargs):
    """Select control with MUI spacing."""
    sel = ui.select(*args, **kwargs)
    sel.props('outlined')
    sel.classes('mui-select')
    return sel

# expose convenience namespace on ui (optional)

ui.material = type('m', (), {})()
ui.material.apply = apply
ui.material.button = button
ui.material.outlined_button = outlined_button
ui.material.card = card
ui.material.text_input = text_input
ui.material.select = select
