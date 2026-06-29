import dearpygui.dearpygui as dpg
from loguru import logger

from core.window_base import WindowBase


class SaturatingPulseWindow(WindowBase):
    """
    Editor for per-period saturating pulse overrides.

    Each row defines a pulse inserted at a specific period of the actinic
    waveform: period number, phase (°), duration (ms), and amplitude
    (0–100). saturating_pulse_data is computed live from the current rows
    whenever it is read. One instance is created per frequency slot in
    Frequency_input_window, embedded directly under that slot's
    wave/detection settings.
    """

    def __init__(
        self,
        label="Saturating Pulse",
        win_width=1,
        win_height=1,
        pos=(0, 0),
        uuid=None,
        visible=False,
        embedded=False,
        parent=None,
    ):
        super().__init__(
            label=label,
            pos=pos,
            win_width=win_width,
            win_height=win_height,
            uuid=uuid,
            visible=visible,
        )

        self.embedded = embedded
        self.parent = parent
        self.row_counter = 0
        self.rows = []

        self._buildui()

    def input_cb(self):
        dpg.show_item(self.winID)

    def _buildui(self):
        if self.embedded:
            with dpg.group(tag=self.winID, parent=self.parent):
                self._build_contents()
        else:
            with dpg.window(
                label=self.label,
                pos=self.pos,
                width=self.win_width,
                height=self.win_height,
                tag=self.winID,
                show=self.visible,
            ):
                self._build_contents()

    def _build_contents(self):
        with dpg.group(horizontal=True):
            dpg.add_button(label="Add row", callback=self._add_row_cb)
            if not self.embedded:
                dpg.add_button(
                    label="Close", callback=self._close_cb
                )

        with dpg.table(header_row=True, tag=f"saturating_pulse_table_{self.UUID}"):
            dpg.add_table_column(label="Period number")
            dpg.add_table_column(label="Degre (°)")
            dpg.add_table_column(label="Duration (ms)")
            dpg.add_table_column(label="Amplitude (0 - 100)")
            dpg.add_table_column(label="Remove")

    def _close_cb(self):
        logger.debug("'Close' button clicked")
        dpg.hide_item(self.winID)

    def _add_row_cb(self, *_):
        logger.debug("'Add row' button clicked")
        self.add_row()

    def add_row(self):
        self.row_counter += 1
        self.rows.append(self.row_counter)

        row_tag = f"saturating_pulse_row_{self.UUID}_{self.row_counter}"

        dpg.add_table_row(parent=f"saturating_pulse_table_{self.UUID}", tag=row_tag)
        dpg.add_input_float(
            tag=f"period_number_{self.UUID}_{self.row_counter}",
            default_value=0,
            min_value=0,
            min_clamped=True,
            width=150,
            parent=row_tag,
        )
        dpg.add_input_float(
            tag=f"degree_{self.UUID}_{self.row_counter}",
            default_value=0,
            min_value=0,
            max_value=360,
            min_clamped=True,
            max_clamped=True,
            width=150,
            parent=row_tag,
        )
        dpg.add_input_float(
            tag=f"duration_{self.UUID}_{self.row_counter}",
            default_value=0,
            min_value=0,
            min_clamped=True,
            width=150,
            parent=row_tag,
        )
        dpg.add_input_float(
            tag=f"amplitude_{self.UUID}_{self.row_counter}",
            default_value=0,
            min_value=0,
            max_value=100,
            min_clamped=True,
            max_clamped=True,
            width=150,
            parent=row_tag,
        )
        dpg.add_button(
            tag=f"remove_button_{self.UUID}_{self.row_counter}",
            label="Remove",
            callback=self.remove_row,
            user_data=(row_tag, self.row_counter),
            parent=row_tag,
        )

    def remove_row(self, sender, app_data, user_data):
        logger.debug("'Remove' button clicked")
        row_tag, row_index = user_data
        dpg.delete_item(row_tag)
        if row_index in self.rows:
            self.rows.remove(row_index)

    @property
    def saturating_pulse_data(self):
        return {
            row_id: {
                "period_number": dpg.get_value(f"period_number_{self.UUID}_{row_id}"),
                "degree": dpg.get_value(f"degree_{self.UUID}_{row_id}"),
                "duration_ms": dpg.get_value(f"duration_{self.UUID}_{row_id}"),
                "amplitude": dpg.get_value(f"amplitude_{self.UUID}_{row_id}"),
            }
            for row_id in self.rows
        }

    @saturating_pulse_data.setter
    def saturating_pulse_data(self, data):
        for row_id in list(self.rows):
            row_tag = f"saturating_pulse_row_{self.UUID}_{row_id}"
            if dpg.does_item_exist(row_tag):
                dpg.delete_item(row_tag)
        self.rows = []

        for values in (data or {}).values():
            self.add_row()
            row_id = self.rows[-1]
            dpg.set_value(
                f"period_number_{self.UUID}_{row_id}", values.get("period_number", 0)
            )
            dpg.set_value(f"degree_{self.UUID}_{row_id}", values.get("degree", 0))
            dpg.set_value(
                f"duration_{self.UUID}_{row_id}", values.get("duration_ms", 0)
            )
            dpg.set_value(
                f"amplitude_{self.UUID}_{row_id}", values.get("amplitude", 0)
            )


EXPORTED_CLASS = SaturatingPulseWindow
EXPORTED_NAME = "Saturating Pulse Settings"
