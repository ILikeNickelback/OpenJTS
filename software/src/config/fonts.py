"""
Centralised font registry.

Call setup_fonts() once, right after dpg.create_context().
Then call large() anywhere to get the large-font handle (or None if unavailable).
Call monospace_large() to get a larger monospace font for sequence inputs.
"""

from pathlib import Path
import dearpygui.dearpygui as dpg

_LARGE = None
_MONOSPACE_LARGE = None

_CANDIDATES = [
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/calibri.ttf",
    "C:/Windows/Fonts/arial.ttf",
]

_CONSOLAS = Path(__file__).parent.parent / "ressources" / "consola.ttf"


def setup_fonts(large_size: int = 19, monospace_large_size: int = 40) -> None:
    """Load and register application fonts into the DearPyGui font registry.

    Must be called once after ``dpg.create_context()`` and before the first
    render frame. Tries each candidate system font in order and uses the first
    one found for the large UI font. Loads Consolas from the bundled resources
    for the monospace sequence-input font.

    Args:
        large_size: Point size for the main UI font.
        monospace_large_size: Point size for the monospace sequence-input font.
    """
    global _LARGE, _MONOSPACE_LARGE
    font_path = next((p for p in _CANDIDATES if Path(p).exists()), None)
    with dpg.font_registry():
        if font_path is not None:
            _LARGE = dpg.add_font(font_path, large_size)
        if _CONSOLAS.exists():
            _MONOSPACE_LARGE = dpg.add_font(str(_CONSOLAS), monospace_large_size)


def large():
    """Return the large-font handle, or None if fonts were not loaded."""
    return _LARGE


def monospace_large():
    """Return the larger monospace (Consolas) font handle for sequence inputs."""
    return _MONOSPACE_LARGE
