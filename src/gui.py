from __future__ import annotations

import subprocess
import threading
import time
import traceback
from io import BytesIO

import dearpygui.dearpygui as dpg
import xdialog
from PIL import Image, ImageGrab, BmpImagePlugin

import DearPyGui_ImageController as dpg_img
import font
from tools import ViewportResizeManager, dpg_callback, LoadedImage, RequestQueue, CallWhenDPGStarted, image_to_clipboard


class AutoImageWrapper:
    theme = 0
    table: int
    all_items: list[int]
    item_width: int
    items_in_last_row: int
    _now_count_items_in_row: int
    spacers_list: list

    def __new__(cls, *args, **kwargs):
        if cls.theme == 0:
            with dpg.theme() as cls.theme:
                with dpg.theme_component(dpg.mvAll):
                    dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 0, 0, category=dpg.mvThemeCat_Core)
                    dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 0, 0, category=dpg.mvThemeCat_Core)
                    dpg.add_theme_style(dpg.mvStyleVar_CellPadding, 0, 0, category=dpg.mvThemeCat_Core)
                    dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 0, 0, category=dpg.mvThemeCat_Core)
        return object.__new__(cls)

    def __init__(self, item_width: int):
        self.item_width = item_width
        self.items_in_last_row = 0
        self._now_count_items_in_row = 0
        self.all_items = []
        self.spacers_list = []

    def delete(self):
        ViewportResizeManager.remove_callback(self.resize_tag)
        dpg.delete_item(self.window)

    def update(self):
        if self.item_width <= 0:
            return
        viewport_width = dpg.get_item_rect_size(self.window)[0]
        count_items_in_row = viewport_width // self.item_width
        if count_items_in_row <= 0:
            count_items_in_row = 1
        if count_items_in_row > len(self.all_items):
            count_items_in_row = len(self.all_items)

        between_spacer_width: int = (viewport_width - count_items_in_row * self.item_width) / (count_items_in_row + 1)  # noqa

        dpg.configure_item(self.spacer, width=between_spacer_width, show=between_spacer_width > 0)
        if self._now_count_items_in_row == count_items_in_row:
            for spacer in self.spacers_list:
                dpg.configure_item(spacer, width=between_spacer_width)
            return

        self._now_count_items_in_row = count_items_in_row
        self.spacers_list = []
        for item in self.all_items:
            dpg.move_item(item, parent=self.stage)

        dpg.delete_item(self.table, children_only=True)
        for i in range(count_items_in_row):
            dpg.add_table_column(width_fixed=True, parent=self.table)

        for i, item in enumerate(self.all_items):
            if not i % count_items_in_row:
                row = dpg.add_table_row(parent=self.table)

            with dpg.group(parent=row, horizontal=True) as cell_group:  # noqa
                dpg.move_item(self.all_items[i], parent=cell_group)
                if not (i + 1) % count_items_in_row:
                    dpg.configure_item(cell_group, horizontal=False)
                    dpg.add_spacer(height=10, parent=cell_group)
                    continue
                spacer = dpg.add_spacer(width=between_spacer_width, parent=cell_group)
                self.spacers_list.append(spacer)

    def window_resize(self):
        self.update()

    def append_items(self, dpg_items: int | list[int]):
        if isinstance(dpg_items, list):
            self.all_items.extend(dpg_items)
        else:
            self.all_items.append(dpg_items)
        self._now_count_items_in_row = -1
        self.update()

    def create(self, parent=0):
        self.resize_tag = ViewportResizeManager.add_callback(self.window_resize)
        with dpg.child_window(parent=parent, width=-1) as self.window:
            dpg.bind_item_theme(self.window, self.theme)
            with dpg.group(horizontal=True) as self.main_group:
                self.spacer = dpg.add_spacer(width=0, height=0, show=False, parent=self.main_group)
                self.table = dpg.add_table(resizable=False, header_row=False, parent=self.main_group)
            self.stage = dpg.add_stage()
        if CallWhenDPGStarted.STARTUP_DONE:
            dpg.split_frame()
            self.update()
        else:
            CallWhenDPGStarted.append(
                self.update
            )


