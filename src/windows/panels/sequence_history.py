import dearpygui.dearpygui as dpg
from datetime import datetime

from core.window_base import WindowBase


class Sequence_history_window(WindowBase):
    def __init__(self, label="Sequence history", pos=None, width=None, height=None,
                 uuid=None, outputs=None, visible=True, state=None, bus=None):
        super().__init__(label=label, uuid=uuid, outputs=outputs, visible=visible)

        self.state = state
        self.bus = bus

        self.pos = pos
        self.width = width
        self.height = height

        # List of recorded entries: {date, time, str_sequence, n_avg}
        self._history = []
        self._last_date = None   # track to suppress repeated date headers

        self._buildui()

        if bus:
            bus.subscribe("final_data", self._on_final)

    # ------------------------------------------------------------------
    # Tag helper
    # ------------------------------------------------------------------
    def _t(self, name): return f"hist_{name}_{self.UUID}"

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _buildui(self):
        with dpg.child_window(label=self.label,
                              width=self.width,
                              height=self.height,
                              pos=self.pos,
                              tag=self.winID,
                              show=self.visible):

            dpg.add_text("Sequence history")
            dpg.add_separator()
            dpg.add_spacer(height=2)

            # Scrollable list container
            dpg.add_group(tag=self._t("list"))

    # ------------------------------------------------------------------
    # Bus handler
    # ------------------------------------------------------------------
    def _on_final(self, str_sequence=None, n_avg=1, series_id=0, **_):
        """Called when a final averaged result is published."""
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")

        seq_str = str_sequence if str_sequence else "—"

        entry = {
            "date":     date_str,
            "time":     time_str,
            "sequence": seq_str,
            "n_avg":    n_avg,
        }
        self._history.append(entry)
        self._append_entry(entry)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _append_entry(self, entry: dict):
        """Add one entry to the visible list."""
        parent = self._t("list")
        if not dpg.does_item_exist(parent):
            return

        date_str = entry["date"]
        time_str = entry["time"]
        seq_str  = entry["sequence"]
        n_avg    = entry["n_avg"]

        # Date header — only if date changed
        if date_str != self._last_date:
            self._last_date = date_str
            dpg.add_spacer(height=4, parent=parent)
            dpg.add_text(date_str, parent=parent, color=(160, 160, 160))
            dpg.add_separator(parent=parent)

        # Entry row: time + avg count
        run_num = len(self._history)
        with dpg.group(horizontal=True, parent=parent):
            dpg.add_text(f"#{run_num:>3}  {time_str}", color=(200, 200, 200))
            if n_avg > 1:
                dpg.add_text(f"  avg×{n_avg}", color=(120, 200, 255))

        dpg.add_text(seq_str, parent=parent, indent=10, color=(220, 220, 180))

        dpg.add_spacer(height=2, parent=parent)

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------
    def load_history(self, entries: list):
        """Clear existing history and re-render from a saved list of entry dicts."""
        self._clear()
        for entry in entries:
            self._history.append(entry)
            self._append_entry(entry)

    # ------------------------------------------------------------------
    # Clear
    # ------------------------------------------------------------------
    def _clear(self):
        self._history.clear()
        self._last_date = None
        if dpg.does_item_exist(self._t("list")):
            dpg.delete_item(self._t("list"), children_only=True)
