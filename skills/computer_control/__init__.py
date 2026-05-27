"""
Computer control skill — merged from YahavisAI's `computer/` modules.

Wraps:
  - app_manager     (open / close / list apps)
  - browser_control (URL navigation via system browser)
  - file_ops        (search, read, write, list)
  - mouse_keyboard  (click, type, hotkey)
  - screen_reader   (OCR, find on screen)
  - system_ops      (screenshot, volume, brightness, info)

Cross-platform best-effort. Degrades gracefully when host dependencies
(mss, pyautogui, pygetwindow) aren't installed — common on headless
Render free tier. Designed to run with full power on Boss's Windows /
macOS / Linux desktop or via the Tauri shell.
"""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from core.logger import get_logger

log = get_logger("skill:computer_control")

manifest = {
    "description": (
        "Desktop control — open/close apps, screenshot, type, click, "
        "system info, file ops, browser URL launch. Best-effort cross-platform."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": [
                "open_app", "close_app", "list_apps", "open_url",
                "screenshot", "type_text", "click", "mouse_move", "hotkey",
                "system_info", "volume", "brightness",
                "file_search", "file_read", "file_write", "file_list",
            ]},
            "name":       {"type": "string"},
            "url":        {"type": "string"},
            "text":       {"type": "string"},
            "x":          {"type": "integer"},
            "y":          {"type": "integer"},
            "keys":       {"type": "array", "items": {"type": "string"}},
            "level":      {"type": "number"},
            "query":      {"type": "string"},
            "path":       {"type": "string"},
            "content":    {"type": "string"},
            "root":       {"type": "string"},
            "save_path":  {"type": "string"},
        },
        "required": ["action"],
    },
}


# ---------------- app management ----------------------------------------
APP_MAP_WINDOWS = {
    "vs code": "code", "vscode": "code", "chrome": "chrome", "firefox": "firefox",
    "notepad": "notepad", "calculator": "calc", "explorer": "explorer",
    "task manager": "taskmgr", "cmd": "cmd", "powershell": "powershell",
    "terminal": "wt", "word": "winword", "excel": "excel", "powerpoint": "powerpnt",
    "outlook": "outlook", "slack": "slack", "spotify": "spotify",
    "discord": "discord", "edge": "msedge",
}

APP_MAP_MAC = {
    "vs code": "Visual Studio Code", "vscode": "Visual Studio Code",
    "chrome": "Google Chrome", "firefox": "Firefox", "safari": "Safari",
    "terminal": "Terminal", "finder": "Finder", "notes": "Notes",
    "calculator": "Calculator", "slack": "Slack", "spotify": "Spotify",
}


def _is_win()  -> bool: return platform.system() == "Windows"
def _is_mac()  -> bool: return platform.system() == "Darwin"
def _is_linux() -> bool: return platform.system() == "Linux"


def _open_app(name: str) -> dict:
    raw = name.lower().strip()
    if _is_win():
        exe = APP_MAP_WINDOWS.get(raw, raw)
        try:
            subprocess.Popen(["cmd", "/c", "start", "", exe], shell=False)
            return {"ok": True, "platform": "windows", "exe": exe}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
    if _is_mac():
        app = APP_MAP_MAC.get(raw, name)
        try:
            subprocess.Popen(["open", "-a", app])
            return {"ok": True, "platform": "darwin", "app": app}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
    if _is_linux():
        for candidate in (raw, raw.replace(" ", "-")):
            if shutil.which(candidate):
                subprocess.Popen([candidate])
                return {"ok": True, "platform": "linux", "exe": candidate}
        return {"ok": False, "error": f"no executable for '{raw}' on PATH"}
    return {"ok": False, "error": "unsupported platform"}


