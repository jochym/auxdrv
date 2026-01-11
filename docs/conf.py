import os
import sys
from datetime import datetime

# Add src to path so sphinx can find the modules
sys.path.insert(0, os.path.abspath("../src"))

# -- Project information -----------------------------------------------------
project = "indi-celestron-aux"
copyright = f"{datetime.now().year}, Paweł T. Jochym"
author = "Paweł T. Jochym"
release = "1.6.5"

# -- General configuration ---------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "myst_parser",
    "sphinx_copybutton",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "venv"]

# -- Options for HTML output -------------------------------------------------
html_theme = "furo"
html_static_path = ["_static"]
html_title = "INDI Celestron AUX Driver"

# -- Intersphinx mapping -----------------------------------------------------
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "scipy": ("https://docs.scipy.org/doc/scipy/", None),
}

# -- MyST Parser configuration -----------------------------------------------
myst_enable_extensions = [
    "colon_fence",
    "deflist",
]
