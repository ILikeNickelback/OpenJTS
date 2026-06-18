import dearpygui.dearpygui as dpg

from core.window_base import WindowBase
from config import fonts


class Frequency_handler_window(WindowBase):
    """
    Status panel for loaded frequency configs.

    Displays the number of loaded configs and estimated total acquisition
    time (accounting for averaging and ignore runs). Updates when
    ``sequence_list_ready`` is published on the bus.
    """

    def __init__(
        self,
        label="Frequency Handler",
        pos=None,
        width=None,
        height=None,
        uuid=None,
        visible=True,
        state=None,
        bus=None,
    ):
        super().__init__(label=label, uuid=uuid, visible=visible)
        self.state = state
        self.bus = bus

        self.pos = pos
        self.width = width
        self.height = height

        self._buildui()

        if bus:
            bus.subscribe("sequence_list_ready", self._on_loaded)

    def _t(self, name):
        return f"freqh_{name}_{self.UUID}"

    def _buildui(self):
        with dpg.child_window(
            label=self.label,
            width=self.width,
            height=self.height,
            pos=self.pos,
            tag=self.winID,
            show=self.visible,
        ):
            dpg.add_text("Frequency handler")
            dpg.add_separator()
            dpg.add_spacer(height=6)

            with dpg.table(header_row=False, borders_innerV=False):
                dpg.add_table_column(width_fixed=True, init_width_or_weight=110)
                dpg.add_table_column(width_stretch=True)

                with dpg.table_row():
                    dpg.add_text("Configs")
                    dpg.add_text("—", tag=self._t("configs"))

                with dpg.table_row():
                    dpg.add_text("Total time")
                    dpg.add_text("—", tag=self._t("time"))

            dpg.add_spacer(height=8)
            dpg.add_text("Not loaded", tag=self._t("status"), color=(255, 80, 80))
            dpg.add_spacer(height=8)
            dpg.add_button(
                label="Load sequences", width=-1, height=40, callback=self._load
            )

        if fonts.large():
            dpg.bind_item_font(self.winID, fonts.large())

    def _load(self):
        if self.bus:
            self.bus.publish("load_frequency_configs")

    def _on_loaded(self, **_):
        """Update stats after frequency_input has processed and stored all configs."""
        seq_list = self.state.get_decoded_sequence_list() if self.state else {}
        if not seq_list:
            return

        total_configs = len(seq_list)
        total_ms = 0.0

        for entry in seq_list.values():
            # entry is a 4-tuple: (tokens, nbr_of_points, slot_idx, freq_cfg)
            if not (isinstance(entry, (tuple, list)) and len(entry) >= 4):
                continue
            cfg = entry[3]
            if not cfg:
                continue

            freq = cfg.get("frequency", 0)
            pre = cfg.get("pre_detection", 0)
            n_det = cfg.get("nbr_of_periods", 0)
            post = cfg.get("post_detection", 0)

            if freq <= 0:
                continue

            period_ms = 1000.0 / freq
            slot_ms = (pre + n_det + post) * period_ms

            # Scale by averaging/ignore params if available
            slot_idx = entry[2]
            params = (
                self.state.get_parameter_list(slot_idx) if self.state else None
            ) or {}
            n_avg = params.get("nbr_of_averages", 1)
            n_ignore = params.get("nbr_sequences_ignored", 0)
            t_between = params.get("time_between_averages_ms", 0)
            runs = n_ignore + n_avg

            total_ms += runs * slot_ms + max(0, runs - 1) * t_between

        dpg.set_value(self._t("configs"), str(total_configs))
        dpg.set_value(self._t("time"), _fmt_time(total_ms))
        dpg.set_value(self._t("status"), "Ready")
        dpg.configure_item(self._t("status"), color=(100, 220, 100))


def _fmt_time(ms: float) -> str:
    total_s = int(ms / 1000)
    h = total_s // 3600
    m = (total_s % 3600) // 60
    s = total_s % 60
    remainder_ms = int(ms % 1000)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s {remainder_ms:03d}ms"
    return f"{s}s {remainder_ms:03d}ms"