def _close_app(name: str) -> dict:
    if _is_win():
        subprocess.run(["taskkill", "/F", "/IM", name + ".exe"], capture_output=True)
        return {"ok": True}
    if _is_mac():
        subprocess.run(["pkill", "-x", name], capture_output=True)
        return {"ok": True}
    if _is_linux():
        subprocess.run(["pkill", "-f", name], capture_output=True)
        return {"ok": True}
    return {"ok": False, "error": "unsupported platform"}


def _list_apps() -> dict:
    try:
        if _is_win():
            r = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True)
            apps = [line.split('","')[0].strip('"') for line in r.stdout.splitlines() if line]
        elif _is_mac():
            r = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to get name of (every process whose background only is false)'],
                capture_output=True, text=True)
            apps = [a.strip() for a in r.stdout.split(",")]
        else:
            r = subprocess.run(["ps", "-eo", "comm"], capture_output=True, text=True)
            apps = sorted(set(line.strip() for line in r.stdout.splitlines() if line))
        return {"count": len(apps), "apps": apps[:120]}
    except Exception as exc:
        return {"error": str(exc)}


def _open_url(url: str) -> dict:
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        if _is_win():
            os.startfile(url)  # noqa: WPS328
        elif _is_mac():
            subprocess.Popen(["open", url])
        else:
            subprocess.Popen(["xdg-open", url])
        return {"ok": True, "url": url}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------- screenshot / mouse / keyboard --------------------------
def _screenshot(save_path: str | None = None) -> dict:
    target = save_path or f"/tmp/screenshot_{int(time.time())}.png"
    try:
        import mss
        import mss.tools
        with mss.mss() as sct:
            img = sct.grab(sct.monitors[0])
            mss.tools.to_png(img.rgb, img.size, output=target)
        return {"ok": True, "path": target, "engine": "mss"}
    except ImportError:
        pass
    try:
        from PIL import ImageGrab
        ImageGrab.grab().save(target)
        return {"ok": True, "path": target, "engine": "PIL"}
    except Exception as exc:
        return {"ok": False, "error": f"no screenshot backend available ({exc})"}


