import dearpygui.dearpygui as dpg

from core.window_base import WindowBase


_DEFAULTS = {
    "baseline_points":          0,
    "nbr_of_averages":          1,
    "time_between_averages_ms": 0,
    "nbr_sequences_ignored":    0,
    "time_before_next_seq_ms":  0,
}


class Experiment_settings_window(WindowBase):
    def __init__(self, label="Data Processing", pos=None, width=None, height=None,
                 uuid=None, visible=True, state=None, bus=None):
        super().__init__(label=label, uuid=uuid, visible=visible)

        self.state = state
        self.bus = bus

        self.pos = pos
        self.width = width
        self.height = height

        # n of the sequence whose params are currently shown; None = global
        self._current_n = None

        self._buildui()
        self._on_open_sequence(n=1, label="Sequence 1")  # start by showing params for seq 1

        if bus:
            bus.subscribe("open_sequence_settings", self._on_open_sequence)

    def _t(self, name): return f"settings_{name}_{self.UUID}"

    def _buildui(self):
        with dpg.child_window(label=self.label,
                              width=self.width,
                              height=self.height,
                              pos=self.pos,
                              tag=self.winID,
                              show=self.visible):

            dpg.add_text("Experiment settings", tag=self._t("title"))
            dpg.add_separator()
            dpg.add_spacer(height=6)

            with dpg.table(header_row=False, borders_innerV=False):
                dpg.add_table_column(width_fixed=True, init_width_or_weight=200)
                dpg.add_table_column(width_fixed=True, init_width_or_weight=100)
                dpg.add_table_column(width_stretch=True)

                # ── Baseline ────────────────────────────────────────
                with dpg.table_row():
                    dpg.add_text("Baseline points")
                    dpg.add_input_int(tag=self._t("baseline"),
                                      default_value=4, min_value=0,
                                      min_clamped=True, step=1, width=-1,
                                      callback=self._on_change)
                    dpg.add_text("points")

                # ── Averaging section header ─────────────────────────
                with dpg.table_row():
                    dpg.add_text("Number of averages")
                    dpg.add_input_int(tag=self._t("nbr_averages"),
                                      default_value=1, min_value=1,
                                      min_clamped=True, step=1, width=-1,
                                      callback=self._on_change)
                    dpg.add_text("averages")

                with dpg.table_row():
                    dpg.add_text("Time between averages")
                    dpg.add_input_int(tag=self._t("time_averages"),
                                      default_value=0, min_value=0,
                                      min_clamped=True, step=100, width=-1,
                                      callback=self._on_change)
                    dpg.add_text("ms")

                # ── Sequence control section header ──────────────────

                with dpg.table_row():
                    dpg.add_text("Sequences to ignore")
                    dpg.add_input_int(tag=self._t("seq_ignored"),
                                      default_value=0, min_value=0,
                                      min_clamped=True, step=1, width=-1,
                                      callback=self._on_change)
                    dpg.add_text("sequences")

                with dpg.table_row():
                    dpg.add_text("Time before next sequence")
                    dpg.add_input_int(tag=self._t("time_next_seq"),
                                      default_value=0, min_value=0,
                                      min_clamped=True, step=100, width=-1,
                                      callback=self._on_change)
                    dpg.add_text("ms")

    # ------------------------------------------------------------------

    def _on_change(self):
        settings = {
            "baseline_points":          dpg.get_value(self._t("baseline")),
            "nbr_of_averages":          dpg.get_value(self._t("nbr_averages")),
            "time_between_averages_ms": dpg.get_value(self._t("time_averages")),
            "nbr_sequences_ignored":    dpg.get_value(self._t("seq_ignored")),
            "time_before_next_seq_ms":  dpg.get_value(self._t("time_next_seq")),
        }

        if self.state:
            if self._current_n is not None:
                # Save into per-sequence dict
                if not hasattr(self.state, "sequence_parameters"):
                    self.state.sequence_parameters = {}
                self.state.sequence_parameters[self._current_n] = dict(settings)
            else:
                self.state.parameter_config.update(settings)

        if self.bus:
            self.bus.publish("experiment_settings_changed", **settings)

    def _on_open_sequence(self, n: int = None, label: str = "", **_):
        """Switch the panel to show/edit the parameters for sequence n."""
        self._current_n = n
        if dpg.does_item_exist(self._t("title")):
            title = f"{label} parameters" if label else "Experiment settings"
            dpg.set_value(self._t("title"), title)
        self._load_params()

    def _load_params(self):
        """Populate the input fields from the stored params for the current sequence."""
        if self.state and self._current_n is not None:
            params = getattr(self.state, "sequence_parameters", {}).get(
                self._current_n, _DEFAULTS
            )
        elif self.state:
            params = self.state.parameter_config
        else:
            params = _DEFAULTS

        dpg.set_value(self._t("baseline"),    params.get("baseline_points",          _DEFAULTS["baseline_points"]))
        dpg.set_value(self._t("nbr_averages"), params.get("nbr_of_averages",          _DEFAULTS["nbr_of_averages"]))
        dpg.set_value(self._t("time_averages"), params.get("time_between_averages_ms", _DEFAULTS["time_between_averages_ms"]))
        dpg.set_value(self._t("seq_ignored"),  params.get("nbr_sequences_ignored",    _DEFAULTS["nbr_sequences_ignored"]))
        dpg.set_value(self._t("time_next_seq"), params.get("time_before_next_seq_ms", _DEFAULTS["time_before_next_seq_ms"]))

    def input_cb(self):
        dpg.show_item(self.winID)
