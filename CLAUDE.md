# EDITH — Project Context

## What this is
EDITH is a minimal terminal dashboard for system monitoring: one Python file, no config,
no server, no network. Type a command to get CPU / RAM / disk / cache / temperature / GPU
stats, or run `monitor` for a live view that refreshes every 2 seconds.

## Stack
- Python 3.10+, single module: `edith.py`
- Runtime dependency: `psutil` only
- GPU: `nvidia-smi` called directly with `subprocess` (no shell, 2s timeout). No NVIDIA
  GPU or driver means `N/A`, never a crash
- Packaging: `pyproject.toml` (setuptools), console script `edith` → `edith:run`
- Dev tools: `pytest`, `ruff` (lint + format), installed via the `dev` extra
- Licence: MIT

## Commands
```bash
pip install -e ".[dev]"   # editable install with dev tools
python edith.py           # or: edith
ruff check .
ruff format --check .
pytest
```

## Conventions
- Keep it one file. Split only if `edith.py` passes ~300 lines.
- Measuring lives in small helpers (`cpu_usage`, `ram_gb`, `disk_gb`, `cpu_temperature`,
  `gpu_stats`); `get_stats()` composes them; commands only format.
- Unavailable hardware returns `None`; `fmt()` turns it into `N/A` without a unit.
- `psutil.cpu_percent()` averages since its previous call. Go through `cpu_usage()`,
  which guards against readings that are too close together or too far apart.
- No bare `except:`. Catch the specific psutil / `OSError` / `subprocess` errors.
- No `os.system` beyond the existing screen clear, and never `shell=True`.
- Terminal key handling (msvcrt on Windows, termios cbreak on POSIX) stays inside
  `single_keys()` and `sleep_or_key()`. Always restore terminal settings in `finally`.
- Tests mock psutil and `nvidia-smi`; they never depend on the CI machine's hardware.
- No new runtime dependency without asking.

## Roadmap
- [x] Fix GPU on Python 3.12+, CPU first-read, any-key on POSIX
- [x] `pyproject.toml`, `edith` entry point, MIT licence, ruff config
- [ ] Tests + GitHub Actions matrix (Ubuntu / Windows / macOS × Python 3.10 and 3.13)
- [ ] Design pass: usage bars, warning thresholds, width-aware layout, `NO_COLOR`
- [ ] README with screenshot
- Later, only if wanted: network I/O, top processes, battery
