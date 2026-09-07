"""Configuration for the bot permission extension."""

from dataclasses import dataclass
import os


def _required_snowflake(name: str) -> int:
    value = os.getenv(name, "").strip()
    try:
        snowflake = int(value)
    except ValueError as error:
        raise RuntimeError(f"{name} must be a Discord ID") from error
    if snowflake <= 0:
        raise RuntimeError(f"{name} must be a positive Discord ID")
    return snowflake


def _owner_ids() -> frozenset[int]:
    values = [value.strip() for value in os.getenv("BOT_OWNER_IDS", "").split(",")]
    try:
        owner_ids = frozenset(int(value) for value in values if value)
    except ValueError as error:
        raise RuntimeError("BOT_OWNER_IDS must contain comma-separated Discord IDs") from error
    if not owner_ids or any(owner_id <= 0 for owner_id in owner_ids):
        raise RuntimeError("BOT_OWNER_IDS must contain at least one positive Discord ID")
    return owner_ids


@dataclass(frozen=True)
class AccessSettings:
    guild_id: int
    owner_ids: frozenset[int]
    database_path: str

    @classmethod
    def from_environment(cls) -> "AccessSettings":
        return cls(
            guild_id=_required_snowflake("BOT_GUILD_ID"),
            owner_ids=_owner_ids(),
            database_path=os.getenv(
                "BOT_PERMISSION_DB_PATH",
                "data/permissions.sqlite3",
            ).strip()
            or "data/permissions.sqlite3",
        )