def _type_text(text: str) -> dict:
    try:
        import pyautogui
        pyautogui.typewrite(text, interval=0.02)
        return {"ok": True}
    except ImportError:
        return {"ok": False, "error": "pyautogui not installed"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _click(x: int | None, y: int | None) -> dict:
    try:
        import pyautogui
        pyautogui.click(x=x, y=y)
        return {"ok": True, "pos": (x, y)}
    except ImportError:
        return {"ok": False, "error": "pyautogui not installed"}


def _mouse_move(x: int, y: int) -> dict:
    try:
        import pyautogui
        pyautogui.moveTo(x, y, duration=0.2)
        return {"ok": True}
    except ImportError:
        return {"ok": False, "error": "pyautogui not installed"}


def _hotkey(keys: list[str]) -> dict:
    try:
        import pyautogui
        pyautogui.hotkey(*keys)
        return {"ok": True, "keys": keys}
    except ImportError:
        return {"ok": False, "error": "pyautogui not installed"}


# ---------------- system info / volume / brightness ----------------------
def _system_info() -> dict:
    info: dict[str, Any] = {
        "platform": platform.system(),
        "release":  platform.release(),
        "machine":  platform.machine(),
        "python":   platform.python_version(),
        "hostname": platform.node(),
        "user":     os.environ.get("USER") or os.environ.get("USERNAME"),
        "cwd":      os.getcwd(),
    }
    try:
        import psutil
        info["cpu_percent"] = psutil.cpu_percent(interval=0.2)
        info["memory_percent"] = psutil.virtual_memory().percent
        info["disk_percent"] = psutil.disk_usage("/").percent
        battery = psutil.sensors_battery()
        if battery:
            info["battery"] = {"percent": battery.percent, "plugged": battery.power_plugged}
    except ImportError:
        pass
    return info


def _volume(level: float) -> dict:
    """Set volume 0.0–1.0. Best-effort per OS."""
    pct = max(0, min(100, int(level * 100)))
    try:
        if _is_mac():
            subprocess.run(["osascript", "-e", f"set volume output volume {pct}"], check=False)
            return {"ok": True, "percent": pct}
        if _is_linux():
            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{pct}%"], check=False)
            return {"ok": True, "percent": pct}
        if _is_win():
            # nirsoft nircmd is a common dep; otherwise fall back to PowerShell
            subprocess.run(
                ["powershell", "-Command",
                 f"$wsh = New-Object -ComObject WScript.Shell; (1..{pct/2}) | %{{$wsh.SendKeys([char]175)}}"],
                check=False)
            return {"ok": True, "percent": pct, "note": "windows volume keys"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": False, "error": "unsupported platform"}


def _brightness(level: float) -> dict:
    pct = max(0, min(100, int(level * 100)))
    try:
        if _is_linux():
            subprocess.run(["brightnessctl", "set", f"{pct}%"], check=False)
            return {"ok": True, "percent": pct}
        if _is_win():
            subprocess.run(
                ["powershell", "-Command",
                 f"(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{pct})"],
                check=False)
            return {"ok": True, "percent": pct}
        if _is_mac():
            try:
                import brightness  # type: ignore
                brightness.set_brightness(pct / 100)
                return {"ok": True, "percent": pct}
            except ImportError:
                return {"ok": False, "error": "install `brightness` (brew) for macOS brightness control"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": False, "error": "unsupported platform"}


# ---------------- file operations ----------------------------------------
def _file_search(query: str, root: str = ".") -> dict:
    matches = []
    rp = Path(root).expanduser()
    if not rp.exists():
        return {"error": f"root not found: {rp}"}
    for p in rp.rglob("*"):
        if query.lower() in p.name.lower():
            matches.append(str(p))
            if len(matches) >= 200:
                break
    return {"matches": matches, "count": len(matches)}


def _file_read(path: str) -> dict:
    p = Path(path).expanduser()
    if not p.exists():
        return {"error": "not found"}
    return {"path": str(p), "size": p.stat().st_size,
            "text": p.read_text(errors="replace")[:30000]}


def _file_write(path: str, content: str) -> dict:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return {"ok": True, "bytes": len(content), "path": str(p)}


def _file_list(root: str = ".") -> dict:
    rp = Path(root).expanduser()
    if not rp.exists():
        return {"error": "not found"}
    items = []
    for entry in sorted(rp.iterdir()):
        items.append({"name": entry.name,
                      "is_dir": entry.is_dir(),
                      "size": entry.stat().st_size if entry.is_file() else 0})
    return {"path": str(rp), "items": items}


# =========================================================================
async def run(action: str, **kwargs: Any) -> dict:
    return await asyncio.to_thread(_dispatch, action, kwargs)


def _dispatch(action: str, kw: dict) -> dict:
    if action == "open_app":     return _open_app(kw["name"])
    if action == "close_app":    return _close_app(kw["name"])
    if action == "list_apps":    return _list_apps()
    if action == "open_url":     return _open_url(kw["url"])
    if action == "screenshot":   return _screenshot(kw.get("save_path"))
    if action == "type_text":    return _type_text(kw["text"])
    if action == "click":        return _click(kw.get("x"), kw.get("y"))
    if action == "mouse_move":   return _mouse_move(kw["x"], kw["y"])
    if action == "hotkey":       return _hotkey(kw["keys"])
    if action == "system_info":  return _system_info()
    if action == "volume":       return _volume(float(kw["level"]))
    if action == "brightness":   return _brightness(float(kw["level"]))
    if action == "file_search":  return _file_search(kw["query"], kw.get("root", "."))
    if action == "file_read":    return _file_read(kw["path"])
    if action == "file_write":   return _file_write(kw["path"], kw["content"])
    if action == "file_list":    return _file_list(kw.get("root", "."))
    return {"error": f"unknown action: {action}"}
