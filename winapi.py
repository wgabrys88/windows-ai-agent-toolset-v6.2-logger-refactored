# FILE: winapi.py

from __future__ import annotations

import ctypes
import struct
import time
import zlib
from ctypes import wintypes
from typing import Tuple

# Some Python builds have incomplete wintypes; define missing aliases defensively.
if not hasattr(wintypes, "HCURSOR"):
    wintypes.HCURSOR = wintypes.HANDLE
if not hasattr(wintypes, "HICON"):
    wintypes.HICON = wintypes.HANDLE
if not hasattr(wintypes, "HBITMAP"):
    wintypes.HBITMAP = wintypes.HANDLE
if not hasattr(wintypes, "HGDIOBJ"):
    wintypes.HGDIOBJ = wintypes.HANDLE
if not hasattr(wintypes, "HBRUSH"):
    wintypes.HBRUSH = wintypes.HANDLE
if not hasattr(wintypes, "HDC"):
    wintypes.HDC = wintypes.HANDLE
if not hasattr(wintypes, "ULONG_PTR"):
    wintypes.ULONG_PTR = ctypes.c_size_t


user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)

SM_CXSCREEN = 0
SM_CYSCREEN = 1

CURSOR_SHOWING = 0x00000001
DI_NORMAL = 0x0003

BI_RGB = 0
DIB_RGB_COLORS = 0

HALFTONE = 4
SRCCOPY = 0x00CC0020

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_WHEEL = 0x0800


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class CURSORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hCursor", wintypes.HCURSOR),
        ("ptScreenPos", POINT),
    ]


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", wintypes.HBITMAP),
        ("hbmColor", wintypes.HBITMAP),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", wintypes.ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", wintypes.ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class INPUT_I(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("ii", INPUT_I)]


# API signatures
user32.GetSystemMetrics.argtypes = [wintypes.INT]
user32.GetSystemMetrics.restype = wintypes.INT

user32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
user32.GetCursorInfo.restype = wintypes.BOOL

user32.GetIconInfo.argtypes = [wintypes.HICON, ctypes.POINTER(ICONINFO)]
user32.GetIconInfo.restype = wintypes.BOOL

user32.DrawIconEx.argtypes = [
    wintypes.HDC, wintypes.INT, wintypes.INT, wintypes.HICON,
    wintypes.INT, wintypes.INT, wintypes.UINT, wintypes.HBRUSH, wintypes.UINT
]
user32.DrawIconEx.restype = wintypes.BOOL

user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC

user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.ReleaseDC.restype = wintypes.INT

user32.SetCursorPos.argtypes = [wintypes.INT, wintypes.INT]
user32.SetCursorPos.restype = wintypes.BOOL

user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT

user32.SetProcessDpiAwarenessContext.argtypes = [wintypes.HANDLE]
user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL

gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC

gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.DeleteDC.restype = wintypes.BOOL

gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.SelectObject.restype = wintypes.HGDIOBJ

gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteObject.restype = wintypes.BOOL

gdi32.CreateDIBSection.argtypes = [
    wintypes.HDC,
    ctypes.POINTER(BITMAPINFO),
    wintypes.UINT,
    ctypes.POINTER(ctypes.c_void_p),
    wintypes.HANDLE,
    wintypes.DWORD,
]
gdi32.CreateDIBSection.restype = wintypes.HBITMAP

gdi32.StretchBlt.argtypes = [
    wintypes.HDC, wintypes.INT, wintypes.INT, wintypes.INT, wintypes.INT,
    wintypes.HDC, wintypes.INT, wintypes.INT, wintypes.INT, wintypes.INT,
    wintypes.DWORD
]
gdi32.StretchBlt.restype = wintypes.BOOL

gdi32.SetStretchBltMode.argtypes = [wintypes.HDC, wintypes.INT]
gdi32.SetStretchBltMode.restype = wintypes.INT

gdi32.SetBrushOrgEx.argtypes = [wintypes.HDC, wintypes.INT, wintypes.INT, ctypes.POINTER(POINT)]
gdi32.SetBrushOrgEx.restype = wintypes.BOOL


def init_dpi() -> None:
    user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)


