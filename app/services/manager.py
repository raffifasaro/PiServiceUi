"""ServiceManager: discover, provision, run and supervise services.

Each service runs as a child *subprocess* of this (host) process, using its
own virtualenv under ``data/venvs/<name>``. A periodic :meth:`poll` reaps
exits, refreshes metrics and applies the restart policy.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import psutil

from ..logs import ServiceLogger, log_path, tail_file
from ..metrics import process_metrics
from .model import (
    ManifestError,
    RestartPolicy,
    Service,
    ServiceState,
    load_manifest,
)

log = logging.getLogger("piserviceui.manager")

IS_WINDOWS = os.name == "nt"

# Restart-loop guard: at most this many automatic restarts within the window.
_RESTART_LIMIT = 5
_RESTART_WINDOW = 60.0


class ServiceManager:
    def __init__(
        self,
        services_dir: Path,
        venvs_dir: Path,
        logs_dir: Path,
        state_file: Path,
        pip_extra_index_url: str = "",
        stop_timeout: float = 10.0,
    ) -> None:
        self.services_dir = Path(services_dir)
        self.venvs_dir = Path(venvs_dir)
        self.logs_dir = Path(logs_dir)
        self.state_file = Path(state_file)
        self.pip_extra_index_url = pip_extra_index_url
        self.stop_timeout = stop_timeout

        self._services: dict[str, Service] = {}
        self._errors: dict[str, str] = {}  # dir name -> manifest error
        self._procs: dict[str, subprocess.Popen] = {}
        self._ps: dict[str, psutil.Process] = {}
        self._loggers: dict[str, ServiceLogger] = {}
        self._metrics: dict[str, dict] = {}
        self._restarts: dict[str, list[float]] = {}
        self._manual_stop: set[str] = set()
        self._lock = threading.RLock()

        for d in (self.services_dir, self.venvs_dir, self.logs_dir):
            d.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Discovery
    # ------------------------------------------------------------------ #
    def discover(self) -> None:
        found: dict[str, tuple] = {}
        errors: dict[str, str] = {}
        if self.services_dir.exists():
            for d in sorted(p for p in self.services_dir.iterdir() if p.is_dir()):
                if not (d / "service.yaml").exists():
                    continue
                try:
                    manifest = load_manifest(d)
                except ManifestError as exc:
                    errors[d.name] = str(exc)
                    continue
                found[manifest.name] = (manifest, d)

        with self._lock:
            self._errors = errors
            for name, (manifest, d) in found.items():
                if name in self._services:
                    svc = self._services[name]
                    svc.manifest = manifest
                    svc.directory = d
                else:
                    self._services[name] = Service(manifest=manifest, directory=d)
            # Drop services that disappeared from disk, unless still running.
            for name in list(self._services):
                if name not in found and name not in self._procs:
                    self._services.pop(name, None)

    # ------------------------------------------------------------------ #
    # Environment provisioning
    # ------------------------------------------------------------------ #
    def _venv_python(self, name: str) -> Path:
        venv = self.venvs_dir / name
        return venv / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")

    def ensure_env(self, svc: Service) -> None:
        venv = self.venvs_dir / svc.name
        py = self._venv_python(svc.name)
        if not py.exists():
            log.info("creating venv for %s", svc.name)
            subprocess.run(
                [sys.executable, "-m", "venv", str(venv)],
                check=True,
                capture_output=True,
            )

        req_name = svc.manifest.requirements
        if not req_name:
            return
        req_path = svc.directory / req_name
        if not req_path.exists():
            return
        digest = hashlib.sha256(req_path.read_bytes()).hexdigest()
        marker = venv / ".req_hash"
        if marker.exists() and marker.read_text().strip() == digest:
            return

        cmd = [str(py), "-m", "pip", "install", "--no-cache-dir", "-r", str(req_path)]
        if self.pip_extra_index_url:
            cmd += ["--extra-index-url", self.pip_extra_index_url]
        log.info("installing requirements for %s", svc.name)
        subprocess.run(cmd, check=True)
        marker.write_text(digest)

    # ------------------------------------------------------------------ #
    # Process control
    # ------------------------------------------------------------------ #
    def _build_cmd(self, svc: Service, py: Path) -> list[str]:
        ep = svc.manifest.entrypoint.strip()
        if ep.endswith(".py"):
            return [str(py), "-u", ep]
        # Otherwise treat as a module path: "python -u -m package.module"
        return [str(py), "-u", "-m", ep]

    def _load_env_file(self, svc: Service) -> dict:
        env: dict[str, str] = {}
        if not svc.manifest.env_file:
            return env
        path = svc.directory / svc.manifest.env_file
        if not path.exists():
            return env
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
        return env

    def start(self, name: str) -> Service:
        with self._lock:
            svc = self._services.get(name)
            if svc is None:
                raise KeyError(name)
            if svc.state in (ServiceState.RUNNING, ServiceState.STARTING):
                return svc
            svc.state = ServiceState.STARTING
            svc.error = None
            self._manual_stop.discard(name)

        try:
            self.ensure_env(svc)
        except subprocess.CalledProcessError as exc:
            with self._lock:
                svc.state = ServiceState.CRASHED
                svc.error = f"environment setup failed (exit {exc.returncode})"
            raise RuntimeError(svc.error) from exc

        logger = self._loggers.get(name) or ServiceLogger(self.logs_dir, name)
        self._loggers[name] = logger

        env = os.environ.copy()
        env.update(self._load_env_file(svc))
        cmd = self._build_cmd(svc, self._venv_python(name))

        popen_kwargs: dict = dict(
            cwd=str(svc.directory),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
        )
        if IS_WINDOWS:
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["start_new_session"] = True  # own process group

        logger.system(f"starting: {' '.join(cmd)}")
        proc = subprocess.Popen(cmd, **popen_kwargs)
        logger.attach(proc)

        with self._lock:
            self._procs[name] = proc
            self._ps[name] = psutil.Process(proc.pid)
            self._metrics[name] = {"cpu_percent": 0.0, "mem_rss": 0, "uptime_s": 0}
            svc.state = ServiceState.RUNNING
            svc.pid = proc.pid
            svc.started_at = time.time()
            svc.last_exit_code = None
        self._save_state()
        return svc

    def stop(self, name: str) -> Service:
        with self._lock:
            svc = self._services.get(name)
            if svc is None:
                raise KeyError(name)
            proc = self._procs.get(name)
            if proc is None:
                svc.state = ServiceState.STOPPED
                return svc
            svc.state = ServiceState.STOPPING
            self._manual_stop.add(name)
            logger = self._loggers.get(name)

        if logger:
            logger.system("stopping")
        self._terminate(proc)
        try:
            proc.wait(timeout=self.stop_timeout)
        except subprocess.TimeoutExpired:
            self._kill(proc)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass

        with self._lock:
            svc.state = ServiceState.STOPPED
            svc.last_exit_code = proc.returncode
            svc.pid = None
            self._procs.pop(name, None)
            self._ps.pop(name, None)
            self._metrics.pop(name, None)
        self._save_state()
        return svc

    def restart(self, name: str) -> Service:
        self.stop(name)
        return self.start(name)

    def _terminate(self, proc: subprocess.Popen) -> None:
        if proc.poll() is not None:
            return
        try:
            if IS_WINDOWS:
                proc.terminate()
            else:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, OSError):
            try:
                proc.terminate()
            except OSError:
                pass

    def _kill(self, proc: subprocess.Popen) -> None:
        try:
            if IS_WINDOWS:
                proc.kill()
            else:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, OSError):
            try:
                proc.kill()
            except OSError:
                pass

    # ------------------------------------------------------------------ #
    # Supervision (called periodically from the event loop)
    # ------------------------------------------------------------------ #
    def poll(self) -> None:
        with self._lock:
            names = list(self._procs.keys())

        for name in names:
            proc = self._procs.get(name)
            if proc is None:
                continue
            ret = proc.poll()
            if ret is None:
                ps = self._ps.get(name)
                if ps is not None:
                    try:
                        self._metrics[name] = process_metrics(ps)
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
            else:
                self._handle_exit(name, proc, ret)

    def _handle_exit(self, name: str, proc: subprocess.Popen, ret: int) -> None:
        with self._lock:
            svc = self._services.get(name)
            manual = name in self._manual_stop
            self._procs.pop(name, None)
            self._ps.pop(name, None)
            self._metrics.pop(name, None)
            if svc is None:
                return
            svc.pid = None
            svc.last_exit_code = ret
            failed = ret != 0
            svc.state = ServiceState.CRASHED if failed else ServiceState.STOPPED

        logger = self._loggers.get(name)
        if logger:
            logger.system(f"exited with code {ret}")

        if manual:
            with self._lock:
                self._manual_stop.discard(name)
            self._save_state()
            return

        policy = svc.manifest.restart
        should_restart = policy is RestartPolicy.ALWAYS or (
            policy is RestartPolicy.ON_FAILURE and failed
        )
        if should_restart and self._allow_restart(name):
            if logger:
                logger.system("auto-restarting")
            try:
                self.start(name)
                return
            except Exception as exc:  # noqa: BLE001 - record and leave crashed
                log.warning("auto-restart of %s failed: %s", name, exc)
                with self._lock:
                    svc.state = ServiceState.CRASHED
                    svc.error = f"restart failed: {exc}"
        self._save_state()

    def _allow_restart(self, name: str) -> bool:
        now = time.time()
        history = [t for t in self._restarts.get(name, []) if now - t < _RESTART_WINDOW]
        if len(history) >= _RESTART_LIMIT:
            self._restarts[name] = history
            log.warning("%s hit the restart limit; leaving it crashed", name)
            return False
        history.append(now)
        self._restarts[name] = history
        return True

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def startup(self) -> None:
        self.discover()
        desired: set[str] = set()
        try:
            if self.state_file.exists():
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                desired |= set(data.get("running", []))
        except (OSError, json.JSONDecodeError):
            pass
        for name, svc in self._services.items():
            if svc.manifest.autostart:
                desired.add(name)
        for name in desired:
            if name in self._services:
                try:
                    self.start(name)
                except Exception as exc:  # noqa: BLE001
                    log.warning("startup of %s failed: %s", name, exc)

    def shutdown(self) -> None:
        for name in list(self._procs.keys()):
            try:
                self.stop(name)
            except Exception:  # noqa: BLE001
                pass

    def _save_state(self) -> None:
        try:
            with self._lock:
                running = [
                    n
                    for n, s in self._services.items()
                    if s.state in (ServiceState.RUNNING, ServiceState.STARTING)
                ]
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(json.dumps({"running": running}), encoding="utf-8")
        except OSError:
            pass

    # ------------------------------------------------------------------ #
    # Read API
    # ------------------------------------------------------------------ #
    def list(self) -> list[dict]:
        out: list[dict] = []
        with self._lock:
            now = time.time()
            for name, svc in self._services.items():
                m = self._metrics.get(name, {})
                running = svc.state is ServiceState.RUNNING
                out.append(
                    {
                        "name": name,
                        "description": svc.manifest.description,
                        "state": svc.state.value,
                        "pid": svc.pid,
                        "restart": svc.manifest.restart.value,
                        "autostart": svc.manifest.autostart,
                        "uptime_s": int(now - svc.started_at)
                        if running and svc.started_at
                        else 0,
                        "cpu_percent": m.get("cpu_percent"),
                        "mem_rss": m.get("mem_rss"),
                        "last_exit_code": svc.last_exit_code,
                        "error": svc.error,
                    }
                )
            for dirname, msg in self._errors.items():
                if dirname in self._services:
                    continue
                out.append(
                    {
                        "name": dirname,
                        "description": "",
                        "state": "error",
                        "pid": None,
                        "restart": None,
                        "autostart": False,
                        "uptime_s": 0,
                        "cpu_percent": None,
                        "mem_rss": None,
                        "last_exit_code": None,
                        "error": msg,
                    }
                )
        out.sort(key=lambda s: s["name"])
        return out

    def get_logs(self, name: str, lines: int = 200) -> list[str]:
        with self._lock:
            known = name in self._services or name in self._errors
        if not known:
            raise KeyError(name)
        return tail_file(log_path(self.logs_dir, name), lines)
