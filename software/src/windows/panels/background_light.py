import dearpygui.dearpygui as dpg

from core.window_base import WindowBase
from config import fonts


class Background_light_window(WindowBase):
    """
    Actinic (background) light intensity control panel.

    Provides a slider and a fine-adjust float input that stay in sync.
    The light must be toggled ON before intensity changes are sent to the
    ADC. Each change is also published on the bus as
    ``background_light_changed`` so the acquisition worker can pick it up.
    """

    def __init__(self, label="Actinic Light", pos=None, width=None, height=None,
                 uuid=None, visible=True, state=None, bus=None):
        super().__init__(label=label, uuid=uuid, visible=visible)

        self.state = state
        self.bus = bus

        self.pos = pos
        self.width = width
        self.height = height

        self._light_on = False

        self._buildui()

    # ------------------------------------------------------------------
    # Tag helper
    # ------------------------------------------------------------------
    def _t(self, name): return f"bl_{name}_{self.UUID}"

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _buildui(self):
        with dpg.child_window(label=self.label,
                              width=self.width,
                              height=self.height,
                              pos=self.pos,
                              tag=self.winID,
                              show=self.visible,
                              border=True):

            dpg.add_text("Background light")
            dpg.add_separator()
            dpg.add_spacer(height=6)

            # ── Intensity slider ─────────────────────────────────────
            with dpg.table(header_row=False, borders_innerV=False):
                dpg.add_table_column(width_fixed=True, init_width_or_weight=120)
                dpg.add_table_column(width_stretch=True)
                dpg.add_table_column(width_fixed=True, init_width_or_weight=40)

                with dpg.table_row():
                    dpg.add_text("Intensity")
                    dpg.add_slider_float(
                        tag=self._t("slider"),
                        default_value=100.0,
                        min_value=0.0, max_value=100.0,
                        width=-1,
                        callback=self._on_slider,
                        format="%.1f",
                    )
                    dpg.add_text("%")

                with dpg.table_row():
                    dpg.add_text("Fine adjust")
                    dpg.add_input_float(
                        tag=self._t("input"),
                        default_value=100.0,
                        min_value=0.0, max_value=100.0,
                        min_clamped=True, max_clamped=True,
                        step=0.1, width=-1,
                        callback=self._on_input,
                        format="%.1f",
                    )
                    dpg.add_text("%")

            dpg.add_spacer(height=8)

            # ── Toggle button ────────────────────────────────────────
            dpg.add_button(
                tag=self._t("toggle"),
                label="Turn ON",
                width=-1,
                height=40,
                callback=self._toggle,
            )

            dpg.add_spacer(height=4)
            dpg.add_text("OFF", tag=self._t("status"), color=(180, 180, 180))

        if fonts.large():
            dpg.bind_item_font(self.winID, fonts.large())

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------
    def _on_slider(self, sender=None, app_data=None, user_data=None):
        val = dpg.get_value(self._t("slider"))
        dpg.set_value(self._t("input"), val)
        if self._light_on:
            self._send(val)

    def _on_input(self, sender=None, app_data=None, user_data=None):
        val = dpg.get_value(self._t("input"))
        dpg.set_value(self._t("slider"), val)
        if self._light_on:
            self._send(val)

    def _toggle(self, sender=None, app_data=None, user_data=None):
        if not self.state.get_adc_instance() or not self.state.get_adc_instance().is_connected():
            return  # ignore toggle if ADC not connected
        
        self._light_on = not self._light_on

        if self._light_on:
            dpg.set_item_label(self._t("toggle"), "Turn OFF")
            dpg.configure_item(self._t("status"), default_value="ON", color=(0, 220, 80))
            self._send(dpg.get_value(self._t("slider")))
        else:
            dpg.set_item_label(self._t("toggle"), "Turn ON")
            dpg.configure_item(self._t("status"), default_value="OFF", color=(180, 180, 180))
            self._send(0.0)

    # ------------------------------------------------------------------
    # Hardware
    # ------------------------------------------------------------------
    def _send(self, amplitude: float):
        adc = self.state.get_adc_instance() if self.state else None
        if adc is not None and adc.is_connected() and hasattr(adc, "set_background_light"):
            adc.set_background_light(amplitude)
        if self.bus:
            self.bus.publish("background_light_changed", amplitude=amplitude)

    def input_cb(self):
        dpg.show_item(self.winID)
