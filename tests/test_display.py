import os
import re
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import edith
import edith_display as display


@pytest.mark.parametrize(
    "no_color,tty,enabled",
    [
        (None, True, True),
        ("", True, True),
        ("1", True, False),
        ("0", True, False),
        (None, False, False),
        ("", False, False),
        ("1", False, False),
    ],
)
def test_paint_color_control(monkeypatch, no_color, tty, enabled):
    if no_color is None:
        monkeypatch.delenv("NO_COLOR", raising=False)
    else:
        monkeypatch.setenv("NO_COLOR", no_color)
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(isatty=lambda: tty))
    assert display.color_enabled() is enabled
    expected = f"{display.WARN}text{display.RESET}" if enabled else "text"
    assert display.paint("text", display.WARN) == expected
    assert display.paint("text", "") == "text"


def test_paint_rechecks_color_once_per_call(monkeypatch):
    enabled = Mock(side_effect=[True, False])
    monkeypatch.setattr(display, "color_enabled", enabled)
    assert display.paint("text", display.WARN) == f"{display.WARN}text{display.RESET}"
    assert display.paint("text", display.WARN) == "text"
    assert enabled.call_count == 2


@pytest.mark.parametrize(
    "value,expected", [(None, "ok"), (69, "ok"), (70, "warn"), (89, "warn"), (90, "crit")]
)
def test_level_usage_boundaries(value, expected):
    assert display.level(value, display.USAGE_WARN, display.USAGE_CRIT) == expected


@pytest.mark.parametrize(
    "value,expected", [(None, "ok"), (79, "ok"), (80, "warn"), (89, "warn"), (90, "crit")]
)
def test_level_temperature_boundaries(value, expected):
    assert display.level(value, display.TEMP_WARN, display.TEMP_CRIT) == expected


@pytest.mark.parametrize(
    "percent,width,filled",
    [
        (None, 10, 0),
        (-10, 10, 0),
        (0, 10, 0),
        (50, 10, 5),
        (100, 10, 10),
        (150, 10, 10),
        (50, 0, 5),
        (50, -1, 5),
        (50, 20, 10),
    ],
)
def test_bar_clamp_and_width(monkeypatch, percent, width, filled):
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(encoding="utf-8", isatty=lambda: False))
    assert display.bar(percent, width) == "█" * filled + "░" * (max(10, width) - filled)


@pytest.mark.parametrize("encoding", ["cp1252", "ascii", None, "unknown-encoding"])
def test_bar_ascii_fallback(monkeypatch, encoding):
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(encoding=encoding, isatty=lambda: False))
    assert display.bar(50, 10) == "#####-----"
    assert display.bar(None, 10) == "----------"


@pytest.mark.parametrize(
    "used,total,expected",
    [(9.8, 16, 61.25), (0, 16, 0), (1, 0, None), (None, 16, None), (1, None, None)],
)
def test_usage_percent(used, total, expected):
    result = display.usage_percent(used, total)
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected)


@pytest.fixture
def dashboard_stats(monkeypatch):
    stats = {
        "cpu": 42,
        "gpu": 37,
        "ram_used": 9.8,
        "ram_total": 16,
        "disk_used": 420,
        "disk_total": 476,
        "cache": 1.25,
        "cpu_temp": 72,
        "gpu_temp": 55,
    }
    monkeypatch.setattr(edith, "get_stats", Mock(return_value=stats))
    monkeypatch.setattr(edith, "clear", Mock())
    monkeypatch.setattr(display.platform, "system", lambda: "Windows")
    return stats


@pytest.mark.parametrize("columns,frame_width", [(20, 40), (40, 40), (64, 64), (120, 64)])
@pytest.mark.parametrize(
    "tty,no_color,colored", [(True, "1", False), (True, None, True), (False, None, False)]
)
@pytest.mark.parametrize("missing_gpu", [False, True])
def test_dashboard_width_and_no_color(
    monkeypatch, capsys, dashboard_stats, columns, frame_width, tty, no_color, colored, missing_gpu
):
    terminal_size = Mock(return_value=os.terminal_size((columns, 24)))
    monkeypatch.setattr(display.shutil, "get_terminal_size", terminal_size)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: tty)
    if no_color is None:
        monkeypatch.delenv("NO_COLOR", raising=False)
    else:
        monkeypatch.setenv("NO_COLOR", no_color)
    if missing_gpu:
        dashboard_stats.update(gpu=None, gpu_temp=None)

    edith.dashboard()
    output = capsys.readouterr().out
    if colored:
        assert display.ACCENT in output
    else:
        assert "\033" not in output
    plain = re.sub(r"\x1b\[[0-9;]*m", "", output)
    lines = plain.splitlines()
    assert all(len(line) <= frame_width for line in lines)
    assert lines[0] == lines[2] == "=" * frame_width
    assert lines[-1] == "-" * frame_width
    usage_rows = [line for line in lines if line.startswith(("CPU ", "GPU ", "RAM ", "DISK "))]
    bars = [line.split("[", 1)[1].split("]", 1)[0] for line in usage_rows]
    assert len(usage_rows) == 4
    assert len({len(cells) for cells in bars}) == 1
    assert len(bars[0]) >= 10
    assert max(len(line) for line in usage_rows) == frame_width
    assert "STATUS: ACTIVE" in plain
    assert "[ INFO ]" in plain
    assert "[ COMMANDS ]" in plain
    assert "61%  9.8 / 16 GB" in plain
    assert "88%  420 / 476 GB" in plain
    assert "CACHE 1.25 GB" in plain
    for command in ("help", "cpu", "ram", "disk", "temp", "monitor", "clear", "exit"):
        assert command in plain.split()
    if missing_gpu:
        gpu_row = next(line for line in lines if line.startswith("GPU "))
        cells = gpu_row.split("[", 1)[1].split("]", 1)[0]
        assert len(cells) >= 10
        assert set(cells) <= {"░", "-"}
        assert gpu_row.endswith("N/A")
        assert "GPU N/A" in plain
    edith.get_stats.assert_called_once_with()
    edith.clear.assert_called_once_with()
    terminal_size.assert_called_once_with((80, 24))


