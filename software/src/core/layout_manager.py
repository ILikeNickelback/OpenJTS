# core/layout_manager.py
"""Viewport-relative panel layout definitions and pixel-position resolver."""
import dearpygui.dearpygui as dpg

# Pixel heights/widths of fixed UI chrome subtracted from the viewport
_MENU_BAR_H = 45
_TAB_BAR_H = 40
_SCROLLBAR_W = 20

# Panel geometry as relative fractions (0.0–1.0) of the usable viewport area.
# Format: {tab_name: {panel_name: (x, y, width, height)}}
LAYOUTS = {
    "overview": {
        "experiment metadata": (0.00, 0.00, 0.20, 1.00),
        "sequence history":    (0.20, 0.00, 0.80, 1.00),
    },
    "processing": {
        "plot":        (0.20, 0.00, 0.80, 1.00),
        "samples":     (0.00, 0.00, 0.20, 0.80),
        "acquisition": (0.00, 0.80, 0.20, 0.20),
    },
    # ── Setup tab ──────────────────────────────────────────────────────
    # Left  (0–30 %):  sequence writer — full height
    # Middle(30–70 %): sequence plot (top 40 %) + settings (mid 30 %) + library (bot 30 %)
    # Right (70–100%): background (top 22 %) + calibration (mid 40 %) + handler (bot 38 %)
    "setup": {
        "sequence_writer":  (0.00, 0.00, 0.30, 1.00),
        "sequence_plot":    (0.30, 0.00, 0.40, 0.40),
        "settings":         (0.30, 0.40, 0.40, 0.30),
        "Load_experiment":  (0.30, 0.70, 0.40, 0.30),
        "background":       (0.70, 0.00, 0.30, 0.22),
        "calibration":      (0.70, 0.22, 0.30, 0.40),
        "sequence_handler": (0.70, 0.62, 0.30, 0.38),
        "Timer":            (0.00, 0.00, 0.00, 0.00),
    },
    # ── Frequency setup tab ────────────────────────────────────────────
    # Left  (0–30 %):  frequency input — full height
    # Middle(30–70 %): sequence plot (top 40 %) + settings (mid 30 %) + library (bot 30 %)
    # Right (70–100%): background (top 22 %) + calibration (mid 40 %) + handler (bot 38 %)
    "frequency_setup": {
        "frequency_input":   (0.00, 0.00, 0.30, 1.00),
        "sequence_plot":     (0.30, 0.00, 0.40, 0.40),
        "settings":          (0.30, 0.40, 0.40, 0.25),
        "Load_experiment":   (0.30, 0.65, 0.40, 0.35),
        "background":        (0.70, 0.00, 0.30, 0.30),
        "calibration":       (0.70, 0.30, 0.30, 0.32),
        "frequency_handler": (0.70, 0.62, 0.30, 0.38),
    },
}


def get(tab: str, panel: str) -> dict:
    """Return absolute pixel geometry for a named panel within a tab.

    Queries the live viewport size on every call so positions remain
    correct after a window resize.

    Args:
        tab: Layout key (e.g. ``"setup"``, ``"processing"``).
        panel: Panel name within that layout (e.g. ``"sequence_writer"``).

    Returns:
        Dict with keys ``"pos"`` (x, y tuple), ``"width"``, and ``"height"``
        in pixels, ready to unpack as DearPyGui widget keyword arguments.

    Raises:
        KeyError: If ``tab`` or ``panel`` is not defined in ``LAYOUTS``.
    """
    usable_w = dpg.get_viewport_client_width() - _SCROLLBAR_W
    usable_h = dpg.get_viewport_client_height() - _MENU_BAR_H - _TAB_BAR_H
    x, y, w, h = LAYOUTS[tab][panel]
    return {
        "pos":    (int(x * usable_w), int(y * usable_h)),
        "width":  int(w * usable_w),
        "height": int(h * usable_h),
    }
