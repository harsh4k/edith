# EDITH

Minimal terminal dashboard for system monitoring — a single-file Python script, no config, no server.

## Features

* CPU, RAM, disk usage
* Memory cache tracking
* CPU temperature (via `psutil` sensors, when the platform exposes it)
* GPU load & temperature (via `nvidia-smi`, when an NVIDIA GPU and driver are present — falls back to `N/A` otherwise)
* Live monitor mode — auto-refreshing dashboard
* Clean, single-command terminal interface

## Commands

`help`, `cpu`, `ram`, `disk`, `temp`, `monitor`, `clear`, `exit`

`monitor` refreshes the dashboard every 2s — press any key to stop.
Ctrl+C exits cleanly from anywhere.

## Install

```
pip install psutil
```

## Run

```
python edith.py
```
