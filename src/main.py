import dearpygui.dearpygui as dpg

import _xdialog_fix  # noqa
import font
import gui

dpg.create_context()
dpg.create_viewport(title='DifferentDimensionMe-GUI by @ivannazaruk', width=1000, height=800, small_icon='icon.ico', large_icon='icon.ico', clear_color=(71, 71, 72))
dpg.bind_font(font.load())

with dpg.theme() as global_theme:
    with dpg.theme_component(dpg.mvAll):
        dpg.add_theme_color(dpg.mvThemeCol_CheckMark, (0, 255, 255), category=dpg.mvThemeCat_Core)
        dpg.add_theme_color(dpg.mvThemeCol_SliderGrab, (0, 255, 255), category=dpg.mvThemeCat_Core)
    with dpg.theme_component(dpg.mvButton, enabled_state=True):
        dpg.add_theme_color(dpg.mvThemeCol_Button, (51, 51, 55), category=dpg.mvThemeCat_Core)
        dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (29, 151, 236, 103), category=dpg.mvThemeCat_Core)
        dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (0, 119, 200, 153), category=dpg.mvThemeCat_Core)
    with dpg.theme_component(dpg.mvButton, enabled_state=False):
        dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 255, 125), category=dpg.mvThemeCat_Core)
        dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 0, 0, 0), category=dpg.mvThemeCat_Core)
        dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (0, 0, 0, 0), category=dpg.mvThemeCat_Core)
        dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (0, 0, 0, 0), category=dpg.mvThemeCat_Core)
dpg.bind_theme(global_theme)

MainWindow = gui.MainWindow()
MainWindow.create()

dpg.set_primary_window(MainWindow.window, True)

dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()
