import json
import math
from pathlib import Path

import dearpygui.dearpygui as dpg

from config.config import config
from core.window_base import WindowBase
from sequence_builders.control import sequence_control
from sequence_builders.sequence_waveform_builder import SequencePreviewBuilder

_SEQUENCES_FILE = Path(__file__).parent.parent.parent / "config" / "sequences.json"

_ALL_SECTIONS = ["Sequence_Fluo", "Sequence_Spectro", "Frequency_Fluo", "Frequency_Spectro"]


def _load_file() -> dict:
    try:
        with open(_SEQUENCES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key in _ALL_SECTIONS:
            data.setdefault(key, [])
        return data
    except Exception:
        return {k: [] for k in _ALL_SECTIONS}


def _save_file(data: dict) -> None:
    with open(_SEQUENCES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


class SequenceLibraryWindow(WindowBase):
    def __init__(self, label="Load Experiment", pos=None, width=None, height=None,
                 uuid=None, outputs=None, visible=True, state=None, bus=None):
        super().__init__(label=label, uuid=uuid, outputs=outputs, visible=visible)

        self.state = state
        self.bus = bus
        self.pos = pos
        self.width = width
        self.height = height

        self._file_data = _load_file()
        self._seq_control = sequence_control()

        self._buildui()

        if bus:
            bus.subscribe("experiment_added", self._on_mode_changed)

    # ------------------------------------------------------------------
    # Mode helpers
    # ------------------------------------------------------------------
    def _section_key(self) -> str:
        acq = (self.state.get_acquisition_type() if self.state else None) or "Sequence"
        exp = config["General"].get("experiment_type", "Fluo")
        return f"{acq}_{exp}"

    def _is_frequency(self) -> bool:
        return self._section_key().startswith("Frequency")

    def _entries(self) -> list:
        return self._file_data.get(self._section_key(), [])

    # ------------------------------------------------------------------
    # Tag helper
    # ------------------------------------------------------------------
    def _t(self, name): return f"le_{name}_{self.UUID}"

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _buildui(self):
        with dpg.child_window(label=self.label,
                              width=self.width,
                              height=self.height,
                              pos=self.pos,
                              tag=self.winID,
                              show=self.visible):

            dpg.add_text("Sequence library")
            dpg.add_text("", tag=self._t("section_label"), color=(180, 180, 100))
            dpg.add_separator()
            dpg.add_spacer(height=4)

            with dpg.table(tag=self._t("table"),
                           header_row=True,
                           borders_outerH=True, borders_outerV=True,
                           borders_innerH=True, borders_innerV=True,
                           row_background=True,
                           scrollY=True,
                           freeze_rows=1,
                           height=-40):
                dpg.add_table_column(label="Name",     width_fixed=True,  init_width_or_weight=120)
                dpg.add_table_column(label="Sequence", width_stretch=True)
                dpg.add_table_column(label="",         width_fixed=True,  init_width_or_weight=60)
                dpg.add_table_column(label="",         width_fixed=True,  init_width_or_weight=55)

            self._populate_table()

            dpg.add_spacer(height=4)
            with dpg.group(horizontal=True):
                dpg.add_button(label="+ New",        tag=self._t("btn_new"),
                               width=90,  callback=self._new_entry_modal)
                dpg.add_button(label="Save current", tag=self._t("btn_save"),
                               width=110, callback=self._save_current)
                dpg.add_button(label="Reload",       tag=self._t("btn_reload"),
                               width=80,  callback=self._reload)

        self._build_modal()

    def _populate_table(self):
        table = self._t("table")
        if not dpg.does_item_exist(table):
            return

        key = self._section_key()
        dpg.set_value(self._t("section_label"), f"[ {key.replace('_', '  ')} ]")

        freq_mode = self._is_frequency()

        dpg.delete_item(table, children_only=True, slot=1)

        for idx, entry in enumerate(self._entries()):
            name    = entry.get("name", "")
            preview = self._entry_preview(entry)

            with dpg.table_row(parent=table):
                dpg.add_text(name)

                seq_item = dpg.add_text(preview[:60] + "…" if len(preview) > 60 else preview)
                with dpg.tooltip(seq_item):
                    dpg.add_text(preview, wrap=400)

                dpg.add_button(label="View", width=-1,
                               callback=self._visualize_cb, user_data=idx)
                dpg.add_button(label="+ Add", width=-1,
                               callback=self._add_cb, user_data=idx)

    def _entry_preview(self, entry: dict) -> str:
        """One-line summary shown in the table."""
        if "str_sequence" in entry:
            return entry["str_sequence"]
        cfg = entry.get("frequency_config", {})
        return (f"{cfg.get('frequency', '?')} Hz  "
                f"amp={cfg.get('amplitude', '?')}%  "
                f"offset={cfg.get('offset', '?')}%  "
                f"periods={cfg.get('nbr_of_periods', '?')}")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _visualize_cb(self, _, __, user_data): self._visualize(user_data)
    def _add_cb(self, _, __, user_data):       self._add_to_current(user_data)

    def _visualize(self, idx: int):
        entries = self._entries()
        if idx >= len(entries):
            return
        entry = entries[idx]

        if self._is_frequency():
            cfg = entry.get("frequency_config", {})
            preview = self._build_frequency_preview(cfg)
        else:
            str_seq = entry.get("str_sequence", "")
            if not str_seq.strip():
                return
            decoded, _ = self._seq_control.decode_sequence(str_seq)
            preview = SequencePreviewBuilder().build(decoded)

        if self.bus:
            self.bus.publish("visualize_sequence", preview=preview)

    def _add_to_current(self, idx: int):
        entries = self._entries()
        if idx >= len(entries):
            return
        entry = entries[idx]

        if self._is_frequency():
            cfg = entry.get("frequency_config", {})
            if self.bus:
                self.bus.publish("add_frequency_from_library", frequency_config=cfg)
        else:
            str_seq = entry.get("str_sequence", "")
            if self.bus:
                self.bus.publish("add_sequence_from_library", str_sequence=str_seq)

    def _reload(self, *_):
        self._file_data = _load_file()
        self._populate_table()

    def _save_current(self, *_):
        if self.bus:
            self.bus.publish("request_current_sequence")

    def _on_mode_changed(self, **_):
        self._populate_table()

    # ------------------------------------------------------------------
    # Frequency preview math (mirrors Frequency_input_window._build_preview)
    # ------------------------------------------------------------------
    def _build_frequency_preview(self, cfg: dict) -> dict:
        freq   = cfg.get("frequency", 1.0)
        amp    = cfg.get("amplitude", 50.0)
        offset = cfg.get("offset", 50.0)
        n_det  = cfg.get("nbr_of_periods", 1)
        pre    = cfg.get("pre_detection", 0)
        post   = cfg.get("post_detection", 0)

        total_periods = pre + n_det + post
        if freq <= 0 or total_periods <= 0:
            return {"time_ms": [], "actinic": [], "pulses": []}

        period_ms    = 1000.0 / freq
        total_ms     = total_periods * period_ms
        n_pts        = max(int(total_periods * 80), 3)
        det_start_ms = pre * period_ms
        det_end_ms   = (pre + n_det) * period_ms

        time_ms, actinic, pulses = [], [], []
        for i in range(n_pts):
            t = i * total_ms / (n_pts - 1)
            sine_val = offset + (amp / 2.0) * math.sin(2 * math.pi * freq * t / 1000.0)
            time_ms.append(t)
            actinic.append(max(0.0, min(100.0, sine_val)))
            pulses.append(100.0 if det_start_ms <= t <= det_end_ms else 0.0)

        return {"time_ms": time_ms, "actinic": actinic, "pulses": pulses}

    # ------------------------------------------------------------------
    # New entry modal  (sequence mode only — frequency presets are saved
    # via the "Save current" button from frequency_input)
    # ------------------------------------------------------------------
    def _build_modal(self):
        modal_tag = self._t("modal")
        with dpg.window(tag=modal_tag, label="New saved sequence",
                        modal=True, show=False,
                        no_resize=True, width=420, height=200):
            dpg.add_text("Name:")
            dpg.add_input_text(tag=self._t("new_name"), hint="e.g. Fast decay", width=-1)
            dpg.add_spacer(height=4)
            dpg.add_text("Sequence:")
            dpg.add_input_text(tag=self._t("new_seq"),
                               hint="e.g. 4(100msD)A[100]20msA[0]...",
                               width=-1, multiline=True, height=60)
            dpg.add_spacer(height=6)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Save",   width=100, callback=self._confirm_new)
                dpg.add_button(label="Cancel", width=100,
                               callback=lambda: dpg.hide_item(self._t("modal")))

    def _new_entry_modal(self, *_):
        if self._is_frequency():
            return  # frequency presets are saved via "Save current"
        vw = dpg.get_viewport_client_width()
        vh = dpg.get_viewport_client_height()
        dpg.set_item_pos(self._t("modal"), [vw // 2 - 210, vh // 2 - 100])
        dpg.set_value(self._t("new_name"), "")
        dpg.set_value(self._t("new_seq"),  "")
        dpg.show_item(self._t("modal"))

    def _confirm_new(self, *_):
        name    = dpg.get_value(self._t("new_name")).strip()
        str_seq = dpg.get_value(self._t("new_seq")).strip()
        if not name or not str_seq:
            return
        key = self._section_key()
        self._file_data[key].append({"name": name, "str_sequence": str_seq})
        _save_file(self._file_data)
        self._populate_table()
        dpg.hide_item(self._t("modal"))
