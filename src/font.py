import ctypes
import sys

import dearpygui.dearpygui as dpg

font_size = 25
default_path = './fonts/InterTight-Regular.ttf'

texture_registry = None
font_registry = None


def add_font(file, size: int | float, parent=0, **kwargs) -> int:
    if not isinstance(size, (int, float)):
        raise ValueError(f'font size must be an integer or float. Not {type(size)}')

    with dpg.font(file, size, parent=parent, **kwargs) as font:
        dpg.add_font_range_hint(dpg.mvFontRangeHint_Default, parent=font)
        # dpg.add_font_range_hint(dpg.mvFontRangeHint_Cyrillic, parent=font)
    return font


def load() -> int:
    '''
    :return: default font
    '''
    global texture_registry, font_registry
    if sys.platform.startswith('win'):
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(u'CompanyName.ProductName.SubProduct.VersionInformation')
    ctypes.windll.shcore.SetProcessDpiAwareness(1)

    texture_registry = dpg.add_texture_registry(show=False)
    font_registry = dpg.add_font_registry()

    return add_font(default_path, font_size, parent=font_registry)
