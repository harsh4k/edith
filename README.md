# EDITH

Minimal terminal dashboard for system monitoring.

## Features

* CPU, RAM, Disk usage
* Cache tracking
* CPU/GPU temperature (if available)
* Live monitor mode
* Clean command interface

## Commands

help, cpu, ram, disk, temp, monitor, stop, clear, exit

`monitor` refreshes the dashboard every 2s — press any key to stop.
Ctrl+C exits cleanly from anywhere.

## Install

pip install psutil gputil

## Run

python edith.py
