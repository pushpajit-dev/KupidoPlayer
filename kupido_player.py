# kupido_player.py
import sys
import os
import traceback
import json
import threading
import time
import datetime
import subprocess
import yt_dlp
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageDraw, ImageTk, ImageFont
import pystray
from pystray import MenuItem as item
import keyboard
import requests
import re
from pathlib import Path
import win32gui
import win32con
import win32api
import ctypes
import io
import tempfile
import webbrowser
import queue
import base64
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import shutil
import hashlib
from mutagen.mp4 import MP4
from mutagen.mp3 import MP3
import pickle
import uuid
from collections import deque
import atexit

# ==================== Optional VLC import ====================
try:
    import vlc
    VLC_AVAILABLE = True
except ImportError:
    VLC_AVAILABLE = False
    vlc = None

# ==================== Kupido branding ====================
APP_NAME = "kupido"
APP_VERSION = "4.5.0"
APP_ICON_URL = "https://i.ibb.co/V0PNsR5L/kupido.png"
DEV_INFO = {
    "name": "Aivory.space",
    "email": "aivorygen@gmail.com",
    "youtube": "https://www.youtube.com/@AivoryGen",
    "website": "https://aivory.space",
}
DOCS_URL = "https://docs.google.com/document/d/e/2PACX-1vSba3y_XxpZZgAA4XHy9qxavHoJ2zncXfOuOAYi2raKYF2NrTT0zsnnwwjhphcVcjMJMeXdDscxPbCd/pub"

# ==================== Colors & Theme (Modern Electric Blue & Dark Navy) ====================
COLORS = {
    "bg_dark": "#0B0E14",
    "bg_medium": "#161B26",
    "bg_light": "#1E2536",
    "surface": "#161D2C",
    "border": "#2D3748",
    "accent": "#2563EB",
    "accent_hover": "#3B82F6",
    "accent_light": "#60A5FA",
    "success": "#2563EB",
    "warning": "#3B82F6",
    "error": "#EF4444",
    "text_primary": "#FFFFFF",
    "text_secondary": "#94A3B8",
}

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# resource_path defined at module top

def set_window_icon(window):
    """Ensure Kupido brand icon is displayed on the window title bar (replaces default OS / CTkToplevel icon)."""
    ico_p = resource_path("kupido.ico")
    if os.path.exists(ico_p):
        try:
            window.iconbitmap(ico_p)
            window._iconbitmap_method_called = True
        except Exception:
            pass
        if sys.platform.startswith("win"):
            def _apply_win32():
                if not (hasattr(window, "winfo_exists") and window.winfo_exists()):
                    return
                try:
                    import ctypes
                    user32 = ctypes.windll.user32
                    wid = window.winfo_id()
                    hwnd = user32.GetParent(wid) or wid
                    hicon_sm = user32.LoadImageW(None, ico_p, 1, 16, 16, 0x00000010)
                    hicon_lg = user32.LoadImageW(None, ico_p, 1, 32, 32, 0x00000010)
                    if hicon_sm:
                        user32.SendMessageW(hwnd, 0x80, 0, hicon_sm)
                    if hicon_lg:
                        user32.SendMessageW(hwnd, 0x80, 1, hicon_lg)
                except Exception:
                    pass
            _apply_win32()
            try:
                window.after(80, _apply_win32)
                window.after(250, _apply_win32)
                window.after(500, _apply_win32)
            except Exception:
                pass

# Monkey-patch CTkToplevel & CTk so every dialog or secondary window automatically uses kupido.ico
_orig_ctk_toplevel_init = ctk.CTkToplevel.__init__
def _patched_ctk_toplevel_init(self, *args, **kwargs):
    _orig_ctk_toplevel_init(self, *args, **kwargs)
    set_window_icon(self)

ctk.CTkToplevel.__init__ = _patched_ctk_toplevel_init

def _patched_windows_set_titlebar_icon(self):
    set_window_icon(self)

ctk.CTkToplevel._windows_set_titlebar_icon = _patched_windows_set_titlebar_icon
ctk.CTk._windows_set_titlebar_icon = _patched_windows_set_titlebar_icon

# Language support
LANGUAGES = {
    "English": {"code": "en", "script": "latin", "voice": "en-US", "whisper": "en", "display": "English"},
    "Hindi": {"code": "hi", "script": "devanagari", "voice": "hi-IN", "whisper": "hi", "display": "हिन्दी"},
    "Bengali": {"code": "bn", "script": "bengali", "voice": "bn-IN", "whisper": "bn", "display": "বাংলা"},
    "Tamil": {"code": "ta", "script": "tamil", "voice": "ta-IN", "whisper": "ta", "display": "தமிழ்"},
    "Japanese": {"code": "ja", "script": "japanese", "voice": "ja-JP", "whisper": "ja", "display": "日本語"},
    "Chinese": {"code": "zh", "script": "chinese", "voice": "zh-CN", "whisper": "zh", "display": "中文"},
}

WHISPER_CHECKSUMS = {
    "tiny": "65147644a518d12f04e32d6f3b26facc3f8dd46e5390956a9424a650c0ce22b9",
    "base": "ed3a0b6b1c0edf879ad9b11b1af5a0e6ab5db9205f891f668f8b0e6c6326e34e",
    "small": "9ecf779972d90ba49c06d9683d12bf128fd161cbc0d83b6c1ab00c717db64e6a",
    "medium": "345ae4da62f9b3d59415adc60127b97c714f32e89e936602e85993674d08dcb1",
}

# ==================== Fast File & Spec-based Capability Flags (Instant Startup) ====================
import importlib.util

WHISPER_AVAILABLE = importlib.util.find_spec("whisper") is not None
TORCH_AVAILABLE = importlib.util.find_spec("torch") is not None
TRANSFORMERS_AVAILABLE = importlib.util.find_spec("transformers") is not None
LLAMA_CPP_AVAILABLE = importlib.util.find_spec("llama_cpp") is not None
TTS_AVAILABLE = importlib.util.find_spec("pyttsx3") is not None
GTTS_AVAILABLE = importlib.util.find_spec("gtts") is not None
REPORTLAB_AVAILABLE = importlib.util.find_spec("reportlab") is not None
FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None

