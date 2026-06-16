import dearpygui.dearpygui as dpg
from typing import Dict, List, Optional, Callable
from loguru import logger


class TabbedWindowManager:
    """
    Manages a full-filling tab bar inside any DPG container.

    Supports:
    - Static tabs (e.g. Home)        — not closeable
    - Dynamic tabs (e.g. Experiment) — closeable via an [x] button
    - A '+' tab_button that opens a modal prompt for the new tab name
    """

    def __init__(self, label: str = "Tabbed Window Manager", parent=None):
        self.label = label

        self._child_id = dpg.generate_uuid()
        self._tab_bar_id = dpg.generate_uuid()
        self._modal_id = dpg.generate_uuid()
        self._input_id = dpg.generate_uuid()
        self._acq_type_id = dpg.generate_uuid()
        self._exp_type_id = dpg.generate_uuid()

        self.tabs:      Dict[str, int] = {}
        self.tab_order: List[str] = []
        self._builders: Dict[str, Callable] = {}

        # Set from outside: manager.on_add_tab = fn(name: str)
        self.on_add_tab: Optional[Callable[[str], None]] = None

        self._build_ui(parent=parent)
        self._build_modal()

    # ------------------------------------------------------------------
    # Internal UI
    # ------------------------------------------------------------------

    def _build_ui(self, parent=None):
        kwargs = dict(
            tag=self._child_id,
            autosize_x=True,
            autosize_y=True,
            border=False,
        )
        if parent is not None:
            kwargs["parent"] = parent

        with dpg.child_window(**kwargs):
            with dpg.tab_bar(tag=self._tab_bar_id):
                dpg.add_tab_button(
                    label=" + ",
                    callback=self._open_name_modal,
                    trailing=True,
                    no_tooltip=True,
                )

    def _build_modal(self):
        """
        A modal popup that asks the user to name the new experiment.
        Built once; shown/hidden on demand.
        """
        with dpg.window(
            tag=self._modal_id,
            label="New Experiment",
            modal=True,
            show=False,
            no_resize=True,
            width=340,
            height=210,
            pos=[0, 0],   # repositioned dynamically when opened
        ):
            dpg.add_text("Experiment name:")
            dpg.add_input_text(
                tag=self._input_id,
                hint="e.g. Run 01",
                width=-1,
                on_enter=True,           # pressing Enter confirms
                callback=self._confirm,
            )
            dpg.add_separator()

            with dpg.group(horizontal=True):
                dpg.add_radio_button(["Fluo", "Spectro"], tag=self._exp_type_id,
                                     horizontal=True, default_value="Fluo")

            with dpg.group(horizontal=True):
                dpg.add_radio_button(["Sequence", "Frequency"], tag=self._acq_type_id,
                                     horizontal=True, default_value="Sequence")

            dpg.add_spacer(height=6)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Create", width=120,
                               callback=self._confirm)
                dpg.add_button(label="Cancel", width=120,
                               callback=self._cancel)

    # ------------------------------------------------------------------
    # Modal logic
    # ------------------------------------------------------------------

    def _open_name_modal(self):
        # Centre the modal on the viewport
        vw = dpg.get_viewport_client_width()
        vh = dpg.get_viewport_client_height()
        dpg.set_item_pos(self._modal_id, [vw // 2 - 170, vh // 2 - 55])
        dpg.set_value(self._input_id, "")
        dpg.show_item(self._modal_id)
        dpg.focus_item(self._input_id)

    def _confirm(self, *_):
        name = dpg.get_value(self._input_id).strip()
        # "Sequence" or "Frequency"
        acq_type = dpg.get_value(self._acq_type_id)
        exp_type = dpg.get_value(self._exp_type_id)   # "Fluo" or "Spectro"
        dpg.hide_item(self._modal_id)

        if not name:
            logger.warning("No experiment name entered — tab not created.")
            return

        if name in self.tabs:
            logger.warning(f"A tab named '{name}' already exists.")
            return

        if self.on_add_tab is not None:
            self.on_add_tab(name, acq_type, exp_type)
        else:
            logger.warning(
                "on_add_tab callback not set on TabbedWindowManager")

    def _cancel(self, *_):
        dpg.hide_item(self._modal_id)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_tab(
        self,
        tab_label: str,
        builder: Callable,
        select: bool = False,
        closeable: bool = False,
    ) -> bool:
        if tab_label in self.tabs:
            logger.warning(f"Tab '{tab_label}' already exists – replacing.")
            self.remove_tab(tab_label)

        tab_id = dpg.generate_uuid()

        with dpg.tab(
            label=tab_label,
            tag=tab_id,
            parent=self._tab_bar_id,
            closable=False,
        ):
            with dpg.child_window(autosize_x=True, autosize_y=True, border=False):
                try:
                    builder()
                except Exception:
                    logger.exception(
                        f"Error building content for tab '{tab_label}'")

        self.tabs[tab_label] = tab_id
        self._builders[tab_label] = builder
        self.tab_order.append(tab_label)

        if select:
            dpg.set_value(self._tab_bar_id, tab_id)

        if closeable:
            self._watch_for_close(tab_label, tab_id)

        logger.info(f"Added tab '{tab_label}' (closeable={closeable})")
        return True

    def remove_tab(self, tab_label: str) -> bool:
        if tab_label not in self.tabs:
            logger.warning(f"Tab '{tab_label}' not found.")
            return False

        tab_id = self.tabs.pop(tab_label)
        self._builders.pop(tab_label, None)
        self.tab_order.remove(tab_label)

        if dpg.does_item_exist(tab_id):
            dpg.delete_item(tab_id)

        logger.info(f"Removed tab '{tab_label}'")
        return True

    def select_tab(self, tab_label: str):
        if tab_label in self.tabs:
            dpg.set_value(self._tab_bar_id, self.tabs[tab_label])
        else:
            logger.warning(f"Tab '{tab_label}' not found.")

    def get_current_tab(self) -> Optional[str]:
        current_id = dpg.get_value(self._tab_bar_id)
        for label, tid in self.tabs.items():
            if tid == current_id:
                return label
        return None

    @property
    def tab_labels(self) -> List[str]:
        return list(self.tab_order)

    # ------------------------------------------------------------------
    # Close-button detection
    # ------------------------------------------------------------------

    def _watch_for_close(self, tab_label: str, tab_id: int):
        def _check():
            if not dpg.does_item_exist(tab_id):
                return
            if not dpg.is_item_shown(tab_id):
                if tab_label in self.tabs:
                    self.remove_tab(tab_label)
                return
            dpg.set_frame_callback(dpg.get_frame_count() + 6, _check)

        dpg.set_frame_callback(dpg.get_frame_count() + 6, _check)
