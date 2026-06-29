import dearpygui.dearpygui as dpg
from loguru import logger

from core.window_base import WindowBase
from config import fonts

from utils.json_file_manager import JsonFileManager
from sequence_builders.control import sequence_control
from sequence_builders.sequence_waveform_builder import SequencePreviewBuilder


class Sequence_input_window(WindowBase):
    """
    Multi-slot sequence text editor.

    Each slot is a labelled multiline input holding a raw sequence string.
    Slots use an ever-increasing counter so deleted DPG tags never collide
    with new ones. Supports add, delete, visualize, and per-sequence
    parameter access. Position labels (Sequence 1, 2, …) are kept in sync
    with app_state via _sync_state after every structural change.
    """

    def __init__(
        self,
        label="Sequence input",
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

        self.json_file_manager = JsonFileManager()
        self.json_file_manager.create_dialogs()
        self.sequence_control = sequence_control()

        # Ever-increasing counter — gives each sequence a unique DPG tag suffix.
        # Never reused so that deleted tags never collide with new ones.
        self._sequence_counter = 0

        # Ordered list of the n-values that are currently displayed.
        # This is the source of truth for "which sequences exist and in what order".
        self._active_ns = []

        self.pos = pos
        self.width = width
        self.height = height

        self._build_ui()

        if bus:
            bus.subscribe("add_sequence_from_library", self._on_add_from_library)
            bus.subscribe("add_sequences_from_library", self._on_add_many_from_library)
            bus.subscribe("request_current_sequence", self._on_request_current)

    # ----------------------------------------------------------
    # UI BUILDING
    # ----------------------------------------------------------

    def _build_ui(self):
        self._container_tag = f"seq_container_{self.UUID}"
        with dpg.child_window(
            tag=self._container_tag,
            width=self.width,
            height=self.height,
            pos=self.pos,
            border=True,
            show=self.visible,
        ):
            self.add_sequence()

    def add_sequence(self):
        prev_n = self._active_ns[-1] if self._active_ns else None

        self._sequence_counter += 1
        n = self._sequence_counter
        self._active_ns.append(n)

        # Inherit parameters from the previous sequence
        if prev_n is not None and self.state:
            prev_params = (getattr(self.state, "sequence_parameters", {}) or {}).get(
                prev_n
            )
            if prev_params is not None:
                if not hasattr(self.state, "sequence_parameters"):
                    self.state.sequence_parameters = {}
                self.state.sequence_parameters[n] = dict(prev_params)

        parent = self._container_tag
        display_idx = len(self._active_ns)

        # Header row: sequence label + Params + Visualize buttons
        with dpg.group(
            horizontal=True, tag=f"seq_header_{self.UUID}_{n}", parent=parent
        ):
            dpg.add_text(
                f"Sequence {display_idx}",
                tag=f"seq_label_{self.UUID}_{n}",
                color=(180, 220, 255),
            )

        # Full-width multiline input
        input_tag = f"seq_input_{self.UUID}_{n}"
        dpg.add_input_text(
            tag=input_tag,
            hint="Enter sequence here",
            default_value="4(100msD)A[100]20msA[0]300µsD1msD2msD5(5msD)5(10msD)5(20msD)2(100msD)",
            no_horizontal_scroll=False,
            width=-1,
            height=200,
            multiline=True,
            parent=parent,
        )
        font = fonts.monospace_large()
        if font is not None:
            dpg.bind_item_font(input_tag, font)

        # Management buttons
        with dpg.group(
            horizontal=True, tag=f"seq_btn_group_{self.UUID}_{n}", parent=parent
        ):
            dpg.add_button(label="+ Add", callback=self._add_sequence_cb)
            dpg.add_button(
                label="Delete",
                tag=f"seq_del_{self.UUID}_{n}",
                callback=lambda _, __, user_data: self._delete_sequence_cb(user_data),
                user_data=n,
            )
            dpg.add_button(
                label="Parameters",
                tag=f"seq_params_{self.UUID}_{n}",
                callback=lambda _, __, user_data: self._open_params(user_data),
                user_data=n,
            )
            dpg.add_button(
                label="Visualize",
                callback=lambda _, __, user_data: self._visualize(user_data),
                user_data=n,
            )

        dpg.add_separator(tag=f"seq_sep_{self.UUID}_{n}", parent=parent)

        self._relabel_all()
        self._sync_state()

    def _add_sequence_cb(self):
        logger.debug("'+ Add' button clicked")
        self.add_sequence()

    def delete_sequence(self, n):
        if len(self._active_ns) <= 1 or n not in self._active_ns:
            return  # never delete the last sequence or if n is not active

        self._active_ns.remove(n)

        for tag in [
            f"seq_header_{self.UUID}_{n}",  # group containing label + key buttons
            f"seq_input_{self.UUID}_{n}",
            f"seq_btn_group_{self.UUID}_{n}",
            f"seq_sep_{self.UUID}_{n}",
        ]:
            if dpg.does_item_exist(tag):
                dpg.delete_item(tag)

        self._relabel_all()
        self._sync_state()

    def _delete_sequence_cb(self, n):
        logger.debug("'Delete' button clicked")
        self.delete_sequence(n)

    # ----------------------------------------------------------
    # Renaming and state sync
    # ----------------------------------------------------------

    def _open_params(self, n: int):
        """Publish event to open/focus the settings panel for sequence n."""
        logger.debug("'Parameters' button clicked")
        display_idx = self._active_ns.index(n) + 1 if n in self._active_ns else n
        if self.bus:
            self.bus.publish(
                "open_sequence_settings", n=n, label=f"Sequence {display_idx}"
            )

    def _visualize(self, n: int):
        """Decode the sequence for row n, build a preview, and publish it on the bus."""
        logger.debug("'Visualize' button clicked")
        str_seq = dpg.get_value(f"seq_input_{self.UUID}_{n}") or ""
        if not str_seq.strip():
            return
        decoded, _ = self.sequence_control.decode_sequence(str_seq)
        preview = SequencePreviewBuilder().build(decoded)
        if self.bus:
            self.bus.publish("visualize_sequence", preview=preview)

    def _on_add_from_library(self, str_sequence: str = "", **_):
        """Add a new sequence row pre-filled with the library entry."""
        self._append_sequence(str_sequence)

    def _on_add_many_from_library(self, str_sequences=None, **_):
        """Add one new row per sequence in a saved protocol, in order."""
        for str_sequence in str_sequences or []:
            self._append_sequence(str_sequence)

    def _append_sequence(self, str_sequence: str):
        self.add_sequence()
        last_n = self._active_ns[-1]
        dpg.set_value(f"seq_input_{self.UUID}_{last_n}", str_sequence)

    def _on_request_current(self, **_):
        """Answer request_current_sequence with every active sequence string."""
        if self.bus:
            self.bus.publish(
                "current_sequence_data", str_sequences=self.get_sequence_strings()
            )

    def _relabel_all(self):
        """Update every sequence label to reflect its current position (1 to n)."""
        for display_idx, n in enumerate(self._active_ns, start=1):
            label_tag = f"seq_label_{self.UUID}_{n}"
            if dpg.does_item_exist(label_tag):
                dpg.set_value(label_tag, f"Sequence {display_idx}")

    def _sync_state(self):
        """Rebuild app_state UUID map so positions 1..n stay contiguous."""
        if not self.state:
            return
        self.state.UUID_sequence_input_list = {}
        for display_idx, n in enumerate(self._active_ns, start=1):
            self.state.set_UUID_sequence_input(f"{self.UUID}_{n}", display_idx)

    # ----------------------------------------------------------
    # Sequence processing
    # ----------------------------------------------------------

    def _process_all_sequences(self):
        """Decode every sequence field and push the list to app_state."""
        uuid_map = self.state.get_UUID_sequence_input()
        sequence_list = []

        for pos in sorted(uuid_map.keys()):
            uuid = uuid_map[pos]
            str_seq = dpg.get_value(f"seq_input_{uuid}")
            if not str_seq.strip():
                continue
            decoded, nbr_of_points = self.sequence_control.decode_sequence(str_seq)
            sequence_list.append(
                {
                    "str_sequence": str_seq,
                    "decoded": decoded,
                    "nbr_of_points": nbr_of_points,
                }
            )

        self.state.set_sequence_list(sequence_list)
        self.bus.publish("sequence_list_ready", count=len(sequence_list))

        dpg.set_value(
            f"process_status_{self.UUID}", f"{len(sequence_list)} sequence(s) ready."
        )

    # ----------------------------------------------------------
    # Save / Load
    # ----------------------------------------------------------

    def get_sequence_strings(self) -> list:
        """Return the current text value of every active sequence input."""
        return [
            dpg.get_value(f"seq_input_{self.UUID}_{n}") or "" for n in self._active_ns
        ]

    def load_sequences(self, strings: list):
        """Replace all current sequences with the given string list."""
        # Remove all but the first active sequence (can never delete the last)
        while len(self._active_ns) > 1:
            self.delete_sequence(self._active_ns[-1])

        # Set the first slot if there are strings; otherwise leave it blank
        if strings:
            dpg.set_value(f"seq_input_{self.UUID}_{self._active_ns[0]}", strings[0])
            for s in strings[1:]:
                self.add_sequence()
                last_n = self._active_ns[-1]
                dpg.set_value(f"seq_input_{self.UUID}_{last_n}", s)
        else:
            dpg.set_value(f"seq_input_{self.UUID}_{self._active_ns[0]}", "")

        self._sync_state()

    # ----------------------------------------------------------
    # Visibility
    # ----------------------------------------------------------

    def show(self):
        dpg.configure_item(self._container_tag, show=True)

    def hide(self):
        dpg.configure_item(self._container_tag, show=False)
