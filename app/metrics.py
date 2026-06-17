"""Host and per-process performance metrics (psutil based)."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import psutil

_THERMAL = Path("/sys/class/thermal/thermal_zone0/temp")


def cpu_temp() -> Optional[float]:
    """CPU temperature in °C, or None if unavailable (e.g. on Windows dev)."""
    if _THERMAL.exists():
        try:
            return round(int(_THERMAL.read_text().strip()) / 1000.0, 1)
        except (ValueError, OSError):
            pass
    try:
        temps = psutil.sensors_temperatures()  # type: ignore[attr-defined]
        for entries in temps.values():
            if entries:
                return round(entries[0].current, 1)
    except (AttributeError, OSError):
        pass
    return None


def host_metrics() -> dict:
    """A snapshot of host-level metrics for the sidebar."""
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage(str(Path.home().anchor or "/"))
    try:
        load = list(psutil.getloadavg())
    except (AttributeError, OSError):
        load = [0.0, 0.0, 0.0]
    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "cpu_count": psutil.cpu_count() or 1,
        "mem_used": vm.used,
        "mem_total": vm.total,
        "mem_percent": vm.percent,
        "disk_used": disk.used,
        "disk_total": disk.total,
        "disk_percent": disk.percent,
        "load": load,
        "temp_c": cpu_temp(),
        "uptime_s": int(time.time() - psutil.boot_time()),
    }


def process_metrics(proc: psutil.Process) -> dict:
    """CPU%, RSS and uptime for a single process.

    Note: ``cpu_percent`` is relative to the previous call on the same object,
    so the manager keeps one ``psutil.Process`` per service and polls it
    periodically; the first reading after start is ~0.
    """
    with proc.oneshot():
        cpu = proc.cpu_percent(interval=None)
        rss = proc.memory_info().rss
        created = proc.create_time()
    return {
        "cpu_percent": round(cpu, 1),
        "mem_rss": rss,
        "uptime_s": int(time.time() - created),
    }
