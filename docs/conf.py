import os
import sys

# software/src is added directly (not "software") because the application's
# own modules import each other as top-level packages, e.g. "from core.event_bus
# import EventBus" — autodoc needs that same layout on sys.path to resolve them.
sys.path.insert(0, os.path.abspath("../software/src"))

project = "OpenJTS"
copyright = "2026, Christopher LARRAN"
author = "Christopher LARRAN"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
]

autosummary_generate = True

# Without this, automodule only lists each function/class as a one-line
# summary; this makes every module page render the full docstring body.
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}

# Without this, Napoleon renders Google-style "Attributes:" sections as
# .. attribute:: directives, which duplicate the same name already picked
# up by autodoc's introspection of the real class attribute.
napoleon_use_ivar = True

# Hardware/GUI dependencies that can't (or shouldn't) be installed on the doc
# build server: mcculw needs the native MCC driver, dearpygui needs a display/GL,
# tkinter needs a system Tk build. Sphinx mocks them so autodoc can still import
# and document everything else that depends on them.
autodoc_mock_imports = ["mcculw", "dearpygui", "tkinter"]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

html_theme = "sphinx_rtd_theme"
