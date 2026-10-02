"""
AURA / JARVIS Windows Workspace & Multi-Window Architect.
=========================================================
Voice-controlled desktop window manipulation, tiling, and layout manager
using native Win32 APIs (win32gui, win32con, ctypes).
"""

import ctypes
import win32gui
import win32con
from typing import List, Dict, Any, Optional


def get_screen_dimensions():
    """Gets the resolution of the primary display monitor."""
    user32 = ctypes.windll.user32
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def find_windows_by_title(keyword: str) -> List[int]:
    """Finds all visible window handles matching a title keyword."""
    matches = []
    kw = keyword.lower().strip()

    def enum_handler(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd).strip()
            if title and kw in title.lower():
                matches.append(hwnd)
        return True

    win32gui.EnumWindows(enum_handler, None)
    return matches


def bring_window_to_front(keyword: str) -> str:
    """Restores and brings a specific window to the foreground."""
    hwnds = find_windows_by_title(keyword)
    if not hwnds:
        return f"Could not find any active window matching '{keyword}', Sir."

    hwnd = hwnds[0]
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(hwnd)
    title = win32gui.GetWindowText(hwnd)
    return f"Brought '{title[:35]}' to the front, Sir."


def snap_window(keyword: str, side: str = "left", ratio: float = 0.5) -> str:
    """Snaps the specified window to the left or right portion of the primary screen."""
    hwnds = find_windows_by_title(keyword)
    if not hwnds:
        return f"No matching window found for '{keyword}', Sir."

    hwnd = hwnds[0]
    screen_w, screen_h = get_screen_dimensions()

    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

    if side.lower() == "left":
        x = 0
        y = 0
        w = int(screen_w * ratio)
        h = screen_h - 40  # reserve space for Windows taskbar
    else:  # right
        w = int(screen_w * (1.0 - ratio))
        x = screen_w - w
        y = 0
        h = screen_h - 40

    win32gui.MoveWindow(hwnd, x, y, w, h, True)
    win32gui.SetForegroundWindow(hwnd)
    title = win32gui.GetWindowText(hwnd)
    return f"Snapped '{title[:30]}' to the {side} side ({int(ratio*100 if side=='left' else (1-ratio)*100)}% width), Sir."


def arrange_coding_workspace() -> str:
    """Snaps VS Code to the left 60% and Browser to the right 40%."""
    screen_w, screen_h = get_screen_dimensions()
    h = screen_h - 40

    code_hwnds = find_windows_by_title("visual studio code") or find_windows_by_title("code")
    browser_hwnds = find_windows_by_title("chrome") or find_windows_by_title("edge") or find_windows_by_title("firefox") or find_windows_by_title("brave")

    arranged = []

    if code_hwnds:
        hwnd_code = code_hwnds[0]
        win32gui.ShowWindow(hwnd_code, win32con.SW_RESTORE)
        w_code = int(screen_w * 0.60)
        win32gui.MoveWindow(hwnd_code, 0, 0, w_code, h, True)
        arranged.append("VS Code (60% Left)")

    if browser_hwnds:
        hwnd_br = browser_hwnds[0]
        win32gui.ShowWindow(hwnd_br, win32con.SW_RESTORE)
        w_br = int(screen_w * 0.40)
        x_br = screen_w - w_br
        win32gui.MoveWindow(hwnd_br, x_br, 0, w_br, h, True)
        arranged.append("Browser (40% Right)")

    if arranged:
        return f"Workspace arranged, Sir: {', '.join(arranged)}."
    return "Neither VS Code nor a supported browser was found open to tile, Sir."


def minimize_all_except(keyword: str) -> str:
    """Minimizes all top-level windows except the one matching the keyword."""
    keep_hwnds = find_windows_by_title(keyword)
    if not keep_hwnds:
        return f"Could not find any window matching '{keyword}' to keep focused, Sir."

    keep_hwnd = keep_hwnds[0]
    keep_title = win32gui.GetWindowText(keep_hwnd)

    minimized_count = 0

    def enum_handler(hwnd, extra):
        nonlocal minimized_count
        if win32gui.IsWindowVisible(hwnd) and hwnd != keep_hwnd:
            title = win32gui.GetWindowText(hwnd).strip()
            # Don't minimize the shell or taskbar
            if title and title not in ["Program Manager", "Settings", "Windows Shell Experience Host"]:
                try:
                    win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                    minimized_count += 1
                except Exception:
                    pass
        return True

    win32gui.EnumWindows(enum_handler, None)
    win32gui.ShowWindow(keep_hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(keep_hwnd)

    return f"Minimized {minimized_count} background windows. Kept '{keep_title[:30]}' focused, Sir."