def resource_path(relative_path):
    """Get absolute path to resource, checking local script folder and parent folders."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(base_path, relative_path)
    if os.path.exists(candidate):
        return candidate
    parent_candidate = os.path.join(os.path.dirname(base_path), relative_path)
    if os.path.exists(parent_candidate):
        return parent_candidate
    root_candidate = os.path.join(os.path.dirname(os.path.dirname(base_path)), relative_path)
    if os.path.exists(root_candidate):
        return root_candidate
    return os.path.join(os.path.abspath("."), relative_path)



def safe_get_clipboard(root=None):
    """Retrieve clipboard text reliably across Windows API and Tkinter."""
    if root:
        try:
            val = root.clipboard_get()
            if val and val.strip():
                return val.strip()
        except Exception:
            pass
    try:
        import ctypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        user32.OpenClipboard.argtypes = [ctypes.c_void_p]
        user32.OpenClipboard.restype = ctypes.c_bool
        user32.CloseClipboard.restype = ctypes.c_bool
        user32.GetClipboardData.argtypes = [ctypes.c_uint]
        user32.GetClipboardData.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_wchar_p
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]

        if user32.OpenClipboard(None):
            try:
                h = user32.GetClipboardData(13)  # CF_UNICODETEXT
                if h:
                    ptr = kernel32.GlobalLock(h)
                    if ptr:
                        val = str(ptr)
                        kernel32.GlobalUnlock(h)
                        if val and val.strip():
                            return val.strip()
            finally:
                user32.CloseClipboard()
    except Exception:
        pass
    return ""


def safe_set_clipboard(text, root=None):
    """Set clipboard text reliably across Tkinter and Windows API."""
    if not text:
        return
    if root:
        try:
            root.clipboard_clear()
            root.clipboard_append(text)
        except Exception:
            pass
    try:
        import ctypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        user32.OpenClipboard.argtypes = [ctypes.c_void_p]
        user32.OpenClipboard.restype = ctypes.c_bool
        user32.CloseClipboard.restype = ctypes.c_bool
        user32.EmptyClipboard.restype = ctypes.c_bool
        user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
        user32.SetClipboardData.restype = ctypes.c_void_p
        kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]

        if user32.OpenClipboard(None):
            try:
                user32.EmptyClipboard()
                text_bytes = (text + "\0").encode("utf-16le")
                GMEM_MOVEABLE = 0x0002
                h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(text_bytes))
                if h:
                    ptr = kernel32.GlobalLock(h)
                    ctypes.memmove(ptr, text_bytes, len(text_bytes))
                    kernel32.GlobalUnlock(h)
                    user32.SetClipboardData(13, h)
            finally:
                user32.CloseClipboard()
    except Exception:
        pass


class IconFactory:
    """Loads crisp icons from SVG assets, pre-rendered PNGs, Kupido branding, or vector fallbacks."""
    _cache = {}
    _asset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    _png_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "png")

    SVG_MAP = {
        "backward": "backward.png",
        "-10s": "backward.png",
        "rewind": "backward.png",
        "forward": "forward.png",
        "+10s": "forward.png",
        "copy": "copy.png",
        "paste": "copy.png",
        "download": "download.png",
        "dl": "download.png",
        "float": "float player.png",
        "float player": "float player.png",
        "pip": "float player.png",
        "mini": "float player.png",
        "folder": "folder.png",
        "browse": "folder.png",
        "open": "folder.png",
        "fullscreen": "full screen.png",
        "full screen": "full screen.png",
        "fs": "full screen.png",
        "loop": "loop.png",
        "repeat": "loop.png",
        "pause": "pause.png",
        "play": "play.png",
        "transcribe": "transcription icon.png",
        "transcription": "transcription icon.png",
        "transcription icon": "transcription icon.png",
        "volume": "volume-up.png",
        "volume-up": "volume-up.png",
        "volume_up": "volume-up.png",
        "volume-down": "volume-down.png",
        "volume_down": "volume-down.png",
        "mute": "volume-down.png",
        "unmute": "volume-up.png",
    }

    @classmethod
    def _load_asset_image(cls, name, size):
        name_lower = name.lower()
        if name_lower in ("backward", "-10s", "rewind"):
            # Horizontal mirror of the forward icon as requested by user
            fwd_img = cls._load_asset_image("forward", size)
            if fwd_img is not None:
                from PIL import ImageOps
                return ImageOps.mirror(fwd_img)

        if name_lower in ("kupido", "logo"):
            logo_path = resource_path("kupido.png")
            if os.path.exists(logo_path):
                try:
                    return Image.open(logo_path).convert("RGBA").resize(size, Image.Resampling.LANCZOS)
                except Exception:
                    pass

        png_filename = cls.SVG_MAP.get(name_lower)
        if png_filename:
            # Check cached png first
            p_png = os.path.join(cls._png_dir, png_filename)
            if os.path.exists(p_png):
                try:
                    return Image.open(p_png).convert("RGBA").resize(size, Image.Resampling.LANCZOS)
                except Exception:
                    pass

            # Try direct SVG rendering via resvg_py
            svg_filename = png_filename.replace(".png", ".svg")
            p_svg = os.path.join(cls._asset_dir, svg_filename)
            if os.path.exists(p_svg):
                try:
                    import resvg_py
                    with open(p_svg, "r", encoding="utf-8") as fh:
                        raw = fh.read()
                    png_bytes = resvg_py.svg_to_bytes(raw)
                    return Image.open(io.BytesIO(png_bytes)).convert("RGBA").resize(size, Image.Resampling.LANCZOS)
                except Exception:
                    pass
        return None

    @classmethod
    def get(cls, name, size=(18, 18), color="white"):
        key = (name, size, color)
        if key in cls._cache:
            return cls._cache[key]

        # 1. Try loading from assets (SVG/PNG/Brand logo)
        loaded = cls._load_asset_image(name, size)
        if loaded is not None:
            ctk_img = ctk.CTkImage(light_image=loaded, dark_image=loaded, size=size)
            cls._cache[key] = ctk_img
            return ctk_img

        # 2. Vector fallback drawing on PIL canvas
        canvas_size = (48, 48)
        img = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        c = color

        if name == "play":
            d.polygon([(16, 12), (16, 36), (38, 24)], fill=c)
        elif name == "pause":
            d.rounded_rectangle([15, 12, 21, 36], radius=2, fill=c)
            d.rounded_rectangle([27, 12, 33, 36], radius=2, fill=c)
        elif name == "stop":
            d.rounded_rectangle([14, 14, 34, 34], radius=3, fill=c)
        elif name == "search":
            d.ellipse([12, 12, 28, 28], outline=c, width=3)
            d.line([(25, 25), (36, 36)], fill=c, width=4)
        elif name in ("paste", "copy"):
            d.rounded_rectangle([14, 16, 34, 38], radius=3, outline=c, width=3)
            d.rounded_rectangle([18, 10, 30, 18], radius=2, fill=c)
        elif name in ("download", "dl"):
            d.line([(24, 12), (24, 28)], fill=c, width=3)
            d.polygon([(18, 26), (30, 26), (24, 34)], fill=c)
            d.line([(14, 38), (34, 38)], fill=c, width=3)
        elif name in ("pip", "mini", "float", "float player"):
            d.rounded_rectangle([10, 14, 38, 34], radius=3, outline=c, width=3)
            d.rounded_rectangle([24, 22, 34, 30], radius=2, fill=c)
        elif name in ("loop", "repeat"):
            d.arc([14, 14, 34, 34], start=45, end=315, fill=c, width=3)
            d.polygon([(30, 10), (36, 17), (28, 18)], fill=c)
        elif name in ("fullscreen", "full screen", "fs"):
            d.line([(12, 18), (12, 12), (18, 12)], fill=c, width=3)
            d.line([(36, 18), (36, 12), (30, 12)], fill=c, width=3)
            d.line([(12, 30), (12, 36), (18, 36)], fill=c, width=3)
            d.line([(36, 30), (36, 36), (30, 36)], fill=c, width=3)
        elif name == "close":
            d.line([(14, 14), (34, 34)], fill=c, width=3)
            d.line([(34, 14), (14, 34)], fill=c, width=3)
        elif name in ("volume", "volume-up", "unmute"):
            d.polygon([(12, 20), (18, 20), (26, 14), (26, 34), (18, 28), (12, 28)], fill=c)
            d.arc([22, 16, 34, 32], start=-50, end=50, fill=c, width=3)
        elif name in ("mute", "volume-down"):
            d.polygon([(12, 20), (18, 20), (26, 14), (26, 34), (18, 28), (12, 28)], fill=c)
            d.line([(14, 14), (34, 34)], fill="#EF4444", width=3)
        elif name in ("folder", "browse", "open"):
            d.polygon([(12, 16), (20, 16), (24, 20), (36, 20), (36, 34), (12, 34)], outline=c, width=3)
        elif name == "backward":
            d.polygon([(26, 14), (14, 24), (26, 34)], fill=c)
            d.polygon([(38, 14), (26, 24), (38, 34)], fill=c)
        elif name == "forward":
            d.polygon([(12, 14), (24, 24), (12, 34)], fill=c)
            d.polygon([(24, 14), (36, 24), (24, 34)], fill=c)
        else:
            d.rounded_rectangle([14, 14, 34, 34], radius=3, outline=c, width=3)

        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=size)
        cls._cache[key] = ctk_img
        return ctk_img


class SplashScreen(tk.Toplevel):
    """Clean modern startup splash showing only the Kupido banner graphic and sleek edge-to-edge progress loading bar."""
    def __init__(self, master=None):
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=COLORS["bg_dark"])

        w, h = 600, 206
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        main = tk.Frame(self, bg=COLORS["bg_dark"], bd=0)
        main.pack(fill=tk.BOTH, expand=True)

        self.banner_image = None
        for p in ["kupido_banner.png", "kupido.png"]:
            image_path = resource_path(p)
            if os.path.exists(image_path):
                try:
                    pil_image = Image.open(image_path).resize((600, 198), Image.Resampling.LANCZOS)
                    self.banner_image = ImageTk.PhotoImage(pil_image, master=self)
                    break
                except Exception:
                    pass

        if self.banner_image:
            self.banner_label = tk.Label(main, image=self.banner_image, bg=COLORS["bg_dark"], bd=0)
            self.banner_label.image = self.banner_image
            self.banner_label.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Loading bar: spans entire left to right width with zero margin
        self.canvas_width = 600
        self.bar_height = 8
        self.canvas = tk.Canvas(
            main, height=self.bar_height, width=self.canvas_width,
            bg=COLORS["bg_dark"], highlightthickness=0, bd=0
        )
        self.canvas.pack(fill=tk.X, side=tk.BOTTOM, padx=0, pady=0)

        self.gradient_colors = self._make_gradient(COLORS["accent"], COLORS["accent_light"], 100)
        self.progress_value = 0

        self.deiconify()
        self.lift()
        self.update_idletasks()

    def _make_gradient(self, color1, color2, steps=100):
        def hex_to_rgb(h):
            h = h.lstrip('#')
            return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        def rgb_to_hex(rgb):
            return '#{:02x}{:02x}{:02x}'.format(*rgb)
        rgb1 = hex_to_rgb(color1)
        rgb2 = hex_to_rgb(color2)
        colors = []
        for i in range(steps):
            ratio = i / max(1, steps - 1)
            r = int(rgb1[0] + (rgb2[0] - rgb1[0]) * ratio)
            g = int(rgb1[1] + (rgb2[1] - rgb1[1]) * ratio)
            b = int(rgb1[2] + (rgb2[2] - rgb1[2]) * ratio)
            colors.append(rgb_to_hex((r, g, b)))
        return colors

    def update_progress(self, percent, message=""):
        try:
            if not self.winfo_exists():
                return
            self.progress_value = percent
            width = int((percent / 100.0) * self.canvas_width)
            if hasattr(self, "canvas") and self.canvas:
                self.canvas.delete("all")
                if width > 0:
                    for i in range(width):
                        color = self.gradient_colors[min(99, int((i / max(1, width)) * 99))]
                        self.canvas.create_line(i, 0, i, self.bar_height, fill=color, width=1)
            self.update_idletasks()
            self.update()
        except Exception:
            pass

    def close(self):
        try:
            self.destroy()
        except Exception:
            pass


class ToolManager:
    """Manages portable ffmpeg/ffprobe binaries, yt-dlp auto-updates, and runtime health."""
    BIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
    _cached_ffmpeg = None
    _cached_ffprobe = None

    @classmethod
    def init_env(cls):
        try:
            os.makedirs(cls.BIN_DIR, exist_ok=True)
            ff = cls.get_ffmpeg_path()
            if ff:
                ff_dir = os.path.dirname(ff)
                if ff_dir not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = ff_dir + os.pathsep + os.environ.get("PATH", "")
            if cls.BIN_DIR not in os.environ.get("PATH", ""):
                os.environ["PATH"] = cls.BIN_DIR + os.pathsep + os.environ.get("PATH", "")
        except Exception as e:
            print(f"ToolManager init notice: {e}")

    @classmethod
    def get_ffmpeg_path(cls):
        if cls._cached_ffmpeg and os.path.exists(cls._cached_ffmpeg):
            return cls._cached_ffmpeg

        # 1. Check shutil.which (instant)
        w = shutil.which("ffmpeg")
        if w and os.path.exists(w):
            cls._cached_ffmpeg = w
            return w

        # 2. Check local bin/
        local_exe = os.path.join(cls.BIN_DIR, "ffmpeg.exe")
        if os.path.exists(local_exe):
            cls._cached_ffmpeg = local_exe
            return local_exe

        # 3. Check known WinGet / Gyan FFmpeg paths
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            gyan_path = os.path.join(
                local_app_data,
                r"Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin\ffmpeg.exe"
            )
            if os.path.exists(gyan_path):
                cls._cached_ffmpeg = gyan_path
                return gyan_path

        # 4. Check common installation directories
        common_dirs = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        ]
        for c in common_dirs:
            if os.path.exists(c):
                cls._cached_ffmpeg = c
                return c
        return None

    @classmethod
    def get_ffprobe_path(cls):
        if cls._cached_ffprobe and os.path.exists(cls._cached_ffprobe):
            return cls._cached_ffprobe

        # 1. Check shutil.which
        w = shutil.which("ffprobe")
        if w and os.path.exists(w):
            cls._cached_ffprobe = w
            return w

        # 2. Check same directory as ffmpeg
        ff = cls.get_ffmpeg_path()
        if ff:
            candidate = os.path.join(os.path.dirname(ff), "ffprobe.exe")
            if os.path.exists(candidate):
                cls._cached_ffprobe = candidate
                return candidate

        # 3. Check local bin/
        local_exe = os.path.join(cls.BIN_DIR, "ffprobe.exe")
        if os.path.exists(local_exe):
            cls._cached_ffprobe = local_exe
            return local_exe

        return None

    @classmethod
    def is_ffmpeg_available(cls):
        return cls.get_ffmpeg_path() is not None

    @classmethod
    def get_ytdlp_version(cls):
        try:
            return yt_dlp.version.__version__
        except:
            return "Unknown"

    @classmethod
    def get_base_ydl_opts(cls, extra_headers=None):
        opts = {
            "quiet": True,
            "no_warnings": True,
            "nocheckcertificate": True,
            "ignoreerrors": False,
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "ios", "web"],
                }
            },
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
                "Sec-Fetch-Mode": "navigate",
            },
        }
        if extra_headers:
            opts["http_headers"].update(extra_headers)
        ff = cls.get_ffmpeg_path()
        if ff:
            opts["ffmpeg_location"] = os.path.dirname(ff)
        return opts

    @classmethod
    def check_and_update_ytdlp(cls, callback=None):
        """Update yt-dlp via pip install in a background thread."""
        def _worker():
            try:
                if callback:
                    callback(15, "Checking for yt-dlp release...")
                headers = {"User-Agent": "Mozilla/5.0"}
                latest_tag = None
                try:
                    resp = requests.get("https://pypi.org/pypi/yt-dlp/json", headers=headers, timeout=8)
                    if resp.status_code == 200:
                        latest_tag = resp.json().get("info", {}).get("version", "")
                except:
                    pass

                current_ver = cls.get_ytdlp_version()
                if callback:
                    callback(40, f"Installed: {current_ver} | Latest: {latest_tag or 'online'}")

                if callback:
                    callback(60, "Updating yt-dlp package...")
                cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if proc.returncode == 0:
                    try:
                        import importlib
                        importlib.reload(yt_dlp)
                    except:
                        pass
                    new_ver = cls.get_ytdlp_version()
                    if callback:
                        callback(100, f"yt-dlp updated to {new_ver}!")
                    return True, f"Updated to {new_ver}"
                else:
                    err = proc.stderr.strip() or proc.stdout.strip()
                    if callback:
                        callback(0, f"Update notice: {err[:60]}")
                    return False, err
            except Exception as e:
                if callback:
                    callback(0, f"Error updating yt-dlp: {e}")
                return False, str(e)

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        return t

    @classmethod
    def get_runtime_health(cls, settings=None):
        """Fast file/spec-based runtime health status without heavy imports or network calls."""
        health = {}
        health["python"] = {"ok": True, "info": sys.version.split()[0]}
        health["vlc"] = {"ok": bool(globals().get("VLC_AVAILABLE", False)), "info": "VLC Engine Active" if globals().get("VLC_AVAILABLE", False) else "Not Available"}
        
        ff = cls.get_ffmpeg_path()
        health["ffmpeg"] = {"ok": ff is not None, "info": "Installed" if ff else "Missing"}
        health["ytdlp"] = {"ok": True, "info": f"v{cls.get_ytdlp_version()}"}
        
        torch_ok = importlib.util.find_spec("torch") is not None
        health["torch"] = {"ok": torch_ok, "info": "Installed" if torch_ok else "Missing"}
        
        whisper_ok = importlib.util.find_spec("whisper") is not None
        whisper_info = "Installed" if whisper_ok else "Missing"
        
        models_path = settings.models_path if settings and hasattr(settings, "models_path") else os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
        if not os.path.exists(models_path):
            alt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
            if os.path.exists(alt_path):
                models_path = alt_path
        if os.path.exists(models_path):
            models_found = [m for m in ["tiny", "base", "small", "medium"] if os.path.exists(os.path.join(models_path, f"{m}.pt"))]
            if models_found:
                whisper_info = f"Ready ({len(models_found)} weights)"
        health["whisper"] = {"ok": whisper_ok, "info": whisper_info}
        return health

ToolManager.init_env()


class AdBlocker:
    """Blocks YouTube ads via hosts file modification"""

    def __init__(self):
        self.hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
        self.ad_domains = [
            "0.0.0.0 doubleclick.net",
            "0.0.0.0 googleads.g.doubleclick.net",
            "0.0.0.0 pagead2.googlesyndication.com",
            "0.0.0.0 youtubeadss.github.io",
            "0.0.0.0 s.youtube.com",
            "0.0.0.0 ad.youtube.com",
            "0.0.0.0 www.youtube.com/pagead",
            "0.0.0.0 googleads.g.doubleclick.net",
            "0.0.0.0 static.doubleclick.net",
            "0.0.0.0 securepubads.g.doubleclick.net",
        ]

    def enable_adblock(self):
        try:
            if not self.is_admin():
                return False
            with open(self.hosts_path, "a") as f:
                f.write("\n# YouTube Ad Blocking\n")
                for domain in self.ad_domains:
                    f.write(f"{domain}\n")
            return True
        except:
            return False

    def disable_adblock(self):
        try:
            if not self.is_admin():
                return False
            with open(self.hosts_path, "r") as f:
                lines = f.readlines()
            with open(self.hosts_path, "w") as f:
                in_adblock = False
                for line in lines:
                    if "# YouTube Ad Blocking" in line:
                        in_adblock = True
                        continue
                    if in_adblock and line.strip() == "":
                        in_adblock = False
                        continue
                    if not in_adblock:
                        f.write(line)
            return True
        except:
            return False

    def is_admin(self):
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False


class Settings:
    """Application settings manager with model folder path"""

    def __init__(self):
        self.settings_file = "kupido_settings.json"
        self.download_path = os.path.expanduser("~/Downloads/kupido")
        self.cache_path = os.path.join(self.download_path, "cache")
        # Default models folder: same as installation directory/models
        self.models_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "models"
        )
        self.transcription_model = "whisper"
        self.tts_engine = "pyttsx3"
        self.auto_load_subs = True
        self.subtitle_lang = "en"
        self.default_quality = "best"
        self.network_caching = 300
        self.offline_cache_enabled = True
        self.models_downloaded = {"whisper": False, "tinyllama": False, "llama3": False}
        self.hotkeys = {
            "play_pause": "ctrl+shift+p",
            "forward": "ctrl+shift+right",
            "backward": "ctrl+shift+left",
            "mute": "ctrl+shift+m",
            "unmute": "ctrl+shift+u",
            "hover": "ctrl+shift+v",
            "hide": "ctrl+shift+h",
            "show": "ctrl+shift+s",
            "download": "ctrl+shift+d",
            "subtitles": "ctrl+shift+t",
            "transcribe": "ctrl+shift+g",
            "kill": "ctrl+shift+q",
            "fullscreen": "ctrl+shift+f",
        }
        self.load()
        # Ensure folders exist
        os.makedirs(self.download_path, exist_ok=True)
        os.makedirs(self.cache_path, exist_ok=True)
        os.makedirs(self.models_path, exist_ok=True)

    def load(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, "r") as f:
                    data = json.load(f)
                    for key, value in data.items():
                        if hasattr(self, key):
                            setattr(self, key, value)
        except:
            pass

    def save(self):
        try:
            with open(self.settings_file, "w") as f:
                json.dump(
                    {
                        "download_path": self.download_path,
                        "cache_path": self.cache_path,
                        "models_path": self.models_path,
                        "transcription_model": self.transcription_model,
                        "tts_engine": self.tts_engine,
                        "auto_load_subs": self.auto_load_subs,
                        "subtitle_lang": self.subtitle_lang,
                        "default_quality": self.default_quality,
                        "network_caching": self.network_caching,
                        "offline_cache_enabled": self.offline_cache_enabled,
                        "models_downloaded": self.models_downloaded,
                        "hotkeys": self.hotkeys,
                    },
                    f,
                    indent=2,
                )
        except:
            pass


class TextToSpeech:
    """Text to speech engine with multiple language support"""

    def __init__(self):
        self.engine = None
        self.gtts_available = GTTS_AVAILABLE
        self.pyttsx3_available = TTS_AVAILABLE
        self.current_engine = (
            "pyttsx3"
            if self.pyttsx3_available
            else "gtts" if self.gtts_available else None
        )
        self.voices = []
        self.voice_map = {}

        if self.pyttsx3_available:
            try:
                self.engine = pyttsx3.init()
                self.voices = self.engine.getProperty("voices")
                for voice in self.voices:
                    for lang_name, lang_data in LANGUAGES.items():
                        if (
                            lang_data["voice"] in voice.id
                            or lang_data["voice"] in voice.name
                        ):
                            self.voice_map[lang_data["code"]] = voice.id
                            break
            except:
                self.pyttsx3_available = False

        print(f"TTS: pyttsx3={self.pyttsx3_available}, gTTS={self.gtts_available}")

    def speak(self, text, lang_code="en", voice=None):
        if not text:
            return False

        try:
            if self.current_engine == "pyttsx3" and self.pyttsx3_available:
                return self._speak_pyttsx3(text, lang_code, voice)
            elif self.current_engine == "gtts" and self.gtts_available:
                return self._speak_gtts(text, lang_code)
        except Exception as e:
            print(f"TTS error: {e}")
        return False

    def _speak_pyttsx3(self, text, lang_code, voice=None):
        if not self.engine:
            self.engine = pyttsx3.init()
        if voice and voice in [v.id for v in self.voices]:
            self.engine.setProperty("voice", voice)
        elif lang_code in self.voice_map:
            self.engine.setProperty("voice", self.voice_map[lang_code])
        self.engine.say(text)
        self.engine.runAndWait()
        return True

    def _speak_gtts(self, text, lang_code):
        try:
            import pygame
            tts = gTTS(text=text, lang=lang_code.split("-")[0], slow=False)
            temp = os.path.join(tempfile.gettempdir(), f"tts_{time.time()}.mp3")
            tts.save(temp)
            pygame.mixer.init()
            pygame.mixer.music.load(temp)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            pygame.mixer.quit()
            os.remove(temp)
            return True
        except:
            return False

    def set_engine(self, engine):
        if engine == "pyttsx3" and self.pyttsx3_available:
            self.current_engine = "pyttsx3"
            return True
        elif engine == "gtts" and self.gtts_available:
            self.current_engine = "gtts"
            return True
        return False


class ModelDownloader:
    """Handles downloading of ML models with progress tracking (atomic writes)"""

    MODEL_URLS = {
        "whisper_tiny": "https://openaipublic.azureedge.net/main/whisper/models/65147644a518d12f04e32d6f3b26facc3f8dd46e5390956a9424a650c0ce22b9/tiny.pt",
        "whisper_base": "https://openaipublic.azureedge.net/main/whisper/models/ed3a0b6b1c0edf879ad9b11b1af5a0e6ab5db9205f891f668f8b0e6c6326e34e/base.pt",
        "whisper_small": "https://openaipublic.azureedge.net/main/whisper/models/9ecf779972d90ba49c06d9683d12bf128fd161cbc0d83b6c1ab00c717db64e6a/small.pt",
        "whisper_medium": "https://openaipublic.azureedge.net/main/whisper/models/345ae4da62f9b3d59415adc60127b97c714f32e89e936602e85993674d08dcb1/medium.pt",
        "tinyllama": "https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
        "llama3_8b": "https://huggingface.co/bartowski/Meta-Llama-3-8B-Instruct-GGUF/resolve/main/Meta-Llama-3-8B-Instruct-Q5_K_M.gguf",
    }

    @staticmethod
    def check_model_exists(models_path, model_name):
        if model_name == "whisper_tiny":
            path = os.path.join(models_path, "tiny.pt")
        elif model_name == "whisper_base":
            path = os.path.join(models_path, "base.pt")
        elif model_name == "whisper_small":
            path = os.path.join(models_path, "small.pt")
        elif model_name == "whisper_medium":
            path = os.path.join(models_path, "medium.pt")
        elif model_name == "tinyllama":
            path = os.path.join(models_path, "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf")
        elif model_name == "llama3_8b":
            path = os.path.join(models_path, "Meta-Llama-3-8B-Instruct-Q5_K_M.gguf")
        else:
            return False
        return os.path.exists(path)

    @staticmethod
    def download_model(model_name, save_path, progress_callback=None):
        """Download with atomic write: temp file then rename to avoid corruption"""
        url = ModelDownloader.MODEL_URLS.get(model_name)
        if not url:
            return False

        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        # Use a temporary file
        temp_path = save_path + ".tmp"
        max_retries = 3
        for attempt in range(max_retries):
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                response = requests.get(url, stream=True, timeout=30, headers=headers)
                response.raise_for_status()
                total_size = int(response.headers.get("content-length", 0))

                with open(temp_path, "wb") as f:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback and total_size > 0:
                                progress = (downloaded / total_size) * 100
                                progress_callback(
                                    progress,
                                    f"Downloading {model_name}: {progress:.1f}%",
                                )
                # Download completed successfully - verify checksum if available
                model_base = os.path.basename(save_path).replace(".pt", "")
                if model_base in WHISPER_CHECKSUMS:
                    with open(temp_path, "rb") as cf:
                        dl_hash = hashlib.sha256(cf.read()).hexdigest()
                    if dl_hash != WHISPER_CHECKSUMS[model_base]:
                        raise Exception(f"Checksum mismatch for {model_base}")
                shutil.move(temp_path, save_path)
                return True
            except Exception as e:
                print(f"Download error (attempt {attempt+1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    if progress_callback:
                        progress_callback(0, f"Download failed: {str(e)}")
                    # Clean up temp file
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except:
                            pass
                    return False
                time.sleep(2**attempt)
        return False


class Transcriber:
    """Speech to text with multi-language support preserving original script - HIGH QUALITY VERSION"""

    def __init__(self):
        self.whisper_model = None
        self.tinyllama_model = None
        self.current_model = "whisper"
        self.device = self._get_device()
        self.languages = LANGUAGES
        self.tts = TextToSpeech()
        self.models_path = None
        self.last_error = None
        self.model_lock = threading.Lock()

    def _get_device(self):
        if WHISPER_AVAILABLE:
            try:
                if torch.cuda.is_available():
                    return "cuda"
                elif (
                    hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
                ):
                    return "mps"
            except:
                pass
        return "cpu"

    def set_models_path(self, path):
        self.models_path = path
        os.makedirs(path, exist_ok=True)

    def get_whisper_model_filename(self, model_size="medium"):
        return f"{model_size}.pt"

    def verify_whisper_model(self, model_size):
        """Check SHA256 of the model file; delete if corrupt and return False."""
        model_path = os.path.join(self.models_path, f"{model_size}.pt")
        if not os.path.exists(model_path):
            return False
        expected = WHISPER_CHECKSUMS.get(model_size)
        if not expected:
            # No checksum available, assume it's fine
            return True
        try:
            with open(model_path, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            if file_hash == expected:
                return True
            else:
                print(f"❌ Checksum mismatch for {model_size}.pt – deleting corrupt file.")
                os.remove(model_path)
                return False
        except Exception as e:
            print(f"Error verifying model {model_size}: {e}")
            return False

    def load_whisper_if_needed(self, model_size="medium"):
        with self.model_lock:
            if self.whisper_model is not None:
                return True

            if not WHISPER_AVAILABLE:
                self.last_error = "Whisper not installed (pip install openai-whisper)"
                return False

            model_filename = self.get_whisper_model_filename(model_size)
            model_path = os.path.join(self.models_path, model_filename)

            # Verify integrity; if corrupt, it will be deleted
            if os.path.exists(model_path) and not self.verify_whisper_model(model_size):
                self.last_error = f"Whisper model '{model_size}' is corrupt and was deleted. Please download again."
                return False

            if not os.path.exists(model_path):
                self.last_error = f"Whisper model '{model_size}' not downloaded."
                return False

            try:
                import whisper
                print(f"Loading Whisper {model_size} model from {self.models_path}...")
                # If the exact .pt file exists locally, load it directly
                if os.path.exists(model_path):
                    self.whisper_model = whisper.load_model(
                        model_path, device=self.device
                    )
                else:
                    self.whisper_model = whisper.load_model(
                        model_size, device=self.device, download_root=self.models_path
                    )
                self.last_error = None
                return True
            except ImportError:
                self.last_error = "openai-whisper not installed (pip install openai-whisper)"
                return False
            except Exception as e:
                print(f"Whisper load error: {e}")
                self.last_error = f"Failed to load Whisper model: {str(e)}"
                return False

    def load_tinyllama_if_needed(self):
        with self.model_lock:
            if self.tinyllama_model is not None:
                return True

            if not LLAMA_CPP_AVAILABLE:
                self.last_error = "llama-cpp-python not installed"
                return False

            tinyllama_path = os.path.join(
                self.models_path, "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
            )
            if not os.path.exists(tinyllama_path):
                self.last_error = "TinyLlama model not downloaded"
                return False

            try:
                from llama_cpp import Llama
                print("Loading TinyLlama model...")
                self.tinyllama_model = Llama(
                    model_path=tinyllama_path,
                    n_ctx=1024,
                    n_threads=4,
                    n_gpu_layers=-1 if self.device == "cuda" else 0,
                    verbose=False,
                )
                self.last_error = None
                return True
            except Exception as e:
                print(f"TinyLlama load error: {e}")
                self.last_error = f"Failed to load TinyLlama: {str(e)}"
                return False

    def transcribe(self, audio_file, language="en", model_size="medium"):
        """Transcribe audio preserving original script - HIGH QUALITY VERSION"""
        self.last_error = None
        if not self.load_whisper_if_needed(model_size):
            return None

        try:
            # Get the correct Whisper language code
            whisper_lang = language
            for lang_name, lang_data in LANGUAGES.items():
                if lang_data["code"] == language:
                    whisper_lang = lang_data.get("whisper", language)
                    break

            print(f"Transcribing with language: {whisper_lang}, model: {model_size}")

            # HIGH QUALITY transcription settings
            result = self.whisper_model.transcribe(
                audio_file,
                language=whisper_lang,
                task="transcribe",
                verbose=False,
                word_timestamps=True,
                temperature=0.0,
                compression_ratio_threshold=2.4,
                logprob_threshold=-1.0,
                no_speech_threshold=0.6,
                condition_on_previous_text=True,
                fp16=False,
                without_timestamps=False,
                best_of=5,
                beam_size=5,
                patience=2,
                length_penalty=1.0,
                suppress_tokens=[-1],
                initial_prompt=None,
            )

            segments = []
            full_text = []

            for i, seg in enumerate(result["segments"], 1):
                segment_text = seg["text"].strip()
                if segment_text:
                    segments.append(
                        {
                            "start": seg["start"],
                            "end": seg["end"],
                            "text": segment_text,
                            "number": i,
                        }
                    )
                    full_text.append(segment_text)

            if not segments:
                print("No segments found, retrying with different parameters...")
                result = self.whisper_model.transcribe(
                    audio_file,
                    language=whisper_lang,
                    task="transcribe",
                    verbose=False,
                    word_timestamps=True,
                    temperature=0.2,
                    compression_ratio_threshold=2.4,
                    logprob_threshold=-1.0,
                    no_speech_threshold=0.6,
                    condition_on_previous_text=True,
                    fp16=False,
                    without_timestamps=False,
                )
                for i, seg in enumerate(result["segments"], 1):
                    segment_text = seg["text"].strip()
                    if segment_text:
                        segments.append(
                            {
                                "start": seg["start"],
                                "end": seg["end"],
                                "text": segment_text,
                                "number": i,
                            }
                        )
                        full_text.append(segment_text)

            print(f"✅ Transcription complete: {len(segments)} segments found")

            return {
                "text": " ".join(full_text),
                "segments": segments,
                "language": result["language"],
                "segment_count": len(segments),
            }

        except Exception as e:
            print(f"❌ Transcription error: {e}")
            self.last_error = str(e)
            return None

    def transcribe_from_url(
        self, url, language="en", model_size="medium", progress_callback=None
    ):
        """Download HIGHEST QUALITY audio from URL and transcribe"""
        try:
            cache_dir = os.path.join(tempfile.gettempdir(), "kupido_cache")
            os.makedirs(cache_dir, exist_ok=True)

            if progress_callback:
                progress_callback(5, "Analyzing video...")

            base_opts = ToolManager.get_base_ydl_opts()
            with yt_dlp.YoutubeDL(base_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                video_title = info.get("title", "Unknown")
                video_id = info.get("id", str(int(time.time())))

            if progress_callback:
                progress_callback(15, f"Downloading audio: {video_title[:50]}...")

            out_pattern = os.path.join(cache_dir, f"audio_{video_id}.%(ext)s")
            ydl_opts = {
                **base_opts,
                "format": "bestaudio/best",
                "outtmpl": out_pattern,
            }
            if ToolManager.is_ffmpeg_available():
                ydl_opts["postprocessors"] = [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ]

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Find the actual audio file created
            filename = None
            for ext in [".mp3", ".m4a", ".webm", ".opus", ".wav", ".aac", ".ogg"]:
                candidate = os.path.join(cache_dir, f"audio_{video_id}{ext}")
                if os.path.exists(candidate) and os.path.getsize(candidate) > 1000:
                    filename = candidate
                    break

            if not filename or not os.path.exists(filename):
                error_msg = "Audio file was not created or download failed"
                print(f"❌ {error_msg}")
                if progress_callback:
                    progress_callback(0, error_msg)
                return None, video_title

            file_size = os.path.getsize(filename)
            print(f"✅ Audio downloaded: {file_size/1024/1024:.1f} MB")

            if progress_callback:
                progress_callback(
                    50, f"Transcribing audio ({file_size/1024/1024:.1f} MB)..."
                )

            result = self.transcribe(filename, language, model_size)

            if progress_callback:
                progress_callback(90, "Finalizing...")

            try:
                os.remove(filename)
                print("✅ Temporary audio file removed")
            except Exception as e:
                print(f"⚠️ Could not remove temp file: {e}")

            if result:
                print(f"✅ Transcription successful: {result['segment_count']} segments")
                if progress_callback:
                    progress_callback(
                        100, f"Complete! {result['segment_count']} segments"
                    )
            else:
                print(f"❌ Transcription failed: {self.last_error}")
                if progress_callback:
                    progress_callback(0, f"Failed: {self.last_error}")

            return result, video_title

        except Exception as e:
            print(f"❌ URL transcription error: {e}")
            self.last_error = str(e)
            if progress_callback:
                progress_callback(0, f"Error: {str(e)[:50]}")
            return None, None

    def save_as_srt(self, segments, filename):
        try:
            with open(filename, "w", encoding="utf-8") as f:
                for i, seg in enumerate(segments, 1):
                    seg_num = seg.get("number", i)
                    start = self._format_srt_time(seg["start"])
                    end = self._format_srt_time(seg["end"])
                    f.write(f"{seg_num}\n")
                    f.write(f"{start} --> {end}\n")
                    f.write(f"{seg['text']}\n\n")
            print(f"✅ SRT file saved: {filename}")
            return True
        except Exception as e:
            print(f"❌ SRT save error: {e}")
            return False

    def save_as_txt(self, text, filename):
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"✅ TXT file saved: {filename}")
            return True
        except:
            return False

    def save_as_pdf(self, text, filename):
        if not REPORTLAB_AVAILABLE:
            return False
        try:
            c = canvas.Canvas(filename, pagesize=letter)
            width, height = letter
            y = height - 40
            margin = 40
            c.setFont("Helvetica", 11)
            lines = text.split("\n")
            for line in lines:
                if y < 40:
                    c.showPage()
                    c.setFont("Helvetica", 11)
                    y = height - 40
                wrapped_lines = simpleSplit(
                    line, c._fontname, c._fontsize, width - 2 * margin
                )
                for wrapped_line in wrapped_lines:
                    c.drawString(margin, y, wrapped_line)
                    y -= 15
            c.save()
            return True
        except:
            return False

    def save_as_json(self, data, filename):
        try:
            json_data = {
                "text": data["text"],
                "segments": data["segments"],
                "language": data["language"],
                "segment_count": data.get("segment_count", len(data["segments"])),
                "timestamp": time.time(),
            }
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            print(f"✅ JSON file saved: {filename}")
            return True
        except:
            return False

    def _format_srt_time(self, seconds):
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def format_with_tinyllama(self, text, style="summary"):
        if not self.load_tinyllama_if_needed():
            return self._format_basic(text, style)
        try:
            prompts = {
                "summary": "Summarize the following text concisely while preserving the original language:\n\n",
                "single": "Convert to a single line while preserving the original language:\n\n",
                "paragraph": "Format as proper paragraphs while preserving the original language:\n\n",
                "timestamps": "Keep the timestamps and improve the text while preserving the original language:\n\n",
            }
            prompt = prompts.get(style, "Process this text:\n\n") + text
            output = self.tinyllama_model.create_completion(
                prompt,
                max_tokens=len(text.split()) * 2,
                temperature=0.3,
                stop=["\n\n", "```"],
                echo=False,
            )
            if output and "choices" in output and len(output["choices"]) > 0:
                return output["choices"][0]["text"].strip()
            return self._format_basic(text, style)
        except Exception as e:
            print(f"TinyLlama error: {e}")
            return self._format_basic(text, style)

    def _format_basic(self, text, style):
        if style == "summary":
            sentences = re.split(r"(?<=[.!?])\s+", text)
            return " ".join(sentences[:3]) + "..."
        elif style == "single":
            return " ".join(text.split())
        elif style == "paragraph":
            return text
        elif style == "timestamps":
            return text
        else:
            return text


class RightClickMenu:
    """Enhanced context menu for entry widgets with reliable clipboard support."""
    def __init__(self, widget, app=None):
        self.widget = widget
        self.app = app
        self.menu = tk.Menu(widget, tearoff=0, bg=COLORS["bg_medium"], fg=COLORS["text_primary"], activebackground=COLORS["accent"])
        self._create_menu()
        self._bind_events()

    def _create_menu(self):
        self.menu.add_command(label="✂️ Cut", command=self.cut, accelerator="Ctrl+X")
        self.menu.add_command(label="📋 Copy", command=self.copy, accelerator="Ctrl+C")
        self.menu.add_command(label="📋 Paste", command=self.paste, accelerator="Ctrl+V")
        self.menu.add_separator()
        self.menu.add_command(label="✓ Select All", command=self.select_all, accelerator="Ctrl+A")
        self.menu.add_command(label="🗑️ Clear", command=self.clear)
        self.menu.add_separator()
        self.menu.add_command(label="🔍 Search on YouTube", command=self.search_youtube)
        self.menu.add_command(label="📋 Copy URL to Clipboard", command=self.copy_url)
        if hasattr(self.widget, "get") and callable(self.widget.get):
            self.menu.add_command(label="📂 Load in Player", command=self.load_in_player)

    def _bind_events(self):
        target = self.widget.entry if hasattr(self.widget, "entry") else self.widget
        target.bind("<Button-3>", self.show_menu)
        self.widget.bind("<Button-3>", self.show_menu)

    def show_menu(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def cut(self):
        try:
            self.copy()
            self.clear()
        except Exception:
            pass

    def copy(self):
        try:
            text = ""
            target = self.widget.entry if hasattr(self.widget, "entry") else self.widget
            if hasattr(target, "selection_get"):
                try:
                    text = target.selection_get()
                except Exception:
                    pass
            if not text and hasattr(self.widget, "get"):
                text = self.widget.get()
            if text:
                safe_set_clipboard(text, getattr(self.app, "root", None))
        except Exception:
            pass

    def paste(self):
        try:
            clip_text = safe_get_clipboard(getattr(self.app, "root", None))
            if clip_text:
                if hasattr(self.widget, "delete") and hasattr(self.widget, "insert"):
                    self.widget.delete(0, tk.END)
                    self.widget.insert(0, clip_text)
                elif hasattr(self.widget, "entry"):
                    self.widget.entry.delete(0, tk.END)
                    self.widget.entry.insert(0, clip_text)
        except Exception:
            pass

    def clear(self):
        try:
            if hasattr(self.widget, "delete"):
                self.widget.delete(0, tk.END)
            elif hasattr(self.widget, "entry"):
                self.widget.entry.delete(0, tk.END)
        except Exception:
            pass

    def select_all(self):
        try:
            if hasattr(self.widget, "select_range"):
                self.widget.select_range(0, tk.END)
            elif hasattr(self.widget, "entry") and hasattr(self.widget.entry, "select_range"):
                self.widget.entry.select_range(0, tk.END)
        except Exception:
            pass

    def search_youtube(self):
        try:
            q = self.widget.get().strip() if hasattr(self.widget, "get") else ""
            if q:
                webbrowser.open(f"https://www.youtube.com/results?search_query={q}")
        except Exception:
            pass

    def copy_url(self):
        try:
            q = self.widget.get().strip() if hasattr(self.widget, "get") else ""
            if q:
                safe_set_clipboard(q, getattr(self.app, "root", None))
        except Exception:
            pass

    def load_in_player(self):
        try:
            if self.app:
                self.app.play_url()
        except Exception:
            pass


class ModernEntry(ctk.CTkFrame):
    """Full-featured modern entry forwarding all editing and binding methods."""
    def __init__(self, master, placeholder="", **kwargs):
        super().__init__(master, fg_color="transparent")
        self.entry = ctk.CTkEntry(
            self,
            height=45,
            font=ctk.CTkFont(size=14),
            border_width=2,
            corner_radius=12,
            placeholder_text=placeholder,
            **kwargs,
        )
        self.entry.pack(fill="x", expand=True)
        RightClickMenu(self)

    def get(self):
        return self.entry.get()

    def set(self, value):
        self.entry.delete(0, "end")
        self.entry.insert(0, value)

    def delete(self, first, last=None):
        return self.entry.delete(first, last)

    def insert(self, index, string):
        return self.entry.insert(index, string)

    def select_range(self, start, end):
        return self.entry.select_range(start, end)

    def icursor(self, index):
        return self.entry.icursor(index)

    def focus(self):
        return self.entry.focus()

    def focus_set(self):
        return self.entry.focus_set()

    def bind(self, sequence=None, func=None, add='+'):
        try:
            self.entry.bind(sequence, func, add='+')
        except Exception:
            pass
        return super().bind(sequence, func, add)


class ModernCard(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        border_width = kwargs.pop("border_width", 1)
        border_color = kwargs.pop("border_color", "#242C3F")
        corner_radius = kwargs.pop("corner_radius", 16)
        fg_color = kwargs.pop("fg_color", COLORS["surface"])
        super().__init__(
            master,
            fg_color=fg_color,
            corner_radius=corner_radius,
            border_width=border_width,
            border_color=border_color,
            **kwargs,
        )


class ModernProgressBar(ctk.CTkFrame):
    """Interactive, draggable, smooth animated progress bar for video playback seeking."""
    def __init__(self, master, height=14, command=None, **kwargs):
        super().__init__(master, height=height, fg_color="transparent", **kwargs)
        self.command = command
        self._value = 0.0  # 0.0 to 100.0
        self.is_scrubbing = False
        self._bar_height = height

        # Hardware-rendered Canvas for sleek progress track and scrubber knob
        self.canvas = tk.Canvas(
            self,
            height=self._bar_height,
            bg=COLORS["bg_dark"],
            highlightthickness=0,
            bd=0,
            cursor="hand2"
        )
        self.canvas.pack(fill=tk.X, expand=True)

        # Mouse event bindings for clicking and smooth dragging
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event=None):
        self._redraw()

    def _calc_fraction(self, event):
        w = max(1, self.canvas.winfo_width())
        return max(0.0, min(1.0, float(event.x) / float(w)))

    def _on_click(self, event):
        self.is_scrubbing = True
        frac = self._calc_fraction(event)
        self._value = frac * 100.0
        self._redraw()
        if self.command:
            try:
                self.command(self._value)
            except Exception:
                pass

    def _on_drag(self, event):
        self.is_scrubbing = True
        frac = self._calc_fraction(event)
        self._value = frac * 100.0
        self._redraw()
        if self.command:
            try:
                self.command(self._value)
            except Exception:
                pass

    def _on_release(self, event):
        frac = self._calc_fraction(event)
        self._value = frac * 100.0
        self._redraw()
        if self.command:
            try:
                self.command(self._value)
            except Exception:
                pass
        self.after(200, self._finish_scrubbing)

    def _finish_scrubbing(self):
        self.is_scrubbing = False

    def set(self, value):
        """Set progress from 0.0 to 100.0 (ignored while user is dragging)."""
        if self.is_scrubbing:
            return
        try:
            self._value = max(0.0, min(100.0, float(value)))
            self._redraw()
        except Exception:
            pass

    def get(self):
        return self._value

    def _redraw(self):
        if not self.winfo_exists() or not self.canvas.winfo_exists():
            return
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w <= 1:
            return

        self.canvas.delete("all")
        track_h = 6
        track_y1 = (h - track_h) // 2
        track_y2 = track_y1 + track_h

        # Background track
        self.canvas.create_rectangle(
            0, track_y1, w, track_y2,
            fill=COLORS["bg_light"], outline="", width=0
        )

        # Filled progress portion
        fill_w = int((self._value / 100.0) * w)
        if fill_w > 0:
            self.canvas.create_rectangle(
                0, track_y1, fill_w, track_y2,
                fill=COLORS["accent"], outline="", width=0
            )
            # Scrubber knob at current position
            r = 5
            knob_x = min(w - r, max(r, fill_w))
            knob_y = h // 2
            self.canvas.create_oval(
                knob_x - r, knob_y - r,
                knob_x + r, knob_y + r,
                fill="#FFFFFF", outline=COLORS["accent_light"], width=1
            )


class ModernSwitch(ctk.CTkSwitch):
    """Modern antialiased switch with crisp electric-blue graphics and zero clipping."""
    def __init__(self, master, text="Offline", command=None, variable=None, **kwargs):
        self._callback = command
        super().__init__(
            master,
            text=text,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["text_secondary"],
            progress_color=COLORS["accent"],
            button_color="#FFFFFF",
            button_hover_color=COLORS["accent_light"],
            fg_color=COLORS["bg_light"],
            switch_width=38,
            switch_height=20,
            corner_radius=10,
            command=self._on_switch_change,
            variable=variable,
            **kwargs
        )

    def _on_switch_change(self):
        val = bool(self.get())
        if self._callback:
            self._callback(val)

    def toggle(self, event=None):
        if self.get() == 1:
            self.deselect()
        else:
            self.select()
        self._on_switch_change()

    @property
    def is_on(self):
        return bool(self.get())


class ModernSlider(ctk.CTkFrame):
    def __init__(self, master, from_=0, to=100, command=None, **kwargs):
        super().__init__(master, fg_color="transparent")
        self.command = command
        self.value_label = ctk.CTkLabel(
            self, text="50%", font=ctk.CTkFont(size=12), width=40, anchor="e"
        )
        self.value_label.pack(side="right", padx=(5, 0))
        self.slider = ctk.CTkSlider(
            self,
            from_=from_,
            to=to,
            command=self.on_slide,
            progress_color=COLORS["accent"],
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            height=6,
            **kwargs,
        )
        self.slider.pack(side="right", fill="x", expand=True)
        self.slider.set(50)

    def on_slide(self, value):
        self.value_label.configure(text=f"{int(value)}%")
        if self.command:
            self.command(value)

    def set(self, value):
        self.slider.set(value)
        self.value_label.configure(text=f"{int(value)}%")

    def get(self):
        return self.slider.get()


# ==================== Video Player ====================

class VideoPlayer:
    """Enhanced video player supporting YouTube streams, web media, and local files directly."""
    def __init__(self, settings, player_type="main"):
        self.settings = settings
        self.player_type = player_type
        self.instance = None
        self.player = None
        self.is_playing = False
        self.volume = 50
        self.current_time = 0
        self.duration = 0
        self.current_url = None
        self.current_title = ""
        self.is_looping = False
        self.is_muted = False
        self.is_fullscreen = False
        self.event_manager = None
        self.vlc_available = VLC_AVAILABLE
        self.main_app = None
        self.update_thread_running = True
        self.update_thread = None
        self.video_frame = None
        self.normal_geometry = None
        self._last_update = 0
        self._update_interval = 0.1
        self._play_queue = queue.Queue()
        self._speed = 1.0
        self._fallback_audio = None

        self._init_vlc()
        self._start_update_thread()
        self._start_playback_thread()

    def _init_vlc(self):
        if not self.vlc_available:
            return
        try:
            caching = getattr(self.settings, "network_caching", 1000)
            vlc_args = [
                "--quiet",
                "--no-xlib",
                f"--network-caching={caching}",
                "--no-video-title-show",
            ]
            self.instance = vlc.Instance(vlc_args)
            self.player = self.instance.media_player_new()
            self.player.audio_set_volume(self.volume)

            self.event_manager = self.player.event_manager()
            self.event_manager.event_attach(vlc.EventType.MediaPlayerTimeChanged, self._on_time_changed)
            self.event_manager.event_attach(vlc.EventType.MediaPlayerLengthChanged, self._on_length_changed)
            self.event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_media_end)
            self.event_manager.event_attach(vlc.EventType.MediaPlayerPlaying, self._on_playing)
            self.event_manager.event_attach(vlc.EventType.MediaPlayerPaused, self._on_paused)
            self.event_manager.event_attach(vlc.EventType.MediaPlayerStopped, self._on_stopped)
            self.event_manager.event_attach(vlc.EventType.MediaPlayerEncounteredError, self._on_error)
        except Exception as e:
            print(f"VLC init error: {e}")
            self.vlc_available = False

    def _start_update_thread(self):
        def update_handler():
            while self.update_thread_running:
                try:
                    if self.is_playing and self.player_type == "hover":
                        if self.main_app and getattr(self.main_app, "hover_window", None):
                            hw = self.main_app.hover_window
                            if getattr(hw, "is_visible", False) and hasattr(hw, "update_display"):
                                hw.update_display()
                    time.sleep(0.5)
                except:
                    pass
        self.update_thread = threading.Thread(target=update_handler, daemon=True)
        self.update_thread.start()

    def _start_playback_thread(self):
        def playback_handler():
            while self.update_thread_running:
                try:
                    url, use_cache = self._play_queue.get(timeout=0.5)
                    if url:
                        self._do_play_url(url, use_cache)
                except queue.Empty:
                    continue
                except:
                    pass
        self.playback_thread = threading.Thread(target=playback_handler, daemon=True)
        self.playback_thread.start()

    def _on_time_changed(self, event):
        try:
            self.current_time = self.player.get_time() / 1000.0
        except:
            pass

    def _on_length_changed(self, event):
        try:
            self.duration = self.player.get_length() / 1000.0
            if self.main_app and self.player_type == "main":
                self.main_app.update_duration(self.duration)
        except:
            pass

    def _on_media_end(self, event):
        self.is_playing = False
        if self.is_looping and self.current_url:
            self.play_url(self.current_url)
        elif self.main_app and self.player_type == "main":
            self.main_app.on_video_end()
        if self.main_app and hasattr(self.main_app, "update_play_button"):
            self.main_app.update_play_button()

    def _on_playing(self, event):
        self.is_playing = True
        if self.main_app:
            if hasattr(self.main_app, "update_play_button"):
                self.main_app.update_play_button()
            if hasattr(self.main_app, "hover_window") and self.main_app.hover_window:
                if hasattr(self.main_app.hover_window, "update_play_button"):
                    self.main_app.hover_window.update_play_button()

    def _on_paused(self, event):
        self.is_playing = False
        if self.main_app:
            if hasattr(self.main_app, "update_play_button"):
                self.main_app.update_play_button()
            if hasattr(self.main_app, "hover_window") and self.main_app.hover_window:
                if hasattr(self.main_app.hover_window, "update_play_button"):
                    self.main_app.hover_window.update_play_button()

    def _on_stopped(self, event):
        self.is_playing = False
        if self.main_app:
            if hasattr(self.main_app, "update_play_button"):
                self.main_app.update_play_button()
            if hasattr(self.main_app, "hover_window") and self.main_app.hover_window:
                if hasattr(self.main_app.hover_window, "update_play_button"):
                    self.main_app.hover_window.update_play_button()

    def _on_error(self, event):
        self.is_playing = False
        if self.main_app:
            self.main_app.play_error("Playback stream error")

    def set_hwnd(self, hwnd):
        if self.vlc_available and self.player:
            self.player.set_hwnd(hwnd)
            self.video_frame = hwnd

    def get_time(self):
        if self.vlc_available and self.player:
            try:
                t = self.player.get_time()
                if t >= 0:
                    self.current_time = t / 1000.0
            except Exception:
                pass
        return getattr(self, "current_time", 0.0)

    def get_duration(self):
        if self.vlc_available and self.player:
            try:
                d = self.player.get_length()
                if d > 0:
                    self.duration = d / 1000.0
            except Exception:
                pass
        return getattr(self, "duration", 0.0)

    def set_time(self, seconds):
        if self.vlc_available and self.player and self.duration > 0:
            target_ms = int(max(0, min(self.duration, seconds)) * 1000)
            self.player.set_time(target_ms)
            self.current_time = target_ms / 1000.0

    def set_speed(self, speed):
        self._speed = max(0.25, min(4.0, speed))
        if self.vlc_available and self.player:
            self.player.set_rate(self._speed)

    def get_speed(self):
        return self._speed

    def play_url(self, url, use_cache=False):
        self._play_queue.put((url, use_cache))
        return None

    def _do_play_url(self, url, use_cache=False):
        try:
            self.duration = 0.0
            self.current_time = 0.0
            if not self.vlc_available:
                self._play_audio_fallback(url)
                return

            clean_target = url.strip().strip('"').strip("'")

            # 1. Check if direct local file path (supports offline video mode without yt-dlp)
            if os.path.isfile(clean_target):
                media = self.instance.media_new(clean_target)
                self.player.set_media(media)
                self.player.play()
                self.current_url = clean_target
                self.current_title = os.path.splitext(os.path.basename(clean_target))[0]
                self.set_speed(self._speed)
                if self.main_app:
                    self.main_app.play_callback(
                        {
                            "title": self.current_title,
                            "duration": 0,
                            "uploader": "Local Video",
                            "views": 0,
                            "quality": "Direct",
                        },
                        clean_target,
                    )
                return

            # 2. Check offline cache
            if use_cache:
                cache_file = self._get_cache_filename(clean_target)
                if os.path.exists(cache_file):
                    media = self.instance.media_new(cache_file)
                    self.player.set_media(media)
                    self.player.play()
                    self.current_url = clean_target
                    self.current_title = os.path.basename(cache_file)
                    self.set_speed(self._speed)
                    if self.main_app:
                        self.main_app.play_callback(
                            {
                                "title": self.current_title,
                                "duration": 0,
                                "uploader": "Offline Cache",
                                "views": 0,
                                "quality": "Cached",
                            },
                            clean_target,
                        )
                    return

            # 3. Clean target URL for Reels, Shorts, and social media links
            if "youtube.com/shorts/" in clean_target:
                s_id = clean_target.split("/shorts/")[1].split("?")[0].split("/")[0]
                clean_target = f"https://www.youtube.com/watch?v={s_id}"
            elif "instagram.com/reel" in clean_target or "instagram.com/reels" in clean_target:
                clean_target = clean_target.split("?")[0]
            elif "facebook.com/reel" in clean_target:
                clean_target = clean_target.split("?")[0]

            base_opts = ToolManager.get_base_ydl_opts()
            q = getattr(self, "selected_quality", "best").lower()
            if q == "1080p":
                fmt_str = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
            elif q == "720p":
                fmt_str = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
            elif q == "480p":
                fmt_str = "bestvideo[height<=480]+bestaudio/best[height<=480]/best"
            elif q == "360p":
                fmt_str = "bestvideo[height<=360]+bestaudio/best[height<=360]/best"
            elif q == "audio":
                fmt_str = "bestaudio/best"
            else:
                fmt_str = "bestvideo+bestaudio/best"

            ydl_opts = {
                **base_opts,
                "format": fmt_str,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(clean_target, download=False)
                video_url = None
                audio_url = None

                # Check if yt-dlp returned separate video and audio streams (e.g. 1080p/DASH)
                if info.get("requested_formats"):
                    rf = info["requested_formats"]
                    if len(rf) >= 2:
                        video_url = rf[0].get("url")
                        audio_url = rf[1].get("url")
                    elif len(rf) == 1:
                        video_url = rf[0].get("url")

                if not video_url and "url" in info:
                    video_url = info["url"]

                if not video_url and "formats" in info and len(info["formats"]) > 0:
                    formats = info["formats"]
                    max_h = 1080 if q == "1080p" else (720 if q == "720p" else (480 if q == "480p" else (360 if q == "360p" else 9999)))
                    valid_fmts = [f for f in formats if f.get("height") and f.get("height") <= max_h]
                    if valid_fmts:
                        prog = [f for f in valid_fmts if f.get("vcodec") != "none" and f.get("acodec") != "none"]
                        if prog:
                            prog.sort(key=lambda x: x.get("height", 0), reverse=True)
                            video_url = prog[0].get("url")
                        else:
                            valid_fmts.sort(key=lambda x: x.get("height", 0), reverse=True)
                            video_url = valid_fmts[0].get("url")
                    if not video_url:
                        video_url = formats[-1].get("url")

                if not video_url:
                    if self.main_app:
                        self.main_app.play_error("No playable stream found")
                    return

                self.current_title = info.get("title", "Unknown")
                self.duration = info.get("duration", 0)
                self.current_url = clean_target

                height = info.get("height", 0)
                quality_text = f"{height}p" if height > 0 else "HD"

                media = self.instance.media_new(video_url)
                if audio_url:
                    media.add_option(f":input-slave={audio_url}")
                http_headers = info.get("http_headers", {})
                ua = http_headers.get("User-Agent", "Mozilla/5.0")
                media.add_option(f":http-user-agent={ua}")
                if "Referer" in http_headers:
                    media.add_option(f":http-referrer={http_headers['Referer']}")

                self.player.set_media(media)
                self.player.play()
                self.set_speed(self._speed)

                if (
                    self.main_app
                    and getattr(self.main_app, "offline_mode", None)
                    and hasattr(self.main_app.offline_mode, "get")
                    and self.main_app.offline_mode.get()
                    and not use_cache
                ):
                    threading.Thread(
                        target=self._cache_video,
                        args=(clean_target, self.current_title),
                        daemon=True,
                    ).start()

                if self.main_app:
                    self.main_app.play_callback(
                        {
                            "title": self.current_title,
                            "duration": self.duration,
                            "uploader": info.get("uploader") or info.get("channel") or "Unknown",
                            "upload_date": str(info.get("upload_date") or ""),
                            "views": info.get("view_count", 0),
                            "likes": info.get("like_count", 0),
                            "description": info.get("description", "") or "",
                            "quality": quality_text,
                        },
                        clean_target,
                    )
        except Exception as e:
            if self.main_app:
                self.main_app.play_error(str(e))
            self._play_audio_fallback(url)

    def _play_audio_fallback(self, url):
        try:
            import pygame
            pygame.mixer.init()
            # fallback placeholder
        except:
            if self.main_app:
                self.main_app.show_notification("Notice", "Audio fallback unavailable")

    def _cache_video(self, url, title):
        try:
            cache_file = self._get_cache_filename(url)
            os.makedirs(os.path.dirname(cache_file), exist_ok=True)
            if not os.path.exists(cache_file):
                base_opts = ToolManager.get_base_ydl_opts()
                ydl_opts = {
                    **base_opts,
                    "format": "best[ext=mp4]/best",
                    "outtmpl": cache_file,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                if self.main_app and hasattr(self.main_app, "cache_manager"):
                    self.main_app.cache_manager.add_to_cache(url, title, cache_file)
        except Exception as e:
            print(f"Cache video error: {e}")

    def _get_cache_filename(self, url):
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return os.path.join(self.settings.cache_path, f"{url_hash}.mp4")

    def toggle_play_pause(self):
        """Robust play/pause toggle querying real VLC state."""
        if self.vlc_available and self.player:
            state = self.player.get_state()
            if state in (vlc.State.Playing, vlc.State.Buffering):
                self.player.pause()
                self.is_playing = False
            elif state in (vlc.State.Paused, vlc.State.Stopped):
                self.player.play()
                self.is_playing = True
            else:
                if self.is_playing:
                    self.player.pause()
                    self.is_playing = False
                else:
                    self.player.play()
                    self.is_playing = True
            if self.main_app and hasattr(self.main_app, "update_play_button"):
                self.main_app.update_play_button()

    def pause(self):
        """Explicitly pause playback."""
        if self.vlc_available and self.player:
            state = self.player.get_state()
            if state in (vlc.State.Playing, vlc.State.Buffering):
                self.player.pause()
            self.is_playing = False
            if self.main_app and hasattr(self.main_app, "update_play_button"):
                self.main_app.update_play_button()

    def play(self):
        """Explicitly resume or start playback."""
        if self.vlc_available and self.player:
            state = self.player.get_state()
            if state != vlc.State.Playing:
                self.player.play()
            self.is_playing = True
            if self.main_app and hasattr(self.main_app, "update_play_button"):
                self.main_app.update_play_button()

    def set_subtitle_file(self, srt_path):
        """Load external subtitle file into VLC video player."""
        if self.vlc_available and self.player and os.path.exists(srt_path):
            try:
                res = self.player.video_set_subtitle_file(str(os.path.normpath(srt_path)))
                logger.info(f"Loaded subtitle file {srt_path}: {res}")
                return True
            except Exception as e:
                logger.error(f"Error setting subtitle: {e}")
                return False
        return False

    def disable_subtitles(self):
        """Disable current subtitle track."""
        if self.vlc_available and self.player:
            try:
                self.player.video_set_spu(-1)
                return True
            except Exception:
                pass
        return False

    def stop(self):
        if self.vlc_available and self.player:
            self.player.stop()
            self.is_playing = False
            self.current_time = 0
            if self.main_app and hasattr(self.main_app, "update_play_button"):
                self.main_app.update_play_button()

    def set_volume(self, volume):
        self.volume = max(0, min(100, volume))
        if self.vlc_available and self.player:
            self.player.audio_set_volume(self.volume)

    def seek(self, position):
        if self.vlc_available and self.player:
            dur = self.get_duration()
            # Support both percentage (0-100) and fraction (0-1)
            if position > 1.0:
                pos = max(0.0, min(1.0, float(position) / 100.0))
            else:
                pos = max(0.0, min(1.0, float(position)))
            try:
                self.player.set_position(pos)
                if dur > 0:
                    self.current_time = pos * dur
            except Exception:
                pass

    def seek_forward(self, seconds=10):
        if self.vlc_available and self.player:
            new_time = min(self.duration, self.current_time + seconds)
            self.set_time(new_time)

    def seek_backward(self, seconds=10):
        if self.vlc_available and self.player:
            new_time = max(0, self.current_time - seconds)
            self.set_time(new_time)

    def go_to_time(self, time_str):
        try:
            parts = [float(p) for p in time_str.strip().split(":")]
            if len(parts) == 1:
                target_secs = parts[0]
            elif len(parts) == 2:
                target_secs = parts[0] * 60 + parts[1]
            elif len(parts) == 3:
                target_secs = parts[0] * 3600 + parts[1] * 60 + parts[2]
            else:
                return False
            self.set_time(target_secs)
            return True
        except:
            return False

    def mute(self):
        if self.vlc_available and self.player:
            self.player.audio_set_mute(True)
            self.is_muted = True

    def unmute(self):
        if self.vlc_available and self.player:
            self.player.audio_set_mute(False)
            self.is_muted = False

    def toggle_loop(self):
        self.is_looping = not self.is_looping
        return self.is_looping

    def toggle_fullscreen(self, window):
        self.is_fullscreen = not self.is_fullscreen
        if self.is_fullscreen:
            self.normal_geometry = window.geometry()
            window.attributes("-fullscreen", True)
        else:
            window.attributes("-fullscreen", False)
            if self.normal_geometry:
                window.geometry(self.normal_geometry)
        return self.is_fullscreen

    def cleanup(self):
        self.update_thread_running = False
        if self.vlc_available and self.player:
            try:
                self.player.stop()
                self.player.release()
            except:
                pass


class ModernHoverWindow:
    """Floating Mini Player with all essential controls: Mute/Unmute, Loop, Seek 10s, Volume, Fullscreen, and Pin."""
    def __init__(self, main_app):
        self.main_app = main_app
        self.player = VideoPlayer(main_app.settings, player_type="hover")
        self.player.main_app = main_app
        self.window = None
        self.is_visible = False
        self.current_url = None
        self.is_dragging = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.video_frame = None
        self.is_fullscreen = False
        self.normal_geometry = None
        self.context_menu = None

    def create_window(self):
        self.window = tk.Toplevel(self.main_app.root)
        self.window.title("Kupido Mini Player")
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.geometry("560x420")
        self.window.minsize(440, 320)
        self.window.configure(bg=COLORS["bg_dark"])

        main_frame = ctk.CTkFrame(self.window, fg_color=COLORS["surface"], corner_radius=14)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # 1. Title bar with Video Title Display, Dragging, and Window Controls
        title_bar = ctk.CTkFrame(main_frame, height=36, fg_color=COLORS["bg_medium"], corner_radius=12)
        title_bar.pack(fill=tk.X, padx=2, pady=2)
        title_bar.pack_propagate(False)

        ctk.CTkLabel(title_bar, text="", image=IconFactory.get("pip", (16, 16))).pack(side=tk.LEFT, padx=(10, 4))

        self.title_label = ctk.CTkLabel(
            title_bar, text="Kupido Mini Player", font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS["text_primary"], anchor="w"
        )
        self.title_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        win_ctrls = ctk.CTkFrame(title_bar, fg_color="transparent")
        win_ctrls.pack(side=tk.RIGHT, padx=6)

        self.fs_btn = ctk.CTkButton(
            win_ctrls, text="⛶", width=28, height=28, corner_radius=14,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            font=ctk.CTkFont(size=11, weight="bold"), command=self.toggle_fullscreen
        )
        self.fs_btn.pack(side=tk.LEFT, padx=2)

        self.top_btn = ctk.CTkButton(
            win_ctrls, text="📌", width=28, height=28, corner_radius=14,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            font=ctk.CTkFont(size=11), command=self.toggle_topmost
        )
        self.top_btn.pack(side=tk.LEFT, padx=2)

        ctk.CTkButton(
            win_ctrls, text="✕", width=28, height=28, corner_radius=14,
            fg_color=COLORS["bg_light"], hover_color=COLORS["error"],
            font=ctk.CTkFont(size=11, weight="bold"), command=self.hide
        ).pack(side=tk.LEFT, padx=2)

        title_bar.bind("<Button-1>", self.start_drag)
        title_bar.bind("<B1-Motion>", self.on_drag)

        # 2. VLC Video Canvas Frame
        video_wrap = ctk.CTkFrame(main_frame, fg_color=COLORS["bg_dark"], corner_radius=10)
        video_wrap.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        video_wrap.grid_columnconfigure(0, weight=1)
        video_wrap.grid_rowconfigure(0, weight=1)

        self.video_frame = tk.Frame(video_wrap, bg=COLORS["bg_dark"], highlightthickness=0)
        self.video_frame.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        self.window.update_idletasks()
        if self.player.vlc_available:
            self.player.set_hwnd(self.video_frame.winfo_id())

        # Right Click Context Menu on Video Area
        self.context_menu = tk.Menu(self.window, tearoff=0, bg=COLORS["bg_medium"], fg=COLORS["text_primary"], activebackground=COLORS["accent"])
        self.context_menu.add_command(label="Play / Pause", command=self.toggle_play)
        self.context_menu.add_command(label="Use Main Track", command=self.use_main_url)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Paste & Play", command=self.paste_from_clipboard)
        self.context_menu.add_command(label="Loop On/Off", command=self.toggle_loop)
        self.context_menu.add_command(label="Mute / Unmute", command=self.toggle_mute)
        self.context_menu.add_command(label="Download Media", command=self.download_current)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Copy Link", command=lambda: safe_set_clipboard(self.current_url or "", self.window))
        self.context_menu.add_command(label="Close Mini Player", command=self.hide)

        self.video_frame.bind("<Button-3>", lambda e: self.context_menu.tk_popup(e.x_root, e.y_root))

        # 3. Mini Navigation Bar (URL, Paste, Use Main, Play, Download)
        nav_bar = ctk.CTkFrame(main_frame, fg_color="transparent")
        nav_bar.pack(fill=tk.X, padx=6, pady=(4, 2))

        self.url_entry = ctk.CTkEntry(
            nav_bar, placeholder_text="Enter video link...",
            height=28, corner_radius=14, border_width=0, fg_color=COLORS["bg_light"]
        )
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self.url_entry.bind("<Return>", lambda e: self.play_url(self.url_entry.get()))

        # Right-click context menu on URL entry (Cut, Copy, Paste, Select All)
        entry_ctx = tk.Menu(self.window, tearoff=0, bg=COLORS["bg_medium"], fg=COLORS["text_primary"], activebackground=COLORS["accent"])
        entry_ctx.add_command(label="Cut", command=lambda: self.url_entry.event_generate("<<Cut>>"))
        entry_ctx.add_command(label="Copy", command=lambda: self.url_entry.event_generate("<<Copy>>"))
        entry_ctx.add_command(label="Paste", command=self.paste_from_clipboard)
        entry_ctx.add_separator()
        entry_ctx.add_command(label="Select All", command=lambda: self.url_entry.select_range(0, tk.END))
        self.url_entry.bind("<Button-3>", lambda e: entry_ctx.tk_popup(e.x_root, e.y_root))

        ctk.CTkButton(
            nav_bar, text=" Paste", image=IconFactory.get("copy", (14, 14)), width=68, height=28, corner_radius=14,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self.paste_from_clipboard
        ).pack(side=tk.LEFT, padx=2)

        ctk.CTkButton(
            nav_bar, text=" Main", image=IconFactory.get("play", (14, 14)), width=68, height=28, corner_radius=14,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self.use_main_url
        ).pack(side=tk.LEFT, padx=2)

        ctk.CTkButton(
            nav_bar, text=" Play", image=IconFactory.get("play", (14, 14)), width=62, height=28, corner_radius=14,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(size=10, weight="bold"),
            command=lambda: self.play_url(self.url_entry.get())
        ).pack(side=tk.LEFT, padx=2)

        ctk.CTkButton(
            nav_bar, text="", image=IconFactory.get("download", (15, 15)), width=34, height=28, corner_radius=14,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            command=self.download_current
        ).pack(side=tk.LEFT, padx=2)

        # 4. Progress bar with Current / Total Time
        prog_row = ctk.CTkFrame(main_frame, fg_color="transparent")
        prog_row.pack(fill=tk.X, padx=8, pady=(2, 2))

        self.time_current = ctk.CTkLabel(prog_row, text="0:00", font=ctk.CTkFont(size=10), text_color=COLORS["text_secondary"])
        self.time_current.pack(side=tk.LEFT, padx=(0, 4))

        self.progress_bar = ModernProgressBar(prog_row, command=self.seek_from_progress)
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        self.time_total = ctk.CTkLabel(prog_row, text="0:00", font=ctk.CTkFont(size=10), text_color=COLORS["text_secondary"])
        self.time_total.pack(side=tk.RIGHT, padx=(4, 0))

        # 5. Playback Controls Bottom Row (Play, Stop, -10s, +10s, Loop, Mute, Volume Slider, Vol Up/Down)
        bottom_bar = ctk.CTkFrame(main_frame, height=36, fg_color=COLORS["bg_medium"], corner_radius=10)
        bottom_bar.pack(fill=tk.X, padx=4, pady=(2, 4))
        bottom_bar.pack_propagate(False)

        self.play_btn = ctk.CTkButton(
            bottom_bar, text="", image=IconFactory.get("play", (14, 14)), width=32, height=28, corner_radius=14,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            command=self.toggle_play
        )
        self.play_btn.pack(side=tk.LEFT, padx=2)

        ctk.CTkButton(
            bottom_bar, text="", image=IconFactory.get("stop", (12, 12)), width=28, height=28, corner_radius=14,
            fg_color=COLORS["bg_light"], hover_color=COLORS["error"],
            command=self.stop_video
        ).pack(side=tk.LEFT, padx=2)

        ctk.CTkButton(
            bottom_bar, text="", image=IconFactory.get("backward", (14, 14)), width=30, height=28, corner_radius=14,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            command=lambda: self.player.seek_backward(10)
        ).pack(side=tk.LEFT, padx=2)

        ctk.CTkButton(
            bottom_bar, text="", image=IconFactory.get("forward", (14, 14)), width=30, height=28, corner_radius=14,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            command=lambda: self.player.seek_forward(10)
        ).pack(side=tk.LEFT, padx=2)

        self.loop_btn = ctk.CTkButton(
            bottom_bar, text="", image=IconFactory.get("loop", (14, 14)), width=30, height=28, corner_radius=14,
            fg_color=(COLORS["success"] if getattr(self.player, "is_looping", False) else COLORS["bg_light"]),
            hover_color=COLORS["accent"],
            command=self.toggle_loop
        )
        self.loop_btn.pack(side=tk.LEFT, padx=2)

        self.mute_btn = ctk.CTkButton(
            bottom_bar, text="", image=IconFactory.get("volume", (14, 14)), width=30, height=28, corner_radius=14,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            command=self.toggle_mute
        )
        self.mute_btn.pack(side=tk.LEFT, padx=2)

        # Mini Quality Selector
        self.quality_menu = ctk.CTkOptionMenu(
            bottom_bar, values=["Auto", "1080p", "720p", "480p", "360p"],
            width=68, height=28, corner_radius=14, font=ctk.CTkFont(size=9, weight="bold"),
            fg_color=COLORS["bg_light"], button_color=COLORS["accent"],
            command=self.change_quality
        )
        self.quality_menu.set("Auto")
        self.quality_menu.pack(side=tk.LEFT, padx=2)

        # Mini Subtitle Selector
        self.sub_menu = ctk.CTkOptionMenu(
            bottom_bar, values=["CC: Off", "CC: Auto", "CC: en", "Load SRT"],
            width=76, height=28, corner_radius=14, font=ctk.CTkFont(size=9, weight="bold"),
            fg_color=COLORS["bg_light"], button_color=COLORS["accent"],
            command=self.change_subtitle
        )
        self.sub_menu.set("CC: Auto")
        self.sub_menu.pack(side=tk.LEFT, padx=2)

        self.volume_slider = ModernSlider(
            bottom_bar, from_=0, to=100, command=lambda v: self.set_volume(int(v))
        )
        self.volume_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.volume_slider.set(self.player.volume)

        self.volume_label = ctk.CTkLabel(
            bottom_bar, text=f"{self.player.volume}%", font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COLORS["text_secondary"], width=35
        )
        self.volume_label.pack(side=tk.LEFT, padx=(0, 6))

    def paste_from_clipboard(self):
        try:
            txt = safe_get_clipboard(self.main_app.root)
            if txt:
                self.url_entry.delete(0, tk.END)
                self.url_entry.insert(0, txt)
        except Exception:
            pass

    def use_main_url(self):
        main_url = ""
        main_title = ""
        if hasattr(self.main_app, "url_entry"):
            main_url = self.main_app.url_entry.get().strip()
        if not main_url and hasattr(self.main_app, "player") and getattr(self.main_app.player, "current_url", None):
            main_url = getattr(self.main_app.player, "current_url", "")
        if hasattr(self.main_app.player, "current_title"):
            main_title = getattr(self.main_app.player, "current_title", "")

        if main_url:
            if hasattr(self.main_app, "player") and self.main_app.player:
                if hasattr(self.main_app.player, "pause"):
                    self.main_app.player.pause()
                elif hasattr(self.main_app.player, "stop"):
                    self.main_app.player.stop()
            if hasattr(self.main_app, "update_play_button"):
                self.main_app.update_play_button()

            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, main_url)
            self.play_url(main_url)
            if main_title:
                self.update_title(main_title)
        else:
            if hasattr(self.main_app, "show_notification"):
                self.main_app.show_notification("Mini Player", "No media is currently playing in main player")

    def seek_from_progress(self, percent):
        """Handle mouse click and drag seeking from mini player progress bar."""
        dur = self.player.get_duration() if hasattr(self.player, "get_duration") else getattr(self.player, "duration", 0)
        if dur > 0:
            target_sec = (percent / 100.0) * dur
            if hasattr(self, "time_current") and self.time_current and self.time_current.winfo_exists():
                self.time_current.configure(text=self.main_app._format_time(target_sec))
            self.player.seek(percent / 100.0)

    def play_url(self, url):
        clean_url = url.strip().strip('"').strip("'") if url else ""
        if not clean_url:
            return
        self.current_url = clean_url
        # Reset mini player progress bar and elapsed/duration labels immediately
        if hasattr(self, "progress_bar") and self.progress_bar:
            self.progress_bar.set(0)
        if hasattr(self, "time_current") and self.time_current and self.time_current.winfo_exists():
            self.time_current.configure(text="0:00")
        if hasattr(self, "time_total") and self.time_total and self.time_total.winfo_exists():
            self.time_total.configure(text="0:00")
        self.player.play_url(clean_url)
        t = getattr(self.player, "current_title", "") or os.path.basename(clean_url)
        self.update_title(t)
        self.update_play_button()

    def update_title(self, title):
        if hasattr(self, "title_label") and self.title_label and self.title_label.winfo_exists():
            self.title_label.configure(text=str(title)[:45])

    def update_play_button(self):
        if hasattr(self, "play_btn") and self.play_btn and self.play_btn.winfo_exists():
            is_playing = getattr(self.player, "is_playing", False)
            if self.player.vlc_available and getattr(self.player, "player", None):
                try:
                    state = self.player.player.get_state()
                    if state in (vlc.State.Playing, vlc.State.Buffering):
                        is_playing = True
                    elif state == vlc.State.Paused:
                        is_playing = False
                except Exception:
                    pass
            self.play_btn.configure(text="", image=IconFactory.get("pause" if is_playing else "play", (14, 14)))

    def update_mute_button(self):
        if hasattr(self, "mute_btn") and self.mute_btn and self.mute_btn.winfo_exists():
            is_muted = getattr(self.player, "is_muted", False) or self.player.volume == 0
            self.mute_btn.configure(text="", image=IconFactory.get("mute" if is_muted else "volume", (14, 14)))

    def change_quality(self, choice):
        """Change playback quality in mini player."""
        clean_q = choice.replace("Auto", "best").lower()
        self.player.selected_quality = clean_q
        cur_url = getattr(self.player, "current_url", None)
        if cur_url and str(cur_url).startswith("http"):
            cur_pos = getattr(self.player, "current_time", 0)
            self.play_url(cur_url)
            if cur_pos > 0:
                self.window.after(2000, lambda: self.player.seek(cur_pos))

    def change_subtitle(self, choice):
        """Change or load subtitle track in mini player."""
        if "Load" in choice:
            srt_path = filedialog.askopenfilename(
                title="Select Subtitle File",
                filetypes=[("Subtitle files", "*.srt *.vtt *.ass"), ("All files", "*.*")]
            )
            if srt_path:
                self.player.set_subtitle_file(srt_path)
        elif "Off" in choice:
            self.player.disable_subtitles()
        else:
            cur_url = getattr(self.player, "current_url", None)
            if cur_url and str(cur_url).startswith("http") and hasattr(self.main_app, "load_subtitles"):
                self.main_app.load_subtitles(cur_url, getattr(self.player, "current_title", ""), lang="en")

    def toggle_play(self):
        url = self.url_entry.get().strip() if hasattr(self, "url_entry") else ""
        cur = getattr(self.player, "current_url", "") or ""
        if url and (not cur or url != cur):
            self.play_url(url)
            return
        self.player.toggle_play_pause()
        self.update_play_button()

    def stop_video(self):
        self.player.stop()
        if hasattr(self, "progress_bar"):
            self.progress_bar.set(0)
        if hasattr(self, "time_current"):
            self.time_current.configure(text="0:00")
        self.update_play_button()

    def toggle_mute(self):
        if hasattr(self.player, "is_muted") and self.player.is_muted:
            self.player.unmute()
        else:
            self.player.mute()
        self.update_mute_button()

    def toggle_loop(self):
        if hasattr(self.player, "toggle_loop"):
            is_looping = self.player.toggle_loop()
            if hasattr(self, "loop_btn") and self.loop_btn and self.loop_btn.winfo_exists():
                self.loop_btn.configure(fg_color=(COLORS["success"] if is_looping else COLORS["bg_light"]))

    def set_volume(self, val):
        self.player.set_volume(val)
        if hasattr(self, "volume_label"):
            self.volume_label.configure(text=f"{val}%")

    def volume_up(self):
        new_vol = min(100, self.player.volume + 10)
        self.set_volume(new_vol)
        if hasattr(self, "volume_slider"):
            self.volume_slider.set(new_vol)

    def volume_down(self):
        new_vol = max(0, self.player.volume - 10)
        self.set_volume(new_vol)
        if hasattr(self, "volume_slider"):
            self.volume_slider.set(new_vol)

    def download_current(self):
        target = self.current_url or (self.url_entry.get().strip() if hasattr(self, "url_entry") else "")
        if target:
            self.main_app.show_download_dialog(target)

    def toggle_fullscreen(self):
        self.is_fullscreen = not getattr(self, "is_fullscreen", False)
        if self.is_fullscreen:
            self.normal_geometry = self.window.geometry()
            self.window.attributes("-fullscreen", True)
        else:
            self.window.attributes("-fullscreen", False)
            if hasattr(self, "normal_geometry") and self.normal_geometry:
                self.window.geometry(self.normal_geometry)

    def toggle_topmost(self):
        cur = self.window.attributes("-topmost")
        self.window.attributes("-topmost", not cur)

    def start_drag(self, event):
        self.is_dragging = True
        self.drag_start_x = event.x_root - self.window.winfo_x()
        self.drag_start_y = event.y_root - self.window.winfo_y()

    def on_drag(self, event):
        if self.is_dragging:
            x = event.x_root - self.drag_start_x
            y = event.y_root - self.drag_start_y
            self.window.geometry(f"+{x}+{y}")

    def show(self):
        if not self.window or not self.window.winfo_exists():
            self.create_window()
        if self.window:
            self.window.deiconify()
            self.is_visible = True

    def hide(self):
        if self.window:
            self.window.withdraw()
            self.is_visible = False

    def toggle(self):
        if self.is_visible:
            self.hide()
        else:
            self.show()

    def destroy(self):
        if self.player:
            self.player.cleanup()
        if self.window:
            try:
                self.window.destroy()
            except Exception:
                pass


class DownloadItem:
    """Clean, modern download item card with simple percentage, ETA, and post-download action buttons."""
    def __init__(self, parent, download_id, title, fmt, quality, app=None):
        self.parent = parent
        self.download_id = download_id
        self.title = title
        self.fmt = fmt
        self.quality = quality
        self.app = app
        self.filename = ""
        self.frame = ctk.CTkFrame(parent, fg_color=COLORS["surface"], corner_radius=10, border_width=1, border_color=COLORS.get("border", "#2E364A"))
        self.frame.pack(fill=tk.X, padx=6, pady=3)

        header_row = ctk.CTkFrame(self.frame, fg_color="transparent")
        header_row.pack(fill=tk.X, padx=12, pady=(6, 2))

        clean_title = title if len(title) <= 52 else title[:50] + "..."
        self.title_label = ctk.CTkLabel(
            header_row, text=clean_title, font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS["text_primary"], anchor="w"
        )
        self.title_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.badge_label = ctk.CTkLabel(
            header_row, text=f" {fmt.upper()} • {quality} ",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=COLORS["bg_light"], corner_radius=6,
            text_color=COLORS["accent"]
        )
        self.badge_label.pack(side=tk.RIGHT)

        self.progress = ModernProgressBar(self.frame)
        self.progress.pack(fill=tk.X, padx=12, pady=(4, 4))

        self.status_label = ctk.CTkLabel(
            self.frame, text="Starting download...",
            font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"], anchor="w"
        )
        self.status_label.pack(fill=tk.X, padx=12, pady=(0, 6))

    def update_progress(self, percent, eta_str, extra=""):
        try:
            val = float(percent)
            self.progress.set(val)
            pct_str = f"{val:.1f}%"
        except:
            pct_str = f"{percent}%"
        self.status_label.configure(
            text=f"Downloading: {pct_str}  |  {eta_str}"
        )

    def complete(self, filename, file_size, app=None):
        self.progress.set(100)
        self.filename = filename
        if app:
            self.app = app
        size_str = self._format_size(file_size)
        clean_name = os.path.basename(filename) if filename else "media"
        self.status_label.configure(
            text=f"Completed • {clean_name} ({size_str})",
            text_color=COLORS["success"]
        )
        if not hasattr(self, "action_bar"):
            self.action_bar = ctk.CTkFrame(self.frame, fg_color="transparent")
            self.action_bar.pack(fill=tk.X, padx=12, pady=(0, 6))

            ctk.CTkButton(
                self.action_bar, text=" Play", image=IconFactory.get("play", (13, 13)),
                width=75, height=26, corner_radius=13,
                fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                font=ctk.CTkFont(size=11, weight="bold"),
                command=self._play_file
            ).pack(side=tk.LEFT, padx=(0, 4))

            ctk.CTkButton(
                self.action_bar, text=" Folder", image=IconFactory.get("folder", (13, 13)),
                width=85, height=26, corner_radius=13,
                fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
                font=ctk.CTkFont(size=11, weight="bold"),
                command=self._open_folder
            ).pack(side=tk.LEFT, padx=4)

            ctk.CTkButton(
                self.action_bar, text=" Copy Path", image=IconFactory.get("copy", (13, 13)),
                width=95, height=26, corner_radius=13,
                fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
                font=ctk.CTkFont(size=11, weight="bold"),
                command=self._copy_path
            ).pack(side=tk.LEFT, padx=4)

    def _play_file(self):
        if self.filename and os.path.exists(self.filename):
            target_app = self.app
            if target_app and hasattr(target_app, "play_downloaded_file"):
                target_app.play_downloaded_file(self.filename)
            elif target_app and hasattr(target_app, "player"):
                target_app.player.play_url(self.filename)
                if hasattr(target_app, "url_entry"):
                    target_app.url_entry.delete(0, tk.END)
                    target_app.url_entry.insert(0, self.filename)
                target_app.tab_view.set("Player")

    def _open_folder(self):
        if self.filename and os.path.exists(self.filename):
            try:
                subprocess.Popen(f'explorer /select,"{os.path.normpath(self.filename)}"')
                return
            except Exception:
                try:
                    os.startfile(os.path.dirname(self.filename))
                    return
                except Exception:
                    pass
        download_dir = os.path.dirname(self.filename) if self.filename else os.getcwd()
        try:
            os.startfile(download_dir)
        except Exception as e:
            logger.error(f"Failed to open download folder: {e}")

    def _copy_path(self):
        if self.filename:
            try:
                safe_set_clipboard(self.filename, self.frame)
            except Exception:
                pass

    def fail(self, error):
        self.progress.set(0)
        self.status_label.configure(
            text=f"Failed: {error}",
            text_color=COLORS["error"]
        )

    def _format_size(self, size_bytes):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB" 


class OfflineCacheManager:
    """Manages offline cached videos and local media library with live search and sort."""
    VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".flv", ".mpv", ".m4v", ".wmv", ".mp3", ".wav", ".m4a", ".flac"}

    def __init__(self, cache_path):
        self.cache_path = cache_path
        self.index_file = os.path.join(cache_path, "cache_index.json")
        self.cache_index = self._load_index()

    def _load_index(self):
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_index(self):
        try:
            os.makedirs(self.cache_path, exist_ok=True)
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(self.cache_index, f, indent=2)
        except Exception as e:
            print(f"Cache index save notice: {e}")

    def add_to_cache(self, url, title, filepath, source="download"):
        """Add a video or local file to the offline cache index."""
        if not os.path.exists(filepath):
            return
        file_size = os.path.getsize(filepath)
        key = filepath if (not url or url == filepath) else url
        self.cache_index[key] = {
            "title": title or os.path.splitext(os.path.basename(filepath))[0],
            "filepath": filepath,
            "size": file_size,
            "timestamp": time.time(),
            "source": source,
            "format": os.path.splitext(filepath)[1].lower().lstrip("."),
        }
        self._save_index()

    def scan_directory(self, dir_path):
        """Scan a folder and add all supported offline video/audio files to library."""
        added = 0
        if not os.path.exists(dir_path):
            return added
        try:
            for root, dirs, files in os.walk(dir_path):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in self.VIDEO_EXTS:
                        full_p = os.path.join(root, f)
                        if full_p not in self.cache_index:
                            self.add_to_cache(full_p, os.path.splitext(f)[0], full_p, source="scan")
                            added += 1
        except Exception as e:
            print(f"Scan directory error: {e}")
        return added

    def get_filtered(self, search_query="", sort_by="date_desc"):
        """Return list of cached video items filtered by search query and sorted."""
        items = []
        for url, info in list(self.cache_index.items()):
            fp = info.get("filepath", "")
            if os.path.exists(fp):
                items.append({"url": url, **info})
            else:
                pass

        if search_query:
            q = search_query.lower().strip()
            items = [
                it for it in items
                if q in it.get("title", "").lower()
                or q in it.get("filepath", "").lower()
                or q in it.get("format", "").lower()
            ]

        if sort_by == "date_desc":
            items.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        elif sort_by == "date_asc":
            items.sort(key=lambda x: x.get("timestamp", 0))
        elif sort_by == "name_asc":
            items.sort(key=lambda x: x.get("title", "").lower())
        elif sort_by == "name_desc":
            items.sort(key=lambda x: x.get("title", "").lower(), reverse=True)
        elif sort_by == "size_desc":
            items.sort(key=lambda x: x.get("size", 0), reverse=True)
        elif sort_by == "size_asc":
            items.sort(key=lambda x: x.get("size", 0))

        return items

    def clear_cache(self):
        """Delete all cached files and reset index."""
        for info in self.cache_index.values():
            try:
                if os.path.exists(info["filepath"]) and info.get("source") == "download":
                    os.remove(info["filepath"])
            except:
                pass
        self.cache_index = {}
        self._save_index()

    def get_all_cached(self):
        """Return list of cached video info dictionaries."""
        return self.get_filtered()

    def get_cached_path(self, url):
        info = self.cache_index.get(url)
        if info and os.path.exists(info.get("filepath", "")):
            return info.get("filepath")
        return None

    def is_cached(self, url):
        return self.get_cached_path(url) is not None


class ModelLoadingDialog:
    """Simple dialog with progress bar for model downloads with proper title bar icon."""
    def __init__(self, parent, title="Downloading Model"):
        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("420x150")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        set_window_icon(self.dialog)
        self.dialog.after(80, lambda: set_window_icon(self.dialog) if (hasattr(self.dialog, "winfo_exists") and self.dialog.winfo_exists()) else None)
        self.dialog.after(250, lambda: set_window_icon(self.dialog) if (hasattr(self.dialog, "winfo_exists") and self.dialog.winfo_exists()) else None)
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - 210
        y = (self.dialog.winfo_screenheight() // 2) - 75
        self.dialog.geometry(f"+{x}+{y}")

        header_frame = ctk.CTkFrame(self.dialog, fg_color="transparent")
        header_frame.pack(pady=(16, 4))

        kupido_img = IconFactory.get("kupido", (22, 22))
        if kupido_img:
            icon_label = ctk.CTkLabel(header_frame, image=kupido_img, text="")
            icon_label.pack(side=tk.LEFT, padx=(0, 8))

        self.title_label = ctk.CTkLabel(
            header_frame, text=title, font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["accent_light"]
        )
        self.title_label.pack(side=tk.LEFT)

        self.label = ctk.CTkLabel(
            self.dialog, text="Starting download...", font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"]
        )
        self.label.pack(pady=(2, 8))

        self.progress = ModernProgressBar(self.dialog)
        self.progress.pack(fill=tk.X, padx=20, pady=(4, 12))

    def update_progress(self, percent, message):
        try:
            self.progress.set(percent)
            self.label.configure(text=message)
        except tk.TclError:
            # Dialog has been destroyed – ignore
            pass

    def close(self):
        self.dialog.destroy()


class CacheVideoFrame:
    """Modern card for offline video/audio items with play, hover, and explorer reveal."""
    def __init__(self, parent, video_info, app):
        self.app = app
        self.video_info = video_info
        self.url = video_info["url"]
        self.filepath = video_info["filepath"]
        title = video_info.get("title", "Unknown")
        size = video_info.get("size", 0)
        size_str = self._format_size(size)
        fmt = video_info.get("format", os.path.splitext(self.filepath)[1].lstrip(".")).upper() or "VIDEO"

        self.frame = ctk.CTkFrame(parent, fg_color=COLORS["surface"], corner_radius=10, border_width=1, border_color=COLORS.get("border", "#2E364A"))
        self.frame.pack(fill=tk.X, padx=5, pady=3)

        info_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        info_frame.pack(fill=tk.X, padx=12, pady=(8, 4))

        clean_title = title if len(title) <= 50 else title[:48] + "..."
        self.title_label = ctk.CTkLabel(
            info_frame, text=clean_title, font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS["text_primary"], anchor="w"
        )
        self.title_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        meta_badge = ctk.CTkLabel(
            info_frame, text=f" {fmt} • {size_str} ", font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=COLORS["bg_light"], corner_radius=6, text_color=COLORS["accent"]
        )
        meta_badge.pack(side=tk.RIGHT)

        btn_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        btn_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

        ctk.CTkButton(
            btn_frame, text=" Play", image=IconFactory.get("play", (13, 13)),
            width=75, height=28, corner_radius=14,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.play_cached
        ).pack(side=tk.LEFT, padx=2)

        ctk.CTkButton(
            btn_frame, text=" Mini Player", image=IconFactory.get("pip", (13, 13)),
            width=100, height=28, corner_radius=14,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.play_hover
        ).pack(side=tk.LEFT, padx=2)

        ctk.CTkButton(
            btn_frame, text=" Reveal", image=IconFactory.get("folder", (13, 13)),
            width=80, height=28, corner_radius=14,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.reveal_file
        ).pack(side=tk.LEFT, padx=2)

        ctk.CTkButton(
            btn_frame, text=" Delete", image=IconFactory.get("close", (13, 13)),
            width=80, height=28, corner_radius=14,
            fg_color=COLORS["bg_light"], hover_color=COLORS["error"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.delete_cached
        ).pack(side=tk.RIGHT, padx=2)

    def _format_size(self, size_bytes):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def play_cached(self):
        """Play the video directly in offline mode."""
        if os.path.exists(self.filepath):
            self.app.url_entry.delete(0, tk.END)
            self.app.url_entry.insert(0, self.filepath)
            self.app.player.play_url(self.filepath)
            self.app.show_window()
            self.app.tab_view.set("Player")
        else:
            self.app.show_notification("Error", "Video file missing on disk")

    def play_hover(self):
        """Play in floating mini-player."""
        if os.path.exists(self.filepath):
            if not self.app.hover_window.is_visible:
                self.app.hover_window.show()
            self.app.hover_window.play_url(self.filepath)
        else:
            self.app.show_notification("Error", "Video file missing on disk")

    def reveal_file(self):
        """Open containing folder in Explorer with file selected."""
        try:
            if os.path.exists(self.filepath):
                subprocess.Popen(f'explorer /select,"{os.path.abspath(self.filepath)}"')
        except Exception as e:
            self.app.show_notification("Notice", f"Could not open explorer: {e}")

    def delete_cached(self):
        try:
            if os.path.exists(self.filepath) and self.video_info.get("source") == "download":
                os.remove(self.filepath)
            self.app.cache_manager.cache_index.pop(self.url, None)
            self.app.cache_manager._save_index()
            self.frame.destroy()
            self.app.show_notification("Cache", "Item removed from library")
        except Exception as e:
            self.app.show_notification("Error", f"Could not delete: {e}")


# ==================== Main Application ====================

class KupidoApp:
    def __init__(self, root, splash=None):
        self.root = root          # use the root passed from main
        self.splash = splash
        if splash:
            splash.update_progress(0, "Starting Kupido...")

        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("kupido.player")
        except:
            pass

        if splash:
            splash.update_progress(5, "Loading settings...")
        self.settings = Settings()
        self.player = VideoPlayer(self.settings, player_type="main")
        self.player.main_app = self
        self.transcriber = Transcriber()
        self.transcriber.set_models_path(self.settings.models_path)
        self.adblocker = AdBlocker()
        self.cache_manager = OfflineCacheManager(self.settings.cache_path)

        if splash:
            splash.update_progress(10, "Creating UI...")
        # Do NOT create self.root here – it's already passed in
        self.icon = None
        self.icon_thread = None
        self.icon_running = True
        self.search_history = []
        self.download_items = {}
        self.current_transcription = None
        self._last_update = 0
        self.offline_mode = None
        self.cache_frames = []

        self.hover_window = ModernHoverWindow(self)
        # Removed splash.log calls

        atexit.register(self.cleanup)

        self.load_history()
        if splash:
            splash.update_progress(20, "Setting up hotkeys...")
        self.setup_hotkeys()
        self.offline_mode = tk.BooleanVar(value=False)

        if splash:
            splash.update_progress(30, "Building main window...")
        self.create_ui()          # this will use self.root

        if splash:
            splash.update_progress(70, "Checking models...")
       
        if splash:
            splash.update_progress(90, "Creating system tray icon...")
        self.create_tray_icon()
        self.start_playback_update_loop()

        if self.adblocker.enable_adblock():
            print("✅ Ad blocking enabled")

        # Background verification for FFmpeg
        if not ToolManager.is_ffmpeg_available():
            threading.Thread(target=lambda: ToolManager.download_portable_ffmpeg(), daemon=True).start()

        if splash:
            splash.update_progress(100, "Ready!")

    def cleanup(self):
        if self.player:
            self.player.cleanup()
        if self.hover_window:
            self.hover_window.destroy()
        if self.icon:
            self.icon.stop()

    def load_history(self):
        try:
            if os.path.exists("kupido_history.json"):
                with open("kupido_history.json", "r") as f:
                    self.search_history = json.load(f)
        except:
            self.search_history = []

    def save_history(self):
        try:
            with open("kupido_history.json", "w") as f:
                json.dump(self.search_history[-100:], f)
        except:
            pass

    def add_to_history(self, url, title):
        for item in self.search_history:
            if item["url"] == url:
                return
        self.search_history.append(
            {"url": url, "title": title, "timestamp": time.time()}
        )
        self.save_history()
        self.update_history_display()

    def setup_hotkeys(self):
        """Configure safe local window keyboard shortcuts without global typing hijack."""
        try:
            self.root.bind("<space>", lambda e: self.handle_main_play_pause())
            self.root.bind("<Left>", lambda e: self.player.seek_backward(10) if self.player else None)
            self.root.bind("<Right>", lambda e: self.player.seek_forward(10) if self.player else None)
            self.root.bind("<Up>", lambda e: self.change_volume(min(100, self.player.volume + 5)) if self.player else None)
            self.root.bind("<Down>", lambda e: self.change_volume(max(0, self.player.volume - 5)) if self.player else None)
            self.root.bind("<m>", lambda e: self.player.toggle_mute() if self.player else None)
            self.root.bind("<M>", lambda e: self.player.toggle_mute() if self.player else None)
            self.root.bind("<f>", lambda e: self.toggle_fullscreen())
            self.root.bind("<F>", lambda e: self.toggle_fullscreen())
            self.root.bind("<F11>", lambda e: self.toggle_fullscreen())
            self.root.bind("<l>", lambda e: self.toggle_loop())
            self.root.bind("<L>", lambda e: self.toggle_loop())
            self.root.bind("<Control-h>", lambda e: self.toggle_hover())
            self.root.bind("<Control-H>", lambda e: self.toggle_hover())
            self.root.bind("<Control-d>", lambda e: self.show_download_dialog())
            self.root.bind("<Control-D>", lambda e: self.show_download_dialog())
            self.root.bind("<Control-q>", lambda e: self.quit_app())
            self.root.bind("<Control-Q>", lambda e: self.quit_app())
            self.root.bind("<Escape>", lambda e: self.toggle_fullscreen() if getattr(self.player, "is_fullscreen", False) else None)
        except Exception as e:
            print(f"Hotkeys notice: {e}")

    def toggle_window_visibility(self):
        if self.root:
            if self.root.state() == "normal" and self.root.winfo_viewable():
                self.hide_window()
            else:
                self.show_window()

    def mute_both(self):
        self.player.mute()
        if self.hover_window and self.hover_window.is_visible:
            self.hover_window.player.mute()

    def unmute_both(self):
        self.player.unmute()
        if self.hover_window and self.hover_window.is_visible:
            self.hover_window.player.unmute()

    def check_and_load_models(self):
        models_to_download = []

        whisper_path = os.path.join(self.settings.models_path, "medium.pt")
        if (
            WHISPER_AVAILABLE
            and not os.path.exists(whisper_path)
            and not self.settings.models_downloaded.get("whisper", False)
        ):
            models_to_download.append("whisper_medium")

        tinyllama_path = os.path.join(
            self.settings.models_path, "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
        )
        if (
            LLAMA_CPP_AVAILABLE
            and not os.path.exists(tinyllama_path)
            and not self.settings.models_downloaded.get("tinyllama", False)
        ):
            models_to_download.append("tinyllama")

        if models_to_download:
            self.model_dialog = ModelLoadingDialog(self.root)

            def download_models():
                for model in models_to_download:
                    if model == "whisper_medium":

                        def whisper_progress(p, m):
                            self.root.after_idle(
                                lambda: self.model_dialog.update_progress(p, m)
                            )

                        success = ModelDownloader.download_model(
                            "whisper_medium", whisper_path, whisper_progress
                        )
                        if success:
                            self.settings.models_downloaded["whisper"] = True
                            self.settings.save()
                        else:
                            self.root.after_idle(
                                lambda: self.show_notification(
                                    "Download Failed", "Whisper model download failed."
                                )
                            )

                    elif model == "tinyllama":

                        def tiny_progress(p, m):
                            self.root.after_idle(
                                lambda: self.model_dialog.update_progress(p, m)
                            )

                        success = ModelDownloader.download_model(
                            "tinyllama", tinyllama_path, tiny_progress
                        )
                        if success:
                            self.settings.models_downloaded["tinyllama"] = True
                            self.settings.save()
                        else:
                            self.root.after_idle(
                                lambda: self.show_notification(
                                    "Download Failed",
                                    "TinyLlama model download failed.",
                                )
                            )

                self.root.after_idle(self.model_dialog.close)
                if all(self.settings.models_downloaded.values()):
                    self.root.after_idle(
                        lambda: self.show_notification(
                            "Models Ready",
                            "All required models downloaded successfully!",
                        )
                    )

            threading.Thread(target=download_models, daemon=True).start()

    def create_tray_icon(self):
        """Minimal system tray with only essential playback and window controls using original kupido logo."""
        try:
            icon_img = None
            png_p = resource_path("kupido.png")
            if os.path.exists(png_p):
                try:
                    icon_img = Image.open(png_p).resize((64, 64), Image.Resampling.LANCZOS)
                except Exception:
                    icon_img = None

            if not icon_img:
                ico_p = resource_path("kupido.ico")
                if os.path.exists(ico_p):
                    try:
                        icon_img = Image.open(ico_p).resize((64, 64), Image.Resampling.LANCZOS)
                    except Exception:
                        icon_img = None

            if not icon_img:
                icon_img = Image.new("RGBA", (64, 64), color=(37, 99, 235, 255))
                dc = ImageDraw.Draw(icon_img)
                dc.polygon([(20, 14), (20, 50), (48, 32)], fill="white")

            menu = pystray.Menu(
                item("▶ / ⏸ Play / Pause", lambda: self.handle_main_play_pause()),
                item("🔊 Volume Up (+10%)", lambda: self.change_volume(min(100, self.player.volume + 10))),
                item("🔉 Volume Down (-10%)", lambda: self.change_volume(max(0, self.player.volume - 10))),
                item("🔇 Mute / Unmute", lambda: self.player.toggle_mute() if self.player else None),
                item("🔁 Loop On/Off", lambda: self.toggle_loop()),
                item("---", None),
                item("🪟 Open / Close Kupido", lambda: self.toggle_window_visibility()),
                item("❌ Exit Kupido", lambda: self.quit_app()),
            )

            self.icon = pystray.Icon("kupido", icon_img, f"Kupido v{APP_VERSION}", menu)
            self.icon_thread = threading.Thread(target=self.icon.run, daemon=True)
            self.icon_thread.start()
            print("[OK] Minimal system tray icon created with original logo")
        except Exception as e:
            print(f"[ERROR] Tray icon error: {e}")

    def change_volume(self, value):
        self.player.set_volume(int(value))
        if hasattr(self, "volume_slider"):
            self.volume_slider.set(value)

    def show_download_tab(self):
        self.show_window()
        self.tab_view.set("Downloads")

    def show_history_tab(self):
        self.show_window()
        self.tab_view.set("History")

    def show_transcribe_tab(self):
        self.show_window()
        self.tab_view.set("Transcribe")

    def show_settings_tab(self):
        self.show_window()
        self.tab_view.set("Settings")

    def show_info_tab(self):
        self.show_window()
        self.tab_view.set("Info")

    def show_cache_tab(self):
        self.show_window()
        self.tab_view.set("Offline Cache")
        self.update_cache_display()

    def load_icon(self):
        """Load original kupido brand icon safely with fallback."""
        for fn in ["kupido.png", "kupido.ico"]:
            p = resource_path(fn)
            if os.path.exists(p):
                try:
                    return Image.open(p)
                except Exception:
                    pass
        img = Image.new("RGBA", (32, 32), color=(37, 99, 235, 255))
        return img

    def create_ui(self):
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1200x750")
        self.root.minsize(900, 600)

        try:
            icon_img = self.load_icon().resize((32, 32))
            icon_photo = ImageTk.PhotoImage(icon_img)
            self.root.iconphoto(True, icon_photo)
        except:
            pass

        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.create_modern_toolbar()
        self.create_modern_tabs()
        self.create_modern_status_bar()

        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)

    def create_modern_toolbar(self):
        """Top navigation bar starting immediately with search, white-stroke icons, and top-right terminate button."""
        toolbar = ctk.CTkFrame(self.root, height=54, fg_color=COLORS["surface"], corner_radius=0)
        toolbar.grid(row=0, column=0, padx=0, pady=0, sticky="ew")
        toolbar.grid_columnconfigure(0, weight=1)
        toolbar.pack_propagate(False)

        # Left / Center: Spacious Search Bar immediately on start (no bulky text/film logo)
        search_container = ctk.CTkFrame(toolbar, fg_color="transparent")
        search_container.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(14, 8), pady=8)

        self.url_entry = ModernEntry(search_container, placeholder="Search or paste YouTube URL, media stream, or local video path...")
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        if hasattr(self.url_entry, "entry"):
            self.url_entry.entry.bind("<Return>", lambda e: self.play_url())

        # Clean white stroke Paste button
        ctk.CTkButton(
            search_container, text=" Paste", image=IconFactory.get("paste", (16, 16)),
            width=76, height=34, corner_radius=17,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.paste_and_play
        ).pack(side=tk.LEFT, padx=3)

        # Clean white stroke Play button
        self.play_btn = ctk.CTkButton(
            search_container, text=" Play", image=IconFactory.get("play", (16, 16)),
            width=76, height=34, corner_radius=17,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.handle_main_play_pause
        )
        self.play_btn.pack(side=tk.LEFT, padx=3)

        # Right Action Buttons
        controls_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        controls_frame.pack(side=tk.RIGHT, padx=(4, 14), pady=8)

        # Offline toggle switch
        self.offline_switch = ModernSwitch(
            controls_frame, text="Offline", variable=self.offline_mode,
            command=self.toggle_offline_mode
        )
        self.offline_switch.pack(side=tk.LEFT, padx=(4, 6))

        # Hover Mini-player button (white stroke icon)
        self.hover_btn = ctk.CTkButton(
            controls_frame, text="", image=IconFactory.get("pip", (18, 18)),
            width=38, height=34, corner_radius=17,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            command=self.toggle_hover
        )
        self.hover_btn.pack(side=tk.LEFT, padx=2)

        # Loop button (white stroke icon)
        self.loop_btn = ctk.CTkButton(
            controls_frame, text="", image=IconFactory.get("loop", (18, 18)),
            width=38, height=34, corner_radius=17,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            command=self.toggle_loop
        )
        self.loop_btn.pack(side=tk.LEFT, padx=2)

        # Download button (white stroke icon)
        self.dl_btn = ctk.CTkButton(
            controls_frame, text="", image=IconFactory.get("download", (18, 18)),
            width=38, height=34, corner_radius=17,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            command=self.show_download_dialog
        )
        self.dl_btn.pack(side=tk.LEFT, padx=2)

        # Fullscreen button (white stroke icon)
        self.fs_btn = ctk.CTkButton(
            controls_frame, text="", image=IconFactory.get("fullscreen", (18, 18)),
            width=38, height=34, corner_radius=17,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            command=self.toggle_fullscreen
        )
        self.fs_btn.pack(side=tk.LEFT, padx=2)

        # Top-Right Terminate / Close Button
        self.term_btn = ctk.CTkButton(
            controls_frame, text=" ✕", width=38, height=34, corner_radius=17,
            fg_color="#B91C1C", hover_color="#EF4444",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.quit_app
        )
        self.term_btn.pack(side=tk.LEFT, padx=(4, 0))

    def paste_and_play(self):
        """Get link from clipboard, insert into search/URL entry, and start playback."""
        try:
            cb = safe_get_clipboard(self.root)
            if cb:
                if hasattr(self, "url_entry"):
                    self.url_entry.delete(0, tk.END)
                    self.url_entry.insert(0, cb)
                self.play_url()
            else:
                curr = self.url_entry.get().strip() if hasattr(self, "url_entry") else ""
                if curr:
                    self.play_url()
                else:
                    self.show_notification("Notice", "Clipboard is empty or does not contain text")
        except Exception:
            curr = self.url_entry.get().strip() if hasattr(self, "url_entry") else ""
            if curr:
                self.play_url()
            else:
                self.show_notification("Notice", "Please paste or enter a media link")

    def create_modern_tabs(self):
        self.tab_view = ctk.CTkTabview(
            self.root,
            fg_color=COLORS["bg_dark"],
            segmented_button_fg_color=COLORS["surface"],
            segmented_button_selected_color=COLORS["accent"],
            segmented_button_selected_hover_color=COLORS["accent_hover"],
        )
        self.tab_view.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        self.player_tab = self.tab_view.add("Player")
        self.playlist_tab = self.tab_view.add("Playlist")
        self.download_tab = self.tab_view.add("Downloads")
        self.history_tab = self.tab_view.add("History")
        self.transcribe_tab = self.tab_view.add("Transcribe")
        self.cache_tab = self.tab_view.add("Offline Cache")
        self.settings_tab = self.tab_view.add("Settings")
        self.info_tab = self.tab_view.add("Info")

        self.create_modern_player_tab()
        self.create_modern_playlist_tab()
        self.create_modern_download_tab()
        self.create_modern_history_tab()
        self.create_modern_transcribe_tab()
        self.create_modern_cache_tab()
        self.create_modern_settings_tab()
        self.create_modern_info_tab()

    def create_modern_playlist_tab(self):
        """Playlist Maker tab with Playlist Name, Group, live search, save/load JSON offline, and single/bulk deletion."""
        self.playlist_tab.grid_columnconfigure(0, weight=1)
        self.playlist_tab.grid_rowconfigure(3, weight=1)

        # 1. Top Metadata Bar: Playlist Name & Playlist Group
        meta_bar = ctk.CTkFrame(self.playlist_tab, fg_color=COLORS["surface"], corner_radius=12)
        meta_bar.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))

        ctk.CTkLabel(
            meta_bar, text="Playlist Name:", font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["accent_light"]
        ).pack(side=tk.LEFT, padx=(12, 4), pady=6)

        self.pl_name_var = tk.StringVar(value="My Playlist")
        self.pl_name_entry = ctk.CTkEntry(
            meta_bar, textvariable=self.pl_name_var, width=160, height=28,
            corner_radius=14, fg_color=COLORS["bg_light"], border_width=0
        )
        self.pl_name_entry.pack(side=tk.LEFT, padx=(0, 10), pady=6)
        self.pl_name_var.trace_add("write", lambda *args: self._save_offline_playlist())

        ctk.CTkLabel(
            meta_bar, text="Group:", font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["accent_light"]
        ).pack(side=tk.LEFT, padx=(4, 4), pady=6)

        self.pl_group_var = tk.StringVar(value="Favorites")
        self.pl_group_combo = ctk.CTkComboBox(
            meta_bar, values=["Favorites", "Music", "Podcasts", "Videos", "Lectures", "General"],
            variable=self.pl_group_var, width=120, height=28, corner_radius=14,
            fg_color=COLORS["bg_light"], button_color=COLORS["accent"]
        )
        self.pl_group_combo.pack(side=tk.LEFT, padx=(0, 10), pady=6)
        self.pl_group_var.trace_add("write", lambda *args: self._save_offline_playlist())

        # Save & Load JSON Buttons in Meta Bar
        ctk.CTkButton(
            meta_bar, text=" Save JSON", image=IconFactory.get("download", (13, 13)),
            width=95, height=28, corner_radius=14,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.save_playlist_json
        ).pack(side=tk.RIGHT, padx=(4, 12), pady=6)

        ctk.CTkButton(
            meta_bar, text=" Load JSON", image=IconFactory.get("folder", (13, 13)),
            width=95, height=28, corner_radius=14,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.load_playlist_json
        ).pack(side=tk.RIGHT, padx=4, pady=6)

        # 2. Add Item Controls Bar
        top_bar = ctk.CTkFrame(self.playlist_tab, fg_color="transparent")
        top_bar.grid(row=1, column=0, sticky="ew", padx=12, pady=(2, 4))

        self.pl_add_entry = ctk.CTkEntry(
            top_bar, placeholder_text="Enter video URL or local file path to add...",
            height=32, corner_radius=16, border_width=0, fg_color=COLORS["surface"]
        )
        self.pl_add_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        ctk.CTkButton(
            top_bar, text=" Add", image=IconFactory.get("play", (13, 13)),
            width=75, height=32, corner_radius=16,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.add_entry_to_playlist
        ).pack(side=tk.LEFT, padx=3)

        ctk.CTkButton(
            top_bar, text=" Add Current", image=IconFactory.get("play", (13, 13)),
            width=110, height=32, corner_radius=16,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.add_current_to_playlist
        ).pack(side=tk.LEFT, padx=3)

        ctk.CTkButton(
            top_bar, text=" Remove All", image=IconFactory.get("close", (13, 13)),
            width=105, height=32, corner_radius=16,
            fg_color=COLORS["bg_light"], hover_color=COLORS["error"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.clear_all_playlist
        ).pack(side=tk.LEFT, padx=3)

        # 3. Filter Bar & Options Row
        filter_bar = ctk.CTkFrame(self.playlist_tab, fg_color="transparent")
        filter_bar.grid(row=2, column=0, sticky="ew", padx=12, pady=(2, 6))

        self.pl_search_var = tk.StringVar()
        self.pl_search_entry = ctk.CTkEntry(
            filter_bar, placeholder_text="Search playlist by title, URL or group...",
            textvariable=self.pl_search_var, width=240, height=30, corner_radius=15,
            border_width=0, fg_color=COLORS["surface"]
        )
        self.pl_search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.pl_search_var.trace_add("write", lambda *args: self.render_playlist_items())

        # Filter by Group
        self.pl_filter_group_var = tk.StringVar(value="All Groups")
        self.pl_filter_menu = ctk.CTkOptionMenu(
            filter_bar, values=["All Groups", "Favorites", "Music", "Podcasts", "Videos", "Lectures", "General"],
            variable=self.pl_filter_group_var, width=115, height=30, corner_radius=15,
            fg_color=COLORS["surface"], button_color=COLORS["accent"],
            command=lambda v: self.render_playlist_items()
        )
        self.pl_filter_menu.pack(side=tk.LEFT, padx=(0, 6))

        self.pl_count_label = ctk.CTkLabel(
            filter_bar, text="0 items", font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLORS["text_secondary"]
        )
        self.pl_count_label.pack(side=tk.LEFT, padx=6)

        self.pl_autoplay_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            filter_bar, text="Auto-play next", variable=self.pl_autoplay_var,
            font=ctk.CTkFont(size=11), fg_color=COLORS["accent"]
        ).pack(side=tk.RIGHT, padx=4)

        # 4. Scrollable List of Items
        self.pl_scroll = ctk.CTkScrollableFrame(
            self.playlist_tab, fg_color=COLORS["bg_dark"], corner_radius=12
        )
        self.pl_scroll.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 10))
        self.pl_scroll.grid_columnconfigure(0, weight=1)

        self.playlist_items = []
        self.current_playlist_index = -1
        self._load_offline_playlist()
        self.render_playlist_items()

    def _get_offline_playlist_path(self):
        try:
            base_dir = getattr(self.settings, "cache_path", "") or os.path.dirname(os.path.abspath(__file__))
            os.makedirs(base_dir, exist_ok=True)
            return os.path.join(base_dir, "playlist_offline.json")
        except Exception:
            return "playlist_offline.json"

    def _load_offline_playlist(self):
        p = self._get_offline_playlist_path()
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    if hasattr(self, "pl_name_var"):
                        self.pl_name_var.set(data.get("playlist_name", "My Playlist"))
                    if hasattr(self, "pl_group_var"):
                        self.pl_group_var.set(data.get("playlist_group", "Favorites"))
                    self.playlist_items = data.get("items", [])
                elif isinstance(data, list):
                    self.playlist_items = data
            except Exception:
                self.playlist_items = []

    def _save_offline_playlist(self):
        p = self._get_offline_playlist_path()
        try:
            name = self.pl_name_var.get().strip() if hasattr(self, "pl_name_var") else "My Playlist"
            group = self.pl_group_var.get().strip() if hasattr(self, "pl_group_var") else "Favorites"
            payload = {
                "playlist_name": name,
                "playlist_group": group,
                "items": self.playlist_items,
            }
            with open(p, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            print(f"Playlist save error: {e}")

    def add_entry_to_playlist(self):
        val = self.pl_add_entry.get().strip() if hasattr(self, "pl_add_entry") else ""
        if not val:
            self.show_notification("Playlist", "Please enter a URL or file path")
            return
        title = os.path.splitext(os.path.basename(val))[0] or val
        group = self.pl_group_var.get().strip() if hasattr(self, "pl_group_var") else "Favorites"
        item = {
            "id": f"pl_{int(time.time() * 1000)}",
            "title": title,
            "url": val,
            "group": group or "General",
            "added_at": time.time(),
        }
        self.playlist_items.append(item)
        self._save_offline_playlist()
        self.pl_add_entry.delete(0, tk.END)
        self.render_playlist_items()
        self.show_notification("Playlist", f"Added to {group}: {title[:30]}")

    def add_current_to_playlist(self):
        url = getattr(self.player, "current_url", "") or (self.url_entry.get().strip() if hasattr(self, "url_entry") else "")
        if not url:
            self.show_notification("Playlist", "No video currently playing")
            return
        title = getattr(self.player, "current_title", "") or os.path.splitext(os.path.basename(url))[0] or url
        group = self.pl_group_var.get().strip() if hasattr(self, "pl_group_var") else "Favorites"
        item = {
            "id": f"pl_{int(time.time() * 1000)}",
            "title": title,
            "url": url,
            "group": group or "General",
            "added_at": time.time(),
        }
        self.playlist_items.append(item)
        self._save_offline_playlist()
        self.render_playlist_items()
        self.show_notification("Playlist", f"Added to {group}: {title[:30]}")

    def remove_playlist_item(self, item_id):
        self.playlist_items = [it for it in self.playlist_items if it.get("id") != item_id]
        self._save_offline_playlist()
        self.render_playlist_items()

    def clear_all_playlist(self):
        q = self.pl_search_var.get().strip().lower() if hasattr(self, "pl_search_var") else ""
        grp_filter = self.pl_filter_group_var.get() if hasattr(self, "pl_filter_group_var") else "All Groups"
        if q or grp_filter != "All Groups":
            # If search or group filter is active, remove only matching items
            self.playlist_items = [
                it for it in self.playlist_items
                if (q and (q not in it.get("title", "").lower() and q not in it.get("url", "").lower()))
                or (grp_filter != "All Groups" and it.get("group", "General") != grp_filter)
            ]
        else:
            self.playlist_items = []
        self._save_offline_playlist()
        self.render_playlist_items()
        self.show_notification("Playlist", "Playlist cleared")

    def save_playlist_json(self):
        name = self.pl_name_var.get().strip() if hasattr(self, "pl_name_var") else "My Playlist"
        fn = filedialog.asksaveasfilename(
            title="Save Playlist JSON Offline",
            initialfile=f"{name.replace(' ', '_')}.json",
            defaultextension=".json",
            filetypes=[("JSON Playlist", "*.json"), ("All Files", "*.*")]
        )
        if fn:
            try:
                group = self.pl_group_var.get().strip() if hasattr(self, "pl_group_var") else "Favorites"
                payload = {
                    "playlist_name": name,
                    "playlist_group": group,
                    "items": self.playlist_items,
                }
                with open(fn, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
                self.show_notification("Playlist", f"Saved '{name}' ({len(self.playlist_items)} items)")
            except Exception as e:
                self.show_notification("Error", f"Failed saving JSON: {e}")

    def load_playlist_json(self):
        fn = filedialog.askopenfilename(
            title="Load Playlist JSON Offline",
            filetypes=[("JSON Playlist", "*.json"), ("All Files", "*.*")]
        )
        if fn and os.path.exists(fn):
            try:
                with open(fn, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    name = loaded.get("playlist_name", "Loaded Playlist")
                    group = loaded.get("playlist_group", "General")
                    items = loaded.get("items", [])
                    if hasattr(self, "pl_name_var"):
                        self.pl_name_var.set(name)
                    if hasattr(self, "pl_group_var"):
                        self.pl_group_var.set(group)
                    self.playlist_items = items
                    self._save_offline_playlist()
                    self.render_playlist_items()
                    self.show_notification("Playlist", f"Loaded '{name}' ({len(items)} items)")
                elif isinstance(loaded, list):
                    self.playlist_items = loaded
                    self._save_offline_playlist()
                    self.render_playlist_items()
                    self.show_notification("Playlist", f"Loaded {len(loaded)} items from JSON")
                else:
                    self.show_notification("Error", "Invalid playlist JSON format")
            except Exception as e:
                self.show_notification("Error", f"Failed loading JSON: {e}")

    def play_playlist_item(self, index):
        if 0 <= index < len(self.playlist_items):
            self.current_playlist_index = index
            item = self.playlist_items[index]
            url = item.get("url", "")
            if url:
                if hasattr(self, "url_entry"):
                    self.url_entry.delete(0, tk.END)
                    self.url_entry.insert(0, url)
                self.player.play_url(url)
                self.tab_view.set("Player")
                self.render_playlist_items()

    def play_next_playlist_item(self):
        if self.playlist_items and self.current_playlist_index + 1 < len(self.playlist_items):
            self.play_playlist_item(self.current_playlist_index + 1)

    def render_playlist_items(self):
        if not hasattr(self, "pl_scroll") or not self.pl_scroll.winfo_exists():
            return
        for w in self.pl_scroll.winfo_children():
            w.destroy()

        q = self.pl_search_var.get().strip().lower() if hasattr(self, "pl_search_var") else ""
        grp_filter = self.pl_filter_group_var.get() if hasattr(self, "pl_filter_group_var") else "All Groups"

        filtered = []
        for idx, it in enumerate(self.playlist_items):
            # Text search filter
            text_match = not q or q in it.get("title", "").lower() or q in it.get("url", "").lower() or q in it.get("group", "").lower()
            # Group filter
            group_match = (grp_filter == "All Groups") or (it.get("group", "General") == grp_filter)
            if text_match and group_match:
                filtered.append((idx, it))

        if hasattr(self, "pl_count_label"):
            self.pl_count_label.configure(text=f"{len(filtered)} / {len(self.playlist_items)} items")

        if not filtered:
            ctk.CTkLabel(
                self.pl_scroll, text="No playlist items found. Add URLs or files above.",
                font=ctk.CTkFont(size=12), text_color=COLORS["text_secondary"]
            ).pack(pady=40)
            return

        for original_idx, item in filtered:
            is_active = (original_idx == self.current_playlist_index)
            border_c = COLORS["accent"] if is_active else COLORS.get("border", "#2D3748")
            bg_c = COLORS["surface"]

            card = ctk.CTkFrame(
                self.pl_scroll, fg_color=bg_c, corner_radius=10,
                border_width=1, border_color=border_c
            )
            card.pack(fill=tk.X, padx=4, pady=3)

            # Left index badge
            idx_badge = ctk.CTkLabel(
                card, text=f"#{original_idx + 1}", width=32,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=COLORS["accent_light"] if is_active else COLORS["text_secondary"]
            )
            idx_badge.pack(side=tk.LEFT, padx=(8, 2))

            # Group badge
            item_grp = item.get("group", "General").upper()
            grp_badge = ctk.CTkLabel(
                card, text=f" {item_grp} ", font=ctk.CTkFont(size=9, weight="bold"),
                fg_color=COLORS["bg_light"], corner_radius=6, text_color=COLORS["accent_light"]
            )
            grp_badge.pack(side=tk.LEFT, padx=(2, 6))

            # Center text
            text_box = ctk.CTkFrame(card, fg_color="transparent")
            text_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, pady=6)

            title_txt = item.get("title", "Unknown")
            clean_title = title_txt if len(title_txt) <= 50 else title_txt[:48] + "..."
            t_lbl = ctk.CTkLabel(
                text_box, text=clean_title, font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLORS["text_primary"], anchor="w"
            )
            t_lbl.pack(fill=tk.X)

            url_txt = item.get("url", "")
            clean_url = url_txt if len(url_txt) <= 60 else url_txt[:58] + "..."
            u_lbl = ctk.CTkLabel(
                text_box, text=clean_url, font=ctk.CTkFont(size=10),
                text_color=COLORS["text_secondary"], anchor="w"
            )
            u_lbl.pack(fill=tk.X)

            # Right action buttons
            btn_box = ctk.CTkFrame(card, fg_color="transparent")
            btn_box.pack(side=tk.RIGHT, padx=8)

            ctk.CTkButton(
                btn_box, text=" Play", image=IconFactory.get("play", (12, 12)),
                width=65, height=28, corner_radius=14,
                fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda idx=original_idx: self.play_playlist_item(idx)
            ).pack(side=tk.LEFT, padx=3)

            ctk.CTkButton(
                btn_box, text="", image=IconFactory.get("close", (12, 12)),
                width=28, height=28, corner_radius=14,
                fg_color=COLORS["bg_light"], hover_color=COLORS["error"],
                command=lambda item_id=item.get("id"): self.remove_playlist_item(item_id)
            ).pack(side=tk.LEFT, padx=3)

    def create_modern_player_tab(self):
        """Complete video player tab with full playback controls, loop, mute/unmute, seek 10s, speed, and volume."""
        self.player_tab.grid_columnconfigure(0, weight=1)
        self.player_tab.grid_rowconfigure(0, weight=1)

        player_card = ModernCard(self.player_tab)
        player_card.grid(row=0, column=0, sticky="nsew", padx=6, pady=4)
        player_card.grid_columnconfigure(0, weight=1)
        player_card.grid_rowconfigure(0, weight=1)

        # Video canvas container
        video_wrapper = ctk.CTkFrame(player_card, fg_color=COLORS["bg_dark"], corner_radius=12)
        video_wrapper.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 4))
        video_wrapper.grid_columnconfigure(0, weight=1)
        video_wrapper.grid_rowconfigure(0, weight=1)

        self.video_frame = tk.Frame(video_wrapper, bg=COLORS["bg_dark"], highlightthickness=0)
        self.video_frame.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        self.root.update_idletasks()
        if self.player.vlc_available:
            self.player.set_hwnd(self.video_frame.winfo_id())

        # Controls panel
        controls_panel = ctk.CTkFrame(player_card, fg_color=COLORS["surface"], height=135, corner_radius=14)
        controls_panel.grid(row=1, column=0, sticky="ew", padx=8, pady=(2, 8))
        controls_panel.pack_propagate(False)

        # Top row inside controls: Now Playing title + VLC Status
        title_row = ctk.CTkFrame(controls_panel, fg_color="transparent")
        title_row.pack(fill=tk.X, padx=14, pady=(6, 2))

        self.now_playing = ctk.CTkLabel(
            title_row, text="Ready to play", font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["text_primary"], anchor="w"
        )
        self.now_playing.pack(side=tk.LEFT, fill=tk.X, expand=True)

        status_text = "[OK] VLC Ready" if self.player.vlc_available else "[WARN] Audio Engine"
        self.player_status = ctk.CTkLabel(
            title_row, text=status_text, font=ctk.CTkFont(size=10, weight="bold"),
            text_color=(COLORS["success"] if self.player.vlc_available else COLORS["warning"])
        )
        self.player_status.pack(side=tk.RIGHT, padx=4)

        # Progress bar with seeking
        progress_section = ctk.CTkFrame(controls_panel, fg_color="transparent")
        progress_section.pack(fill=tk.X, padx=14, pady=(2, 2))

        self.progress_bar = ModernProgressBar(progress_section, command=self.seek_from_progress)
        self.progress_bar.pack(fill=tk.X, pady=(0, 2))

        # Time labels
        time_frame = ctk.CTkFrame(progress_section, fg_color="transparent")
        time_frame.pack(fill=tk.X)

        self.time_label = ctk.CTkLabel(time_frame, text="0:00", font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"])
        self.time_label.pack(side=tk.LEFT)
        self.current_time_label = self.time_label

        self.duration_label = ctk.CTkLabel(time_frame, text="0:00", font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"])
        self.duration_label.pack(side=tk.RIGHT)

        # Bottom row: Play controls + Loop + Mute + Speed + Single Volume
        bottom_row = ctk.CTkFrame(controls_panel, fg_color="transparent")
        bottom_row.pack(fill=tk.X, padx=14, pady=4)

        # Play / Pause toggle
        self.pp_btn = ctk.CTkButton(
            bottom_row, text="", image=IconFactory.get("play", (18, 18)),
            width=44, height=34, corner_radius=17,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            command=self.handle_main_play_pause
        )
        self.pp_btn.pack(side=tk.LEFT, padx=2)

        # Stop button
        ctk.CTkButton(
            bottom_row, text="", image=IconFactory.get("stop", (16, 16)),
            width=36, height=34, corner_radius=17,
            fg_color=COLORS["bg_light"], hover_color=COLORS["error"],
            command=self.player.stop
        ).pack(side=tk.LEFT, padx=2)

        # Rewind 10s (using RuneIcon backward.svg)
        ctk.CTkButton(
            bottom_row, text="", image=IconFactory.get("backward", (18, 18)),
            width=38, height=34, corner_radius=17,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            command=lambda: self.player.seek_backward(10)
        ).pack(side=tk.LEFT, padx=2)

        # Forward 10s (using RuneIcon forward.svg)
        ctk.CTkButton(
            bottom_row, text="", image=IconFactory.get("forward", (18, 18)),
            width=38, height=34, corner_radius=17,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            command=lambda: self.player.seek_forward(10)
        ).pack(side=tk.LEFT, padx=2)

        # Loop toggle button
        self.player_loop_btn = ctk.CTkButton(
            bottom_row, text="", image=IconFactory.get("loop", (16, 16)),
            width=38, height=34, corner_radius=17,
            fg_color=(COLORS["success"] if getattr(self.player, "is_looping", False) else COLORS["bg_light"]),
            hover_color=COLORS["accent"],
            command=self.toggle_loop
        )
        self.player_loop_btn.pack(side=tk.LEFT, padx=2)

        # Mute / Unmute toggle button
        self.mute_btn = ctk.CTkButton(
            bottom_row, text="", image=IconFactory.get("volume", (16, 16)),
            width=38, height=34, corner_radius=17,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            command=self.toggle_mute
        )
        self.mute_btn.pack(side=tk.LEFT, padx=2)

        # Go to time entry
        self.goto_entry = ctk.CTkEntry(
            bottom_row, placeholder_text="mm:ss", width=68, height=32, corner_radius=16,
            border_width=0, fg_color=COLORS["bg_light"]
        )
        self.goto_entry.pack(side=tk.LEFT, padx=(6, 2))
        self.goto_entry.bind("<Return>", self.go_to_time)

        ctk.CTkButton(
            bottom_row, text="Go", width=38, height=32, corner_radius=16,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            command=self.go_to_time
        ).pack(side=tk.LEFT, padx=(0, 6))

        # Speed selector
        self.speed_combo = ctk.CTkComboBox(
            bottom_row, values=["0.25x", "0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"],
            width=72, height=32, corner_radius=16, fg_color=COLORS["bg_light"], border_width=0,
            button_color=COLORS["accent"], command=self.change_speed
        )
        self.speed_combo.set("1.0x")
        self.speed_combo.pack(side=tk.LEFT, padx=2)

        # Quality selector dropdown (Auto/Best, 1080p, 720p, 480p, 360p, Audio)
        self.quality_menu = ctk.CTkOptionMenu(
            bottom_row, values=["Auto", "1080p", "720p", "480p", "360p", "Audio"],
            width=78, height=32, corner_radius=16, fg_color=COLORS["bg_light"],
            button_color=COLORS["accent"], font=ctk.CTkFont(size=11, weight="bold"),
            command=self.change_quality
        )
        self.quality_menu.set("Auto")
        self.quality_menu.pack(side=tk.LEFT, padx=2)

        # Subtitle / Caption selector dropdown
        self.sub_menu = ctk.CTkOptionMenu(
            bottom_row, values=["CC: Off", "CC: Auto", "CC: en", "Load .SRT..."],
            width=94, height=32, corner_radius=16, fg_color=COLORS["bg_light"],
            button_color=COLORS["accent"], font=ctk.CTkFont(size=11, weight="bold"),
            command=self.change_subtitle_track
        )
        self.sub_menu.set("CC: Auto")
        self.sub_menu.pack(side=tk.LEFT, padx=2)

        # Single Volume Control
        vol_frame = ctk.CTkFrame(bottom_row, fg_color="transparent")
        vol_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(8, 0))

        self.volume_slider = ModernSlider(
            vol_frame, from_=0, to=100, command=lambda v: self.change_volume(int(v))
        )
        self.volume_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.volume_slider.set(self.player.volume)

        # Video Metadata Bar (Uploader, Date, Views, Likes, Quality, Description toggle)
        meta_panel = ctk.CTkFrame(player_card, fg_color=COLORS["surface"], corner_radius=10)
        meta_panel.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 6))

        meta_top = ctk.CTkFrame(meta_panel, fg_color="transparent")
        meta_top.pack(fill=tk.X, padx=12, pady=4)

        self.meta_summary_label = ctk.CTkLabel(
            meta_top, text="👤 Media details will appear when playing",
            font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"], anchor="w"
        )
        self.meta_summary_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.desc_toggle_btn = ctk.CTkButton(
            meta_top, text="ℹ️ Description", width=95, height=24, corner_radius=12,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self.toggle_description
        )
        self.desc_toggle_btn.pack(side=tk.RIGHT)

        self.desc_container = ctk.CTkFrame(meta_panel, fg_color="transparent")
        self.description_box = ctk.CTkTextbox(
            self.desc_container, height=90, corner_radius=8, fg_color=COLORS["bg_dark"],
            font=ctk.CTkFont(family="Consolas", size=11)
        )
        self.description_box.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.desc_expanded = False

    def toggle_description(self):
        """Expand or collapse the video description panel."""
        if not getattr(self, "desc_expanded", False):
            self.desc_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 6))
            self.desc_toggle_btn.configure(text="▲ Close Desc", fg_color=COLORS["accent"])
            self.desc_expanded = True
        else:
            self.desc_container.pack_forget()
            self.desc_toggle_btn.configure(text="ℹ️ Description", fg_color=COLORS["bg_light"])
            self.desc_expanded = False

    def go_to_time(self, event=None):
        """Jump to specific time in current playback."""
        time_str = self.goto_entry.get().strip() if hasattr(self, "goto_entry") else ""
        if time_str:
            if hasattr(self.player, "go_to_time") and self.player.go_to_time(time_str):
                self.show_notification("Jump", f"Jumped to {time_str}")
            else:
                self.show_notification("Notice", "Format: mm:ss or seconds (e.g. 1:30 or 90)")

    def toggle_offline_mode(self, val=None):
        """Toggle offline playback mode from local cache."""
        if val is None:
            val = bool(self.offline_switch.get()) if hasattr(self, "offline_switch") else False
        if hasattr(self, "offline_mode") and self.offline_mode:
            self.offline_mode.set(val)
        status_txt = "Offline Mode Enabled (playing from local cache)" if val else "Online Streaming Mode"
        self.show_notification("Mode", status_txt)

    def change_speed(self, value):
        """Change video playback speed."""
        try:
            val_clean = str(value).replace("x", "")
            speed = round(float(val_clean), 2)
            if hasattr(self.player, "set_speed"):
                self.player.set_speed(speed)
        except Exception:
            pass

    def change_quality(self, choice):
        """Change video stream playback quality."""
        clean_q = choice.replace("Auto", "best").lower()
        if hasattr(self, "player") and self.player:
            self.player.selected_quality = clean_q
            self.show_notification("Quality", f"Playback quality set to {choice}")
            cur_url = getattr(self.player, "current_url", None)
            if cur_url and str(cur_url).startswith("http"):
                cur_pos = getattr(self.player, "current_time", 0)
                self.player.play_url(cur_url)
                if cur_pos > 0:
                    self.root.after(2000, lambda: self.player.seek(cur_pos))

    def change_subtitle_track(self, choice):
        """Configure and load subtitle / caption track."""
        if "Load" in choice:
            srt_path = filedialog.askopenfilename(
                title="Select Subtitle File",
                filetypes=[("Subtitle files", "*.srt *.vtt *.ass"), ("All files", "*.*")]
            )
            if srt_path:
                if self.player.set_subtitle_file(srt_path):
                    self.show_notification("Subtitles", f"Loaded: {os.path.basename(srt_path)}")
                else:
                    self.show_notification("Notice", "Could not attach subtitle. Start playing media first.")
        elif "Off" in choice:
            if hasattr(self.player, "disable_subtitles"):
                self.player.disable_subtitles()
            self.show_notification("Subtitles", "Subtitles disabled")
        else:
            cur_url = getattr(self.player, "current_url", None)
            if cur_url and str(cur_url).startswith("http"):
                self.load_subtitles(cur_url, getattr(self.player, "current_title", ""), lang="en")

    def toggle_mute(self):
        """Toggle mute state across both main player and mini player."""
        if hasattr(self.player, "is_muted") and self.player.is_muted:
            self.unmute_both()
        else:
            self.mute_both()
        self.update_mute_button()

    def update_mute_button(self):
        """Update mute button icon to reflect current audio state."""
        is_muted = getattr(self.player, "is_muted", False)
        icon_name = "mute" if is_muted else "volume"
        img = IconFactory.get(icon_name, (16, 16))
        if hasattr(self, "mute_btn") and self.mute_btn and self.mute_btn.winfo_exists():
            self.mute_btn.configure(image=img)
        if hasattr(self, "hover_window") and self.hover_window:
            self.hover_window.update_mute_button()

    def create_modern_download_tab(self):
        """Modern downloads tab with live search and clean item cards."""
        self.download_tab.grid_columnconfigure(0, weight=1)
        self.download_tab.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self.download_tab, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))

        self.dl_search_var = tk.StringVar()
        self.dl_search_entry = ctk.CTkEntry(
            header, placeholder_text="Search active & finished downloads...",
            textvariable=self.dl_search_var, width=320, height=32, corner_radius=16,
            border_width=0, fg_color=COLORS["surface"]
        )
        self.dl_search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.dl_search_var.trace_add("write", lambda *args: self.filter_download_display())

        ctk.CTkButton(
            header, text=" Clear All", image=IconFactory.get("close", (14, 14)),
            width=90, height=32, corner_radius=16,
            fg_color=COLORS["bg_light"], hover_color=COLORS["error"], command=self.clear_all_downloads
        ).pack(side=tk.RIGHT)

        self.downloads_scroll = ctk.CTkScrollableFrame(
            self.download_tab, fg_color=COLORS["bg_dark"], corner_radius=12
        )
        self.downloads_scroll.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 10))
        self.downloads_scroll.grid_columnconfigure(0, weight=1)
        self.download_scroll = self.downloads_scroll

    def filter_download_display(self):
        query = self.dl_search_var.get().lower().strip() if hasattr(self, "dl_search_var") else ""
        for dl_id, item in self.download_items.items():
            if not item or not hasattr(item, "card") or not item.card.winfo_exists():
                continue
            matches = True
            if query:
                matches = query in item.title.lower() or query in getattr(item, "url", "").lower()
            if matches:
                item.card.pack(fill=tk.X, padx=6, pady=4)
            else:
                item.card.pack_forget()

    def create_modern_history_tab(self):
        """History tab with search bar and instant playback cards."""
        self.history_tab.grid_columnconfigure(0, weight=1)
        self.history_tab.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self.history_tab, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))

        self.hist_search_var = tk.StringVar()
        hist_entry = ctk.CTkEntry(
            header, placeholder_text="Search playback history...",
            textvariable=self.hist_search_var, height=32, corner_radius=16,
            border_width=0, fg_color=COLORS["surface"]
        )
        hist_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.hist_search_var.trace_add("write", lambda *args: self.update_history_display())

        ctk.CTkButton(
            header, text="Clear History", width=95, height=32, corner_radius=16,
            fg_color=COLORS["bg_light"], hover_color=COLORS["error"],
            command=self.clear_history
        ).pack(side=tk.RIGHT)

        self.history_scroll = ctk.CTkScrollableFrame(
            self.history_tab, fg_color=COLORS["bg_dark"], corner_radius=12
        )
        self.history_scroll.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 10))
        self.history_scroll.grid_columnconfigure(0, weight=1)

        self.update_history_display()

    def update_history_display(self):
        """Render recent history items matching current search query."""
        if not hasattr(self, "history_scroll") or not self.history_scroll.winfo_exists():
            return
        for widget in self.history_scroll.winfo_children():
            widget.destroy()

        q = getattr(self, "hist_search_var", None)
        query = q.get().lower().strip() if q else ""

        items = list(reversed(self.search_history))
        if query:
            items = [it for it in items if query in it.get("title", "").lower() or query in it.get("url", "").lower()]

        if not items:
            ctk.CTkLabel(
                self.history_scroll, text="No history items found.", font=ctk.CTkFont(size=12),
                text_color=COLORS["text_secondary"]
            ).pack(pady=40)
            return

        for item in items[:60]:
            card = ctk.CTkFrame(self.history_scroll, fg_color=COLORS["bg_light"], corner_radius=10)
            card.pack(fill=tk.X, padx=4, pady=3)

            info_box = ctk.CTkFrame(card, fg_color="transparent")
            info_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=12, pady=8)

            t = item.get("title", "Untitled")
            clean_t = t if len(t) <= 65 else t[:62] + "..."
            ctk.CTkLabel(info_box, text=clean_t, font=ctk.CTkFont(size=12, weight="bold"), text_color=COLORS["text_primary"], anchor="w").pack(anchor="w")

            u = item.get("url", "")
            clean_u = u if len(u) <= 75 else u[:72] + "..."
            ctk.CTkLabel(info_box, text=clean_u, font=ctk.CTkFont(size=10), text_color=COLORS["text_secondary"], anchor="w").pack(anchor="w")

            action_box = ctk.CTkFrame(card, fg_color="transparent")
            action_box.pack(side=tk.RIGHT, padx=10, pady=8)

            url_val = item.get("url", "")
            ctk.CTkButton(
                action_box, text="▶ Play", width=64, height=28, corner_radius=14,
                fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                command=lambda u=url_val: self.play_from_history(u)
            ).pack(side=tk.LEFT, padx=2)

    def play_from_history(self, url):
        if url:
            if hasattr(self, "url_entry"):
                self.url_entry.delete(0, tk.END)
                self.url_entry.insert(0, url)
            self.tab_view.set("Player")
            self.play_url()

    def create_modern_transcribe_tab(self):
        """Modern transcription tab with source picker, model selector, style picker, live progress, and multi-format exports."""
        self.transcribe_tab.grid_columnconfigure(0, weight=1)
        self.transcribe_tab.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self.transcribe_tab, fg_color=COLORS["bg_dark"], corner_radius=12)
        scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        scroll.grid_columnconfigure(0, weight=1)

        container = ctk.CTkFrame(scroll, fg_color="transparent")
        container.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # 1. Source Selection Card
        src_card = ModernCard(container)
        src_card.pack(fill=tk.X, padx=6, pady=4)

        src_hdr = ctk.CTkFrame(src_card, fg_color="transparent")
        src_hdr.pack(fill=tk.X, padx=14, pady=(8, 2))
        ctk.CTkLabel(
            src_hdr, text=" Transcription Source",
            image=IconFactory.get("folder", (16, 16)), compound="left",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=COLORS["accent"]
        ).pack(side=tk.LEFT)

        src_row1 = ctk.CTkFrame(src_card, fg_color="transparent")
        src_row1.pack(fill=tk.X, padx=14, pady=4)

        self.transcribe_url = ModernEntry(src_row1, placeholder="Enter YouTube URL, media link, or select local audio/video file...")
        self.transcribe_url.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        src_row2 = ctk.CTkFrame(src_card, fg_color="transparent")
        src_row2.pack(fill=tk.X, padx=14, pady=(2, 8))

        ctk.CTkButton(
            src_row2, text=" Browse", image=IconFactory.get("folder", (15, 15)),
            width=95, height=28, corner_radius=14,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.browse_audio_file
        ).pack(side=tk.LEFT, padx=(0, 6))

        ctk.CTkButton(
            src_row2, text=" Current", image=IconFactory.get("play", (14, 14)),
            width=95, height=28, corner_radius=14,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.use_current_media_for_transcribe
        ).pack(side=tk.LEFT, padx=6)

        ctk.CTkButton(
            src_row2, text="✖ Clear", width=70, height=28, corner_radius=14,
            fg_color=COLORS["bg_light"], hover_color=COLORS["error"],
            font=ctk.CTkFont(size=11),
            command=lambda: self.transcribe_url.delete(0, tk.END)
        ).pack(side=tk.LEFT, padx=6)

        # 2. Options Card
        opts_card = ModernCard(container)
        opts_card.pack(fill=tk.X, padx=6, pady=4)

        opts_hdr = ctk.CTkFrame(opts_card, fg_color="transparent")
        opts_hdr.pack(fill=tk.X, padx=14, pady=(8, 2))
        ctk.CTkLabel(
            opts_hdr, text=" Speech Transcription Options",
            image=IconFactory.get("transcription", (16, 16)), compound="left",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=COLORS["accent"]
        ).pack(side=tk.LEFT)

        row1 = ctk.CTkFrame(opts_card, fg_color="transparent")
        row1.pack(fill=tk.X, padx=14, pady=4)

        ctk.CTkLabel(row1, text="Language:", width=65, font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"], anchor="w").pack(side=tk.LEFT)
        self.transcribe_lang_menu = ctk.CTkOptionMenu(
            row1, values=list(LANGUAGES.keys()), width=110, height=28, corner_radius=14,
            fg_color=COLORS["bg_light"], button_color=COLORS["accent"]
        )
        self.transcribe_lang_menu.pack(side=tk.LEFT, padx=(0, 8))
        self.transcribe_lang = self.transcribe_lang_menu

        ctk.CTkLabel(row1, text="Model:", width=45, font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"], anchor="w").pack(side=tk.LEFT)
        self.transcribe_model_menu = ctk.CTkOptionMenu(
            row1, values=["medium", "small", "base", "tiny", "llama"],
            width=100, height=28, corner_radius=14,
            fg_color=COLORS["bg_light"], button_color=COLORS["accent"]
        )
        self.transcribe_model_menu.pack(side=tk.LEFT, padx=(0, 8))
        self.transcribe_model = self.transcribe_model_menu

        ctk.CTkLabel(row1, text="Format:", width=50, font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"], anchor="w").pack(side=tk.LEFT)
        self.transcribe_style_menu = ctk.CTkOptionMenu(
            row1, values=["timestamps", "raw", "summary", "single", "paragraph"],
            width=110, height=28, corner_radius=14,
            fg_color=COLORS["bg_light"], button_color=COLORS["accent"]
        )
        self.transcribe_style_menu.pack(side=tk.LEFT, padx=(0, 8))
        self.format_style = self.transcribe_style_menu

        self.transcribe_start_btn = ctk.CTkButton(
            row1, text=" Transcribe", image=IconFactory.get("transcription", (15, 15)),
            width=125, height=28, corner_radius=14,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.start_transcription
        )
        self.transcribe_start_btn.pack(side=tk.LEFT, padx=(4, 0))

        # Progress bar & status log
        prog_row = ctk.CTkFrame(opts_card, fg_color="transparent")
        prog_row.pack(fill=tk.X, padx=14, pady=(4, 8))

        self.transcribe_progress = ModernProgressBar(prog_row)
        self.transcribe_progress.pack(fill=tk.X, pady=(2, 4))

        self.transcribe_status = ctk.CTkLabel(
            prog_row, text="Ready to transcribe", font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"], anchor="w"
        )
        self.transcribe_status.pack(side=tk.LEFT)
        self.model_status_label = self.transcribe_status

        # 3. Result Card
        res_card = ModernCard(container)
        res_card.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        res_header = ctk.CTkFrame(res_card, fg_color="transparent")
        res_header.pack(fill=tk.X, padx=14, pady=(8, 4))
        ctk.CTkLabel(
            res_header, text=" Transcription Result",
            image=IconFactory.get("transcription", (16, 16)), compound="left",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=COLORS["accent"]
        ).pack(side=tk.LEFT)

        # Compact Icon Export Buttons (No overflow)
        exp_box = ctk.CTkFrame(res_header, fg_color="transparent")
        exp_box.pack(side=tk.RIGHT)

        ctk.CTkButton(
            exp_box, text=" Copy", image=IconFactory.get("copy", (14, 14)),
            width=68, height=26, corner_radius=13,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self.copy_transcription
        ).pack(side=tk.LEFT, padx=2)

        for fmt, handler in [
            (".SRT", self.save_as_srt),
            (".VTT", self.save_as_vtt),
            (".TXT", self.save_as_txt),
            (".JSON", self.save_as_json),
            (".PDF", self.save_as_pdf),
        ]:
            ctk.CTkButton(
                exp_box, text=fmt, width=42, height=26, corner_radius=13,
                fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
                font=ctk.CTkFont(size=9, weight="bold"),
                command=handler
            ).pack(side=tk.LEFT, padx=2)

        ctk.CTkButton(
            exp_box, text=" Play Sub", image=IconFactory.get("play", (13, 13)),
            width=88, height=26, corner_radius=13,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(size=10, weight="bold"),
            command=self.load_subtitles_to_player
        ).pack(side=tk.LEFT, padx=2)

        self.transcribe_result = ctk.CTkTextbox(
            res_card, height=320, corner_radius=10, fg_color=COLORS["bg_dark"],
            font=ctk.CTkFont(family="Consolas", size=11)
        )
        self.transcribe_result.pack(fill=tk.BOTH, expand=True, padx=14, pady=(4, 12))

    def copy_transcription(self):
        try:
            txt = self.transcribe_result.get('1.0', tk.END).strip()
            if txt:
                self.root.clipboard_clear()
                self.root.clipboard_append(txt)
                self.show_notification('Copied', 'Transcription copied to clipboard')
        except Exception as e:
            logger.error(f'Copy transcription error: {e}')

    def save_as_vtt(self):
        try:
            if hasattr(self, 'current_transcription') and self.current_transcription:
                filename = filedialog.asksaveasfilename(
                    defaultextension='.vtt',
                    filetypes=[('WebVTT files', '*.vtt'), ('All files', '*.*')],
                )
                if filename:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write("WEBVTT" + chr(10) + chr(10))
                        segs = self.current_transcription.get('segments', [])
                        for idx, s in enumerate(segs, start=1):
                            start = self._format_vtt_time(s.get('start', 0))
                            end = self._format_vtt_time(s.get('end', 0))
                            text = s.get('text', '').strip()
                            f.write(str(idx) + chr(10) + str(start) + " --> " + str(end) + chr(10) + text + chr(10) + chr(10))
                    self.show_notification('Success', 'VTT file saved')
        except Exception as e:
            logger.error(f'Save VTT error: {e}')

    def _format_vtt_time(self, seconds):
        if seconds is None:
            seconds = 0
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f'{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}'

    def create_modern_cache_tab(self):
        """Offline media library tab with search, sorting, folder scanning, and playback."""
        self.cache_tab.grid_columnconfigure(0, weight=1)
        self.cache_tab.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self.cache_tab, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))

        self.cache_search_var = tk.StringVar()
        cache_entry = ctk.CTkEntry(
            header, placeholder_text="Search offline library...",
            textvariable=self.cache_search_var, width=280, height=32, corner_radius=16,
            border_width=0, fg_color=COLORS["surface"]
        )
        cache_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.cache_search_var.trace_add("write", lambda *args: self.update_cache_display())

        # Sort Dropdown
        self.cache_sort_var = tk.StringVar(value="Date (Newest)")
        ctk.CTkOptionMenu(
            header, values=["Date (Newest)", "Date (Oldest)", "Title (A-Z)", "File Size"],
            variable=self.cache_sort_var, width=130, height=32, corner_radius=16,
            fg_color=COLORS["surface"], button_color=COLORS["accent"],
            command=lambda v: self.update_cache_display()
        ).pack(side=tk.LEFT, padx=3)

        # Scan folder button
        def scan_local_folder():
            f = filedialog.askdirectory(title="Select Folder to Import into Library")
            if f:
                added = self.cache_manager.scan_directory(f)
                self.show_notification("Library", f"Imported {added} files into library")
                self.update_cache_display()

        ctk.CTkButton(
            header, text=" Scan Folder", image=IconFactory.get("folder", (16, 16)),
            width=115, height=32, corner_radius=16,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"], command=scan_local_folder
        ).pack(side=tk.LEFT, padx=3)

        ctk.CTkButton(
            header, text="Refresh", width=70, height=32, corner_radius=16,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"], command=self.update_cache_display
        ).pack(side=tk.RIGHT)

        self.cache_scroll = ctk.CTkScrollableFrame(
            self.cache_tab, fg_color=COLORS["bg_dark"], corner_radius=12
        )
        self.cache_scroll.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 10))
        self.cache_scroll.grid_columnconfigure(0, weight=1)

        self.update_cache_display()

    def update_cache_display(self):
        """Update cached video frames in offline cache tab."""
        if not hasattr(self, "cache_scroll") or not self.cache_scroll.winfo_exists():
            return
        for widget in self.cache_scroll.winfo_children():
            widget.destroy()

        q = getattr(self, "cache_search_var", None)
        query = q.get().strip() if q else ""
        s = getattr(self, "cache_sort_var", None)
        sort_mode = s.get() if s else "Date (Newest)"

        sort_map = {
            "Date (Newest)": "date_desc",
            "Date (Oldest)": "date_asc",
            "Title (A-Z)": "title_asc",
            "File Size": "size_desc",
        }
        items = self.cache_manager.get_filtered(query, sort_map.get(sort_mode, "date_desc"))

        if not items:
            ctk.CTkLabel(
                self.cache_scroll, text="No cached or local videos found.",
                font=ctk.CTkFont(size=12), text_color=COLORS["text_secondary"]
            ).pack(pady=40)
            return

        for info in items:
            frame = CacheVideoFrame(self.cache_scroll, info, self)
            frame.pack(fill=tk.X, padx=4, pady=3)

    def create_modern_settings_tab(self):
        """Settings tab with complete Player, Download, Offline Cache, Updaters, Subtitles, AdBlock, and Shortcuts."""
        self.settings_tab.grid_columnconfigure(0, weight=1)
        self.settings_tab.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self.settings_tab, fg_color=COLORS["bg_dark"], corner_radius=12)
        scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        scroll.grid_columnconfigure(0, weight=1)

        container = ctk.CTkFrame(scroll, fg_color="transparent")
        container.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # 1. Download Settings Card
        dl_card = ModernCard(container)
        dl_card.pack(fill=tk.X, padx=8, pady=6)
        ctk.CTkLabel(dl_card, text="📥 Download Settings", font=ctk.CTkFont(size=15, weight="bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=16, pady=(12, 6))

        dl_row = ctk.CTkFrame(dl_card, fg_color="transparent")
        dl_row.pack(fill=tk.X, padx=16, pady=(4, 12))
        ctk.CTkLabel(dl_row, text="Save path:", width=75, font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"], anchor="w").pack(side=tk.LEFT)
        self.download_path_label = ctk.CTkLabel(dl_row, text=self.settings.download_path, font=ctk.CTkFont(size=11, weight="bold"), text_color=COLORS["text_primary"], anchor="w")
        self.download_path_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ctk.CTkButton(dl_row, text="Browse", width=80, height=28, corner_radius=14, fg_color=COLORS["bg_light"], hover_color=COLORS["accent"], command=self.browse_download_path).pack(side=tk.RIGHT)

        # 2. Offline Cache Settings Card
        cache_card = ModernCard(container)
        cache_card.pack(fill=tk.X, padx=8, pady=6)
        ctk.CTkLabel(cache_card, text="💾 Offline Cache Settings", font=ctk.CTkFont(size=15, weight="bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=16, pady=(12, 6))

        cache_row = ctk.CTkFrame(cache_card, fg_color="transparent")
        cache_row.pack(fill=tk.X, padx=16, pady=(4, 12))
        ctk.CTkLabel(cache_row, text="Cache dir:", width=75, font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"], anchor="w").pack(side=tk.LEFT)
        ctk.CTkLabel(cache_row, text=self.settings.cache_path, font=ctk.CTkFont(size=11, weight="bold"), text_color=COLORS["text_primary"], anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ctk.CTkButton(cache_row, text="Clear Cache", width=95, height=28, corner_radius=14, fg_color=COLORS["bg_light"], hover_color=COLORS["error"], command=self.clear_all_cache).pack(side=tk.RIGHT)

        # 3. Model Storage & AI Speech Runtimes Card
        model_card = ModernCard(container)
        model_card.pack(fill=tk.X, padx=8, pady=6)
        ctk.CTkLabel(model_card, text="🤖 Model Storage & Speech AI", font=ctk.CTkFont(size=15, weight="bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=16, pady=(12, 6))

        m_row = ctk.CTkFrame(model_card, fg_color="transparent")
        m_row.pack(fill=tk.X, padx=16, pady=4)
        ctk.CTkLabel(m_row, text="Models folder:", width=95, font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"], anchor="w").pack(side=tk.LEFT)
        self.models_path_label = ctk.CTkLabel(m_row, text=self.settings.models_path, font=ctk.CTkFont(size=11, weight="bold"), text_color=COLORS["text_primary"], anchor="w")
        self.models_path_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        def browse_models_path():
            p = filedialog.askdirectory(initialdir=self.settings.models_path)
            if p:
                self.settings.models_path = p
                self.models_path_label.configure(text=p)
                if hasattr(self, "transcriber") and self.transcriber:
                    self.transcriber.set_models_path(p)
                self.settings.save()
                self.update_model_status()

        ctk.CTkButton(m_row, text="Browse", width=80, height=28, corner_radius=14, fg_color=COLORS["bg_light"], hover_color=COLORS["accent"], command=browse_models_path).pack(side=tk.RIGHT)

        # Model download row
        dl_row = ctk.CTkFrame(model_card, fg_color="transparent")
        dl_row.pack(fill=tk.X, padx=16, pady=(4, 6))

        ctk.CTkLabel(dl_row, text="Fetch AI Model:", width=110, font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"], anchor="w").pack(side=tk.LEFT)
        
        self.model_dl_choice = ctk.CTkOptionMenu(
            dl_row,
            values=[
                "Whisper Tiny (~75 MB)",
                "Whisper Base (~142 MB)",
                "Whisper Small (~466 MB)",
                "Whisper Medium (~1.5 GB)",
                "TinyLlama 1.1B GGUF (~670 MB)",
                "Llama 3 8B GGUF (~5 GB)"
            ],
            width=210, height=28, corner_radius=14,
            fg_color=COLORS["bg_light"], button_color=COLORS["accent"]
        )
        self.model_dl_choice.pack(side=tk.LEFT, padx=(0, 10))

        ctk.CTkButton(
            dl_row, text="⬇️ Download from HuggingFace", width=195, height=28, corner_radius=14,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.download_selected_model_from_settings
        ).pack(side=tk.LEFT)

        self.model_status_frame = ctk.CTkFrame(model_card, fg_color=COLORS["surface"], corner_radius=8)
        self.model_status_frame.pack(fill=tk.X, padx=16, pady=(6, 8))
        self.update_model_status()

        ctk.CTkButton(
            model_card, text="Refresh Model Checks", width=160, height=28, corner_radius=14,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            command=lambda: (self.update_model_status(), self.show_notification("Models", "Local model files re-scanned"))
        ).pack(anchor="w", padx=16, pady=(2, 12))

        # 4. Dependencies & Updaters Card (yt-dlp & FFmpeg)
        dep_card = ModernCard(container)
        dep_card.pack(fill=tk.X, padx=8, pady=6)
        ctk.CTkLabel(dep_card, text="🔧 Tools & Auto-Updaters", font=ctk.CTkFont(size=15, weight="bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=16, pady=(12, 6))

        ytdlp_row = ctk.CTkFrame(dep_card, fg_color="transparent")
        ytdlp_row.pack(fill=tk.X, padx=16, pady=4)
        self.ytdlp_status_label = ctk.CTkLabel(ytdlp_row, text=f"yt-dlp version: v{ToolManager.get_ytdlp_version()}", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLORS["text_primary"])
        self.ytdlp_status_label.pack(side=tk.LEFT)

        def do_update_ytdlp():
            self.ytdlp_status_label.configure(text="Checking for latest yt-dlp release...")
            ToolManager.check_and_update_ytdlp(lambda pct, msg: self.root.after(0, lambda: self.ytdlp_status_label.configure(text=msg)))

        ctk.CTkButton(ytdlp_row, text="Update yt-dlp", width=110, height=28, corner_radius=14, fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"], command=do_update_ytdlp).pack(side=tk.RIGHT)

        ff_row = ctk.CTkFrame(dep_card, fg_color="transparent")
        ff_row.pack(fill=tk.X, padx=16, pady=(4, 12))
        ff_ok = ToolManager.is_ffmpeg_available()
        self.ffmpeg_status_label = ctk.CTkLabel(ff_row, text=f"FFmpeg: {'Installed' if ff_ok else 'Not Found'}", font=ctk.CTkFont(size=11, weight="bold"), text_color=(COLORS["success"] if ff_ok else COLORS["error"]))
        self.ffmpeg_status_label.pack(side=tk.LEFT)

        def do_dl_ffmpeg():
            self.ffmpeg_status_label.configure(text="Downloading portable FFmpeg (bin/)...", text_color=COLORS["warning"])
            def cb(pct, msg):
                def _u():
                    self.ffmpeg_status_label.configure(text=msg)
                    if pct >= 100:
                        self.ffmpeg_status_label.configure(text="FFmpeg: Installed (bin/)", text_color=COLORS["success"])
                self.root.after(0, _u)
            ToolManager.download_portable_ffmpeg(cb)

        ctk.CTkButton(ff_row, text="Get FFmpeg", width=110, height=28, corner_radius=14, fg_color=COLORS["bg_light"], hover_color=COLORS["accent"], command=do_dl_ffmpeg).pack(side=tk.RIGHT)

        # 5. Subtitle & AdBlock Settings Card
        play_opts_card = ModernCard(container)
        play_opts_card.pack(fill=tk.X, padx=8, pady=6)
        ctk.CTkLabel(play_opts_card, text="💬 Subtitles & Ad-Blocking", font=ctk.CTkFont(size=15, weight="bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=16, pady=(12, 6))

        sub_opts = ctk.CTkFrame(play_opts_card, fg_color="transparent")
        sub_opts.pack(fill=tk.X, padx=16, pady=4)
        self.auto_sub_var = ctk.BooleanVar(value=getattr(self.settings, "auto_load_subs", True))
        ctk.CTkCheckBox(sub_opts, text="Auto-load subtitles", variable=self.auto_sub_var, command=self.toggle_auto_subs, fg_color=COLORS["accent"]).pack(side=tk.LEFT, padx=(0, 14))

        ctk.CTkLabel(sub_opts, text="Default Sub Lang:", font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"]).pack(side=tk.LEFT, padx=(6, 2))
        self.sub_lang = ctk.CTkComboBox(sub_opts, values=[l["code"] for l in LANGUAGES.values()], width=80, height=26, fg_color=COLORS["bg_light"], border_width=0, button_color=COLORS["accent"])
        self.sub_lang.set(getattr(self.settings, "subtitle_lang", "en"))
        self.sub_lang.pack(side=tk.LEFT, padx=4)
        ctk.CTkButton(sub_opts, text="Apply", width=55, height=26, corner_radius=13, fg_color=COLORS["accent"], command=self.apply_sub_lang).pack(side=tk.LEFT, padx=4)

        ad_row = ctk.CTkFrame(play_opts_card, fg_color="transparent")
        ad_row.pack(fill=tk.X, padx=16, pady=(4, 12))
        self.adblock_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(ad_row, text="Enable Ad Blocking (hosts-based, requires admin)", variable=self.adblock_var, command=self.toggle_adblock, fg_color=COLORS["accent"]).pack(side=tk.LEFT)

        # 6. Keyboard Shortcuts Manager & Reference Table Card
        sc_card = ModernCard(container)
        sc_card.pack(fill=tk.X, padx=8, pady=6)
        ctk.CTkLabel(sc_card, text="⌨️ Keyboard Shortcuts Reference & Configuration", font=ctk.CTkFont(size=15, weight="bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=16, pady=(12, 6))

        shortcuts_grid = [
            ("Space / Ctrl+Shift+P", "Play / Pause toggle"),
            ("Left / Right Arrow", "Seek backward / forward 10 seconds"),
            ("Up / Down Arrow", "Increase / decrease volume (5%)"),
            ("M / Ctrl+Shift+M", "Mute / Unmute audio toggle"),
            ("F / F11", "Toggle Fullscreen mode"),
            ("L", "Toggle Video Loop mode"),
            ("Ctrl + H / Ctrl+Shift+V", "Toggle Mini Player (PIP)"),
            ("Ctrl + D / Ctrl+Shift+D", "Open Download Media dialog"),
            ("Ctrl + G / Ctrl+Shift+G", "Switch to Transcribe Tab"),
            ("Escape", "Exit Fullscreen"),
            ("Ctrl + Q", "Terminate Kupido Player application"),
        ]

        table_frame = ctk.CTkFrame(sc_card, fg_color=COLORS["surface"], corner_radius=10)
        table_frame.pack(fill=tk.X, padx=16, pady=(4, 12))
        for row_idx, (key, desc) in enumerate(shortcuts_grid):
            bg_col = COLORS["bg_light"] if row_idx % 2 == 0 else COLORS["surface"]
            r_frame = ctk.CTkFrame(table_frame, fg_color=bg_col, corner_radius=4)
            r_frame.pack(fill=tk.X, padx=4, pady=1)
            ctk.CTkLabel(r_frame, text=key, width=190, font=ctk.CTkFont(size=11, weight="bold"), text_color=COLORS["accent_light"], anchor="w").pack(side=tk.LEFT, padx=10, pady=4)
            ctk.CTkLabel(r_frame, text=desc, font=ctk.CTkFont(size=11), text_color=COLORS["text_primary"], anchor="w").pack(side=tk.LEFT, padx=6, pady=4)

        # 7. Session Management & Console Terminal Card
        tools_card = ModernCard(container)
        tools_card.pack(fill=tk.X, padx=8, pady=6)
        ctk.CTkLabel(tools_card, text="⚙️ Session Management & Background Console", font=ctk.CTkFont(size=15, weight="bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=16, pady=(12, 6))

        sess_row = ctk.CTkFrame(tools_card, fg_color="transparent")
        sess_row.pack(fill=tk.X, padx=16, pady=4)
        ctk.CTkLabel(sess_row, text="Workspace Session:", width=140, font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"], anchor="w").pack(side=tk.LEFT)

        ctk.CTkButton(
            sess_row, text="💾 Save Session", width=120, height=28, corner_radius=14,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.save_session
        ).pack(side=tk.LEFT, padx=4)

        ctk.CTkButton(
            sess_row, text="📂 Load Session", width=120, height=28, corner_radius=14,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.load_session
        ).pack(side=tk.LEFT, padx=4)

        term_row = ctk.CTkFrame(tools_card, fg_color="transparent")
        term_row.pack(fill=tk.X, padx=16, pady=(4, 12))
        ctk.CTkLabel(term_row, text="Background Terminal:", width=140, font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"], anchor="w").pack(side=tk.LEFT)
        self.console_status_label = ctk.CTkLabel(term_row, text="Console: ACTIVE", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLORS["accent"], width=120, anchor="w")
        self.console_status_label.pack(side=tk.LEFT)

        ctk.CTkButton(
            term_row, text="Toggle Show / Hide Console", width=190, height=28, corner_radius=14,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
            command=self.toggle_console
        ).pack(side=tk.LEFT, padx=6)

    def update_model_status(self):
        """Check presence of local weights files on disk without loading heavy binaries."""
        if not hasattr(self, "model_status_frame") or not self.model_status_frame.winfo_exists():
            return
        for widget in self.model_status_frame.winfo_children():
            widget.destroy()

        models_list = [
            ("Whisper Tiny", "whisper", "tiny", os.path.join(self.settings.models_path, "tiny.pt"), "75 MB"),
            ("Whisper Base", "whisper", "base", os.path.join(self.settings.models_path, "base.pt"), "142 MB"),
            ("Whisper Small", "whisper", "small", os.path.join(self.settings.models_path, "small.pt"), "466 MB"),
            ("Whisper Medium", "whisper", "medium", os.path.join(self.settings.models_path, "medium.pt"), "1.5 GB"),
            ("TinyLlama 1.1B", "tinyllama", None, os.path.join(self.settings.models_path, "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"), "670 MB"),
            ("Llama 3 8B", "llama3_8b", None, os.path.join(self.settings.models_path, "Meta-Llama-3-8B-Instruct-Q5_K_M.gguf"), "5.0 GB"),
        ]

        for label, m_type, m_size, path, est_size in models_list:
            exists = os.path.exists(path)
            row = ctk.CTkFrame(self.model_status_frame, fg_color="transparent")
            row.pack(fill=tk.X, padx=10, pady=2)
            ctk.CTkLabel(
                row, text=f"{label} ({est_size}):", width=190,
                font=ctk.CTkFont(size=11, weight="bold"), text_color=COLORS["text_primary"], anchor="w"
            ).pack(side=tk.LEFT)

            status_text = "[READY]" if exists else "[NOT DOWNLOADED]"
            color = COLORS["success"] if exists else COLORS["text_secondary"]
            ctk.CTkLabel(row, text=status_text, font=ctk.CTkFont(size=11, weight="bold"), text_color=color).pack(side=tk.LEFT, padx=6)

            if not exists:
                ctk.CTkButton(
                    row, text="⬇️ Fetch Model", width=110, height=22, corner_radius=11,
                    fg_color=COLORS["bg_light"], hover_color=COLORS["accent"],
                    font=ctk.CTkFont(size=10, weight="bold"),
                    command=lambda mt=m_type, ms=m_size: self.download_model_on_demand(
                        mt, ms, lambda ok, err=None: (self.update_model_status(), self.show_notification("Model", "Download finished" if ok else f"Failed: {err}"))
                    )
                ).pack(side=tk.RIGHT, padx=4)

    def download_selected_model_from_settings(self):
        """Download chosen AI model from Settings dropdown using ModelDownloader."""
        choice = self.model_dl_choice.get() if hasattr(self, "model_dl_choice") else "Whisper Tiny"
        if "Tiny" in choice and "Whisper" in choice:
            m_type = "whisper"; m_size = "tiny"
        elif "Base" in choice:
            m_type = "whisper"; m_size = "base"
        elif "Small" in choice:
            m_type = "whisper"; m_size = "small"
        elif "Medium" in choice:
            m_type = "whisper"; m_size = "medium"
        elif "TinyLlama" in choice:
            m_type = "tinyllama"; m_size = None
        elif "Llama 3" in choice:
            m_type = "llama3_8b"; m_size = None
        else:
            m_type = "whisper"; m_size = "tiny"

        self.download_model_on_demand(
            m_type,
            m_size,
            lambda success, err=None: self._on_settings_model_downloaded(success, err, m_type, m_size)
        )

    def _on_settings_model_downloaded(self, success, err, m_type, m_size):
        self.update_model_status()
        if success:
            self.show_notification("Model Downloaded", f"Model is ready in {self.settings.models_path}")
        else:
            self.show_notification("Download Failed", f"Could not download model: {err}")

    def save_session(self):
        """Save current playback and workspace state to kupido_session.json."""
        try:
            current_url = ""
            if hasattr(self, "url_entry"):
                current_url = self.url_entry.get().strip()
            if not current_url and hasattr(self, "player") and getattr(self.player, "current_url", None):
                current_url = self.player.current_url

            pos = getattr(self.player, "current_time", 0) if hasattr(self, "player") else 0
            vol = getattr(self.player, "volume", 50) if hasattr(self, "player") else 50
            loop = getattr(self.player, "is_looping", False) if hasattr(self, "player") else False
            tab = self.tab_view.get() if hasattr(self, "tab_view") else "Player"
            trans_src = self.transcribe_url.get().strip() if hasattr(self, "transcribe_url") else ""
            trans_txt = self.transcribe_result.get("1.0", tk.END).strip() if hasattr(self, "transcribe_result") else ""

            session_data = {
                "url": current_url,
                "position": pos,
                "volume": vol,
                "is_looping": loop,
                "active_tab": tab,
                "transcribe_url": trans_src,
                "transcribe_text": trans_txt,
                "timestamp": time.time(),
            }
            session_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kupido_session.json")
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2)
            self.show_notification("Session Saved", "Current playback and workspace session saved.")
        except Exception as e:
            logger.error(f"Save session error: {e}")
            self.show_notification("Error", f"Failed to save session: {e}")

    def load_session(self):
        """Load previously saved workspace and playback state."""
        try:
            session_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kupido_session.json")
            if not os.path.exists(session_file):
                self.show_notification("Notice", "No saved session found.")
                return
            with open(session_file, "r", encoding="utf-8") as f:
                session_data = json.load(f)

            url = session_data.get("url", "")
            if url:
                if hasattr(self, "url_entry"):
                    self.url_entry.delete(0, tk.END)
                    self.url_entry.insert(0, url)
                self.player.play_url(url)
                pos = session_data.get("position", 0)
                if pos > 0:
                    self.root.after(1500, lambda: self.player.seek(pos))

            vol = session_data.get("volume", 50)
            if hasattr(self.player, "set_volume"):
                self.player.set_volume(vol)
                if hasattr(self, "volume_slider"):
                    self.volume_slider.set(vol)

            tab = session_data.get("active_tab", "Player")
            if hasattr(self, "tab_view"):
                self.tab_view.set(tab)

            trans_src = session_data.get("transcribe_url", "")
            if trans_src and hasattr(self, "transcribe_url"):
                self.transcribe_url.delete(0, tk.END)
                self.transcribe_url.insert(0, trans_src)

            trans_txt = session_data.get("transcribe_text", "")
            if trans_txt and hasattr(self, "transcribe_result"):
                self.transcribe_result.delete("1.0", tk.END)
                self.transcribe_result.insert("1.0", trans_txt)

            self.show_notification("Session Restored", f"Session loaded successfully ({url or 'workspace'}).")
        except Exception as e:
            logger.error(f"Load session error: {e}")
            self.show_notification("Error", f"Failed to load session: {e}")

    def set_console_visibility(self, visible: bool):
        """Show or hide the Windows background terminal window."""
        try:
            import ctypes
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                SW_HIDE = 0
                SW_SHOW = 5
                ctypes.windll.user32.ShowWindow(hwnd, SW_SHOW if visible else SW_HIDE)
                self.console_visible = visible
                return True
        except Exception as e:
            logger.error(f"Console visibility error: {e}")
        return False

    def toggle_console(self):
        """Toggle visibility of background console window."""
        cur = getattr(self, "console_visible", True)
        new_state = not cur
        self.set_console_visibility(new_state)
        status = "SHOWN" if new_state else "HIDDEN"
        self.show_notification("Console", f"Background terminal {status.lower()}")
        if hasattr(self, "console_status_label"):
            self.console_status_label.configure(text=f"Console: {status}")

    def create_modern_info_tab(self):
        container = ctk.CTkFrame(self.info_tab, fg_color="transparent")
        container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        card = ModernCard(container)
        card.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        scroll = ctk.CTkScrollableFrame(card, fg_color="transparent")
        scroll.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        info_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        info_frame.pack(fill=tk.X, pady=10)

        try:
            icon_img = self.load_icon().resize((128, 128))
            icon_photo = ImageTk.PhotoImage(icon_img)
            icon_label = tk.Label(info_frame, image=icon_photo, bg=COLORS["surface"])
            icon_label.image = icon_photo
            icon_label.pack(pady=10)
        except:
            pass

        ctk.CTkLabel(
            info_frame,
            text=APP_NAME,
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color=COLORS["accent"],
        ).pack(pady=5)

        ctk.CTkLabel(
            info_frame,
            text=f"Version {APP_VERSION}",
            font=ctk.CTkFont(size=16),
            text_color=COLORS["text_secondary"],
        ).pack()

        ctk.CTkLabel(
            info_frame,
            text="A modern media player with AI transcription",
            font=ctk.CTkFont(size=14),
            text_color=COLORS["text_primary"],
        ).pack(pady=(10, 5))

        features_card = ModernCard(scroll)
        features_card.pack(fill=tk.X, pady=10)

        ctk.CTkLabel(
            features_card,
            text="✨ Features",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["accent"],
        ).pack(anchor="w", padx=15, pady=10)

        features = [
            "• Dual VLC players with smooth updates",
            "• Floating hover window (Ctrl+Shift+V)",
            "• Multi-language transcription with timestamps",
            "• LLM-powered text formatting (TinyLlama)",
            "• Text-to-Speech in 6 languages",
            "• Offline cache mode",
            "• 4K/HD downloads with original quality",
            "• Right-click context menus",
            "• Ad blocking via hosts file",
            "• Customizable keyboard shortcuts",
            "• Playback speed control (0.25x – 2.0x)",
            "• Go-to-time entry",
            "• Fallback audio-only mode if VLC missing",
        ]

        for feat in features:
            ctk.CTkLabel(
                features_card,
                text=feat,
                font=ctk.CTkFont(size=12),
                text_color=COLORS["text_secondary"],
                anchor="w",
            ).pack(anchor="w", padx=25, pady=2)

        dev_card = ModernCard(scroll)
        dev_card.pack(fill=tk.X, pady=10)

        ctk.CTkLabel(
            dev_card,
            text="👨‍💻 Developer",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["accent"],
        ).pack(anchor="w", padx=15, pady=10)

        ctk.CTkLabel(
            dev_card,
            text=f"Name: {DEV_INFO['name']}",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(anchor="w", padx=25, pady=2)

        ctk.CTkLabel(
            dev_card,
            text=f"Email: {DEV_INFO['email']}",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_primary"],
            anchor="w",
        ).pack(anchor="w", padx=25, pady=2)

        links_card = ModernCard(scroll)
        links_card.pack(fill=tk.X, pady=10)

        ctk.CTkLabel(
            links_card,
            text="🔗 Links",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["accent"],
        ).pack(anchor="w", padx=15, pady=10)

        links_frame = ctk.CTkFrame(links_card, fg_color="transparent")
        links_frame.pack(fill=tk.X, padx=20, pady=10)

        ctk.CTkButton(
            links_frame,
            text="📺 YouTube",
            width=120,
            height=35,
            corner_radius=18,
            fg_color=COLORS["error"],
            hover_color="#CC0000",
            command=lambda: webbrowser.open(DEV_INFO["youtube"]),
        ).pack(side=tk.LEFT, padx=5)

        ctk.CTkButton(
            links_frame,
            text="🌐 Website",
            width=120,
            height=35,
            corner_radius=18,
            fg_color=COLORS["success"],
            hover_color="#00997E",
            command=lambda: webbrowser.open(DEV_INFO["website"]),
        ).pack(side=tk.LEFT, padx=5)

        ctk.CTkButton(
            links_frame,
            text="📚 Docs",
            width=120,
            height=35,
            corner_radius=18,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=lambda: webbrowser.open(DOCS_URL),
        ).pack(side=tk.LEFT, padx=5)

        tech_card = ModernCard(scroll)
        tech_card.pack(fill=tk.X, pady=10)

        ctk.CTkLabel(
            tech_card,
            text="🛠️ Built With",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["accent"],
        ).pack(anchor="w", padx=15, pady=10)

        tech_frame = ctk.CTkFrame(tech_card, fg_color="transparent")
        tech_frame.pack(fill=tk.X, padx=20, pady=10)

        tech_items = [
            "Python 3.11+",
            "VLC Media Player",
            "yt-dlp",
            "Whisper AI",
            "TinyLlama",
            "CustomTkinter",
        ]

        for tech in tech_items:
            ctk.CTkLabel(
                tech_frame,
                text=f"• {tech}",
                font=ctk.CTkFont(size=12),
                text_color=COLORS["text_secondary"],
                anchor="w",
            ).pack(anchor="w", pady=2)

    def create_modern_status_bar(self):
        self.status_bar = ctk.CTkFrame(
            self.root, height=30, fg_color=COLORS["surface"], corner_radius=0
        )
        self.status_bar.grid(row=2, column=0, padx=0, pady=0, sticky="ew")
        self.status_bar.pack_propagate(False)

        self.status_label = ctk.CTkLabel(
            self.status_bar,
            text="✅ Ready",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["success"],
        )
        self.status_label.pack(side=tk.LEFT, padx=15)

        self.download_progress_label = ctk.CTkLabel(
            self.status_bar,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"],
        )
        self.download_progress_label.pack(side=tk.LEFT, padx=15)

        self.offline_status = ctk.CTkLabel(
            self.status_bar, text="", font=ctk.CTkFont(size=11)
        )
        self.offline_status.pack(side=tk.LEFT, padx=15)

        self.tray_indicator = ctk.CTkLabel(
            self.status_bar,
            text="● System Tray",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["success"],
        )
        self.tray_indicator.pack(side=tk.RIGHT, padx=15)

    def play_url(self):
        url = self.url_entry.get().strip()
        if not url:
            return

        self.update_status("⏳ Loading...")
        self.play_btn.configure(state="disabled")
        # Reset main player progress bar and elapsed/duration labels immediately
        if hasattr(self, "progress_bar") and self.progress_bar:
            self.progress_bar.set(0)
        if hasattr(self, "time_label") and self.time_label and self.time_label.winfo_exists():
            self.time_label.configure(text="0:00")
        if hasattr(self, "duration_label") and self.duration_label and self.duration_label.winfo_exists():
            self.duration_label.configure(text="0:00")

        use_cache = False
        if self.offline_mode and hasattr(self.offline_mode, "get"):
            use_cache = self.offline_mode.get()
        self.player.play_url(url, use_cache=use_cache)

    def seek_from_progress(self, percent):
        """Handle mouse click and drag seeking from main player progress bar."""
        dur = self.player.get_duration() if hasattr(self.player, "get_duration") else getattr(self.player, "duration", 0)
        if dur > 0:
            target_sec = (percent / 100.0) * dur
            if hasattr(self, "time_label") and self.time_label and self.time_label.winfo_exists():
                self.time_label.configure(text=self._format_time(target_sec))
            self.player.seek(percent / 100.0)

    def start_playback_update_loop(self):
        """Starts a high-fidelity 10 FPS UI update loop for progress bars, elapsed time, and duration."""
        self._update_playback_ui()

    def _update_playback_ui(self):
        try:
            # 1. Update Main Player UI (strictly using self.player)
            if hasattr(self, "player") and self.player and getattr(self.player, "vlc_available", False) and getattr(self.player, "player", None):
                dur = self.player.get_duration()
                cur = self.player.get_time()

                if dur > 0:
                    dur_str = self._format_time(dur)
                    if hasattr(self, "duration_label") and self.duration_label and self.duration_label.winfo_exists():
                        self.duration_label.configure(text=dur_str)
                elif hasattr(self, "duration_label") and self.duration_label and self.duration_label.winfo_exists():
                    self.duration_label.configure(text="0:00")

                if cur >= 0:
                    cur_str = self._format_time(cur)
                    if hasattr(self, "time_label") and self.time_label and self.time_label.winfo_exists():
                        self.time_label.configure(text=cur_str)

                if dur > 0 and cur >= 0:
                    pct = (cur / dur) * 100.0
                    if hasattr(self, "progress_bar") and self.progress_bar and self.progress_bar.winfo_exists():
                        if not getattr(self.progress_bar, "is_scrubbing", False):
                            self.progress_bar.set(pct)
                elif hasattr(self, "progress_bar") and self.progress_bar and self.progress_bar.winfo_exists():
                    if not getattr(self.progress_bar, "is_scrubbing", False):
                        self.progress_bar.set(0)

            # 2. Update Mini / Hover Player UI INDEPENDENTLY (strictly using self.hover_window.player)
            if hasattr(self, "hover_window") and self.hover_window and getattr(self.hover_window, "is_visible", False):
                hw = self.hover_window
                hw_player = getattr(hw, "player", None)
                if hw_player and getattr(hw_player, "vlc_available", False) and getattr(hw_player, "player", None):
                    hw_dur = hw_player.get_duration()
                    hw_cur = hw_player.get_time()

                    if hw_dur > 0:
                        hw_dur_str = self._format_time(hw_dur)
                        if hasattr(hw, "time_total") and hw.time_total and hw.time_total.winfo_exists():
                            hw.time_total.configure(text=hw_dur_str)
                    elif hasattr(hw, "time_total") and hw.time_total and hw.time_total.winfo_exists():
                        hw.time_total.configure(text="0:00")

                    if hw_cur >= 0:
                        hw_cur_str = self._format_time(hw_cur)
                        if hasattr(hw, "time_current") and hw.time_current and hw.time_current.winfo_exists():
                            hw.time_current.configure(text=hw_cur_str)

                    if hw_dur > 0 and hw_cur >= 0:
                        hw_pct = (hw_cur / hw_dur) * 100.0
                        hw_pb = getattr(hw, "progress_bar", None)
                        if hw_pb and hw_pb.winfo_exists() and not getattr(hw_pb, "is_scrubbing", False):
                            hw_pb.set(hw_pct)
                    elif hasattr(hw, "progress_bar"):
                        hw_pb = getattr(hw, "progress_bar", None)
                        if hw_pb and hw_pb.winfo_exists() and not getattr(hw_pb, "is_scrubbing", False):
                            hw_pb.set(0)
        except Exception:
            pass
        finally:
            if hasattr(self, "root") and self.root and self.root.winfo_exists():
                self.root.after(100, self._update_playback_ui)

    def play_callback(self, video_info, url):
        if hasattr(self, "play_btn") and self.play_btn:
            self.play_btn.configure(state="normal")
        self.update_status("▶ Playing")
        if video_info:
            title = video_info.get("title", "Ready")
            if hasattr(self, "now_playing"):
                self.now_playing.configure(text=title)
            
            # Format rich metadata (uploader, upload date, views, likes, quality)
            uploader = video_info.get("uploader", "Media")
            raw_date = str(video_info.get("upload_date", ""))
            date_str = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}" if len(raw_date) == 8 and raw_date.isdigit() else raw_date
            views = video_info.get("views", 0)
            views_str = f"{views:,} views" if views else ""
            likes = video_info.get("likes", 0)
            likes_str = f"{likes:,} likes" if likes else ""
            quality_text = video_info.get("quality", "HD")

            meta_parts = [f"👤 {uploader}"]
            if date_str:
                meta_parts.append(f"📅 {date_str}")
            if views_str:
                meta_parts.append(f"👁️ {views_str}")
            if likes_str:
                meta_parts.append(f"👍 {likes_str}")
            meta_parts.append(f"📺 {quality_text}")

            meta_summary = "  •  ".join(meta_parts)

            if hasattr(self, "meta_summary_label"):
                self.meta_summary_label.configure(text=meta_summary)
            if hasattr(self, "video_info"):
                self.video_info.configure(text=meta_summary)

            if hasattr(self, "description_box"):
                self.description_box.delete("1.0", tk.END)
                desc = video_info.get("description", "").strip() or f"Source: {url}"
                self.description_box.insert("1.0", desc)

            if hasattr(self, "duration_label"):
                self.duration_label.configure(
                    text=self._format_time(video_info.get("duration", 0))
                )
            self.add_to_history(url, title)
            if getattr(self.settings, "auto_load_subs", False):
                self.load_subtitles(url, title)
        else:
            self.update_status("❌ Playback failed")

    def load_subtitles(self, url, title="", lang="en", **kwargs):
        """Fetch and attach subtitles for the current media using yt-dlp or local files."""
        if not url:
            return
        def _fetch():
            try:
                base_opts = ToolManager.get_base_ydl_opts()
                ydl_opts = {
                    **base_opts,
                    "skip_download": True,
                    "writesubtitles": True,
                    "writeautomaticsub": True,
                    "subtitleslangs": [lang or "en"],
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    subs = info.get("subtitles", {}) or info.get("automatic_captions", {})
                    sub_entries = subs.get(lang, []) or subs.get("en", [])
                    sub_file = None
                    for entry in sub_entries:
                        if entry.get("ext") in ("vtt", "srt"):
                            import urllib.request, tempfile
                            tmp_sub = os.path.join(tempfile.gettempdir(), f"kupido_sub_{int(time.time())}.{entry['ext']}")
                            urllib.request.urlretrieve(entry["url"], tmp_sub)
                            sub_file = tmp_sub
                            break
                    if sub_file and hasattr(self, "player") and self.player:
                        self.root.after(0, lambda: self.player.set_subtitle_file(sub_file))
                        self.root.after(0, lambda: self.show_notification("Subtitles", f"Captions loaded ({lang})"))
            except Exception:
                pass
        threading.Thread(target=_fetch, daemon=True).start()

    def play_error(self, error):
        self.play_btn.configure(state="normal")
        self.update_status(f"❌ Error")

    def update_history_display(self):
        """Render recent history items matching current search query."""
        if not hasattr(self, "history_scroll") or not self.history_scroll.winfo_exists():
            return
        for widget in self.history_scroll.winfo_children():
            widget.destroy()

        q = getattr(self, "hist_search_var", None)
        query = q.get().lower().strip() if q else ""

        items = list(reversed(self.search_history))
        if query:
            items = [it for it in items if query in it.get("title", "").lower() or query in it.get("url", "").lower()]

        if not items:
            ctk.CTkLabel(
                self.history_scroll, text="No history items found.", font=ctk.CTkFont(size=12),
                text_color=COLORS["text_secondary"]
            ).pack(pady=40)
            return

        for item in items[:60]:
            card = ctk.CTkFrame(self.history_scroll, fg_color=COLORS["bg_light"], corner_radius=10)
            card.pack(fill=tk.X, padx=4, pady=3)

            info_box = ctk.CTkFrame(card, fg_color="transparent")
            info_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=12, pady=8)

            t = item.get("title", "Untitled Video")
            ctk.CTkLabel(
                info_box, text=t[:60], font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLORS["text_primary"], anchor="w"
            ).pack(anchor="w")

            meta = f"{item.get('timestamp', '')}  *  {item.get('url', '')[:45]}"
            ctk.CTkLabel(
                info_box, text=meta, font=ctk.CTkFont(size=10),
                text_color=COLORS["text_secondary"], anchor="w"
            ).pack(anchor="w", pady=(2, 0))

            action_box = ctk.CTkFrame(card, fg_color="transparent")
            action_box.pack(side=tk.RIGHT, padx=10, pady=8)

            url_val = item.get("url", "")
            ctk.CTkButton(
                action_box, text="▶ Play", width=64, height=28, corner_radius=14,
                fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                command=lambda u=url_val: self.play_from_history(u)
            ).pack(side=tk.LEFT, padx=2)

    def play_from_history(self, url):
        if url:
            if hasattr(self, "url_entry"):
                self.url_entry.delete(0, tk.END)
                self.url_entry.insert(0, url)
            self.tab_view.set("Player")
            self.play_url()

    def clear_history(self):
        self.search_history = []
        self.save_history()
        self.update_history_display()

    def update_progress(self, current_time):
        now = time.time()
        if now - self._last_update < 0.1:
            return

        self._last_update = now

        lbl = getattr(self, "time_label", None) or getattr(self, "current_time_label", None)
        if lbl and hasattr(lbl, "winfo_exists") and lbl.winfo_exists():
            lbl.configure(text=self._format_time(current_time))
        if hasattr(self, "progress_bar") and self.progress_bar and self.player.duration > 0:
            self.progress_bar.set((current_time / self.player.duration) * 100)

    def update_duration(self, duration):
        lbl = getattr(self, "duration_label", None)
        if lbl and hasattr(lbl, "winfo_exists") and lbl.winfo_exists():
            lbl.configure(text=self._format_time(duration))

    def on_video_end(self):
        self.update_status("⏹️ Video ended")
        if hasattr(self, "progress_bar") and self.progress_bar:
            self.progress_bar.set(0)
        lbl = getattr(self, "time_label", None) or getattr(self, "current_time_label", None)
        if lbl and hasattr(lbl, "winfo_exists") and lbl.winfo_exists():
            lbl.configure(text="0:00")
        self.update_play_button()
        # Auto-play next in playlist if enabled
        if getattr(self, "pl_autoplay_var", None) and self.pl_autoplay_var.get() and hasattr(self, "play_next_playlist_item"):
            self.play_next_playlist_item()

    def update_network_cache(self, value):
        self.settings.network_caching = value
        self.network_cache_label.configure(text=f"{value}ms")
        self.settings.save()

    def save_shortcut(self, action, shortcut):
        self.settings.hotkeys[action] = shortcut
        self.settings.save()
        self.setup_hotkeys()
        self.show_notification("Shortcut", f"{action} updated")

    def browse_download_path(self):
        path = filedialog.askdirectory(initialdir=self.settings.download_path)
        if path:
            self.settings.download_path = path
            self.download_path_label.configure(text=path)
            self.settings.save()

    def toggle_auto_subs(self):
        self.settings.auto_load_subs = self.auto_sub_var.get()
        self.settings.save()

    def apply_sub_lang(self):
        self.settings.subtitle_lang = self.sub_lang.get()
        self.settings.save()
        self.show_notification(
            "Settings", f"Subtitle language set to {self.sub_lang.get()}"
        )

    def toggle_adblock(self):
        if self.adblock_var.get():
            self.adblocker.enable_adblock()
            self.show_notification("Ad Block", "Ad blocking enabled")
        else:
            self.adblocker.disable_adblock()
            self.show_notification("Ad Block", "Ad blocking disabled")

    def apply_tts(self):
        engine = self.tts_engine_combo.get()
        self.settings.tts_engine = engine
        self.settings.save()
        self.transcriber.tts.set_engine(engine)
        self.show_notification("TTS", f"Engine set to {engine}")

    def show_notification(self, title, message):
        self.update_status(f"{title}: {message}")
        self.root.after(3000, lambda: self.update_status("✅ Ready"))

    def update_status(self, message):
        if self.root:
            self.root.after(0, lambda: self.status_label.configure(text=message))

    def toggle_hover(self):
        if self.hover_window:
            self.hover_window.toggle()
            if self.hover_window.is_visible:
                self.hover_btn.configure(fg_color=COLORS["success"])
            else:
                self.hover_btn.configure(fg_color=COLORS["bg_light"])

    def toggle_loop(self):
        is_looping = self.player.toggle_loop()
        color = COLORS["success"] if is_looping else COLORS["bg_light"]
        if hasattr(self, "loop_btn") and self.loop_btn and self.loop_btn.winfo_exists():
            self.loop_btn.configure(fg_color=color)
        if hasattr(self, "player_loop_btn") and self.player_loop_btn and self.player_loop_btn.winfo_exists():
            self.player_loop_btn.configure(fg_color=color)
        if (
            self.hover_window
            and hasattr(self.hover_window, "loop_btn")
            and self.hover_window.loop_btn
            and self.hover_window.loop_btn.winfo_exists()
        ):
            self.hover_window.loop_btn.configure(fg_color=color)
        self.show_notification(
            "Loop", f"Loop {'enabled' if is_looping else 'disabled'}"
        )

    def toggle_fullscreen(self):
        self.player.toggle_fullscreen(self.root)

    def change_volume(self, value):
        self.player.set_volume(int(value))

    def show_download_dialog(self, url=None):
        """Robust download dialog with single/bulk URL support, custom filenames, format selection, and immediate feedback."""
        if not url:
            url = self.url_entry.get().strip() if hasattr(self, "url_entry") else ""
            if not url and hasattr(self.player, "current_url"):
                url = self.player.current_url or ""

        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Download Media (Single or Bulk)")
        dialog.geometry("540x600")
        dialog.transient(self.root)

        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - 270
        y = (dialog.winfo_screenheight() // 2) - 300
        dialog.geometry(f"+{x}+{y}")

        card = ModernCard(dialog)
        card.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Header with Kupido logo
        hdr_box = ctk.CTkFrame(card, fg_color="transparent")
        hdr_box.pack(pady=(12, 4))
        ctk.CTkLabel(
            hdr_box, text="  Kupido Media Downloader",
            image=IconFactory.get("kupido", (28, 28)), compound="left",
            font=ctk.CTkFont(size=16, weight="bold"), text_color=COLORS["accent"]
        ).pack()
        ctk.CTkLabel(card, text="Enter a single media URL or multiple URLs (separated by newlines)", font=ctk.CTkFont(size=10), text_color=COLORS["text_secondary"]).pack(pady=(0, 6))

        # URL Input Text Area
        url_text = ctk.CTkTextbox(card, height=70, corner_radius=12, fg_color=COLORS["bg_light"], border_width=0)
        url_text.pack(fill=tk.X, padx=16, pady=4)
        if url:
            url_text.insert("1.0", url)

        # Custom Filename
        fn_frame = ctk.CTkFrame(card, fg_color="transparent")
        fn_frame.pack(fill=tk.X, padx=16, pady=4)
        ctk.CTkLabel(fn_frame, text="Filename:", width=70, font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"], anchor="w").pack(side=tk.LEFT)
        rename_var = tk.StringVar(value="")
        ctk.CTkEntry(
            fn_frame, textvariable=rename_var, placeholder_text="Custom name (or blank for original title)...",
            height=30, corner_radius=15, border_width=0, fg_color=COLORS["bg_light"]
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Folder Selection
        folder_frame = ctk.CTkFrame(card, fg_color="transparent")
        folder_frame.pack(fill=tk.X, padx=16, pady=4)
        ctk.CTkLabel(folder_frame, text="Folder:", width=70, font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"], anchor="w").pack(side=tk.LEFT)

        base_dl = self.settings.download_path
        custom_folder_path = [base_dl]

        def browse_folder():
            ch = filedialog.askdirectory(initialdir=custom_folder_path[0])
            if ch:
                custom_folder_path[0] = ch
                folder_lbl.configure(text=os.path.basename(ch) or ch)

        folder_lbl = ctk.CTkLabel(folder_frame, text=os.path.basename(base_dl) or "Downloads", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLORS["accent_light"])
        folder_lbl.pack(side=tk.LEFT, padx=4)

        ctk.CTkButton(
            folder_frame, text=" Browse", image=IconFactory.get("folder", (14, 14)), width=85, height=28, corner_radius=14,
            fg_color=COLORS["bg_light"], hover_color=COLORS["accent"], command=browse_folder
        ).pack(side=tk.LEFT, padx=6)

        # Format & Quality
        fmt_frame = ctk.CTkFrame(card, fg_color="transparent")
        fmt_frame.pack(fill=tk.X, padx=16, pady=4)
        ctk.CTkLabel(fmt_frame, text="Format:", width=70, font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"], anchor="w").pack(side=tk.LEFT)

        format_var = tk.StringVar(value="mp4 (video)")
        format_menu = ctk.CTkOptionMenu(
            fmt_frame, values=[
                "mp4 (video)", "mkv (video)", "webm (video)", "mov (video)",
                "mp3 (audio)", "m4a (audio)", "wav (audio)", "flac (audio)", "opus (audio)"
            ],
            variable=format_var, width=140, height=30, corner_radius=15, fg_color=COLORS["bg_light"], button_color=COLORS["accent"]
        )
        format_menu.pack(side=tk.LEFT, padx=(0, 6))

        quality_var = tk.StringVar(value="best")
        quality_menu = ctk.CTkOptionMenu(
            fmt_frame, values=["best", "4K", "1080p", "720p", "480p"],
            variable=quality_var, width=90, height=30, corner_radius=15, fg_color=COLORS["bg_light"], button_color=COLORS["accent"]
        )
        quality_menu.pack(side=tk.LEFT)

        # Bitrate
        bitrate_frame = ctk.CTkFrame(card, fg_color="transparent")
        bitrate_frame.pack(fill=tk.X, padx=16, pady=4)
        ctk.CTkLabel(bitrate_frame, text="Bitrate:", width=70, font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"], anchor="w").pack(side=tk.LEFT)
        bitrate_var = tk.StringVar(value="192k")
        ctk.CTkOptionMenu(
            bitrate_frame, values=["320k", "256k", "192k", "128k"],
            variable=bitrate_var, width=100, height=30, corner_radius=15, fg_color=COLORS["bg_light"], button_color=COLORS["accent"]
        ).pack(side=tk.LEFT)

        # Cache toggle
        cache_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            card, text="Save to Offline Library immediately", variable=cache_var,
            font=ctk.CTkFont(size=11), fg_color=COLORS["accent"]
        ).pack(anchor="w", padx=16, pady=(6, 4))

        def start_download_tasks():
            raw_input = url_text.get("1.0", tk.END).strip()
            if not raw_input:
                self.show_notification("Notice", "Please enter at least one URL")
                return

            raw_urls = [line.strip() for line in raw_input.splitlines() if line.strip()]
            urls_to_dl = [u for u in raw_urls if u.startswith("http") or os.path.exists(u)]
            if not urls_to_dl and raw_urls:
                urls_to_dl = [raw_urls[0]]

            dialog.destroy()
            self.tab_view.set("Downloads")

            for target_url in urls_to_dl:
                self._dispatch_download(
                    target_url,
                    rename_var.get().strip() if len(urls_to_dl) == 1 else "",
                    custom_folder_path[0],
                    format_var.get().split()[0],
                    quality_var.get(),
                    bitrate_var.get(),
                    cache_var.get()
                )

        btn_box = ctk.CTkFrame(card, fg_color="transparent")
        btn_box.pack(pady=(12, 10))

        ctk.CTkButton(
            btn_box, text=" Download", image=IconFactory.get("download", (16, 16)), width=130, height=36, corner_radius=18,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(size=13, weight="bold"),
            command=start_download_tasks
        ).pack(side=tk.LEFT, padx=6)

        ctk.CTkButton(
            btn_box, text=" Cancel", image=IconFactory.get("close", (14, 14)), width=100, height=36, corner_radius=18,
            fg_color=COLORS["bg_light"], hover_color=COLORS["border"],
            command=dialog.destroy
        ).pack(side=tk.LEFT, padx=6)

    def _dispatch_download(self, url, custom_name, dest_dir, fmt, quality, bitrate, save_to_cache):
        """Worker dispatcher for concurrent downloads with robust format specifications."""
        download_id = f"dl_{int(time.time() * 1000)}_{len(self.download_items)}"
        self.add_download_item(download_id, url, fmt, quality)

        def _worker():
            try:
                os.makedirs(dest_dir, exist_ok=True)

                ff_avail = ToolManager.is_ffmpeg_available()
                if fmt in ["mp3", "m4a", "wav", "flac", "opus"]:
                    format_spec = "bestaudio/best" if ff_avail else "bestaudio[ext=m4a]/bestaudio/best"
                elif not ff_avail:
                    format_spec = "best[ext=mp4]/best"
                elif quality == "best":
                    format_spec = "bestvideo+bestaudio/best"
                elif quality == "4K":
                    format_spec = "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best"
                else:
                    h = quality.replace("p", "")
                    format_spec = f"bestvideo[height<={h}]+bestaudio/best[height<={h}]/best"

                if custom_name:
                    safe_title = re.sub(r'[<>:"/\|?*]', '_', custom_name)
                    out_tmpl = os.path.join(dest_dir, f"{safe_title}.%(ext)s")
                else:
                    out_tmpl = os.path.join(dest_dir, "%(title)s.%(ext)s")

                base_opts = ToolManager.get_base_ydl_opts()
                ydl_opts = {
                    **base_opts,
                    "format": format_spec,
                    "outtmpl": out_tmpl,
                    "ignoreerrors": False,
                    "progress_hooks": [lambda d: self._download_hook(d, download_id)],
                }

                if fmt in ["mp4", "mkv", "webm", "mov"]:
                    ydl_opts["merge_output_format"] = fmt

                if fmt in ["mp3", "m4a", "wav", "flac", "opus"]:
                    ydl_opts["postprocessors"] = [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": fmt,
                        "preferredquality": bitrate.replace("k", ""),
                    }]

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if not info:
                        raise RuntimeError("Failed to extract media information")
                    if "entries" in info and info["entries"]:
                        final_fn = ydl.prepare_filename(info["entries"][0])
                        title = info["entries"][0].get("title", os.path.basename(final_fn))
                    else:
                        final_fn = ydl.prepare_filename(info)
                        title = info.get("title", os.path.basename(final_fn))

                    if fmt in ["mp3", "wav", "m4a", "flac", "opus", "webm", "mkv", "mov"]:
                        final_fn = final_fn.rsplit(".", 1)[0] + f".{fmt}"

                    file_sz = os.path.getsize(final_fn) if os.path.exists(final_fn) else 0

                    if save_to_cache and hasattr(self, "cache_manager"):
                        self.cache_manager.add_to_cache(url, title, final_fn, source="download")

                    self.root.after(0, lambda: self.download_completed(download_id, final_fn, title, file_sz))
            except Exception as e:
                err_msg = str(e)
                print(f"[ERROR] Download failure: {err_msg}")
                self.root.after(0, lambda: self.download_failed(download_id, err_msg))

        threading.Thread(target=_worker, daemon=True).start()

    def _download_hook(self, d, download_id):
        """Clean numerical download percentage and ETA formatted string."""
        if d.get("status") == "downloading":
            total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)

            percent = 0.0
            if total_bytes > 0:
                percent = round((downloaded / total_bytes) * 100, 1)

            eta_raw = d.get("eta")
            if eta_raw is not None and eta_raw >= 0:
                mins = int(eta_raw // 60)
                secs = int(eta_raw % 60)
                eta_str = f"ETA: {mins:02d}:{secs:02d}"
            else:
                eta_str = "ETA: --:--"

            self.root.after_idle(
                lambda: self.update_download_progress(download_id, percent, eta_str, total_bytes)
            )

    def add_download_item(self, download_id, url, fmt, quality):
        item = DownloadItem(
            self.download_scroll, download_id, "Loading...", fmt, quality, app=self
        )
        self.download_items[download_id] = item

    def update_download_progress(self, download_id, percent, speed, size):
        if download_id in self.download_items:
            self.download_items[download_id].update_progress(percent, speed, size)
            self.download_progress_label.configure(text=f"⬇ {percent}%")

    def download_completed(self, download_id, filename, title, file_size):
        if download_id in self.download_items:
            self.download_items[download_id].complete(filename, file_size, app=self)
            self.download_progress_label.configure(text="✅ Complete")
            self.update_status("✅ Download complete")

    def play_downloaded_file(self, filepath):
        """Launch downloaded video or audio directly in main player."""
        if filepath and os.path.exists(filepath):
            if hasattr(self, "url_entry"):
                self.url_entry.delete(0, tk.END)
                self.url_entry.insert(0, filepath)
            self.player.play_url(filepath)
            self.tab_view.set("Player")
            self.show_notification("Playing", f"Now playing: {os.path.basename(filepath)}")

    def download_failed(self, download_id, error):
        if download_id in self.download_items:
            self.download_items[download_id].fail(error)
            self.download_progress_label.configure(text="❌ Failed")
            self.update_status("❌ Download failed")

    def clear_all_downloads(self):
        for item in self.download_items.values():
            item.frame.destroy()
        self.download_items.clear()
        self.show_notification("Downloads", "Cleared all downloads")

    def update_cache_display(self):
        if hasattr(self, "cache_scroll"):
            for widget in self.cache_scroll.winfo_children():
                widget.destroy()

            cached = self.cache_manager.get_all_cached()
            if not cached:
                no_cache_label = ctk.CTkLabel(
                    self.cache_scroll,
                    text="No cached videos.\nDownload videos with 'Save to offline cache' option.",
                    font=ctk.CTkFont(size=14),
                    text_color=COLORS["text_secondary"],
                )
                no_cache_label.pack(pady=50)
                return

            for video_info in cached:
                CacheVideoFrame(self.cache_scroll, video_info, self)

    def clear_all_cache(self):
        self.cache_manager.clear_cache()
        self.update_cache_display()
        self.show_notification("Cache", "Offline cache cleared")

    def clear_cache(self):
        return self.clear_all_cache()

    def _format_size(self, size_bytes):
        if size_bytes == 0:
            return "0 B"
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        return f"{size_bytes:.1f} {size_names[i]}"

    def browse_audio_file(self):
        filename = filedialog.askopenfilename(
            title="Select Audio or Video File",
            filetypes=[
                ("Media files", "*.mp3 *.wav *.m4a *.flac *.mp4 *.mkv *.webm *.mov *.avi"),
                ("Audio files", "*.mp3 *.wav *.m4a *.flac"),
                ("Video files", "*.mp4 *.mkv *.webm *.mov *.avi"),
                ("All files", "*.*"),
            ],
        )
        if filename:
            if hasattr(self, "transcribe_url"):
                self.transcribe_url.delete(0, tk.END)
                self.transcribe_url.insert(0, filename)

    def use_current_media_for_transcribe(self):
        url = ""
        if hasattr(self, "player") and getattr(self.player, "current_url", None):
            url = self.player.current_url
        elif hasattr(self, "url_entry"):
            url = self.url_entry.get().strip()
        if url:
            if hasattr(self, "transcribe_url"):
                self.transcribe_url.delete(0, tk.END)
                self.transcribe_url.insert(0, url)
                self.show_notification("Transcribe", "Loaded current media source")
        else:
            self.show_notification("Notice", "No media is currently playing. Paste a URL or select a file.")

    def load_subtitles_to_player(self):
        """Inject current transcription as an active subtitle file into the playing media."""
        try:
            if not hasattr(self, "current_transcription") or not self.current_transcription:
                self.show_notification("Notice", "No transcription generated yet to load as subtitles")
                return
            temp_dir = os.path.join(tempfile.gettempdir(), "kupido_subs")
            os.makedirs(temp_dir, exist_ok=True)
            temp_srt = os.path.join(temp_dir, f"subtitles_{int(time.time())}.srt")
            segs = self.current_transcription.get("segments", [])
            if not segs and "text" in self.current_transcription:
                segs = [{"number": 1, "start": 0, "end": 10, "text": self.current_transcription["text"]}]

            if hasattr(self, "transcriber") and self.transcriber:
                if self.transcriber.save_as_srt(segs, temp_srt):
                    if hasattr(self, "player") and self.player:
                        success = self.player.set_subtitle_file(temp_srt)
                        if success:
                            self.show_notification("Subtitles Loaded", "Live subtitles injected into player!")
                            self.tab_view.set("Player")
                        else:
                            self.show_notification("Notice", f"Subtitle file created: {temp_srt}. Make sure video is playing.")
        except Exception as e:
            logger.error(f"Load subtitle error: {e}")
            self.show_notification("Error", f"Failed to load subtitles: {e}")

    def start_transcription(self):
        source = ""
        if hasattr(self, "transcribe_url"):
            source = self.transcribe_url.get().strip()
        if not source and hasattr(self, "player") and getattr(self.player, "current_url", None):
            source = self.player.current_url
        if not source and hasattr(self, "url_entry"):
            source = self.url_entry.get().strip()

        if not source:
            self.show_notification("Error", "Please enter a URL or select a file to transcribe")
            return

        lang_name = self.transcribe_lang.get() if hasattr(self, "transcribe_lang") else "English"
        lang_code = LANGUAGES.get(lang_name, {}).get("code", "en")
        raw_model = self.transcribe_model.get() if hasattr(self, "transcribe_model") else "medium"
        model_selection = raw_model.split()[0].lower()
        style = self.format_style.get() if hasattr(self, "format_style") else "timestamps"

        if model_selection == "llama":
            model_size = "medium"
        else:
            model_size = model_selection

        model_path = os.path.join(self.settings.models_path, f"{model_size}.pt")
        if not os.path.exists(model_path) and model_selection != "llama":
            response = messagebox.askyesno(
                "Model Missing",
                f"Whisper model '{model_size}' not found. Download it now? (Size varies)",
            )
            if response:
                if hasattr(self, "transcribe_start_btn"):
                    self.transcribe_start_btn.configure(state="disabled")
                if hasattr(self, "model_status_label"):
                    self.model_status_label.configure(text=f"Downloading {model_size} model...")
                self.download_model_on_demand(
                    "whisper",
                    model_size,
                    lambda success, err=None: self._after_model_download(
                        success, err, source, lang_code, model_size, style
                    ),
                )
            return

        self._run_transcription(source, lang_code, model_size, style)

    def download_model_on_demand(self, model_type, model_size, callback):
        self.model_dialog = ModelLoadingDialog(
            self.root, title=f"Downloading {model_type}"
        )
        self.update_status(f"Downloading {model_type} model...")

        def download_thread():
            if model_type == "whisper":
                model_name = f"whisper_{model_size}"
                model_path = os.path.join(self.settings.models_path, f"{model_size}.pt")

                def progress(p, m):
                    self.root.after_idle(lambda: self.model_dialog.update_progress(p, m))
                    self.root.after_idle(lambda: self.update_status(m))

                success = ModelDownloader.download_model(
                    model_name, model_path, progress
                )
                if success:
                    self.settings.models_downloaded["whisper"] = True
                    self.settings.save()
                    self.root.after_idle(lambda: self.model_dialog.close())
                    self.root.after_idle(lambda: self.update_status("✅ Model downloaded"))
                    self.root.after_idle(lambda: callback(True))
                else:
                    self.root.after_idle(lambda: self.model_dialog.close())
                    self.root.after_idle(lambda: self.update_status("❌ Download failed"))
                    self.root.after_idle(lambda: callback(False, "Download failed"))
            elif model_type == "tinyllama":
                model_path = os.path.join(
                    self.settings.models_path, "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
                )

                def progress(p, m):
                    self.root.after_idle(lambda: self.model_dialog.update_progress(p, m))
                    self.root.after_idle(lambda: self.update_status(m))

                success = ModelDownloader.download_model(
                    "tinyllama", model_path, progress
                )
                if success:
                    self.settings.models_downloaded["tinyllama"] = True
                    self.settings.save()
                    self.root.after_idle(lambda: self.model_dialog.close())
                    self.root.after_idle(lambda: self.update_status("✅ Model downloaded"))
                    self.root.after_idle(lambda: callback(True))
                else:
                    self.root.after_idle(lambda: self.model_dialog.close())
                    self.root.after_idle(lambda: self.update_status("❌ Download failed"))
                    self.root.after_idle(lambda: callback(False, "TinyLlama download failed"))

        threading.Thread(target=download_thread, daemon=True).start()

    def _after_model_download(
        self, success, error, source, lang_code, model_size, style
    ):
        self.transcribe_start_btn.configure(state="normal")
        if success:
            self.model_status_label.configure(
                text="Model downloaded. Starting transcription..."
            )
            self._run_transcription(source, lang_code, model_size, style)
        else:
            self.model_status_label.configure(text=f"Download failed: {error}")
            self.transcribe_result.delete("1.0", "end")
            self.transcribe_result.insert("1.0", f"❌ Model download failed: {error}")

    def _run_transcription(self, source, lang_code, model_size, style):
        self.transcribe_result.delete("1.0", "end")
        self.transcribe_result.insert("1.0", "⏳ Transcribing... Please wait...")
        self.transcribe_progress.set(0)
        self.transcribe_status.configure(text="Starting...")

        def progress_callback(percent, message):
            self.root.after(
                0, lambda: self._update_transcribe_progress(percent, message)
            )

        def transcribe_thread():
            if source.startswith("http"):
                result, title = self.transcriber.transcribe_from_url(
                    source, lang_code, model_size, progress_callback
                )
                if result:
                    self.root.after(0, self.display_transcription, result, title, style)
                else:
                    error_msg = self.transcriber.last_error or "Transcription failed"
                    self.root.after(0, lambda: self._transcription_error(error_msg))
            else:
                progress_callback(10, "Loading audio...")
                result = self.transcriber.transcribe(source, lang_code, model_size)
                if result:
                    progress_callback(100, "Complete!")
                    self.root.after(
                        0,
                        self.display_transcription,
                        result,
                        os.path.basename(source),
                        style,
                    )
                else:
                    error_msg = self.transcriber.last_error or "Transcription failed"
                    self.root.after(0, lambda: self._transcription_error(error_msg))

        threading.Thread(target=transcribe_thread, daemon=True).start()

    def _transcription_error(self, error):
        self.transcribe_result.delete("1.0", "end")
        self.transcribe_result.insert("1.0", f"❌ {error}")
        self.model_status_label.configure(text=error)

    def _update_transcribe_progress(self, percent, message):
        self.transcribe_progress.set(percent)
        self.transcribe_status.configure(text=message)

    def display_transcription(self, result, title, style):
        self.transcribe_result.delete("1.0", "end")
        self.current_transcription = result

        if style == "timestamps":
            text = f"Title: {title}\n\n"
            for seg in result["segments"]:
                start = self._format_time(seg["start"])
                end = self._format_time(seg["end"])
                text += (
                    f"{seg.get('number', '')}\n[{start} --> {end}]\n{seg['text']}\n\n"
                )
        elif style == "summary" and self.transcriber.tinyllama_model:
            formatted = self.transcriber.format_with_tinyllama(
                result["text"], "summary"
            )
            text = f"Title: {title}\n\nSummary:\n{formatted}"
        else:
            sentences = re.split(r"(?<=[.!?])\s+", result["text"])
            if style == "single":
                formatted = " ".join(sentences)
            elif style == "paragraph":
                formatted = "\n\n".join(sentences)
            else:
                formatted = result["text"]
            text = f"Title: {title}\n\n{formatted}"

        self.transcribe_result.insert("1.0", text)

    def format_transcription(self):
        if not self.current_transcription:
            self.show_notification("Error", "No transcription to format")
            return
        style = self.format_style.get()

        tinyllama_path = os.path.join(
            self.settings.models_path, "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
        )
        if not os.path.exists(tinyllama_path):
            response = messagebox.askyesno(
                "TinyLlama Missing",
                "TinyLlama model not found. Download it now? (700 MB)",
            )
            if response:
                self.transcribe_format_btn.configure(state="disabled")
                self.download_model_on_demand(
                    "tinyllama",
                    None,
                    lambda success, err=None: self._after_tiny_download(
                        success, err, style
                    ),
                )
            return

        if self.transcriber.tinyllama_model:
            formatted = self.transcriber.format_with_tinyllama(
                self.current_transcription["text"], style
            )
        else:
            sentences = re.split(r"(?<=[.!?])\s+", self.current_transcription["text"])
            if style == "single":
                formatted = " ".join(sentences)
            elif style == "paragraph":
                formatted = "\n\n".join(sentences)
            else:
                formatted = self.current_transcription["text"]

        self.transcribe_result.delete("1.0", "end")
        self.transcribe_result.insert(
            "1.0", f"Formatted Text ({style}):\n\n{formatted}"
        )

    def _after_tiny_download(self, success, error, style):
        self.transcribe_format_btn.configure(state="normal")
        if success:
            self.transcriber.load_tinyllama_if_needed()
            self.format_transcription()
        else:
            self.model_status_label.configure(
                text=f"TinyLlama download failed: {error}"
            )

    def speak_transcription(self):
        if not self.current_transcription:
            self.show_notification("Error", "No transcription to speak")
            return
        text = self.current_transcription["text"]
        lang_name = self.transcribe_lang.get()
        lang_code = LANGUAGES[lang_name]["code"]
        self.transcribe_status.configure(text="Speaking...")

        def speak_thread():
            self.transcriber.tts.speak(text, lang_code)
            self.root.after(0, lambda: self.transcribe_status.configure(text=""))

        threading.Thread(target=speak_thread, daemon=True).start()

    def handle_main_play_pause(self):
        """Unified play/pause toggle that starts playback if idle or toggles pause/play."""
        url = self.url_entry.get().strip() if hasattr(self, "url_entry") else ""
        cur = getattr(self.player, "current_url", "") or ""

        # If user entered or changed URL, or nothing is currently loaded in VLC:
        if url and (not cur or url != cur):
            self.play_url()
            return

        # If a video is already loaded and playing/paused:
        if self.player and getattr(self.player, "player", None) and cur:
            try:
                state = self.player.player.get_state()
                if state in (vlc.State.Playing, vlc.State.Buffering):
                    self.player.toggle_play_pause()
                    self.update_play_button()
                    self.update_status("Paused")
                    return
                elif state in (vlc.State.Paused, vlc.State.Stopped):
                    self.player.toggle_play_pause()
                    self.update_play_button()
                    self.update_status("Playing")
                    return
            except Exception:
                pass

        if url:
            self.play_url()
        else:
            self.show_notification("Notice", "Paste a video link or open a file to play")

    def update_title(self, title):
        if hasattr(self, "title_label") and self.title_label and self.title_label.winfo_exists():
            self.title_label.configure(text=str(title)[:45])

    def update_play_button(self):
        """Update main toolbar and player panel play buttons to reflect VLC state."""
        is_playing = getattr(self.player, "is_playing", False)
        if self.player.vlc_available and getattr(self.player, "player", None):
            try:
                state = self.player.player.get_state()
                if state in (vlc.State.Playing, vlc.State.Buffering):
                    is_playing = True
                elif state == vlc.State.Paused:
                    is_playing = False
            except Exception:
                pass

        try:
            icon_img = IconFactory.get("pause" if is_playing else "play", (18, 18))
            if hasattr(self, "pp_btn") and self.pp_btn and self.pp_btn.winfo_exists():
                self.pp_btn.configure(image=icon_img)
            if hasattr(self, "play_btn") and self.play_btn and self.play_btn.winfo_exists():
                self.play_btn.configure(image=icon_img)
        except Exception:
            pass

    def load_subtitles(self, url, title):
        """Safely handle subtitles without 429 errors breaking playback."""
        pass

    def save_as_srt(self):
        try:
            if hasattr(self, "current_transcription") and self.current_transcription:
                filename = filedialog.asksaveasfilename(
                    defaultextension=".srt",
                    filetypes=[("SRT files", "*.srt"), ("All files", "*.*")],
                )
                if filename and hasattr(self, "transcriber") and self.transcriber:
                    if self.transcriber.save_as_srt(self.current_transcription.get("segments", []), filename):
                        self.show_notification("Success", "SRT file saved")
        except Exception as e:
            logger.error(f"Save SRT error: {e}")

    def save_as_txt(self):
        try:
            if hasattr(self, "current_transcription") and self.current_transcription:
                filename = filedialog.asksaveasfilename(
                    defaultextension=".txt",
                    filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                )
                if filename and hasattr(self, "transcriber") and self.transcriber:
                    if self.transcriber.save_as_txt(self.current_transcription.get("text", ""), filename):
                        self.show_notification("Success", "Text file saved")
        except Exception as e:
            logger.error(f"Save TXT error: {e}")

    def save_as_pdf(self):
        try:
            if hasattr(self, "current_transcription") and self.current_transcription:
                filename = filedialog.asksaveasfilename(
                    defaultextension=".pdf",
                    filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                )
                if filename and hasattr(self, "transcriber") and self.transcriber:
                    if self.transcriber.save_as_pdf(self.current_transcription.get("text", ""), filename):
                        self.show_notification("Success", "PDF file saved")
        except Exception as e:
            logger.error(f"Save PDF error: {e}")

    def save_as_json(self):
        try:
            if hasattr(self, "current_transcription") and self.current_transcription:
                filename = filedialog.asksaveasfilename(
                    defaultextension=".json",
                    filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                )
                if filename and hasattr(self, "transcriber") and self.transcriber:
                    if self.transcriber.save_as_json(self.current_transcription, filename):
                        self.show_notification("Success", "JSON file saved")
        except Exception as e:
            logger.error(f"Save JSON error: {e}")

    def _format_time(self, seconds):
        if seconds < 0:
            return "0:00"
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    def show_window(self):
        if self.root:
            self.root.deiconify()
            self.root.lift()
            self.tray_indicator.configure(
                text="● Visible", text_color=COLORS["success"]
            )

    def hide_window(self):
        if self.root:
            self.root.withdraw()
            self.tray_indicator.configure(
                text="● System Tray", text_color=COLORS["text_secondary"]
            )

    def quit_app(self):
        try:
            self.settings.save()
            self.save_history()
            self.cleanup()
            if self.root:
                self.root.quit()
                self.root.destroy()
            os._exit(0)
        except Exception as e:
            print(f"Quit error: {e}")
            os._exit(0)


def main():
    try:
        ToolManager.init_env()
        print("Starting Kupido Player 4.5...", flush=True)
        root = ctk.CTk()
        root.withdraw()

        # Window & Taskbar Icon
        ico_p = resource_path("kupido.ico")
        if os.path.exists(ico_p):
            try:
                root.iconbitmap(ico_p)
            except Exception:
                pass

        splash = None
        try:
            splash = SplashScreen(root)
            splash.update_progress(10, "Initializing Kupido Player...")
        except Exception as e:
            print(f"Splash notice: {e}", flush=True)

        app = KupidoApp(root, splash)

        def finish_startup():
            try:
                if splash:
                    splash.close()
            except Exception:
                pass
            try:
                root.deiconify()
                root.lift()
                root.after(50, lambda: root.focus_force() if root.winfo_exists() else None)
                print("Kupido Player is ready and running!", flush=True)
            except Exception as ex:
                print(f"Window presentation notice: {ex}")

        if splash:
            splash.update_progress(100, "Ready!")
        root.after(50, finish_startup)
        root.mainloop()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\nFatal startup error: {e}", flush=True)
        try:
            input("Press Enter to exit...")
        except:
            pass


if __name__ == "__main__":
    main()
