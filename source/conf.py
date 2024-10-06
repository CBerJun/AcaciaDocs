# Configuration file for the Sphinx documentation builder.

import os
import sys
sys.path.append(os.path.abspath('.'))
sys.path.append(os.path.abspath("_extensions"))

from sphinx.highlighting import lexers
from acacia_lexer import AcaciaLexer

# -- Project information

project = 'AcaciaMC'
copyright = '2023, CBerJun'
author = 'CBerJun'

release = '0.1'
version = '0.1.0'

language = "zh_CN"

# -- General configuration

extensions = ["acacia_ext", "acacia_theme"]
exclude_patterns = ['_extensions/**']

lexers["acacia"] = AcaciaLexer()
highlight_language = "acacia"

primary_domain = 'aca'

# -- Options for HTML output

html_theme = 'acacia_theme'
html_sidebars = {
    # Remove search box because we put it in other places
    "**": ["localtoc.html", "relations.html", "sourcelink.html"],
}

# -- Options for EPUB output

epub_show_urls = 'footnote'
