from collections import namedtuple
from unittest.mock import Mock

import pytest

import edith

Sensor = namedtuple("Sensor", "current")
Memory = namedtuple("Memory", "used total")
CachedMemory = namedtuple("CachedMemory", "used total cached")


@pytest.fixture(autouse=True)
def isolate_hardware(monkeypatch):
    monkeypatch.setattr(edith, "_cpu_last", {"time": None, "value": 0.0})
    for name in ("cpu_percent", "virtual_memory", "disk_usage", "sensors_temperatures"):
        monkeypatch.setattr(
            edith.psutil,
            name,
            Mock(side_effect=AssertionError(f"Unexpected hardware call: {name}")),
            raising=False,
        )
    monkeypatch.setattr(edith.shutil, "which", Mock(return_value=None))
    monkeypatch.setattr(
        edith.subprocess, "run", Mock(side_effect=AssertionError("Unexpected subprocess"))
    )


@pytest.mark.parametrize("value,unit,expected", [(None, "%", "N/A"), (42, "%", "42%")])
def test_fmt(value, unit, expected):
    assert edith.fmt(value, unit) == expected


@pytest.mark.parametrize(
    "field,expected", [(" 42 ", 42), ("[N/A]", None), ("[Not Supported]", None)]
)
def test_to_int(field, expected):
    assert edith._to_int(field) == expected


@pytest.mark.parametrize(
    "temperatures,expected",
    [
        ({"acpitz": [Sensor(30)], "coretemp": [Sensor(60), Sensor(70)]}, 60),
        ({"other": [Sensor(45)], "another": [Sensor(50)]}, 45),
        ({}, None),
        ({"coretemp": []}, None),
    ],
    ids=["preferred-sensor", "first-sensor-fallback", "no-sensors", "empty-sensor"],
)
def test_cpu_temperature(monkeypatch, temperatures, expected):
    monkeypatch.setattr(edith.psutil, "sensors_temperatures", lambda: temperatures, raising=False)
    assert edith.cpu_temperature() == expected


@pytest.mark.parametrize("error", [AttributeError, OSError])
def test_cpu_temperature_unavailable(monkeypatch, error):
    monkeypatch.setattr(
        edith.psutil, "sensors_temperatures", Mock(side_effect=error), raising=False
    )
    assert edith.cpu_temperature() is None


def test_find_nvidia_smi_on_path(monkeypatch):
    which = Mock(return_value="/tools/nvidia-smi")
    monkeypatch.setattr(edith.shutil, "which", which)
    assert edith.find_nvidia_smi() == "/tools/nvidia-smi"
    which.assert_called_once_with("nvidia-smi")


@pytest.mark.skipif(edith.os.name == "nt", reason="POSIX PATH lookup")
def test_find_nvidia_smi_missing_on_posix():
    assert edith.find_nvidia_smi() is None


@pytest.mark.parametrize("exists", [True, False])
def test_find_nvidia_smi_windows_legacy(monkeypatch, exists):
    monkeypatch.setenv("ProgramFiles", "legacy-programs")
    legacy = edith.os.path.join("legacy-programs", "NVIDIA Corporation", "NVSMI", "nvidia-smi.exe")
    isfile = Mock(return_value=exists)
    monkeypatch.setattr(edith.os.path, "isfile", isfile)
    with monkeypatch.context() as platform_patch:
        platform_patch.setattr(edith.os, "name", "nt")
        result = edith.find_nvidia_smi()
    assert result == (legacy if exists else None)
    isfile.assert_called_once_with(legacy)


def test_gpu_stats_without_smi(monkeypatch):
    monkeypatch.setattr(edith, "find_nvidia_smi", lambda: None)
    assert edith.gpu_stats() == (None, None)
    edith.subprocess.run.assert_not_called()


