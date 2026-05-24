# Sphinx configuration for Thaum Cloud documentation.
# Build from repo root:
#   sphinx-build -c doc/sphinx_config doc doc/_build/html
# Or use the Makefile in this directory: make -C doc/sphinx_config html

from __future__ import annotations

import os
import sys
from datetime import datetime

_conf_dir = os.path.dirname(os.path.abspath(__file__))
_doc_root = os.path.abspath(os.path.join(_conf_dir, ".."))
_repo_root = os.path.abspath(os.path.join(_doc_root, ".."))

sys.path.insert(0, _conf_dir)

# -- Project metadata ---------------------------------------------------------

project = "Thaum Cloud"
author = "Gemstone Software"
copyright = f"{datetime.now().year}, {author}"
release = "0.1.0"
version = release

# -- General ------------------------------------------------------------------

extensions = [
    "sphinx_design",
    "sphinx_copybutton",
]

root_doc = "index"
source_suffix = {".rst": "restructuredtext"}
language = "en"

# Paths are relative to the sourcedir (doc/), not confdir.
templates_path = []
exclude_patterns = [
    "_build",
    "sphinx_config/_build",
    "Thumbs.db",
    ".DS_Store",
]

pygments_style = "sphinx"
highlight_language = "bash"

# sphinx-design: tab-set / tab-item (see quickstart_aca.rst)
sphinx_design_tabs_dynamic = False

# -- HTML (Furo) --------------------------------------------------------------

html_theme = "furo"
html_title = project
html_short_title = "Thaum Cloud"
# Relative to confdir (doc/sphinx_config/) when using sphinx-build -c doc/sphinx_config
html_static_path = ["_static"]

html_theme_options = {
    "light_logo": "Thaum_wizard_cgi.jpg",
    "dark_logo": "Thaum_wizard_cgi.jpg",
    "light_css_variables": {
        "font-stack": '"Open Sans", ui-sans-serif, system-ui, sans-serif',
        "font-stack--monospace": '"Source Code Pro", ui-monospace, monospace',
        "color-thaum-heading-border": "#2e7d4a",
        "color-sidebar-background": "#eaf5ef",
        "color-table-header-background": "var(--color-sidebar-background)",
        "color-code-background": "#eef0f3",
        "color-thaum-target-accent": "#6D28D9",
    },
    "dark_css_variables": {
        "font-stack": '"Open Sans", ui-sans-serif, system-ui, sans-serif',
        "font-stack--monospace": '"Source Code Pro", ui-monospace, monospace',
        "color-thaum-heading-border": "#5cb87a",
        "color-sidebar-background": "#0d1a12",
        "color-table-header-background": "#15241b",
        "color-thaum-target-accent": "#C4B5FD",
    },
}

# -- Plain text ---------------------------------------------------------------

text_newlines = "unix"


# -- Extension setup ----------------------------------------------------------

_LOGO_SIZE = 128
_LOGO_NAME = "Thaum_wizard_cgi.jpg"
_LOGO_SRC = os.path.join(_repo_root, "static", _LOGO_NAME)
_LOGO_DST = os.path.join(_conf_dir, "_static", _LOGO_NAME)


def _resize_logo(src: str, dst: str, size: int) -> None:
    """Write a square logo JPEG; use Pillow when available."""
    try:
        from PIL import Image
    except ImportError:
        import shutil

        shutil.copy2(src, dst)
        return

    with Image.open(src) as img:
        img.convert("RGB").resize((size, size), Image.Resampling.LANCZOS).save(
            dst, format="JPEG", quality=90
        )


def _ensure_logo_asset() -> None:
    if not os.path.isfile(_LOGO_SRC):
        return
    os.makedirs(os.path.dirname(_LOGO_DST), exist_ok=True)
    _resize_logo(_LOGO_SRC, _LOGO_DST, _LOGO_SIZE)


def _on_builder_inited(app) -> None:
    if app.builder.format != "html":
        return
    _ensure_logo_asset()
    # Ensure custom.css is linked for html and singlehtml (same Furo layout).
    app.add_css_file("custom.css")


def setup(app):
    _ensure_logo_asset()
    app.connect("builder-inited", _on_builder_inited)
    return {
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
