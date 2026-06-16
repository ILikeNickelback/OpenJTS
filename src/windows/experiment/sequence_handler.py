import dearpygui.dearpygui as dpg

from core.window_base import WindowBase
from core import fonts
from sequence_builders.control import sequence_control
from sequence_builders.sequence_waveform_builder import SequencePreviewBuilder


class Sequence_handler_window(WindowBase):
    def __init__(self, label="Sequence Handler",
                 pos=None, width=None, height=None,
                 uuid=None, outputs=None, visible=True,
                 state=None, bus=None):

        super().__init__(label=label, uuid=uuid, outputs=outputs, visible=visible)
        self.state = state
        self.bus = bus
        self.sequence_control = sequence_control()
        self._preview_builder = SequencePreviewBuilder()

        self.pos = pos
        self.width = width
        self.height = height

        self._buildui()

    def _t(self, name):
        return f"seqh_{name}_{self.UUID}"

    def _buildui(self):
        with dpg.child_window(label=self.label,
                              width=self.width,
                              height=self.height,
                              pos=self.pos,
                              tag=self.winID,
                              show=self.visible):

            dpg.add_text("Sequence handler")
            dpg.add_separator()
            dpg.add_spacer(height=6)

            with dpg.table(header_row=False, borders_innerV=False):
                dpg.add_table_column(width_fixed=True, init_width_or_weight=110)
                dpg.add_table_column(width_stretch=True)

                with dpg.table_row():
                    dpg.add_text("Runs")
                    dpg.add_text("—", tag=self._t("runs"))

                with dpg.table_row():
                    dpg.add_text("Total time")
                    dpg.add_text("—", tag=self._t("time"))

            dpg.add_spacer(height=8)
            dpg.add_text("Not loaded", tag=self._t("status"), color=(255, 80, 80))
            dpg.add_spacer(height=8)
            dpg.add_button(label="Load sequence",
                           width=-1,
                           height=40,
                           callback=self._load_sequence_protocol)

        if fonts.large():
            dpg.bind_item_font(self.winID, fonts.large())

    def _load_sequence_protocol(self):
        if not self.state.get_adc_instance() or not self.state.get_adc_instance().is_connected():
            dpg.set_value(self._t("status"), "● ADC not connected")
            dpg.configure_item(self._t("status"), color=(255, 80, 80))
            return

        UUID_sequence_input_list = self.state.get_UUID_sequence_input()
        total_runs = 0
        total_time_ms = 0.0

        self.state.decoded_sequence_list.clear()

        for i in range(len(UUID_sequence_input_list)):
            seq_uuid = UUID_sequence_input_list[i + 1]
            try:
                n = int(str(seq_uuid).split("_")[-1])
            except (ValueError, IndexError):
                n = i + 1

            raw_str = dpg.get_value(f"seq_input_{seq_uuid}")
            decoded_sequence, nbr_of_points = self.sequence_control.decode_sequence(raw_str)
            self.state.set_decoded_sequence_list((decoded_sequence, nbr_of_points, n, raw_str), i)

            params    = self.state.get_parameter_list(n) or self.state.parameter_config
            n_avg     = params.get("nbr_of_averages",          1)
            n_ignore  = params.get("nbr_sequences_ignored",    0)
            t_between = params.get("time_between_averages_ms", 0)
            t_before  = params.get("time_before_next_seq_ms",  0)

            runs_this = n_ignore + n_avg
            total_runs += runs_this

            parsed    = self._preview_builder._parse_sequence(decoded_sequence)
            seq_ms    = self._preview_builder._calculate_total_time(parsed)
            total_time_ms += (runs_this * seq_ms
                              + max(0, runs_this - 1) * t_between
                              + t_before)

        dpg.set_value(self._t("runs"), str(total_runs))
        dpg.set_value(self._t("time"), _fmt_time(total_time_ms))
        dpg.set_value(self._t("status"), "Ready")
        dpg.configure_item(self._t("status"), color=(100, 220, 100))

        self.state.set_total_time(total_time_ms)
        self.bus.publish("sequence_list_ready")


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
