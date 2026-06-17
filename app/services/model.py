"""Service manifest schema and runtime model."""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


class ServiceState(str, enum.Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    CRASHED = "crashed"


class RestartPolicy(str, enum.Enum):
    NEVER = "never"
    ON_FAILURE = "on-failure"
    ALWAYS = "always"


class ManifestError(Exception):
    """Raised when a service.yaml is missing or invalid."""


@dataclass
class ServiceManifest:
    name: str
    description: str = ""
    entrypoint: str = "bot.py"
    requirements: Optional[str] = None
    env_file: Optional[str] = None
    autostart: bool = False
    restart: RestartPolicy = RestartPolicy.ON_FAILURE


@dataclass
class Service:
    """Runtime view of a discovered service. Safe to serialize."""

    manifest: ServiceManifest
    directory: Path
    state: ServiceState = ServiceState.STOPPED
    pid: Optional[int] = None
    started_at: Optional[float] = None
    last_exit_code: Optional[int] = None
    error: Optional[str] = None

    @property
    def name(self) -> str:
        return self.manifest.name


def load_manifest(service_dir: Path) -> ServiceManifest:
    """Parse and validate ``<service_dir>/service.yaml``."""
    path = service_dir / "service.yaml"
    if not path.exists():
        raise ManifestError(f"no service.yaml in {service_dir.name}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ManifestError(f"invalid YAML in {path.name}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ManifestError(f"{path.name} must be a mapping")

    name = str(raw.get("name") or service_dir.name).strip()
    if not name:
        raise ManifestError("manifest 'name' is empty")

    entrypoint = str(raw.get("entrypoint", "bot.py")).strip()
    if not entrypoint:
        raise ManifestError(f"[{name}] 'entrypoint' is empty")

    restart_raw = str(raw.get("restart", RestartPolicy.ON_FAILURE.value)).strip()
    try:
        restart = RestartPolicy(restart_raw)
    except ValueError as exc:
        valid = ", ".join(p.value for p in RestartPolicy)
        raise ManifestError(
            f"[{name}] invalid 'restart' {restart_raw!r}; expected one of: {valid}"
        ) from exc

    return ServiceManifest(
        name=name,
        description=str(raw.get("description", "")),
        entrypoint=entrypoint,
        requirements=(str(raw["requirements"]) if raw.get("requirements") else None),
        env_file=(str(raw["env_file"]) if raw.get("env_file") else None),
        autostart=bool(raw.get("autostart", False)),
        restart=restart,
    )
