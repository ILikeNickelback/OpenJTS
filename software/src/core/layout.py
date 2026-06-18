"""Top-level window and tab management for the JTS application.

Provides two entry points:

- :func:`create_windows` — called once at startup to build the Home tab and
  wire up the ``'+'`` button that creates new experiment tabs.
- :func:`restore_workspace` — called when loading a saved workspace to
  rebuild all experiment tabs and restore their state.

The module also maintains :data:`_experiment_tabs`, a registry of all live
:class:`~windows.experiment.experiment_tab.ExperimentTab` instances keyed by
experiment name, accessible via :func:`get_experiment_tabs`.
"""

from windows.home_window import Home_win
from windows.experiment.experiment_tab import ExperimentTab
from core.event_bus import EventBus

# Registry of all live ExperimentTab instances, keyed by experiment name
_experiment_tabs: dict = {}


def get_experiment_tabs() -> dict:
    """Return the current registry of ExperimentTab instances."""
    return _experiment_tabs


def create_windows(app_state, bus, control_tabs):
    """Build the Home tab and register the experiment-creation callback.

    Called once at application startup after the DearPyGui context and
    viewport are ready. Adds a permanent, non-closeable Home tab and binds
    ``control_tabs.on_add_tab`` so that each time the user clicks ``'+'``
    a new :class:`~windows.experiment.experiment_tab.ExperimentTab` is
    created and registered.

    Args:
        app_state: Shared :class:`~core.app_state.AppState` instance.
        bus: Application-level :class:`~core.event_bus.EventBus`.
        control_tabs: Tab-bar controller that exposes ``add_tab`` and
            ``on_add_tab``.

    Returns:
        The ``control_tabs`` controller, with the Home tab added and the
        ``on_add_tab`` callback registered.
    """
    # ── Static Home tab ─────────────────────────────────────────────────
    home = Home_win(state=app_state, bus=bus)
    control_tabs.add_tab("Home", home.build_content, select=True, closeable=False)

    # ── '+' callback — receives the name the user typed ──────────────────
    def add_experiment(
        name: str, acquisition_type: str = "Sequence", experiment_type: str = "Fluo"
    ):
        app_state.acquisition_type = acquisition_type
        app_state.add_experiment(name, acquisition_type, experiment_type)
        bus.publish("experiment_added", name=name, acquisition_type=acquisition_type)

        tab_bus = EventBus()  # isolated bus — events stay within this tab
        exp = ExperimentTab(
            name=name,
            state=app_state,
            bus=tab_bus,
            acquisition_type=acquisition_type,
            global_bus=bus,
        )
        _experiment_tabs[name] = exp
        control_tabs.add_tab(name, exp.build_content, select=True, closeable=True)

    control_tabs.on_add_tab = add_experiment

    return control_tabs


def restore_workspace(workspace_data: dict, app_state, bus, control_tabs) -> None:
    """Recreate all experiment tabs from a loaded workspace dict.

    Tears down every existing experiment tab, clears the state experiment
    list, then rebuilds each tab from the saved data and restores its
    per-tab state via
    :meth:`~windows.experiment.experiment_tab.ExperimentTab.restore_from_data`.

    Args:
        workspace_data: Return value of ``workspace_manager.load()``, expected
            shape ``{"experiments": [<per-experiment dicts>], "global_settings": {...}}``.
        app_state: Shared :class:`~core.app_state.AppState` instance.
        bus: Application-level :class:`~core.event_bus.EventBus`.
        control_tabs: Tab-bar controller that exposes ``add_tab`` and
            ``remove_tab``.
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
        exp_type = data.get("experiment_type", "Fluo")

        # Recreate the tab (mirrors add_experiment)
        app_state.acquisition_type = acq_type
        app_state.add_experiment(name, acq_type, exp_type)
        bus.publish("experiment_added", name=name, acquisition_type=acq_type)

        tab_bus = EventBus()  # isolated bus — events stay within this tab
        exp = ExperimentTab(
            name=name,
            state=app_state,
            bus=tab_bus,
            acquisition_type=acq_type,
            global_bus=bus,
        )
        _experiment_tabs[name] = exp
        control_tabs.add_tab(name, exp.build_content, select=True, closeable=True)

        # build_content was triggered by add_tab — restore state now
        exp.restore_from_data(data)