@pytest.mark.parametrize(
    "stdout,expected",
    [("37, 55\n", (37, 55)), ("[N/A], 50", (None, 50)), ("", (None, None))],
)
def test_gpu_stats_csv(monkeypatch, stdout, expected):
    monkeypatch.setattr(edith, "find_nvidia_smi", lambda: "fake-nvidia-smi")
    runner = Mock(return_value=edith.subprocess.CompletedProcess([], 0, stdout=stdout))
    monkeypatch.setattr(edith.subprocess, "run", runner)
    assert edith.gpu_stats() == expected
    runner.assert_called_once_with(
        [
            "fake-nvidia-smi",
            "--query-gpu=utilization.gpu,temperature.gpu",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        timeout=2,
        check=True,
    )


@pytest.mark.parametrize(
    "error",
    [
        edith.subprocess.TimeoutExpired("fake-nvidia-smi", 2),
        edith.subprocess.CalledProcessError(1, "fake-nvidia-smi"),
        FileNotFoundError("fake-nvidia-smi"),
    ],
)
def test_gpu_stats_subprocess_failure(monkeypatch, error):
    monkeypatch.setattr(edith, "find_nvidia_smi", lambda: "fake-nvidia-smi")
    runner = Mock(side_effect=error)
    monkeypatch.setattr(edith.subprocess, "run", runner)
    assert edith.gpu_stats() == (None, None)
    runner.assert_called_once()


def test_cpu_usage_first_read(monkeypatch):
    percent = Mock(return_value=12.5)
    monkeypatch.setattr(edith.psutil, "cpu_percent", percent)
    monkeypatch.setattr(edith.time, "monotonic", lambda: 100.0)
    assert edith._cpu_last == {"time": None, "value": 0.0}
    assert edith.cpu_usage() == 12.5
    percent.assert_called_once_with(interval=0.3)
    assert edith._cpu_last == {"time": 100.0, "value": 12.5}


@pytest.mark.parametrize(
    "age,expected,call_kwargs",
    [
        (edith.CPU_MIN_AGE / 2, 12.5, None),
        (edith.CPU_MIN_AGE, 50.0, {}),
        ((edith.CPU_MIN_AGE + edith.CPU_MAX_AGE) / 2, 50.0, {}),
        (edith.CPU_MAX_AGE, 50.0, {}),
        (edith.CPU_MAX_AGE + 1, 50.0, {"interval": 0.3}),
    ],
    ids=["cached", "min-boundary", "recent", "max-boundary", "stale"],
)
def test_cpu_usage_cache_age(monkeypatch, age, expected, call_kwargs):
    clock = Mock(return_value=100.0)
    percent = Mock(return_value=12.5)
    monkeypatch.setattr(edith.time, "monotonic", clock)
    monkeypatch.setattr(edith.psutil, "cpu_percent", percent)
    edith.cpu_usage()
    percent.reset_mock()
    percent.return_value = 50.0
    clock.return_value = 100.0 + age
    assert edith.cpu_usage() == expected
    if call_kwargs is None:
        percent.assert_not_called()
        assert edith._cpu_last == {"time": 100.0, "value": 12.5}
    else:
        percent.assert_called_once_with(**call_kwargs)
        assert edith._cpu_last == {"time": 100.0 + age, "value": 50.0}


def test_ram_gb(monkeypatch):
    memory = Mock(return_value=Memory(1.234 * edith.GB, 7.896 * edith.GB))
    monkeypatch.setattr(edith.psutil, "virtual_memory", memory)
    assert edith.ram_gb() == (1.23, 7.9)
    memory.assert_called_once_with()


def test_disk_gb(monkeypatch):
    disk = Mock(return_value=Memory(123.456 * edith.GB, 789.123 * edith.GB))
    monkeypatch.setattr(edith.psutil, "disk_usage", disk)
    assert edith.disk_gb() == (123.46, 789.12)
    disk.assert_called_once_with("/")


@pytest.mark.parametrize(
    "memory,expected_cache",
    [(Memory(1, 2), None), (CachedMemory(1, 2, 1.236 * edith.GB), 1.24)],
    ids=["without-cache", "with-cache"],
)
def test_get_stats(monkeypatch, memory, expected_cache):
    monkeypatch.setattr(edith.psutil, "virtual_memory", lambda: memory)
    monkeypatch.setattr(edith, "ram_gb", lambda: (1.23, 7.9))
    monkeypatch.setattr(edith, "disk_gb", lambda: (123.46, 789.12))
    monkeypatch.setattr(edith, "cpu_usage", lambda: 12.5)
    monkeypatch.setattr(edith, "cpu_temperature", lambda: 60)
    monkeypatch.setattr(edith, "gpu_stats", lambda: (37, 55))
    assert edith.get_stats() == {
        "cpu": 12.5,
        "ram_used": 1.23,
        "ram_total": 7.9,
        "disk_used": 123.46,
        "disk_total": 789.12,
        "cache": expected_cache,
        "cpu_temp": 60,
        "gpu": 37,
        "gpu_temp": 55,
    }


def test_run_commands(monkeypatch, capsys):
    dashboard = Mock()
    commands = iter(["cpu", "ram", "bogus", "exit"])
    monkeypatch.setattr(edith, "dashboard", dashboard)
    monkeypatch.setattr(edith, "cpu_usage", lambda: 12.5)
    monkeypatch.setattr(edith, "ram_gb", lambda: (1.23, 7.9))
    monkeypatch.setattr("builtins.input", lambda prompt: next(commands))
    edith.run()
    output = capsys.readouterr().out
    assert "CPU Usage: 12.5%" in output
    assert "RAM: 1.23 / 7.9 GB" in output
    assert "Unknown command: bogus  (type 'help')" in output
    assert "Shutting down EDITH..." in output
    dashboard.assert_called_once_with()


@pytest.mark.parametrize("error", [EOFError, KeyboardInterrupt])
def test_run_input_interrupted(monkeypatch, capsys, error):
    dashboard = Mock()
    monkeypatch.setattr(edith, "dashboard", dashboard)
    monkeypatch.setattr("builtins.input", Mock(side_effect=error))
    edith.run()
    assert "Shutting down EDITH..." in capsys.readouterr().out
    dashboard.assert_called_once_with()
