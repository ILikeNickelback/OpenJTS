import dearpygui.dearpygui as dpg

from core.window_base import WindowBase


class Sequence_plot_window(WindowBase):
    """
    Read-only waveform preview panel.

    Renders actinic light intensity as a shaded line series and detection
    pulses as stems (one stem centred per contiguous detection window).
    Updates whenever ``visualize_sequence`` is published on the bus, which
    carries a preview dict with time_ms, actinic, and pulses arrays.
    """

    def __init__(self, label="Sequence Plot", pos=None, width=None, height=None,
                 uuid=None, visible=True, state=None, bus=None):
        super().__init__(label=label, uuid=uuid, visible=visible)

        self.state = state
        self.bus = bus

        self.pos = pos
        self.width = width
        self.height = height

        self._buildui()

        if bus:
            bus.subscribe("visualize_sequence", self._on_visualize)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _buildui(self):
        u = self.UUID
        with dpg.child_window(label=self.label,
                              width=self.width,
                              height=self.height,
                              pos=self.pos,
                              tag=self.winID,
                              show=self.visible):

            dpg.add_text("Sequence preview")
            dpg.add_separator()

            self._plot_tag    = f"seq_plot_{u}"
            self._xaxis_tag   = f"seq_xaxis_{u}"
            self._yaxis_tag   = f"seq_yaxis_{u}"
            self._actinic_tag = f"seq_actinic_{u}"
            self._pulses_tag  = f"seq_pulses_{u}"

            with dpg.plot(tag=self._plot_tag,
                          height=-1, width=-1,
                          anti_aliased=True,
                          no_title=True,
                          no_menus=True,
                          no_box_select=True,):
                dpg.add_plot_axis(dpg.mvXAxis, tag=self._xaxis_tag, no_gridlines=True)
                with dpg.plot_axis(dpg.mvYAxis, label="Intensity (%)", tag=self._yaxis_tag, no_gridlines=True):
                    dpg.add_line_series([], [], label="Actinic light",    tag=self._actinic_tag, shaded=True )
                    dpg.add_stem_series([], [], label="Detection pulses", tag=self._pulses_tag)

    # ------------------------------------------------------------------
    # Bus handler
    # ------------------------------------------------------------------

    def _on_visualize(self, preview: dict, **_):
        time_ms = preview.get('time_ms', [])
        actinic = preview.get('actinic', [])
        pulses  = preview.get('pulses',  [])

        if not dpg.does_item_exist(self._plot_tag):
            return

        stem_x, stem_y = _pulse_centers(time_ms, pulses)

        dpg.configure_item(self._actinic_tag, x=time_ms, y=actinic)
        dpg.configure_item(self._pulses_tag,  x=stem_x,  y=stem_y)

        dpg.fit_axis_data(self._xaxis_tag)
        dpg.fit_axis_data(self._yaxis_tag)


# ------------------------------------------------------------------
# Helper
# ------------------------------------------------------------------

def _pulse_centers(time_ms: list, pulses: list):
    """Return (x, y) for one stem per detection pulse window.

    Scans the binary pulse array for contiguous runs of non-zero values
    and places a single stem at the centre of each run.
    """
    stem_x, stem_y = [], []
    in_pulse = False
    start = 0

    for i, p in enumerate(pulses):
        if p > 0 and not in_pulse:
            in_pulse = True
            start = i
        elif p == 0 and in_pulse:
            in_pulse = False
            center = (start + i - 1) // 2
            stem_x.append(time_ms[center])
            stem_y.append(100.0)

    if in_pulse:                          # pulse that runs to the end
        center = (start + len(pulses) - 1) // 2
        stem_x.append(time_ms[center])
        stem_y.append(100.0)

    return stem_x, stem_y
