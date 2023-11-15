# Configuration file for the Sphinx documentation builder.

import os
import sys
sys.path.append(os.path.abspath('.'))

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

extensions = []
source_suffix = '.rst'

lexers["acacia"] = AcaciaLexer()
highlight_language = "acacia"
pygments_style = "default"

# -- Options for HTML output

html_theme = 'sphinx_rtd_theme'

# -- Options for EPUB output

epub_show_urls = 'footnote'