def test_dashboard_wraps_long_capacity(monkeypatch, capsys, dashboard_stats):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr(
        display.shutil, "get_terminal_size", lambda fallback: os.terminal_size((40, 24))
    )
    dashboard_stats.update(disk_used=123456.78, disk_total=234567.89)
    edith.dashboard()
    output = capsys.readouterr().out
    assert all(len(line) <= 40 for line in output.splitlines())
    assert "53% 123456.78 / 234567.89 GB" in " ".join(output.split())


def test_dashboard_wraps_long_temperatures(monkeypatch, capsys, dashboard_stats):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr(
        display.shutil, "get_terminal_size", lambda fallback: os.terminal_size((40, 24))
    )
    dashboard_stats.update(cpu_temp=100.123456789, gpu_temp=100.123456789)
    edith.dashboard()
    output = capsys.readouterr().out
    assert all(len(line) <= 40 for line in output.splitlines())
    assert "TEMP  CPU 100.123456789°C\n      GPU 100.123456789°C" in output


@pytest.mark.parametrize("status,color", [("ACTIVE", display.ACCENT), ("MONITORING", display.WARN)])
def test_dashboard_level_colors(monkeypatch, capsys, dashboard_stats, status, color):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(
        display.shutil, "get_terminal_size", lambda fallback: os.terminal_size((64, 24))
    )
    dashboard_stats.update(cpu=70, gpu=90, cpu_temp=80, gpu_temp=90)
    edith.dashboard(status)
    output = capsys.readouterr().out
    lines = output.splitlines()
    assert f"STATUS: {color}{status}{display.RESET}" in output
    assert display.WARN in next(line for line in lines if line.startswith("CPU "))
    assert display.CRIT in next(line for line in lines if line.startswith("GPU "))
    assert "\033" not in next(line for line in lines if line.startswith("RAM "))
    assert display.WARN in next(line for line in lines if line.startswith("DISK "))
    assert f"CPU {display.WARN}80°C{display.RESET}" in output
    assert f"GPU {display.CRIT}90°C{display.RESET}" in output


@pytest.mark.parametrize("command", ["cpu", "ram", "disk", "temp"])
@pytest.mark.parametrize("colored", [False, True])
def test_single_command_level_colors(monkeypatch, capsys, command, colored):
    monkeypatch.setattr(edith, "dashboard", Mock())
    monkeypatch.setattr(edith, "cpu_usage", lambda: 90)
    monkeypatch.setattr(edith, "ram_gb", lambda: (9, 10))
    monkeypatch.setattr(edith, "disk_gb", lambda: (7, 10))
    monkeypatch.setattr(edith, "cpu_temperature", lambda: 80)
    monkeypatch.setattr(edith, "gpu_stats", lambda: (None, 90))
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    if colored:
        monkeypatch.delenv("NO_COLOR", raising=False)
    else:
        monkeypatch.setenv("NO_COLOR", "1")
    commands = iter([command, "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(commands))
    edith.run()
    output = capsys.readouterr().out
    if colored:
        expected = {
            "cpu": f"CPU Usage: {display.CRIT}90%{display.RESET}",
            "ram": f"RAM: {display.CRIT}9 / 10 GB{display.RESET}",
            "disk": f"Disk: {display.WARN}7 / 10 GB{display.RESET}",
            "temp": f"CPU Temp: {display.WARN}80°C{display.RESET}",
        }
        assert expected[command] in output
        if command == "temp":
            assert f"GPU Temp: {display.CRIT}90°C{display.RESET}" in output
    else:
        assert "\033" not in output
    assert "Shutting down EDITH..." in output


@pytest.mark.parametrize("missing", [False, True])
def test_single_commands_normal_and_unavailable(monkeypatch, capsys, missing):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(edith, "dashboard", Mock())
    monkeypatch.setattr(edith, "cpu_usage", lambda: None if missing else 42)
    monkeypatch.setattr(edith, "ram_gb", lambda: (1, 10))
    monkeypatch.setattr(edith, "disk_gb", lambda: (2, 10))
    monkeypatch.setattr(edith, "cpu_temperature", lambda: None if missing else 72)
    monkeypatch.setattr(edith, "gpu_stats", lambda: (None, None if missing else 55))
    commands = iter(["cpu", "ram", "disk", "temp", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(commands))
    edith.run()
    output = capsys.readouterr().out
    assert "\033" not in output
    assert ("CPU Usage: N/A" if missing else "CPU Usage: 42%") in output
    assert "RAM: 1 / 10 GB" in output
    assert "Disk: 2 / 10 GB" in output
    expected_temp = (
        "CPU Temp: N/A | GPU Temp: N/A" if missing else "CPU Temp: 72°C | GPU Temp: 55°C"
    )
    assert expected_temp in output
