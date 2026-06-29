import json
import math
from pathlib import Path

import dearpygui.dearpygui as dpg

from core.window_base import WindowBase
from windows.panels.saturating_pulse import SaturatingPulseWindow


class Frequency_input_window(WindowBase):
    """
    Multi-slot editor for frequency acquisition parameters.

    Each slot configures one sinusoidal actinic waveform (frequency,
    amplitude, offset, detection window), shown as wave/detection columns
    side by side with the saturating pulse overrides fused in underneath.
    Slots have an ever-increasing counter so deleted DPG tags never
    collide with new ones. Configs are validated and stored in app_state
    when "Load sequences" is pressed.
    """

    def __init__(
        self,
        label="Frequency Settings",
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

        # Ever-increasing counter so deleted slot tags never collide with new ones.
        self._freq_counter = 0
        self._active_ns = []  # ordered list of active slot n-values
        self._sat_windows = {}  # n -> SaturatingPulseWindow

        self._buildui()

        if bus:
            bus.subscribe("add_frequency_from_library", self._on_add_from_library)
            bus.subscribe(
                "add_frequencies_from_library", self._on_add_many_from_library
            )
            bus.subscribe("load_frequency_configs", self._load_all)

    # ------------------------------------------------------------------
    # Tag helpers
    # ------------------------------------------------------------------
    def _t(self, name):
        return f"freq_{name}_{self.UUID}"

    def _st(self, n, name):
        return f"freq_{self.UUID}_{n}_{name}"

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _buildui(self):
        with dpg.child_window(
            label=self.label,
            width=self.width,
            height=self.height,
            pos=self.pos,
            tag=self.winID,
            show=self.visible,
        ):
            dpg.add_text("Frequency acquisition")
            dpg.add_separator()

            dpg.add_text("", tag=self._t("status"), color=(255, 100, 100))

            # Scrollable slot area
            self._slot_container = self._t("slots")
            with dpg.child_window(
                tag=self._slot_container, autosize_x=True, height=-1, border=False
            ):
                self.add_slot()

    # ------------------------------------------------------------------
    # Slot management
    # ------------------------------------------------------------------
    def add_slot(self):
        self._freq_counter += 1
        n = self._freq_counter
        self._active_ns.append(n)
        parent = self._slot_container

        dpg.add_text(
            f"Config {len(self._active_ns)}", tag=self._st(n, "label"), parent=parent
        )

        # Wave shape and detection window side by side
        with dpg.group(horizontal=True, tag=self._st(n, "row"), parent=parent):
            with dpg.group():
                dpg.add_text("Wave", color=(150, 200, 255))
                with dpg.table(
                    header_row=False,
                    borders_innerV=False,
                    tag=self._st(n, "wave_table"),
                    width=250,
                ):
                    dpg.add_table_column(width_fixed=True, init_width_or_weight=95)
                    dpg.add_table_column(width_fixed=True, init_width_or_weight=70)
                    dpg.add_table_column(width_fixed=True, init_width_or_weight=30)
                    self._param_row(n, "Frequency", "freq", "float", 60.0, "Hz")
                    self._param_row(n, "Amplitude", "amp", "float", 50.0, "%")
                    self._param_row(n, "Offset", "offset", "float", 50.0, "%")

            with dpg.group():
                dpg.add_text("Detection", color=(150, 200, 255))
                with dpg.table(
                    header_row=False,
                    borders_innerV=False,
                    tag=self._st(n, "det_table"),
                ):
                    dpg.add_table_column(width_fixed=True, init_width_or_weight=95)
                    dpg.add_table_column(width_fixed=True, init_width_or_weight=70)
                    dpg.add_table_column(width_fixed=True, init_width_or_weight=30)
                    self._param_row(n, "Periods", "periods", "int", 10, "")
                    self._param_row(n, "Pre", "pre", "int", 0, "periods")
                    self._param_row(n, "Post", "post", "int", 0, "periods")

        # Saturating pulse overrides, fused directly underneath
        dpg.add_spacer(height=4, tag=self._st(n, "sat_spacer"), parent=parent)
        dpg.add_text(
            "Saturating pulse",
            tag=self._st(n, "sat_label"),
            color=(150, 200, 255),
            parent=parent,
        )
        sat = SaturatingPulseWindow(
            label=f"Saturating pulse — Config {len(self._active_ns)}",
            embedded=True,
            parent=parent,
            visible=True,
        )
        sat.add_row()
        sat.add_row()
        self._sat_windows[n] = sat

        dpg.add_spacer(height=8, tag=self._st(n, "sat_btn_spacer"), parent=parent)
        dpg.add_separator(tag=self._st(n, "sat_btn_sep"), parent=parent)
        dpg.add_spacer(height=4, tag=self._st(n, "sat_btn_spacer2"), parent=parent)

        with dpg.group(horizontal=True, tag=self._st(n, "btn_group"), parent=parent):
            dpg.add_button(label="+ Add", callback=self.add_slot)
            dpg.add_button(label="Delete", callback=self._delete_cb, user_data=n)
            dpg.add_button(label="Visualize", callback=self._visualize_cb, user_data=n)

        dpg.add_separator(tag=self._st(n, "sep"), parent=parent)
        dpg.add_separator(tag=self._st(n, "sep"), parent=parent)


        self._relabel_all()

    def _param_row(self, n, label, field, kind, default, unit):
        tag = self._st(n, field)
        with dpg.table_row():
            dpg.add_text(label)
            if kind == "float":
                dpg.add_input_float(
                    tag=tag,
                    default_value=default,
                    min_value=0.0,
                    min_clamped=True,
                    step=0.0,
                    width=-1,
                    format="%.7f",
                )
            else:
                dpg.add_input_int(
                    tag=tag,
                    default_value=default,
                    min_value=0,
                    min_clamped=True,
                    step=1,
                    width=-1,
                )
            dpg.add_text(unit)

    def _delete_cb(self, _, __, user_data):
        self.delete_slot(user_data)

    def _visualize_cb(self, _, __, user_data):
        self._visualize(user_data)

    def delete_slot(self, n):
        if len(self._active_ns) <= 1 or n not in self._active_ns:
            return
        self._active_ns.remove(n)
        for tag in [
            self._st(n, "label"),
            self._st(n, "row"),
            self._st(n, "sat_spacer"),
            self._st(n, "sat_label"),
            self._st(n, "sat_btn_spacer"),
            self._st(n, "sat_btn_sep"),
            self._st(n, "sat_btn_spacer2"),
            self._st(n, "btn_group"),
            self._st(n, "sep"),
        ]:
            if dpg.does_item_exist(tag):
                dpg.delete_item(tag)
        sat = self._sat_windows.pop(n, None)
        if sat and dpg.does_item_exist(sat.winID):
            dpg.delete_item(sat.winID)
        self._relabel_all()

    def _relabel_all(self):
        for idx, n in enumerate(self._active_ns, start=1):
            tag = self._st(n, "label")
            if dpg.does_item_exist(tag):
                dpg.set_value(tag, f"Config {idx}")

    def _on_add_from_library(self, frequency_config: dict = None, **_):
        """Add a new slot pre-filled with the library frequency config."""
        if not frequency_config:
            return
        self._append_slot(frequency_config)

    def _on_add_many_from_library(self, frequency_configs=None, **_):
        """Add one new slot per config in a saved protocol, in order."""
        for cfg in frequency_configs or []:
            self._append_slot(cfg)

    def _append_slot(self, cfg: dict):
        self.add_slot()
        n = self._active_ns[-1]
        if "frequency" in cfg:
            dpg.set_value(self._st(n, "freq"), cfg["frequency"])
        if "amplitude" in cfg:
            dpg.set_value(self._st(n, "amp"), cfg["amplitude"])
        if "offset" in cfg:
            dpg.set_value(self._st(n, "offset"), cfg["offset"])
        if "nbr_of_periods" in cfg:
            dpg.set_value(self._st(n, "periods"), cfg["nbr_of_periods"])
        if "pre_detection" in cfg:
            dpg.set_value(self._st(n, "pre"), cfg["pre_detection"])
        if "post_detection" in cfg:
            dpg.set_value(self._st(n, "post"), cfg["post_detection"])

    # ------------------------------------------------------------------
    # Read config for one slot
    # ------------------------------------------------------------------
    def _read_config(self, n) -> dict:
        sat = self._sat_windows.get(n)
        return {
            "frequency": dpg.get_value(self._st(n, "freq")),
            "amplitude": dpg.get_value(self._st(n, "amp")),
            "offset": dpg.get_value(self._st(n, "offset")),
            "nbr_of_periods": dpg.get_value(self._st(n, "periods")),
            "pre_detection": dpg.get_value(self._st(n, "pre")),
            "post_detection": dpg.get_value(self._st(n, "post")),
            "saturating_pulse_data": sat.saturating_pulse_data if sat else {},
        }

    # ------------------------------------------------------------------
    # Visualize — pure-math waveform, no hardware
    # ------------------------------------------------------------------
    def _visualize(self, n):
        cfg = self._read_config(n)
        if cfg["frequency"] <= 0:
            self._set_status("Frequency must be > 0 Hz")
            return
        preview = self._build_preview(cfg)
        if self.bus:
            self.bus.publish("visualize_sequence", preview=preview)
        self._set_status("")

    def _build_preview(self, cfg) -> dict:
        freq = cfg["frequency"]  # Hz
        amp = cfg["amplitude"]  # %
        offset = cfg["offset"]  # %
        n_det = cfg["nbr_of_periods"]
        pre = cfg["pre_detection"]
        post = cfg["post_detection"]

        total_periods = pre + n_det + post
        if freq <= 0 or total_periods <= 0:
            return {"time_ms": [], "actinic": [], "pulses": []}

        period_ms = 1000.0 / freq
        total_ms = total_periods * period_ms
        n_pts = max(int(total_periods * 80), 3)
        det_start_ms = pre * period_ms
        det_end_ms = (pre + n_det) * period_ms

        time_ms = []
        actinic = []
        pulses = []
        for i in range(n_pts):
            t = i * total_ms / (n_pts - 1)
            sine_val = offset + (amp / 2.0) * math.sin(2 * math.pi * freq * t / 1000.0)
            time_ms.append(t)
            actinic.append(max(0.0, min(100.0, sine_val)))
            pulses.append(100.0 if det_start_ms <= t <= det_end_ms else 0.0)

        return {"time_ms": time_ms, "actinic": actinic, "pulses": pulses}

    # ------------------------------------------------------------------
    # Load all slots into state + notify acquisition
    # ------------------------------------------------------------------
    def _load_all(self):
        errors = []
        if self.state:
            self.state.decoded_sequence_list = {}

        for idx, n in enumerate(self._active_ns):
            cfg = self._read_config(n)
            if cfg["frequency"] <= 0:
                errors.append(f"Config {idx + 1}: frequency must be > 0")
                continue
            if cfg["nbr_of_periods"] <= 0:
                errors.append(f"Config {idx + 1}: periods must be > 0")
                continue

            sequence = [
                "F",
                "T",
                str(cfg["frequency"]),
                "^",
                "N",
                str(cfg["nbr_of_periods"]),
                "^ ",
                "A",
                str(cfg["amplitude"]),
                "^",
                "O",
                str(cfg["offset"]),
                "^",
                "P",
                str(cfg["pre_detection"]),
                "^",
                "D",
                str(cfg["post_detection"]),
                "^",
            ]
            # Store as 4-tuple: (token_list, nbr_of_points, slot_index, freq_cfg)
            # acquisition._run_current_sequence reads seq[3] as the per-slot config
            if self.state:
                self.state.set_decoded_sequence_list((sequence, 0, idx, cfg), idx)

        if errors:
            self._set_status(" | ".join(errors))
            return

        if self.bus:
            # Publish the first config so Acquisition_win has a fallback
            first_cfg = self._read_config(self._active_ns[0])
            self.bus.publish("frequency_config_changed", frequency_config=first_cfg)
            self.bus.publish("sequence_list_ready")

        self._set_status(
            f"{len(self._active_ns)} config(s) ready.", color=(100, 220, 100)
        )

    # ------------------------------------------------------------------
    # Status helper
    # ------------------------------------------------------------------
    def _set_status(self, msg, color=(255, 100, 100)):
        tag = self._t("status")
        if dpg.does_item_exist(tag):
            dpg.set_value(tag, msg)
            dpg.configure_item(tag, color=color)

    # ------------------------------------------------------------------
    # Workspace save / restore
    # ------------------------------------------------------------------
    def get_frequency_configs(self) -> list:
        """Return all slot configs as a list (for workspace serialisation)."""
        return [self._read_config(n) for n in self._active_ns]

    def load_frequency_configs(self, configs: list):
        """Restore slots from a saved config list (called on workspace load)."""
        if not configs:
            return

        while len(self._active_ns) > 1:
            self.delete_slot(self._active_ns[-1])

        for i, cfg in enumerate(configs):
            if i > 0:
                self.add_slot()
            n = self._active_ns[i]
            if "frequency" in cfg:
                dpg.set_value(self._st(n, "freq"), cfg["frequency"])
            if "amplitude" in cfg:
                dpg.set_value(self._st(n, "amp"), cfg["amplitude"])
            if "offset" in cfg:
                dpg.set_value(self._st(n, "offset"), cfg["offset"])
            if "nbr_of_periods" in cfg:
                dpg.set_value(self._st(n, "periods"), cfg["nbr_of_periods"])
            if "pre_detection" in cfg:
                dpg.set_value(self._st(n, "pre"), cfg["pre_detection"])
            if "post_detection" in cfg:
                dpg.set_value(self._st(n, "post"), cfg["post_detection"])
            sat = self._sat_windows.get(n)
            if sat and "saturating_pulse_data" in cfg:
                sat.saturating_pulse_data = cfg["saturating_pulse_data"]

    # ------------------------------------------------------------------
    # File I/O — all slots as a JSON list
    # ------------------------------------------------------------------
    def _save_to_file(self):
        dpg.add_file_dialog(
            label="Save frequency config",
            modal=True,
            width=700,
            height=450,
            callback=self._on_save_path,
        )

    def _on_save_path(self, sender, app_data, user_data):
        path = (
            app_data.get("file_path_name", "") or app_data.get("current_path", "")
        ).strip()
        if not path:
            return
        p = Path(path)
        if p.is_dir():
            p = p / "frequency_config.json"
        try:
            data = [self._read_config(n) for n in self._active_ns]
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self._set_status(f"Saved to {p.name}", color=(100, 220, 100))
        except Exception as e:
            self._set_status(f"Save error: {e}")

    def _load_from_file(self):
        tag = dpg.add_file_dialog(
            label="Load frequency config",
            modal=True,
            width=700,
            height=450,
            callback=self._on_load_file,
        )
        dpg.add_file_extension(".json", parent=tag, color=(100, 220, 100, 255))

    def _on_load_file(self, sender, app_data, user_data):
        selections = app_data.get("selections", {})
        path = (
            next(iter(selections.values()), "") or app_data.get("file_path_name", "")
        ).strip()
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                data = [data]  # backward-compat: old single-slot format

            # Remove all but the first slot
            while len(self._active_ns) > 1:
                self.delete_slot(self._active_ns[-1])

            for i, cfg in enumerate(data):
                if i > 0:
                    self.add_slot()
                n = self._active_ns[i]
                if "frequency" in cfg:
                    dpg.set_value(self._st(n, "freq"), cfg["frequency"])
                if "amplitude" in cfg:
                    dpg.set_value(self._st(n, "amp"), cfg["amplitude"])
                if "offset" in cfg:
                    dpg.set_value(self._st(n, "offset"), cfg["offset"])
                if "nbr_of_periods" in cfg:
                    dpg.set_value(self._st(n, "periods"), cfg["nbr_of_periods"])
                if "pre_detection" in cfg:
                    dpg.set_value(self._st(n, "pre"), cfg["pre_detection"])
                if "post_detection" in cfg:
                    dpg.set_value(self._st(n, "post"), cfg["post_detection"])

            self._set_status("Loaded", color=(100, 220, 100))
        except Exception as e:
            self._set_status(f"Load error: {e}")