def get_screen_size() -> Tuple[int, int]:
    w = int(user32.GetSystemMetrics(SM_CXSCREEN))
    h = int(user32.GetSystemMetrics(SM_CYSCREEN))
    return (w if w > 0 else 1920, h if h > 0 else 1080)


def norm_to_screen_px(xn: float, yn: float, screen_w: int, screen_h: int) -> Tuple[int, int]:
    """Convert normalized coordinates (0-1000) to pixel coords."""
    xn = max(0.0, min(1000.0, xn))
    yn = max(0.0, min(1000.0, yn))
    x = int(round((xn / 1000.0) * (screen_w - 1)))
    y = int(round((yn / 1000.0) * (screen_h - 1)))
    return x, y


def move_mouse_to_pixel(x: int, y: int) -> None:
    user32.SetCursorPos(int(x), int(y))


def _draw_cursor_on_dc(hdc_mem: int, screen_w: int, screen_h: int, dst_w: int, dst_h: int) -> None:
    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(CURSORINFO)
    if not user32.GetCursorInfo(ctypes.byref(ci)):
        return
    if not (ci.flags & CURSOR_SHOWING):
        return

    ii = ICONINFO()
    if not user32.GetIconInfo(ci.hCursor, ctypes.byref(ii)):
        return

    try:
        cur_x = int(ci.ptScreenPos.x) - int(ii.xHotspot)
        cur_y = int(ci.ptScreenPos.y) - int(ii.yHotspot)
        dx = int(round(cur_x * (dst_w / float(screen_w))))
        dy = int(round(cur_y * (dst_h / float(screen_h))))
        user32.DrawIconEx(hdc_mem, dx, dy, ci.hCursor, 0, 0, 0, None, DI_NORMAL)
    finally:
        if ii.hbmMask:
            gdi32.DeleteObject(ii.hbmMask)
        if ii.hbmColor:
            gdi32.DeleteObject(ii.hbmColor)


def _png_pack(tag: bytes, data: bytes) -> bytes:
    chunk_head = tag + data
    return struct.pack("!I", len(data)) + chunk_head + struct.pack("!I", zlib.crc32(chunk_head) & 0xFFFFFFFF)


def _rgb_to_png_bytes(rgb: bytes, width: int, height: int) -> bytes:
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)
        start = y * stride
        raw.extend(rgb[start:start + stride])

    compressor = zlib.compressobj(level=6)
    compressed = compressor.compress(bytes(raw)) + compressor.flush()

    png = bytearray()
    png.extend(b"\x89PNG\r\n\x1a\n")
    ihdr = struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png.extend(_png_pack(b"IHDR", ihdr))
    png.extend(_png_pack(b"IDAT", compressed))
    png.extend(_png_pack(b"IEND", b""))
    return bytes(png)


def capture_screenshot_png(target_w: int, target_h: int) -> Tuple[bytes, int, int]:
    """
    Capture the screen into PNG, scaled to target_w x target_h.
    Returns: (png_bytes, screen_w, screen_h)
    """
    screen_w, screen_h = get_screen_size()

    hdc_screen = user32.GetDC(None)
    if not hdc_screen:
        raise RuntimeError("GetDC failed")

    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    if not hdc_mem:
        user32.ReleaseDC(None, hdc_screen)
        raise RuntimeError("CreateCompatibleDC failed")

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = target_w
    bmi.bmiHeader.biHeight = -target_h  # top-down
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = BI_RGB
    bmi.bmiHeader.biSizeImage = 0

    bits_ptr = ctypes.c_void_p()
    hbm = gdi32.CreateDIBSection(hdc_screen, ctypes.byref(bmi), DIB_RGB_COLORS, ctypes.byref(bits_ptr), None, 0)
    if not hbm or not bits_ptr:
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(None, hdc_screen)
        raise RuntimeError("CreateDIBSection failed")

    old = gdi32.SelectObject(hdc_mem, hbm)
    gdi32.SetStretchBltMode(hdc_mem, HALFTONE)
    gdi32.SetBrushOrgEx(hdc_mem, 0, 0, None)

    ok = gdi32.StretchBlt(
        hdc_mem,
        0, 0, target_w, target_h,
        hdc_screen,
        0, 0, screen_w, screen_h,
        SRCCOPY
    )
    if not ok:
        gdi32.SelectObject(hdc_mem, old)
        gdi32.DeleteObject(hbm)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(None, hdc_screen)
        raise RuntimeError("StretchBlt failed")

    _draw_cursor_on_dc(hdc_mem, screen_w, screen_h, target_w, target_h)

    buf_size = target_w * target_h * 4
    raw = (ctypes.c_ubyte * buf_size).from_address(bits_ptr.value)
    raw_bytes = bytes(raw)

    gdi32.SelectObject(hdc_mem, old)
    gdi32.DeleteObject(hbm)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(None, hdc_screen)

    # BGRA -> RGB
    rgb = bytearray(target_w * target_h * 3)
    for i in range(target_w * target_h):
        b = raw_bytes[i * 4 + 0]
        g = raw_bytes[i * 4 + 1]
        r = raw_bytes[i * 4 + 2]
        rgb[i * 3 + 0] = r
        rgb[i * 3 + 1] = g
        rgb[i * 3 + 2] = b

    png_bytes = _rgb_to_png_bytes(bytes(rgb), target_w, target_h)
    return png_bytes, screen_w, screen_h


