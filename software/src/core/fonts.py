"""
Centralised font registry.

Call setup_fonts() once, right after dpg.create_context().
Then call large() anywhere to get the large-font handle (or None if unavailable).
Call monospace_large() to get a larger monospace font for sequence inputs.
"""
from pathlib import Path
import dearpygui.dearpygui as dpg

_large = None
_monospace_large = None

_CANDIDATES = [
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/calibri.ttf",
    "C:/Windows/Fonts/arial.ttf",
]

_CONSOLAS = Path(__file__).parent.parent / "ressources" / "consola.ttf"


def setup_fonts(large_size: int = 19, monospace_large_size: int = 40):
    global _large, _monospace_large
    font_path = next((p for p in _CANDIDATES if Path(p).exists()), None)
    with dpg.font_registry():
        if font_path is not None:
            _large = dpg.add_font(font_path, large_size)
        if _CONSOLAS.exists():
            _monospace_large = dpg.add_font(
                str(_CONSOLAS), monospace_large_size)


def large():
    """Return the large-font handle, or None if fonts were not loaded."""
    return _large


def monospace_large():
    """Return the larger monospace (Consolas) font handle for sequence inputs."""
    return _monospace_large
