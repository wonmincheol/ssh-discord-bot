"""Settings required by the bot core.

Feature-specific settings live beside each extension. The core therefore does
not need to know anything about Palworld and keeps working when that extension
is disabled or removed.
"""

import os


DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "DISCORD_TOKEN")


def _enabled_extensions() -> tuple[str, ...]:
    configured = os.getenv(
        "BOT_EXTENSIONS",
        "extensions.system,extensions.palworld",
    )
    return tuple(name.strip() for name in configured.split(",") if name.strip())


EXTENSIONS = _enabled_extensions()
