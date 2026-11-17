"""Terminal formatting and dashboard rendering; no hardware access."""

import os
import platform
import shutil
import sys
from datetime import datetime
from textwrap import wrap

ACCENT = "\033[96m"
WARN = "\033[93m"
CRIT = "\033[91m"
RESET = "\033[0m"

USAGE_WARN = 70
USAGE_CRIT = 90
TEMP_WARN = 80
TEMP_CRIT = 90
LEVEL_COLORS = {"ok": "", "warn": WARN, "crit": CRIT}


def fmt(value, unit=""):
    """Format a stat, showing N/A (without a unit) when it is unavailable."""
    return "N/A" if value is None else f"{value}{unit}"


def color_enabled():
    return not os.environ.get("NO_COLOR") and sys.stdout.isatty()


def paint(text, color):
    if color_enabled() and color:
        return f"{color}{text}{RESET}"
    return text


def level(value, warn, crit):
    if value is None:
        return "ok"
    if value >= crit:
        return "crit"
    return "warn" if value >= warn else "ok"


def paint_level(text, value, warn=USAGE_WARN, crit=USAGE_CRIT):
    return paint(text, LEVEL_COLORS[level(value, warn, crit)])


def bar(percent, width):
    width = max(10, width)
    filled, empty = "█", "░"
    try:
        (filled + empty).encode(sys.stdout.encoding or "ascii")
    except (UnicodeEncodeError, LookupError):
        filled, empty = "#", "-"
    count = round(width * min(100, max(0, percent or 0)) / 100)
    return filled * count + empty * (width - count)


def usage_percent(used, total):
    return None if used is None or not total else used / total * 100


def _capacity_text(used, total):
    percent = usage_percent(used, total)
    percent_text = "N/A" if percent is None else f"{percent:.0f}%"
    used_text = "N/A" if used is None else f"{used:.2f}".rstrip("0").rstrip(".")
    total_text = "N/A" if total is None else f"{total:.2f}".rstrip("0").rstrip(".")
    return percent, f"{percent_text}  {used_text} / {total_text} GB"


def render_dashboard(stats, status="ACTIVE"):
    width = max(40, min(shutil.get_terminal_size((80, 24)).columns, 64))
    now = datetime.now()
    ram_percent, ram_text = _capacity_text(stats["ram_used"], stats["ram_total"])
    disk_percent, disk_text = _capacity_text(stats["disk_used"], stats["disk_total"])
    rows = [
        ("CPU", stats["cpu"], fmt(stats["cpu"], "%")),
        ("GPU", stats["gpu"], fmt(stats["gpu"], "%")),
        ("RAM", ram_percent, ram_text),
        ("DISK", disk_percent, disk_text),
    ]
    bar_width = max(10, width - 9 - max(len(text) for _, _, text in rows))
    value_width = width - bar_width - 9

    print(paint("=" * width, ACCENT))
    print(paint("EDITH TERMINAL".center(width), ACCENT))
    print(paint("=" * width, ACCENT))
    status_color = WARN if status == "MONITORING" else ACCENT
    print("STATUS: " + paint(status, status_color))
    print()
    print(paint("[ SYSTEM STATS ]", ACCENT))
    for label, percent, text in rows:
        lines = wrap(text, value_width)
        cells = bar(percent, bar_width)
        print(f"{label:<5} " + paint_level(f"[{cells}] {lines[0]}", percent))
        for line in lines[1:]:
            print(" " * (bar_width + 9) + paint_level(line, percent))

    print()
    temperatures = []
    temperature_width = 6
    for label, key in (("CPU", "cpu_temp"), ("GPU", "gpu_temp")):
        value = stats[key]
        text = fmt(value, "°C")
        temperature_width += len(label) + 1 + len(text)
        temperatures.append(label + " " + paint_level(text, value, TEMP_WARN, TEMP_CRIT))
    if temperature_width + 3 <= width:
        print("TEMP  " + " | ".join(temperatures))
    else:
        print("TEMP  " + temperatures[0])
        print("      " + temperatures[1])
    print("CACHE " + fmt(stats["cache"], " GB"))

    print()
    print(paint("[ INFO ]", ACCENT))
    print(f"TIME  : {now:%H:%M:%S}")
    print(f"DATE  : {now:%d-%m-%Y}")
    print("\n".join(wrap(f"OS    : {platform.system()}", width)))

    print()
    print(paint("[ COMMANDS ]", ACCENT))
    print("\n".join(wrap("help   cpu   ram   disk   temp   monitor   clear   exit", width)))
    print()
    print(paint("-" * width, ACCENT))
