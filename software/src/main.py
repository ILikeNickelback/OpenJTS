"""Application entry point for OpenJTS.

Startup sequence
----------------
1. ``multiprocessing.freeze_support()`` — required for Windows frozen builds.
2. DearPyGUI context, viewport (1920×1200, maximised), and fonts are
   initialised before any window objects are created.
3. Per-monitor DPI awareness is set via the Win32 shcore API so the UI
   renders crisply on high-DPI displays.  The thread execution state is
   also locked to prevent the display from sleeping during long acquisitions.
4. ``Main_win`` builds the primary window and menu bar.
5. Hardware instances (ADC, ESP32) and shared application objects
   (``AppState``, ``EventBus``) are constructed and wired together.
6. ``create_windows`` populates the tab bar and registers the experiment-
   creation callback; ``main_window.setup`` hands it the workspace
   save/restore hooks.
7. The explicit render loop runs until the user closes the window.
8. On exit, all experiment tabs are shut down (stopping worker threads),
   hardware is disconnected, and the DPG context is destroyed.

All imports that depend on the DPG context are deferred into the
``if __name__ == '__main__'`` block to prevent import-time side effects
when this module is loaded by multiprocessing worker processes.
"""

import multiprocessing
from pathlib import Path


base = Path(__file__).parent

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from config.config import config
    import dearpygui.dearpygui as dpg

    dpg.create_context()

    from config.fonts import setup_fonts

    setup_fonts()

    dpg.create_viewport(
        title=config["General"]["app_name"],
        width=1920,
        height=1200,
        resizable=True,
        vsync=True,
    )
    dpg.setup_dearpygui()
    dpg.maximize_viewport()
    dpg.configure_app(docking=False)

    import ctypes

    ctypes.windll.shcore.SetProcessDpiAwareness(2)
    ES_CONTINUOUS = 0x80000000
    ES_DISPLAY_REQUIRED = 0x00000002
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_DISPLAY_REQUIRED)

    from windows.main_window import Main_win

    main_window = Main_win()
    dpg.set_primary_window(main_window.winID, True)

    dpg.show_viewport()

    from hardware.adc_sequence import SequenceAcquisitionADC
    from hardware.esp32 import Esp32Base

    adc_instance = SequenceAcquisitionADC()
    esp32_instance = Esp32Base()

    from core.app_state import AppState
    from core.event_bus import EventBus

    app_state = AppState()
    bus = EventBus()

    app_state.set_adc_instance(adc_instance)
    app_state.set_esp32_instance(esp32_instance)

    from core.layout import create_windows, get_experiment_tabs, restore_workspace

    create_windows(app_state, bus, main_window.control_tabs)
    main_window.setup(app_state, bus, get_experiment_tabs, restore_workspace)

    while dpg.is_dearpygui_running():
        dpg.render_dearpygui_frame()

    for tab in get_experiment_tabs().values():
        tab.shutdown()
    adc_instance.shutdown()
    esp32_instance.disconnect()

    dpg.destroy_context()
