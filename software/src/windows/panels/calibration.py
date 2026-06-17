import dearpygui.dearpygui as dpg
import time

from core.window_base import WindowBase
from config import fonts
from workers.calibration_worker import CalibrationAcquisitionWorker


class calibration_win(WindowBase):
    """
    Detection LED calibration panel.

    Flashes the detection LED at 1 Hz via a CalibrationAcquisitionWorker
    thread and displays live measurement and reference channel readings.
    The polling loop uses DPG frame callbacks (one per rendered frame) to
    drain the worker's result queue on the main thread. Intensity changes
    are forwarded to the running worker in real time.
    """

    def __init__(self, label="Detection LED", pos=None, width=None, height=None,
                 uuid=None, visible=True, state=None, bus=None):
        super().__init__(label=label, uuid=uuid, visible=visible)

        self.state = state
        self.bus = bus

        self.pos = pos
        self.width = width
        self.height = height

        self._flashing = False
        self.polling_enabled = False
        self.polling_scheduled = False
        self.worker_thread = None

        self._build_ui()
        self._refresh_adc_status()

    # ------------------------------------------------------------------
    # Tag helper
    # ------------------------------------------------------------------
    def _t(self, name): return f"cal_{name}_{self.UUID}"

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        with dpg.child_window(tag=self.winID,
                              width=self.width,
                              height=self.height,
                              pos=self.pos):

            dpg.add_text("Detection LED")
            dpg.add_separator()
            dpg.add_spacer(height=6)

            # ── Intensity controls ────────────────────────────────────
            with dpg.table(header_row=False, borders_innerV=False):
                dpg.add_table_column(width_fixed=True, init_width_or_weight=110)
                dpg.add_table_column(width_stretch=True)
                dpg.add_table_column(width_fixed=True, init_width_or_weight=50)

                with dpg.table_row():
                    dpg.add_text("Intensity")
                    dpg.add_slider_int(
                        tag=self._t("slider"),
                        default_value=100, min_value=0, max_value=100,
                        width=-1, callback=self._on_slider,
                        format="%d",
                    )
                    dpg.add_text("%")

                with dpg.table_row():
                    dpg.add_text("Fine adjust")
                    dpg.add_input_float(
                        tag=self._t("input"),
                        default_value=100.0, min_value=0.0, max_value=100.0,
                        min_clamped=True, max_clamped=True,
                        step=0.1, width=-1, format="%.1f",
                        callback=self._on_input,
                    )
                    dpg.add_text("%")

            dpg.add_spacer(height=8)

            # ── Flash toggle ─────────────────────────────────────────
            dpg.add_button(
                tag=self._t("toggle"),
                label="Start flash  (1 Hz)",
                width=-1,
                height=40,
                callback=self._toggle_flash,
                enabled=False,
            )
            dpg.add_text("ADC not connected", tag=self._t("status"), color=(255, 80, 80))

            # ── Live readout ─────────────────────────────────────────

            with dpg.table(header_row=True,
                           borders_outerH=True, borders_outerV=True,
                           borders_innerH=True, borders_innerV=True,
                           row_background=True):
                dpg.add_table_column(label="Channel",   width_fixed=True, init_width_or_weight=110)
                dpg.add_table_column(label="Value",     width_stretch=True)

                with dpg.table_row():
                    dpg.add_text("Measurement")
                    dpg.add_text("—", tag=self._t("di"), color=(100, 220, 255))

                with dpg.table_row():
                    dpg.add_text("Reference")
                    dpg.add_text("—", tag=self._t("ref"), color=(180, 255, 140))

        if fonts.large():
            dpg.bind_item_font(self.winID, fonts.large())

    # ------------------------------------------------------------------
    # Intensity callbacks
    # ------------------------------------------------------------------
    def _on_slider(self, sender=None, app_data=None, user_data=None):
        val = float(dpg.get_value(self._t("slider")))
        dpg.set_value(self._t("input"), val)
        self._send_intensity(val)

    def _on_input(self, sender=None, app_data=None, user_data=None):
        val = dpg.get_value(self._t("input"))
        dpg.set_value(self._t("slider"), int(val))
        self._send_intensity(val)

    def _send_intensity(self, val: float):
        if self._flashing and self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.send_command({
                "action": "set_detection_intensity",
                "intensity": val,
            })

        if self.bus:
            self.bus.publish("detection_led_changed", intensity=val)

    # ------------------------------------------------------------------
    # ADC status
    # ------------------------------------------------------------------
    def _refresh_adc_status(self):
        adc = self.state.get_adc_instance() if self.state else None
        connected = adc is not None and (adc.is_connected() if hasattr(adc, "is_connected") else True)
        dpg.configure_item(self._t("toggle"), enabled=connected)
        if not self._flashing:
            if connected:
                dpg.set_value(self._t("status"), "Ready")
                dpg.configure_item(self._t("status"), color=(180, 180, 180))
            else:
                dpg.set_value(self._t("status"), "ADC not connected")
                dpg.configure_item(self._t("status"), color=(255, 80, 80))

    # ------------------------------------------------------------------
    # Flash toggle
    # ------------------------------------------------------------------
    def _toggle_flash(self, sender=None, app_data=None, user_data=None):
        if self._flashing:
            self._stop_flash()
        else:
            self._start_flash()

    def _start_flash(self):
        adc = self.state.get_adc_instance() if self.state else None
        if adc is None or (hasattr(adc, "is_connected") and not adc.is_connected()):
            dpg.set_value(self._t("status"), "ADC not connected")
            dpg.configure_item(self._t("status"), color=(255, 80, 80))
            dpg.configure_item(self._t("toggle"), enabled=False)
            return

        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.send_command({"action": "shutdown"})
            self.worker_thread.join(timeout=1.0)

        adc   = self.state.get_adc_instance()  if self.state else None
        esp32 = self.state.get_esp32_instance() if self.state else None
        self.worker_thread = CalibrationAcquisitionWorker(adc, esp32)
        self.worker_thread.start()
        time.sleep(0.2)

        self.worker_thread.send_command({
            "action": "configure_calibration",
            "sequence": ['#'],
            "intensity": dpg.get_value(self._t("input")),
        })
        self.worker_thread.send_command({"action": "start_calibration"})
        time.sleep(0.1)

        self._flashing = True
        dpg.set_item_label(self._t("toggle"), "Stop flash  (1 Hz)")
        dpg.set_value(self._t("status"), "Flashing")
        dpg.configure_item(self._t("status"), color=(255, 200, 60))

        self.polling_enabled = True
        if not self.polling_scheduled:
            self.polling_scheduled = True
            dpg.set_frame_callback(dpg.get_frame_count() + 1, self._poll)

    def _stop_flash(self):
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.send_command({
                "action": "configure_calibration",
                "sequence": ['@'],
            })
            self.worker_thread.send_command({"action": "stop_calibration"})
            time.sleep(0.2)
            self.worker_thread.send_command({"action": "shutdown"})
            self.worker_thread.join(timeout=2.0)
        self.worker_thread = None

        self._flashing = False
        self.polling_enabled = False
        self.polling_scheduled = False

        dpg.set_item_label(self._t("toggle"), "Start flash  (1 Hz)")
        dpg.set_value(self._t("status"), "Ready")
        dpg.configure_item(self._t("status"), color=(180, 180, 180))
        dpg.set_value(self._t("di"),  "—")
        dpg.set_value(self._t("ref"), "—")

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------
    def _poll(self):
        if not self.polling_enabled:
            self.polling_scheduled = False
            return

        if not self.worker_thread or not self.worker_thread.is_alive():
            self.polling_enabled = False
            self.polling_scheduled = False
            return

        try:
            while True:
                msg = self.worker_thread.result_queue.get_nowait()
                if msg["type"] == "live":
                    di  = msg.get("di",  0)
                    ref = msg.get("ref", 0)
                    dpg.set_value(self._t("di"),  f"{di:.4f}")
                    dpg.set_value(self._t("ref"), f"{ref:.4f}")
        except Exception:
            pass

        dpg.set_frame_callback(dpg.get_frame_count() + 1, self._poll)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def _on_window_close(self):
        self.shutdown()

    def shutdown(self):
        self.polling_enabled = False
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.send_command({"action": "shutdown"})
            self.worker_thread.join(timeout=2.0)

    def __del__(self):
        self.shutdown()


EXPORTED_CLASS = calibration_win
EXPORTED_NAME = "Calibration"