class AIImageViewer:
    image_viewer: dpg_img.ImageViewer
    image_filepath: str = ''

    is_error: bool = False
    loaded: bool = False

    click_handler: int = None
    deleted: bool = False

    class StatusColors:
        wait_queue = (150, 0, 200)
        wait_request = (60, 230, 230)
        wait_load_image = (0, 255, 0)
        error = (255, 0, 0)

    @staticmethod
    def get_loading_indicator_radius(width: int, height: int):
        radius = width if width < height else height
        radius = radius / font.font_size
        return radius

    def __init__(self, loaded_image: LoadedImage, version=2):
        self.request_image = loaded_image
        self.version = version

        self.image_viewer = dpg_img.ImageViewer()

    def start_request(self):
        if self.deleted:
            return
        self.is_error = False
        RequestQueue.append(self.request_image,
                            version=self.version,
                            start_callback=self.started,
                            error_callback=self.error,
                            done_callback=self.done)
        dpg.configure_item(self.loading_indicator,
                           speed=1,
                           color=self.StatusColors.wait_queue)

    def create(self, width: int, height: int, parent: int | str = 0):
        if self.deleted:
            return
        self.parent_window = parent
        self.width = width
        self.height = height

        with dpg.group(parent=parent) as self.group:
            self.loading_indicator = dpg.add_loading_indicator(radius=self.get_loading_indicator_radius(width, height),
                                                               color=self.StatusColors.wait_queue,
                                                               secondary_color=(255, 255, 255),
                                                               parent=self.group)
            self.start_request()

    def started(self):
        if self.deleted:
            return
        dpg.configure_item(self.loading_indicator,
                           color=self.StatusColors.wait_request)

    def error(self, msg: str):
        if self.deleted:
            return
        self.is_error = True
        dpg.configure_item(self.loading_indicator,
                           color=self.StatusColors.error,
                           speed=0)

    def done(self, image: Image.Image, filepath: str):
        if self.deleted:
            return
        dpg.configure_item(self.loading_indicator,
                           color=self.StatusColors.wait_load_image)

        self.image_filepath = filepath

        self.image_viewer.load(image)
        self.loaded = True

        with dpg.item_handler_registry() as self.click_handler:
            dpg.add_item_clicked_handler(callback=lambda _, data: self.click(mouse_button=data[0]))
        self.image_viewer.set_image_handler(self.click_handler)

        self.set_width(self.width)
        self.image_viewer.create(parent=self.parent_window)

        dpg.delete_item(self.loading_indicator)

    def set_width(self, width: int = None):
        if self.deleted:
            return
        self.width = width
        if not self.loaded:
            if width is None:
                width, height = self.request_image.width, self.request_image.height
            else:
                height = self.request_image.height * (width / self.request_image.width)
            dpg.configure_item(self.parent_window, width=width, height=height)
            dpg.configure_item(self.loading_indicator,
                               radius=self.get_loading_indicator_radius(width, height))
        else:
            self.image_viewer.set_width(width)
            width, height = self.image_viewer.get_size()
            dpg.configure_item(self.parent_window, width=width, height=height)

    def click(self, mouse_button):
        if self.deleted:
            return
        if not self.loaded:
            return
        if mouse_button == 1:  # Right button
            if self.image_viewer.info:
                image_to_clipboard(self.image_viewer.info.image)
        else:  # Left or Middle button
            subprocess.Popen(rf'explorer /select,"{self.image_filepath}"')

    def delete(self):
        if self.deleted:
            return
        self.deleted = True

        self.image_viewer.delete()
        self.image_viewer = None  # noqa
        dpg_img.HandlerDeleter.add(self.click_handler)
        self.click_handler = None  # noqa

        try:
            dpg.delete_item(self.group)
        except Exception:
            pass
        finally:
            self.group = None