def _send_input(inputs) -> None:
    n = len(inputs)
    arr = (INPUT * n)(*inputs)
    sent = user32.SendInput(n, arr, ctypes.sizeof(INPUT))
    if sent != n:
        raise RuntimeError("SendInput failed")


def click_mouse() -> None:
    inputs = [
        INPUT(type=INPUT_MOUSE, ii=INPUT_I(mi=MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=MOUSEEVENTF_LEFTDOWN, time=0, dwExtraInfo=0))),
        INPUT(type=INPUT_MOUSE, ii=INPUT_I(mi=MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=MOUSEEVENTF_LEFTUP, time=0, dwExtraInfo=0))),
    ]
    _send_input(inputs)


def scroll_down(amount: int = 120) -> None:
    inputs = [
        INPUT(type=INPUT_MOUSE, ii=INPUT_I(mi=MOUSEINPUT(dx=0, dy=0, mouseData=amount, dwFlags=MOUSEEVENTF_WHEEL, time=0, dwExtraInfo=0))),
    ]
    _send_input(inputs)


def type_text(text: str) -> None:
    for ch in text:
        code = ord(ch)
        down = INPUT(type=INPUT_KEYBOARD, ii=INPUT_I(ki=KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE, time=0, dwExtraInfo=0)))
        up = INPUT(type=INPUT_KEYBOARD, ii=INPUT_I(ki=KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, time=0, dwExtraInfo=0)))
        _send_input([down, up])
        time.sleep(0.005)


_VK = {
    "enter": 0x0D,
    "tab": 0x09,
    "escape": 0x1B,
    "esc": 0x1B,
    "windows": 0x5B,
    "win": 0x5B,
    "ctrl": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "f4": 0x73,
    "c": 0x43,
    "v": 0x56,
    "t": 0x54,
    "w": 0x57,
    "f": 0x46,
    "l": 0x4C,
}


def _key_down(vk: int) -> INPUT:
    return INPUT(type=INPUT_KEYBOARD, ii=INPUT_I(ki=KEYBDINPUT(wVk=vk, wScan=0, dwFlags=0, time=0, dwExtraInfo=0)))


def _key_up(vk: int) -> INPUT:
    return INPUT(type=INPUT_KEYBOARD, ii=INPUT_I(ki=KEYBDINPUT(wVk=vk, wScan=0, dwFlags=KEYEVENTF_KEYUP, time=0, dwExtraInfo=0)))


def press_key(key: str) -> None:
    key = key.strip().lower()
    if not key:
        raise ValueError("empty key")

    parts = [p.strip() for p in key.split("+") if p.strip()]
    if not parts:
        raise ValueError("empty key parts")

    vks = []
    for p in parts:
        if p not in _VK:
            raise ValueError(f"unsupported key: {p}")
        vks.append(_VK[p])

    downs = [_key_down(vk) for vk in vks]
    ups = [_key_up(vk) for vk in reversed(vks)]
    _send_input(downs + ups)
