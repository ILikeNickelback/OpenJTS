from jts.windows.home_window import Home_win
from jts.windows.experiment_tab_window import ExperimentTab


def create_windows(adc_instance, esp32_instance, app_state, bus, control_tabs):

    # ── Static Home tab ─────────────────────────────────────────────────
    home = Home_win()
    control_tabs.add_tab("Home", home.build_content,
                         select=True, closeable=False)

    # ── '+' callback — receives the name the user typed ──────────────────
    def add_experiment(name: str):
        exp = ExperimentTab(name=name, state=app_state, bus=bus)
        control_tabs.add_tab(name, exp.build_content,
                             select=True, closeable=True)

    control_tabs.on_add_tab = add_experiment

    return control_tabs
