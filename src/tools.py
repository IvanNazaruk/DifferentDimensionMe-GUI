from __future__ import annotations

import queue
import threading
import time
import traceback
from ctypes import *
from ctypes.wintypes import *
from io import BytesIO
from typing import Callable

import dearpygui.dearpygui as dpg
from PIL import Image

import ai


class LoadedImage:
    path: str
    image: Image.Image
    width: int
    height: int
    base64: str

    def __init__(self, path: str | BytesIO):
        self.path = path
        self.image = Image.open(self.path)
        self.width = self.image.width
        self.height = self.image.height
        self.base64 = ai.get_base64_image(self.path)

    def get_height(self, width: int):
        image_height = self.height * (width / self.width)
        image_height = int(image_height)
        return image_height


def dpg_callback(sender: bool = False, app_data: bool = False, user_data: bool = False):
    def decorator(function):
        BLOCKER = False
        function_queue: list[Callable, tuple, dict] = None

        def wrapper(sender_var=None, app_data_var=None, user_data_var=None, *args, **kwargs):
            nonlocal BLOCKER
            nonlocal function_queue
            if BLOCKER:
                function_queue = [function, args, kwargs]
                return
            BLOCKER = True
            args = list(args)
            if user_data:
                args.insert(0, user_data_var)
            if app_data:
                args.insert(0, app_data_var)
            if sender:
                args.insert(0, sender_var)
            args = tuple(args)

            def run(function, args, kwargs):
                nonlocal BLOCKER
                nonlocal function_queue
                while True:
                    try:
                        function(*args, **kwargs)
                    except Exception:
                        traceback.print_exc()
                    if function_queue is None:
                        BLOCKER = False
                        return

                    function, args, kwargs = function_queue
                    function_queue = None

            threading.Thread(target=run, args=(function, args, kwargs,), daemon=True).start()

        return wrapper

    return decorator


class CallWhenDPGStarted:
    __thread = None
    STARTUP_DONE = False
    functions_queue = []

    def __new__(cls, func, *args, **kwargs):
        cls.append(func, *args, **kwargs)
        return None

    @classmethod
    def run_worker(cls):
        if cls.__thread is None:
            cls.__thread = True
            threading.Thread(target=cls._worker, daemon=True).start()

    @classmethod
    def append(cls, func, *args, **kwargs):
        cls.run_worker()
        if not cls.STARTUP_DONE:
            cls.functions_queue.append(
                [func, args, kwargs]
            )
            return
        try:
            func(*args, **kwargs)
        except Exception:
            traceback.print_exc()

    @classmethod
    def _worker(cls):
        while dpg.get_frame_count() <= 1:
            time.sleep(0.01)
        dpg.split_frame()
        cls.STARTUP_DONE = True
        for func, args, kwargs in cls.functions_queue:
            try:
                func(*args, **kwargs)
            except Exception:
                traceback.print_exc()
        del cls.functions_queue


class ViewportResizeManager:
    _STARTED = False

    _list_of_callbacks = dict()

    @classmethod
    def _setup(cls):
        dpg.set_viewport_resize_callback(cls._resize_callback)

    @staticmethod
    @dpg_callback()
    def _resize_callback():
        for function_tag in ViewportResizeManager._list_of_callbacks.keys():
            ViewportResizeManager._list_of_callbacks[function_tag]()

    @classmethod
    def add_callback(cls, function, tag: str | int = None) -> str | int:
        if not cls._STARTED:
            cls._STARTED = True
            cls._setup()
        if tag is None:
            tag: int = dpg.generate_uuid()
        cls._list_of_callbacks[tag] = function
        return tag

    @classmethod
    def remove_callback(cls, tag):
        del cls._list_of_callbacks[tag]


class RequestQueue:
    count = 8
    queue = queue.Queue()

    workers = {}

    @classmethod
    def clear(cls):
        cls.queue.queue.clear()

    @classmethod
    def append(cls,
               loaded_image: LoadedImage,
               version: int,
               start_callback: Callable = None,
               error_callback: Callable[[str], None] = None,
               done_callback: Callable[[Image.Image], None] = None,
               ):
        cls.queue.put(
            (loaded_image, version, start_callback, error_callback, done_callback)
        )

    @classmethod
    def update_workers(cls):
        for id in range(1, cls.count + 1):
            if id not in cls.workers:
                cls.workers[id] = False
                threading.Thread(
                    target=cls.worker,
                    args=(id,),
                    daemon=True
                ).start()

    @classmethod
    def set_count(cls, count: int):
        if count <= 0:
            count = 1
        cls.count = count
        cls.update_workers()

    @classmethod
    def worker(cls, id: int):
        loaded_image, version, start_callback, error_callback, done_callback = (None, 2, None, None, None)
        while 1:
            cls.workers[id] = False
            try:
                loaded_image, version, start_callback, error_callback, done_callback = cls.queue.get(timeout=1)
                cls.workers[id] = True
                loaded_image: LoadedImage

                if start_callback:
                    start_callback()

                url = ai.get_ai_image(loaded_image.base64, version)
                image, filepath = ai.download_image(url)

                if done_callback:
                    done_callback(image, filepath)
            except queue.Empty:
                pass
            except Exception as e:
                if type(e) != KeyError:
                    traceback.print_exc()
                if error_callback:
                    try:
                        error_callback(str(e))
                    except Exception:
                        traceback.print_exc()
            finally:
                if id > cls.count:
                    break
        del cls.workers[id]
        cls.update_workers()


RequestQueue.update_workers()

HGLOBAL = HANDLE
SIZE_T = c_size_t
GHND = 0x0042
GMEM_SHARE = 0x2000

GlobalAlloc = windll.kernel32.GlobalAlloc
GlobalAlloc.restype = HGLOBAL
GlobalAlloc.argtypes = [UINT, SIZE_T]

GlobalLock = windll.kernel32.GlobalLock
GlobalLock.restype = LPVOID
GlobalLock.argtypes = [HGLOBAL]

GlobalUnlock = windll.kernel32.GlobalUnlock
GlobalUnlock.restype = BOOL
GlobalUnlock.argtypes = [HGLOBAL]

CF_DIB = 8

OpenClipboard = windll.user32.OpenClipboard
OpenClipboard.restype = BOOL
OpenClipboard.argtypes = [HWND]

EmptyClipboard = windll.user32.EmptyClipboard
EmptyClipboard.restype = BOOL
EmptyClipboard.argtypes = None

SetClipboardData = windll.user32.SetClipboardData
SetClipboardData.restype = HANDLE
SetClipboardData.argtypes = [UINT, HANDLE]

CloseClipboard = windll.user32.CloseClipboard
CloseClipboard.restype = BOOL
CloseClipboard.argtypes = None


def image_to_clipboard(image: Image.Image):
    output = BytesIO()
    image.convert("RGB").save(output, "BMP")
    data = output.getvalue()[14:]
    output.close()

    hData = GlobalAlloc(GHND | GMEM_SHARE, len(data))
    pData = GlobalLock(hData)
    memmove(pData, data, len(data))
    GlobalUnlock(hData)

    OpenClipboard(None)
    EmptyClipboard()
    SetClipboardData(CF_DIB, pData)
    CloseClipboard()
