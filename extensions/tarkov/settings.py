"""Settings for the existing, single-pane tarkov tmux session."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class TarkovSettings:
    # Empty means the bot already runs as the owner of the tmux session.
    user: str = ""
    stop_timeout: float = 120
    command_timeout: float = 10
    poll_interval: float = 1

    @classmethod
    def from_environment(cls) -> "TarkovSettings":
        timeout = float(os.getenv("TARKOV_STOP_TIMEOUT", "120"))
        if not 1 <= timeout <= 600:
            raise ValueError("TARKOV_STOP_TIMEOUT must be between 1 and 600 seconds")
        return cls(user=os.getenv("TARKOV_USER", "").strip(), stop_timeout=timeout)
