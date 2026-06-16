import json
from pathlib import Path

import dearpygui.dearpygui as dpg
from loguru import logger

from core.layout_manager import LayoutManager

from windows.panels.experiment_metadata import Experiment_metadata_window
from windows.panels.sequence_history import Sequence_history_window
from windows.experiment.sequence_input import Sequence_input_window
from windows.experiment.frequency_input import Frequency_input_window
from windows.panels.calibration import calibration_win
from windows.panels.background_light import Background_light_window
from windows.panels.settings import Experiment_settings_window
from windows.plots.sequence_plot import Sequence_plot_window
from windows.experiment.sequence_handler import Sequence_handler_window
from windows.experiment.frequency_handler import Frequency_handler_window
from windows.panels.sequence_library import SequenceLibraryWindow
from windows.plots.lineplot import Lineplot_win
from windows.panels.sample_container import Sample_container_win
from windows.experiment.acquisition import Acquisition_win


class ExperimentTab:
    """
    Content for a single Experiment tab.

    Internally it renders its own nested tab bar with sub-tabs.
    Sub-tabs are defined in _SUB_TABS — add your real builders there.
    """

    _SUB_TABS = [
        ("Overview",    "_build_overview"),
        ("Setup", "_build_setup"),
        ("Acquisition",  "_build_acquisition"),
        ("Post-processing",    "_build_settings"),
    ]

    def __init__(self, name: str = "Experiment", state=None, bus=None, acquisition_type: str = "Sequence",
                 global_bus=None):
        self.name = name
        self.state = state
        self.bus = bus
        self.global_bus = global_bus
        self.acquisition_type = acquisition_type

        # References set during build_content()
        self.sequence_input_win    = None
        self.frequency_input_win   = None
        self.history_win           = None
        self.lineplot_win          = None
        self.metadata_win          = None
        self.sample_container_win: Sample_container_win | None = None

        if bus:
            bus.subscribe("final_data", self._autosave)
            bus.subscribe("metadata_updated",
                          lambda **kw: global_bus.publish("metadata_updated", **kw) if global_bus else None)

    # ------------------------------------------------------------------
    # Top-level builder — called by TabbedWindowManager
    # ------------------------------------------------------------------

    def build_content(self):
        with dpg.tab_bar():
            for sub_label, method_name in self._SUB_TABS:
                with dpg.tab(label=sub_label):
                    with dpg.child_window(autosize_x=True, autosize_y=True, border=False, no_scrollbar=True, no_scroll_with_mouse=True):
                        builder = getattr(self, method_name, None)
                        if builder:
                            try:
                                builder()
                            except Exception:
                                logger.exception(
                                    f"Error building sub-tab '{sub_label}' "
                                    f"for experiment '{self.name}'"
                                )
                        else:
                            dpg.add_text(f"[{sub_label}] — not yet implemented")

    # ------------------------------------------------------------------
    # Sub-tab builders
    # ------------------------------------------------------------------

    def _build_overview(self):
        lm = LayoutManager()
        self.metadata_win = Experiment_metadata_window(
            **lm.get("overview", "experiment metadata"),
            state=self.state, bus=self.bus, experiment_name=self.name)
        self.history_win = Sequence_history_window(
            **lm.get("overview", "sequence history"),
            state=self.state, bus=self.bus)

    def _build_acquisition(self):
        lm = LayoutManager()
        self.lineplot_win         = Lineplot_win(
            **lm.get("processing", "plot"),    state=self.state, bus=self.bus,
            experiment_name=self.name)
        self.sample_container_win = Sample_container_win(
            **lm.get("processing", "samples"), state=self.state, bus=self.bus,
            experiment_name=self.name)
        Acquisition_win(
            **lm.get("processing", "acquisition"), state=self.state, bus=self.bus)

    def _build_setup(self):
        if self.acquisition_type == "Frequency":
            self._build_frequency_setup()
        else:
            self._build_sequence_setup()

    def _build_sequence_setup(self):
        lm = LayoutManager()
        self.sequence_input_win = Sequence_input_window(
            **lm.get("setup", "sequence_writer"), state=self.state, bus=self.bus)
        calibration_win(           **lm.get("setup", "calibration"),      state=self.state, bus=self.bus)
        Background_light_window(   **lm.get("setup", "background"),       state=self.state, bus=self.bus)
        Experiment_settings_window(**lm.get("setup", "settings"),         state=self.state, bus=self.bus)
        Sequence_plot_window(      **lm.get("setup", "sequence_plot"),    state=self.state, bus=self.bus)
        Sequence_handler_window(   **lm.get("setup", "sequence_handler"), state=self.state, bus=self.bus)
        SequenceLibraryWindow(    **lm.get("setup", "Load_experiment"),  state=self.state, bus=self.bus)

    def _build_frequency_setup(self):
        lm = LayoutManager()
        self.frequency_input_win = Frequency_input_window(
            **lm.get("frequency_setup", "frequency_input"),   state=self.state, bus=self.bus)
        Sequence_plot_window(      **lm.get("frequency_setup", "sequence_plot"),     state=self.state, bus=self.bus)
        Experiment_settings_window(**lm.get("frequency_setup", "settings"),          state=self.state, bus=self.bus)
        SequenceLibraryWindow(    **lm.get("frequency_setup", "Load_experiment"),   state=self.state, bus=self.bus)
        calibration_win(           **lm.get("frequency_setup", "calibration"),       state=self.state, bus=self.bus)
        Background_light_window(   **lm.get("frequency_setup", "background"),        state=self.state, bus=self.bus)
        Frequency_handler_window(  **lm.get("frequency_setup", "frequency_handler"), state=self.state, bus=self.bus)

    def _build_settings(self):
        dpg.add_text("Post-processing — coming soon.")

    # ------------------------------------------------------------------
    # Workspace save / restore
    # ------------------------------------------------------------------

    def _autosave(self, **_):
        """Write a temp JSON snapshot after every completed acquisition."""
        try:
            data = self.collect_save_data()
            save_dir = Path(__file__).parent.parent.parent / "temp"
            save_dir.mkdir(exist_ok=True)
            path = save_dir / "autosave.json"
            with open(path, "w") as f:
                json.dump(data, f, indent=4)
            logger.info(f"Autosave written to {path}")
        except Exception:
            logger.exception("Autosave failed")

    def collect_save_data(self) -> dict:
        """Gather all experiment data for workspace serialisation."""
        # Metadata from state
        exp_entry = next(
            (e for e in self.state.get_experiments() if e["name"] == self.name), {}
        )
        metadata = {
            "operator":  exp_entry.get("operator", ""),
            "project":   exp_entry.get("project", ""),
            "sample_id": exp_entry.get("sample_id", ""),
            "date":      exp_entry.get("date", ""),
            "comments":  exp_entry.get("comments", ""),
        }

        # Sequence strings
        sequences = (
            self.sequence_input_win.get_sequence_strings()
            if self.sequence_input_win else []
        )

        # Parameters: convert n-keyed (stable int) to position-keyed (1-based int)
        # UUID_sequence_input_list maps position -> "UUID_n"
        parameters = {}
        uuid_map = self.state.get_UUID_sequence_input()  # {pos: "UUID_n"}
        for pos, uuid_n in uuid_map.items():
            # uuid_n is "UUID_n"; extract the n suffix
            try:
                n = int(uuid_n.split("_")[-1])
            except (ValueError, IndexError):
                n = pos
            params = self.state.get_parameter_list(n)
            if params is not None:
                parameters[str(pos)] = params

        # History
        history = list(self.history_win._history) if self.history_win else []

        # Results
        results = self.lineplot_win.get_results() if self.lineplot_win else []

        # Sample container — all accumulated samples with user-edited names
        samples = self.sample_container_win.get_samples() if self.sample_container_win else []

        # Frequency configs
        frequency_configs = (
            self.frequency_input_win.get_frequency_configs()
            if self.frequency_input_win else []
        )

        return {
            "name":              self.name,
            "acquisition_type":  exp_entry.get("acquisition_type", ""),
            "experiment_type":   exp_entry.get("experiment_type", ""),
            "metadata":          metadata,
            "sequences":         sequences,
            "parameters":        parameters,
            "history":           history,
            "results":           results,
            "samples":           samples,
            "frequency_configs": frequency_configs,
        }

    def restore_from_data(self, data: dict):
        """Restore experiment state from a saved data dict."""
        # Restore metadata into state and notify listeners
        metadata = data.get("metadata", {})
        for key, value in metadata.items():
            self.state.update_experiment_metadata(self.name, key, value)
        if self.bus:
            self.bus.publish("metadata_updated", experiment_name=self.name)

        # Restore sequences
        if self.sequence_input_win:
            self.sequence_input_win.load_sequences(data.get("sequences", []))

        # Restore parameters: position-keyed -> n-keyed via UUID map
        parameters = data.get("parameters", {})
        uuid_map = self.state.get_UUID_sequence_input()  # {pos: "UUID_n"}
        for pos_str, params in parameters.items():
            try:
                pos = int(pos_str)
            except ValueError:
                continue
            uuid_n = uuid_map.get(pos)
            if uuid_n is None:
                continue
            try:
                n = int(uuid_n.split("_")[-1])
            except (ValueError, IndexError):
                n = pos
            self.state.set_parameter_list(n, params)

        # Restore history
        if self.history_win:
            self.history_win.load_history(data.get("history", []))

        # Restore results: lineplot rebuilds _saved_results, sample_container
        # recreates the checkbox entries and drives plotting via plot_cmd.
        results = data.get("results", [])
        if self.lineplot_win:
            self.lineplot_win.load_results(results)
        if self.sample_container_win:
            samples = data.get("samples") or results
            self.sample_container_win.load_results(samples)

        # Restore frequency configs
        frequency_configs = data.get("frequency_configs", [])
        if self.frequency_input_win and frequency_configs:
            self.frequency_input_win.load_frequency_configs(frequency_configs)
