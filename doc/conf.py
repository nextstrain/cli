# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

from pathlib import Path

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))


# -- Project information -----------------------------------------------------

from datetime import date
from nextstrain.cli import __version__ as cli_version

project = 'Nextstrain CLI'
version = cli_version
release = version
copyright = '2018–%d, Trevor Bedford and Richard Neher' % (date.today().year)
author = 'Thomas Sibley and the rest of the Nextstrain team'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'recommonmark',
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx_markdown_tables',
    'nextstrain.sphinx.theme',
    'sphinxcontrib.mermaid',
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store',
    'development.md'
]


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'nextstrain-sphinx-theme'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']


# -- Cross-project references ------------------------------------------------

intersphinx_mapping = {
    'augur': ('https://docs.nextstrain.org/projects/augur/en/stable', None),
    'auspice': ('https://docs.nextstrain.org/projects/auspice/en/stable', None),
    'docs': ('https://docs.nextstrain.org/en/latest/', None),
}

# -- Mermaid -----------------------------------------------------------------

# Render Mermaid.js diagrams to SVG at Sphinx build time (like Graphviz
# diagrams are) so that they don't have to render via JS at page load time.
# Various upsides to this, but one is that you can pass around the SVGs as
# images.
mermaid_output_format = 'svg'

# Use a command wrapper which automatically provisions the Mermaid CLI (mmdc)
# via npx so it doesn't need to be installed on Read the Docs or by developers.
mermaid_cmd = str(Path(__file__).resolve().parent.parent / "devel/mmdc")

# Disable loading the JS library in doc pages.
#
# XXX TODO: Remove this once/if my patch to make it unnecessary¹ is accepted
# and released.
#   -trs, 9 Nov 2023
#
# ¹ <https://github.com/mgaitan/sphinxcontrib-mermaid/pull/132>
mermaid_version = ""
mermaid_init_js = ""
