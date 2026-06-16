"""Config theme for DearPyGui"""

from pathlib import Path
import dearpygui.dearpygui as dpg

BASE_PATH = Path(__file__).parent.parent
FONTSIZE = 15

with dpg.theme() as theme:
    with dpg.font_registry():
        default_font = dpg.add_font(str(BASE_PATH / 'resources' / 'consola.ttf'), FONTSIZE)
    dpg.bind_font(default_font)

    with dpg.theme_component(dpg.mvAll):
        dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5)

def edit_button_style(id, color) :
    """Edit button style with given color and id"""
    with dpg.theme() as button_theme:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, color)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (0,255,0,255))
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding,30)
    dpg.bind_item_theme(id,button_theme)