class AIImageManager:
    group: int
    image_wrapper: AutoImageWrapper
    loaded_image: LoadedImage
    image_viewers_list: list[AIImageViewer]

    def create(self):
        self.image_viewers_list = []
        self.loaded_image = None
        self.image_wrapper = AutoImageWrapper(1_000)
        with dpg.group() as self.group:
            self.image_wrapper.create()

    def clear(self):
        RequestQueue.clear()

        self.image_wrapper.delete()
        del self.image_wrapper

        for image_viewer in self.image_viewers_list:
            image_viewer.delete()
        self.image_viewers_list.clear()

        dpg.delete_item(self.group, children_only=True)

    def start_load(self, loaded_image: LoadedImage, image_width: int, count: int, version: int = 2):
        self.clear()
        self.image_wrapper = AutoImageWrapper(
            item_width=image_width
        )
        self.image_wrapper.create(parent=self.group)
        self.loaded_image = loaded_image

        image_height = self.loaded_image.get_height(width=image_width)

        items_list = []
        self.image_viewers_list = []
        for i in range(count):
            with dpg.child_window(parent=self.image_wrapper.stage,
                                  width=image_width,
                                  height=image_height) as child_window:
                image_viewer = AIImageViewer(loaded_image, version=version)
                image_viewer.create(width=image_width,
                                    height=image_height,
                                    parent=child_window)
                self.image_viewers_list.append(image_viewer)

            items_list.append(child_window)
        self.image_wrapper.append_items(items_list)

    def set_width(self, width: int):
        if self.loaded_image is None:
            return
        self.image_wrapper.item_width = width
        for image_viewer in self.image_viewers_list:
            image_viewer.set_width(width=width)
        self.image_wrapper.update()


