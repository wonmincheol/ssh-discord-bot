"""Configuration for the bot permission extension."""

from dataclasses import dataclass
import os


def _snowflake_ids(name: str, configured: str) -> frozenset[int]:
    values = [value.strip() for value in configured.split(",")]
    try:
        snowflakes = frozenset(int(value) for value in values if value)
    except ValueError as error:
        raise RuntimeError(f"{name} must contain comma-separated Discord IDs") from error
    if not snowflakes or any(snowflake <= 0 for snowflake in snowflakes):
        raise RuntimeError(f"{name} must contain at least one positive Discord ID")
    return snowflakes


def _guild_ids() -> frozenset[int]:
    configured = os.getenv("BOT_GUILD_IDS", "").strip()
    if not configured:
        # Backward compatibility for existing single-server deployments.
        configured = os.getenv("BOT_GUILD_ID", "").strip()
    return _snowflake_ids("BOT_GUILD_IDS", configured)


def _owner_ids() -> frozenset[int]:
    return _snowflake_ids("BOT_OWNER_IDS", os.getenv("BOT_OWNER_IDS", ""))


@dataclass(frozen=True)
class AccessSettings:
    guild_ids: frozenset[int]
    owner_ids: frozenset[int]
    database_path: str

    @classmethod
    def from_environment(cls) -> "AccessSettings":
        return cls(
            guild_ids=_guild_ids(),
            owner_ids=_owner_ids(),
            database_path=os.getenv(
                "BOT_PERMISSION_DB_PATH",
                "data/permissions.sqlite3",
            ).strip()
            or "data/permissions.sqlite3",
        )
