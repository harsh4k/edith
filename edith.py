import os
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager

import psutil

from edith_display import (
    ACCENT,
    TEMP_CRIT,
    TEMP_WARN,
    paint,
    paint_level,
    render_dashboard,
    usage_percent,
)
from edith_display import fmt as fmt

GB = 1024**3

# Sensor names that report the CPU package, in order of preference.
CPU_SENSORS = ("coretemp", "k10temp", "zenpower", "cpu_thermal", "cpu-thermal", "acpitz")


# ===== CLEAR =====
def clear():
    os.system("cls" if os.name == "nt" else "clear")


# ===== SENSORS =====
def cpu_temperature():
    """CPU temperature in °C, or None if the platform doesn't expose one."""
    try:
        temps = psutil.sensors_temperatures()
    except (AttributeError, OSError):  # not available on Windows/macOS
        return None
    if not temps:
        return None
    for name in CPU_SENSORS:
        if temps.get(name):
            return temps[name][0].current
    return next((readings[0].current for readings in temps.values() if readings), None)


def find_nvidia_smi():
    path = shutil.which("nvidia-smi")
    if path is None and os.name == "nt":
        legacy = os.path.join(
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            "NVIDIA Corporation",
            "NVSMI",
            "nvidia-smi.exe",
        )
        if os.path.isfile(legacy):
            path = legacy
    return path


def _to_int(field):
    """nvidia-smi prints '[N/A]' or '[Not Supported]' for missing fields."""
    try:
        return int(field.strip())
    except ValueError:
        return None


def gpu_stats():
    """(load %, temperature °C) of the first NVIDIA GPU; either may be None."""
    smi = find_nvidia_smi()
    if smi is None:
        return None, None
    try:
        out = subprocess.run(
            [smi, "--query-gpu=utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        ).stdout
        load, temp = out.splitlines()[0].split(",")
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None, None
    return _to_int(load), _to_int(temp)


# ===== CPU =====
# psutil.cpu_percent() averages since its previous call: calls milliseconds
# apart return noise (0% or 50%), calls minutes apart hide the current load.
CPU_MIN_AGE = 0.5  # reuse a reading younger than this
CPU_MAX_AGE = 5.0  # older than this, measure afresh for 0.3s
_cpu_last = {"time": None, "value": 0.0}


def cpu_usage():
    last = _cpu_last["time"]
    age = None if last is None else time.monotonic() - last
    if age is not None and age < CPU_MIN_AGE:
        return _cpu_last["value"]
    if age is None or age > CPU_MAX_AGE:
        _cpu_last["value"] = psutil.cpu_percent(interval=0.3)
    else:
        _cpu_last["value"] = psutil.cpu_percent()
    _cpu_last["time"] = time.monotonic()
    return _cpu_last["value"]


def ram_gb():
    ram = psutil.virtual_memory()
    return round(ram.used / GB, 2), round(ram.total / GB, 2)


def disk_gb():
    disk = psutil.disk_usage("/")
    return round(disk.used / GB, 2), round(disk.total / GB, 2)


# ===== SYSTEM STATS =====
def get_stats():
    ram_used, ram_total = ram_gb()
    disk_used, disk_total = disk_gb()
    gpu_load, gpu_temp = gpu_stats()
    cache = getattr(psutil.virtual_memory(), "cached", None)  # Linux only

    return {
        "cpu": cpu_usage(),
        "ram_used": ram_used,
        "ram_total": ram_total,
        "disk_used": disk_used,
        "disk_total": disk_total,
        "cache": None if cache is None else round(cache / GB, 2),
        "cpu_temp": cpu_temperature(),
        "gpu": gpu_load,
        "gpu_temp": gpu_temp,
    }


# ===== KEY INPUT =====
@contextmanager
def single_keys():
    """On a POSIX terminal, deliver key presses without Enter and without echo.

    Held for the whole monitor session so keys pressed mid-redraw aren't echoed.
    Yields True when active; otherwise sleep_or_key() falls back to whole lines.
    """
    if os.name == "nt" or not sys.stdin.isatty():
        yield False
        return
    import termios
    import tty

    fd = sys.stdin.fileno()
    try:
        saved = termios.tcgetattr(fd)
        tty.setcbreak(fd)
    except termios.error:  # e.g. some IDE consoles
        yield False
        return
    try:
        yield True
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)


def sleep_or_key(seconds, single=False):
    """Sleep for `seconds`, returning True early if a key was pressed."""
    if os.name == "nt":
        import msvcrt

        end = time.time() + seconds
        while time.time() < end:
            if msvcrt.kbhit():
                while msvcrt.kbhit():  # arrow/function keys send two bytes
                    msvcrt.getch()
                return True
            time.sleep(0.05)
        return False

    import select

    ready, _, _ = select.select([sys.stdin], [], [], seconds)
    if not ready:
        return False
    if single:
        import termios

        termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)  # drop key + escape bytes
    else:
        sys.stdin.readline()
    return True


# ===== DASHBOARD =====
def dashboard(status="ACTIVE"):
    stats = get_stats()  # collect first so the screen isn't blank while sampling
    clear()
    render_dashboard(stats, status)


# ===== MAIN LOOP =====
def run():
    dashboard()

    while True:
        try:
            cmd = input(paint("EDITH > ", ACCENT)).strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nShutting down EDITH...")
            break

        if not cmd:
            continue

        elif cmd == "help":
            print("help, cpu, ram, disk, temp, monitor, clear, exit")

        elif cmd == "clear":
            dashboard()

        elif cmd == "cpu":
            value = cpu_usage()
            print("CPU Usage: " + paint_level(fmt(value, "%"), value))

        elif cmd == "ram":
            used, total = ram_gb()
            print("RAM: " + paint_level(f"{used} / {total} GB", usage_percent(used, total)))

        elif cmd == "disk":
            used, total = disk_gb()
            print("Disk: " + paint_level(f"{used} / {total} GB", usage_percent(used, total)))

        elif cmd == "temp":
            _, gpu_temp = gpu_stats()
            cpu_temp = cpu_temperature()
            cpu_text = paint_level(fmt(cpu_temp, "°C"), cpu_temp, TEMP_WARN, TEMP_CRIT)
            gpu_text = paint_level(fmt(gpu_temp, "°C"), gpu_temp, TEMP_WARN, TEMP_CRIT)
            print(f"CPU Temp: {cpu_text} | GPU Temp: {gpu_text}")

        elif cmd == "monitor":
            try:
                with single_keys() as single:
                    while True:
                        dashboard("MONITORING")
                        print("Press any key to stop...")
                        if sleep_or_key(2, single):
                            break
            except KeyboardInterrupt:
                pass

            dashboard()

        elif cmd == "exit":
            print("Shutting down EDITH...")
            break

        else:
            print(f"Unknown command: {cmd}  (type 'help')")


# ===== START =====
if __name__ == "__main__":
    run()
