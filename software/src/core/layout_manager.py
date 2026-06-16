# core/layout_manager.py
import dearpygui.dearpygui as dpg


class LayoutManager:
    # Define the layout here
    # Format: {tab_name: {panel_name: (x, y, width, height)}}
    # Values are relative (0 to 1) to the viewport size.

    # Size of menu bar, tab bar, and scrollbar to subtract from the viewport dimensions
    _MENU_BAR_H = 45
    _TAB_BAR_H = 40
    _SCROLLBAR_W = 20

    LAYOUTS = {
        "overview": {
            "experiment metadata": (0.00, 0.00, 0.20, 1.00),
            "sequence history": (0.20, 0.00, 0.80, 1.00),
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

    def __init__(self):
        vp_w = dpg.get_viewport_client_width()
        vp_h = dpg.get_viewport_client_height()

        # Usable area after subtracting container overhead
        self._w = vp_w - self._SCROLLBAR_W
        self._h = vp_h - self._MENU_BAR_H - self._TAB_BAR_H

    def get(self, tab: str, panel: str) -> dict:
        x, y, w, h = self.LAYOUTS[tab][panel]
        return {
            "pos":    (int(x * self._w), int(y * self._h)),
            "width":  int(w * self._w),
            "height": int(h * self._h),
        }
