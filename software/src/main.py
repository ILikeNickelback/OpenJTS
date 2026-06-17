import multiprocessing
from pathlib import Path


base = Path(__file__).parent

if __name__ == '__main__' :

    multiprocessing.freeze_support()
    from config.config import config
    import dearpygui.dearpygui as dpg
    dpg.create_context()

    from config.fonts import setup_fonts
    setup_fonts( )

    dpg.create_viewport(title=config['General']['app_name'], width = 1920, height = 1200, resizable=True, vsync=True)
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

    from hardware.adc_base import ADCBase
    from hardware.esp32 import Esp32Base

    adc_instance = ADCBase()
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

    dpg.destroy_context()
