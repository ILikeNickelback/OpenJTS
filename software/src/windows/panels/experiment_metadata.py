import dearpygui.dearpygui as dpg
from datetime import date

from core.window_base import WindowBase


class Experiment_metadata_window(WindowBase):
    """
    Editable metadata form for an experiment.

    Fields: operator, project, sample ID, date (defaults to today), and
    free-text comments. All changes are written to app_state and broadcast
    as ``metadata_updated`` on the bus so the home tab can refresh its
    experiment list.
    """

    def __init__(
        self,
        label="Overview window",
        pos=None,
        width=None,
        height=None,
        uuid=None,
        visible=True,
        state=None,
        bus=None,
        experiment_name=None,
    ):
        super().__init__(label=label, uuid=uuid, visible=visible)

        self.pos = pos
        self.width = width
        self.height = height
        self._u = f"meta_{self.UUID}"

        self.state = state
        self.bus = bus
        self.experiment_name = experiment_name

        self._buildui()
        # Push the default date to state (default_value never fires the callback)
        self._on_field_change("date", date.today().isoformat())

    def _t(self, name):
        return f"{self._u}_{name}"

    def _buildui(self):
        with dpg.child_window(
            label=self.label,
            width=self.width,
            height=self.height,
            pos=self.pos,
            tag=self.winID,
            show=self.visible,
        ):
            dpg.add_text("Experiment metadata")
            dpg.add_separator()
            dpg.add_spacer(height=6)

            with dpg.table(header_row=False, borders_innerV=False):
                dpg.add_table_column(width_fixed=True, init_width_or_weight=110)
                dpg.add_table_column(width_stretch=True)

                # Read-only: type fields set at creation
                with dpg.table_row():
                    dpg.add_text("Type")
                    exp = next(
                        (
                            e
                            for e in (
                                self.state.get_experiments() if self.state else []
                            )
                            if e["name"] == self.experiment_name
                        ),
                        {},
                    )
                    type_str = f"{exp.get('experiment_type', '')}  ·  {exp.get('acquisition_type', '')}"
                    dpg.add_text(type_str, tag=self._t("type_label"))

                dpg.add_table_row()  # spacer

                for label_text, key in [
                    ("Operator", "operator"),
                    ("Project", "project"),
                    ("Sample ID", "sample_id"),
                    ("Date", "date"),
                ]:
                    with dpg.table_row():
                        dpg.add_text(label_text)
                        dpg.add_input_text(
                            tag=self._t(key),
                            hint=label_text,
                            default_value=date.today().isoformat()
                            if key == "date"
                            else "",
                            width=-1,
                            user_data=key,
                            callback=self._field_cb,
                        )

            dpg.add_spacer(height=6)
            dpg.add_separator()
            dpg.add_spacer(height=4)
            dpg.add_text("Comments")
            dpg.add_input_text(
                tag=self._t("comments"),
                hint="General comments about the experiment...",
                width=-1,
                height=-1,
                multiline=True,
                user_data="comments",
                callback=self._field_cb,
            )

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------
    def _field_cb(self, sender, app_data, user_data):
        """Single callback for all fields — user_data carries the state key."""
        self._on_field_change(user_data, app_data)

    def _on_field_change(self, key: str, value: str):
        if self.state and self.experiment_name:
            self.state.update_experiment_metadata(self.experiment_name, key, value)
        if self.bus:
            self.bus.publish("metadata_updated", experiment_name=self.experiment_name)

    def input_cb(self):
        dpg.show_item(self.winID)
