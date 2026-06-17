"""Application configuration, loaded from environment / .env."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root (…/PiServiceUi), i.e. the parent of the `app` package.
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        # utf-8-sig tolerates a leading BOM, which some Windows editors / the
        # PowerShell `Out-File -Encoding utf8` add and which would otherwise
        # corrupt the first key in the .env file.
        env_file_encoding="utf-8-sig",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Auth / web ---
    ui_password_hash: str = ""
    session_secret: str = "change-me"
    cookie_secure: bool = False
    session_max_age: int = 7 * 24 * 3600  # seconds

    host: str = "0.0.0.0"
    port: int = 8080

    # --- Behaviour ---
    metrics_interval: float = 2.0
    stop_timeout: float = 10.0
    pip_extra_index_url: str = "https://www.piwheels.org/simple"

    # --- Paths (overridable for tests/dev) ---
    services_dir: Path = BASE_DIR / "services"
    data_dir: Path = BASE_DIR / "data"
    web_dist_dir: Path = BASE_DIR / "web" / "dist"

    @property
    def venvs_dir(self) -> Path:
        return self.data_dir / "venvs"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def state_file(self) -> Path:
        return self.data_dir / "state.json"


settings = Settings()
