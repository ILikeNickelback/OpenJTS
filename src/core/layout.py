from windows.home_window import Home_win
from windows.experiment.experiment_tab import ExperimentTab
from core.event_bus import EventBus

# Registry of all live ExperimentTab instances, keyed by experiment name
_experiment_tabs: dict = {}


def get_experiment_tabs() -> dict:
    """Return the current registry of ExperimentTab instances."""
    return _experiment_tabs


def create_windows(adc_instance, esp32_instance, app_state, bus, control_tabs):

    # ── Static Home tab ─────────────────────────────────────────────────
    home = Home_win(state=app_state, bus=bus)
    control_tabs.add_tab("Home", home.build_content,
                         select=True, closeable=False)

    # ── '+' callback — receives the name the user typed ──────────────────
    def add_experiment(name: str, acquisition_type: str = "Sequence", experiment_type: str = "Fluo"):
        app_state.set_acquisition_type(acquisition_type)
        app_state.add_experiment(name, acquisition_type, experiment_type)
        bus.publish("experiment_added", name=name,
                    acquisition_type=acquisition_type)

        tab_bus = EventBus()  # isolated bus — events stay within this tab
        exp = ExperimentTab(name=name, state=app_state, bus=tab_bus, acquisition_type=acquisition_type,
                            global_bus=bus)
        _experiment_tabs[name] = exp
        control_tabs.add_tab(name, exp.build_content,
                             select=True, closeable=True)

    control_tabs.on_add_tab = add_experiment

    return control_tabs


def restore_workspace(workspace_data: dict, app_state, bus, control_tabs):
    """
    Recreate all experiment tabs from a loaded workspace dict.

    workspace_data is the return value of WorkspaceManager.load(), i.e.
    {"experiments": [per-experiment dicts], "global_settings": {...}}.
    """
    # Remove all existing experiment tabs from the UI and registry
    for name in list(_experiment_tabs.keys()):
        control_tabs.remove_tab(name)
        _experiment_tabs.pop(name, None)

    # Also clear the experiments list in state so add_experiment doesn't accumulate
    app_state.experiments.clear()

    for data in workspace_data.get("experiments", []):
        name = data["name"]
        acq_type = data.get("acquisition_type", "Sequence")
        exp_type = data.get("experiment_type",  "Fluo")

        # Recreate the tab (mirrors add_experiment)
        app_state.set_acquisition_type(acq_type)
        app_state.add_experiment(name, acq_type, exp_type)
        bus.publish("experiment_added", name=name, acquisition_type=acq_type)

        tab_bus = EventBus()  # isolated bus — events stay within this tab
        exp = ExperimentTab(name=name, state=app_state, bus=tab_bus, acquisition_type=acq_type,
                            global_bus=bus)
        _experiment_tabs[name] = exp
        control_tabs.add_tab(name, exp.build_content,
                             select=True, closeable=True)

        # build_content was triggered by add_tab — restore state now
        exp.restore_from_data(data)
