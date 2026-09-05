"""Configuration owned exclusively by the Palworld extension."""

from dataclasses import dataclass
from datetime import timedelta
import os


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class PalworldSettings:
    api_url: str
    api_user: str
    api_password: str
    start_script: str
    stop_script: str
    status_script: str
    auto_shutdown_enabled: bool
    auto_shutdown_after: timedelta
    check_interval: float
    command_timeout: float

    @classmethod
    def from_environment(cls) -> "PalworldSettings":
        script_path = os.getenv(
            "PALWORLD_SCRIPT_PATH",
            "/data/ssh-discord-bot/extensions/palworld/server-control",
        ).rstrip("/")

        return cls(
            api_url=os.getenv("PALWORLD_API_URL", "http://127.0.0.1:8212").rstrip("/"),
            api_user=os.getenv("PALWORLD_API_USER", "admin"),
            api_password=os.getenv("PALWORLD_API_PASSWORD", ""),
            start_script=f"{script_path}/start.sh",
            stop_script=f"{script_path}/stop.sh",
            status_script=f"{script_path}/status.sh",
            auto_shutdown_enabled=_as_bool(
                os.getenv("PALWORLD_AUTO_SHUTDOWN_ENABLED", "true")
            ),
            auto_shutdown_after=timedelta(
                seconds=float(os.getenv("PALWORLD_AUTO_SHUTDOWN_SECONDS", "3600"))
            ),
            check_interval=float(os.getenv("PALWORLD_CHECK_INTERVAL", "60")),
            command_timeout=float(os.getenv("PALWORLD_COMMAND_TIMEOUT", "30")),
        )
