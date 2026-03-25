"""System tray launcher pro discord-noter."""

import subprocess
import sys
import threading
from pathlib import Path

from PIL import Image, ImageDraw
import pystray

BOT_SCRIPT = Path(__file__).parent / "bot.py"
PYTHON = sys.executable

_process: subprocess.Popen | None = None
_icon: pystray.Icon | None = None


# ── Ikony ─────────────────────────────────────────────────────────────────────

def _make_icon(running: bool) -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = (88, 101, 242) if running else (128, 132, 142)  # Discord blue / šedá
    draw.ellipse([8, 8, 56, 56], fill=color)
    # Malý zelený/červený indikátor
    dot = (87, 242, 135) if running else (237, 66, 69)
    draw.ellipse([38, 38, 56, 56], fill=dot)
    return img


# ── Bot process ───────────────────────────────────────────────────────────────

def _is_running() -> bool:
    return _process is not None and _process.poll() is None


def _start(_icon, _item=None):
    global _process
    if _is_running():
        return
    _process = subprocess.Popen([PYTHON, str(BOT_SCRIPT)], cwd=BOT_SCRIPT.parent)
    _refresh()


def _stop(_icon, _item=None):
    global _process
    if _process and _is_running():
        _process.terminate()
        _process.wait(timeout=10)
    _process = None
    _refresh()


def _restart(_icon, _item=None):
    _stop(_icon)
    _start(_icon)


def _exit(_icon, _item=None):
    _stop(_icon)
    _icon.stop()


# ── Tray menu ─────────────────────────────────────────────────────────────────

def _menu() -> pystray.Menu:
    return pystray.Menu(
        pystray.MenuItem(
            lambda _: "● Bot běží" if _is_running() else "○ Bot zastaven",
            None,
            enabled=False,
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Spustit", _start, enabled=lambda _: not _is_running()),
        pystray.MenuItem("Zastavit", _stop, enabled=lambda _: _is_running()),
        pystray.MenuItem("Restartovat", _restart, enabled=lambda _: _is_running()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Ukončit", _exit),
    )


def _refresh():
    if _icon:
        _icon.icon = _make_icon(_is_running())
        _icon.title = "discord-noter — běží" if _is_running() else "discord-noter — zastaven"


# ── Watchdog — aktualizuje ikonu pokud bot spadne ─────────────────────────────

def _watchdog():
    import time
    last = None
    while True:
        now = _is_running()
        if now != last:
            _refresh()
            last = now
        time.sleep(3)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    global _icon
    _icon = pystray.Icon(
        name="discord-noter",
        icon=_make_icon(False),
        title="discord-noter — zastaven",
        menu=_menu(),
    )
    threading.Thread(target=_watchdog, daemon=True).start()
    _icon.run()


if __name__ == "__main__":
    main()
