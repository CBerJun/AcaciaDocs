"""
Acacia Doc's theme
"""

from typing import TYPE_CHECKING
from os import path

if TYPE_CHECKING:
    from sphinx.application import Sphinx

def setup(app: "Sphinx"):
    app.add_html_theme('acacia_theme', path.abspath(path.dirname(__file__)))
    app.add_js_file('acacia_menu.js')
    app.add_js_file('acacia_colorscheme.js')
    app.add_css_file('acacia_dark_theme.css', id='acacia_dark_theme_css')
    return {
        'version': '0.1',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