class MainWindow:
    window: int
    image_path_label: int
    AIImagerLoader: AIImageManager
    loaded_image: LoadedImage
    tooltip_image: dpg_img.ImageViewer

    choose_width_options = ['image width', 'self width:']

    def __init__(self):
        self.AIImagerLoader = AIImageManager()
        self.loaded_image = None
        self.tooltip_image = None

    def set_tooltip_image(self, image: Image.Image | None = None):
        if self.tooltip_image is not None:
            self.tooltip_image.delete()
        dpg.delete_item(self.text_tooltip, children_only=True)
        if image:
            self.tooltip_image = dpg_img.add_image(image=image, parent=self.text_tooltip)
        else:
            self.tooltip_image = None

    @dpg_callback()
    def open_image_file(self):
        dpg.configure_item(self.open_image_button, enabled=False)
        dpg.configure_item(self.start_button, enabled=False)

        filetypes = [
            '*.jpg', '*.jpeg', '*.jfif', '*.pjpeg', '*.pjp',  # JPEG
            '*.png',  # PNG
            '*.bmp',  # BMP
            '.ico', '.cur',  # ICO
        ]
        image_path = xdialog.open_file("Select image",
                                       filetypes=[("Image file", " ".join(filetypes)),
                                                  ("Any file", "*")],
                                       multiple=False)
        dpg.set_value(self.image_path_label, "")
        if image_path:
            try:
                dpg.configure_item(self.image_path_label, color=(60, 230, 230))
                dpg.set_value(self.image_path_label, 'Loading...')

                self.loaded_image = LoadedImage(image_path)
                self.set_tooltip_image(self.loaded_image.image)

                dpg.set_value(self.image_path_label, image_path)
                dpg.configure_item(self.image_path_label, color=(100, 255, 100))
            except Exception as e:
                traceback.print_exc()
                dpg.set_value(self.image_path_label, f'ERROR: {e}')
                dpg.configure_item(self.image_path_label, color=(255, 0, 0))
        else:
            self.set_tooltip_image()
        dpg.configure_item(self.start_button, enabled=bool(image_path))
        dpg.configure_item(self.open_image_button, enabled=True)

    @dpg_callback()
    def try_paste_image(self):
        dpg.configure_item(self.open_image_button, enabled=False)
        dpg.configure_item(self.start_button, enabled=False)

        image = ImageGrab.grabclipboard()
        if isinstance(image, list):
            if len(image) > 0:
                image = image[0]
            else:
                image = None

        if isinstance(image, str):
            try:
                image = Image.open(image)
            except Exception:
                traceback.print_exc()
                image = None
        dpg.set_value(self.image_path_label, "")
        if isinstance(image, BmpImagePlugin.DibImageFile) or isinstance(image, Image.Image):
            try:
                output = BytesIO()
                image.save(output, format="png")
                self.loaded_image = LoadedImage(output)
                self.loaded_image.path = None
                self.set_tooltip_image(self.loaded_image.image)
                dpg.set_value(self.image_path_label, "{CLIPBOARD_IMAGE}")
                dpg.configure_item(self.image_path_label, color=(100, 255, 100))
            except Exception as e:
                traceback.print_exc()
                dpg.set_value(self.image_path_label, f'ERROR: {e}')
                dpg.configure_item(self.image_path_label, color=(255, 0, 0))
        else:
            self.set_tooltip_image()
        dpg.configure_item(self.start_button, enabled=bool(image))
        dpg.configure_item(self.open_image_button, enabled=True)

    def check_clipboard_paste(self, _, key):
        if key != 86:  # key != 'V'
            return
        if dpg.is_key_down(17):  # ctrl
            self.try_paste_image(self=self)

    def get_show_image_width(self):
        if dpg.get_value(self.choise_width) == self.choose_width_options[0]:
            image_width = self.loaded_image.width
        else:
            image_width = dpg.get_value(self.image_width_input)
            try:
                image_width = int(image_width)
                if image_width <= 0:
                    raise ValueError
            except Exception:
                dpg.set_value(self.image_width_input, self.loaded_image.width)
                image_width = self.loaded_image.width
        min_value = dpg.get_item_configuration(self.image_width_input)['min_value']
        if image_width < min_value:
            image_width = min_value
            dpg.set_value(self.image_width_input, self.loaded_image.width)
        return image_width

    def start(self):
        dpg.configure_item(self.open_image_button, enabled=False)
        dpg.configure_item(self.start_button, enabled=False)

        ai_images_count = dpg.get_value(self.generate_image_count)
        if ai_images_count <= 0:
            ai_images_count = 1
            dpg.set_value(self.generate_image_count, ai_images_count)

        ai_version = 2
        try:
            ai_version = int(dpg.get_value(self.ai_version_input))
        except Exception:
            dpg.set_value(self.ai_version_input, 2)

        image_width = self.get_show_image_width()
        self.AIImagerLoader.start_load(loaded_image=self.loaded_image,
                                       image_width=image_width,
                                       count=ai_images_count,
                                       version=ai_version)

        dpg.configure_item(self.open_image_button, enabled=True)
        dpg.configure_item(self.start_button, enabled=True)

    def update_width(self):
        dpg.configure_item(self.open_image_button, enabled=False)
        dpg.configure_item(self.start_button, enabled=False)
        dpg.configure_item(self.update_width_button, enabled=False)

        if self.loaded_image is not None:
            image_width = self.get_show_image_width()
            self.AIImagerLoader.set_width(image_width)

        dpg.configure_item(self.update_width_button, enabled=True)
        dpg.configure_item(self.open_image_button, enabled=True)
        dpg.configure_item(self.start_button, enabled=bool(self.loaded_image))

    @dpg_callback()
    def auto_update_width(self):
        if dpg.get_value(self.auto_update_width_checkbox):
            self.update_width()

    def try_again_errors_images(self):
        try:
            for image_viewer in self.AIImagerLoader.image_viewers_list:
                if image_viewer.is_error:
                    image_viewer.start_request()
        except Exception:
            traceback.print_exc()

    def set_download_threads_count(self):
        try:
            count = int(dpg.get_value(self.download_threads_count))
            if count <= 0:
                count = 1
                dpg.set_value(self.download_threads_count, count)
            RequestQueue.set_count(count)
        except ValueError:
            pass

    def update_threads_info_worker(self):
        while 1:
            time.sleep(1)
            working_threads = [*RequestQueue.workers.values()].count(True)
            dpg.set_value(self.threads_info_label,
                          f'Current running/working threads: {len(RequestQueue.workers)}/{working_threads} | '
                          f'Current request queue: {RequestQueue.queue.qsize()}')
            if dpg.get_value(self.auto_try_again_errors):
                self.try_again_errors_images()

    def set_show_settings(self, flag: bool):
        dpg.configure_item(self.settings_group, show=flag)

    def create(self):
        with dpg.window() as self.window:
            with dpg.table(resizable=False, header_row=False):
                dpg.add_table_column(width_fixed=True)
                dpg.add_table_column()
                dpg.add_table_column(width_stretch=False, width_fixed=True)
                dpg.add_table_column(width_stretch=False, width_fixed=True)
                dpg.add_table_column(width_stretch=False, width_fixed=True)

                with dpg.table_row():
                    self.open_image_button = dpg.add_button(
                        label='Open the image file',
                        callback=lambda *, self=self: self.open_image_file(self=self)  # TODO: fix this
                    )
                    with dpg.group():
                        self.image_path_label = dpg.add_text('')
                        with dpg.tooltip(self.image_path_label) as self.text_tooltip:
                            pass
                    with dpg.group(horizontal=True):
                        dpg.add_text('AI version:')
                        self.ai_version_input = dpg.add_input_int(default_value=2, width=25, step=0)
                    dpg.add_checkbox(label='Show settings', default_value=True, callback=lambda _, value: self.set_show_settings(value))
                    self.start_button = dpg.add_button(label='Start', enabled=False, callback=self.start)
            with dpg.group() as self.settings_group:
                with dpg.group(horizontal=True):
                    dpg.add_text('Number of generated images')
                    self.generate_image_count = dpg.add_slider_int(min_value=1, max_value=100,
                                                                   default_value=24,
                                                                   width=-1)
                with dpg.group(horizontal=True):
                    self.update_width_button = dpg.add_button(label='Update', callback=self.update_width)
                    self.auto_update_width_checkbox = dpg.add_checkbox(label='Auto', default_value=True)
                    self.choise_width = dpg.add_radio_button(self.choose_width_options,
                                                             default_value=self.choose_width_options[1],
                                                             horizontal=True,
                                                             callback=lambda *, self=self: self.auto_update_width(self=self))  # TODO: fix this
                    self.image_width_input = dpg.add_drag_int(min_value=50, max_value=10_000,
                                                              default_value=150,
                                                              width=-1,
                                                              callback=lambda *, self=self: self.auto_update_width(self=self))  # TODO: fix this
                with dpg.group(horizontal=True):
                    dpg.add_text('Number of threads of downloaders')
                    self.download_threads_count = dpg.add_slider_int(min_value=1, max_value=100,
                                                                     default_value=RequestQueue.count,
                                                                     width=-1,
                                                                     callback=self.set_download_threads_count)
                with dpg.group(horizontal=True):
                    self.threads_info_label = dpg.add_text(f'Current running/working threads: {len(RequestQueue.workers)}/{0} | '
                                                           f'Current request queue: {RequestQueue.queue.qsize()}')
                    dpg.add_button(label='Try download errors images', callback=self.try_again_errors_images)
                    self.auto_try_again_errors = dpg.add_checkbox(label='Auto', default_value=True)
            with dpg.handler_registry():
                dpg.add_key_press_handler(key=-1, callback=self.check_clipboard_paste)
            threading.Thread(target=self.update_threads_info_worker, daemon=True).start()
            self.AIImagerLoader.create()
