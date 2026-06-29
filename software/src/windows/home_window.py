import dearpygui.dearpygui as dpg
from loguru import logger

from core.window_base import WindowBase


class Home_win(WindowBase):
    """
    Home tab content.

    Sections
    --------
    - Device status  : ADC and ESP32 connection badges + retry button
    - Experiment list: one row per experiment, populated from app_state
    """

    def __init__(self, label="Home", uuid=None, visible=True, state=None, bus=None):
        super().__init__(label=label, uuid=uuid, visible=visible)

        self._persistent_fields = ["label"]
        self.accepted_input_types = []
        self.outputs = {}
        self.connections = {}

        self.state = state
        self.bus = bus

        self._t = f"home_{self.UUID}"

        if bus:
            bus.subscribe("experiment_added", self._on_experiment_added)
            bus.subscribe("metadata_updated", self._on_experiment_added)
            bus.subscribe("device_status_changed", self._on_device_status)

    # ------------------------------------------------------------------
    # Called by TabbedWindowManager
    # ------------------------------------------------------------------

    def build_content(self):
        u = self._t

        with dpg.child_window(autosize_x=True, autosize_y=True, border=False):
            # ── Device status ────────────────────────────────────────────
            dpg.add_text("Device connections")
            dpg.add_separator()

            with dpg.table(header_row=False, borders_innerV=False):
                dpg.add_table_column(width_fixed=True, init_width_or_weight=80)
                dpg.add_table_column(width_fixed=True, init_width_or_weight=100)
                dpg.add_table_column(width_stretch=True)

                with dpg.table_row():
                    dpg.add_text("ADC")
                    dpg.add_text("---", tag=f"{u}_adc_status")
                    dpg.add_button(label="Retry", width=70, callback=self._retry_adc)

                with dpg.table_row():
                    dpg.add_text("ESP32")
                    dpg.add_text("---", tag=f"{u}_esp32_status")
                    dpg.add_button(label="Retry", width=70, callback=self._retry_esp32)

            dpg.add_spacer(height=8)
            dpg.add_separator()
            dpg.add_spacer(height=8)

            # ── Experiment list ──────────────────────────────────────────
            dpg.add_text("Experiments")
            dpg.add_separator()

            # Container so we can delete + recreate the table on each refresh
            dpg.add_group(tag=f"{u}_exp_container")

        # Initial refresh
        self.refresh_status()
        self._refresh_experiment_list()

    # ------------------------------------------------------------------
    # Device status
    # ------------------------------------------------------------------

    def refresh_status(self):
        u = self._t
        adc_ok = self._check_device(
            self.state.get_adc_instance() if self.state else None
        )
        esp32_ok = self._check_device(
            self.state.get_esp32_instance() if self.state else None
        )
        self._set_status_badge(f"{u}_adc_status", adc_ok)
        self._set_status_badge(f"{u}_esp32_status", esp32_ok)

    def _retry_adc(self):
        logger.debug("'Retry' (ADC) button clicked")
        self.refresh_status()

    def _retry_esp32(self):
        logger.debug("'Retry' (ESP32) button clicked")
        self.refresh_status()

    def _on_device_status(self, **_):
        self.refresh_status()

    # ------------------------------------------------------------------
    # Experiment list
    # ------------------------------------------------------------------

    def _on_experiment_added(self, **_):
        self._refresh_experiment_list()

    def _refresh_experiment_list(self):
        u = self._t
        container = f"{u}_exp_container"
        table_tag = f"{u}_exp_table"

        if not dpg.does_item_exist(container):
            return

        # Delete and fully recreate the table so columns are never lost
        if dpg.does_item_exist(table_tag):
            dpg.delete_item(table_tag)

        experiments = self.state.get_experiments() if self.state else []

        with dpg.table(
            tag=table_tag,
            parent=container,
            header_row=True,
            borders_outerH=True,
            borders_outerV=True,
            borders_innerH=True,
            borders_innerV=True,
            row_background=True,
        ):
            dpg.add_table_column(
                label="Name", width_fixed=True, init_width_or_weight=130
            )
            dpg.add_table_column(
                label="Fluo/Spec", width_fixed=True, init_width_or_weight=80
            )
            dpg.add_table_column(
                label="Seq/Freq", width_fixed=True, init_width_or_weight=80
            )
            dpg.add_table_column(label="Operator", width_stretch=True)
            dpg.add_table_column(label="Project", width_stretch=True)
            dpg.add_table_column(label="Sample ID", width_stretch=True)
            dpg.add_table_column(label="Date", width_stretch=True)

            for exp in experiments:
                with dpg.table_row():
                    dpg.add_text(exp.get("name", ""))
                    dpg.add_text(exp.get("experiment_type", ""))
                    dpg.add_text(exp.get("acquisition_type", ""))
                    dpg.add_text(exp.get("operator", ""))
                    dpg.add_text(exp.get("project", ""))
                    dpg.add_text(exp.get("sample_id", ""))
                    dpg.add_text(exp.get("date", ""))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_device(device) -> bool:
        if device is None:
            return False
        for attr in ("is_connected", "connected", "online"):
            val = getattr(device, attr, None)
            if val is not None:
                return bool(val() if callable(val) else val)
        return False

    @staticmethod
    def _set_status_badge(tag: str, ok: bool):
        if not dpg.does_item_exist(tag):
            return
        if ok:
            dpg.set_value(tag, "Connected")
            dpg.configure_item(tag, color=(100, 255, 100))
        else:
            dpg.set_value(tag, "Offline")
            dpg.configure_item(tag, color=(255, 80, 80))
