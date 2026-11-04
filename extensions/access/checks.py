"""Reusable checks for operational commands, including future extensions."""

from .service import MANAGER


async def require_manager(interaction) -> bool:
    manager = getattr(interaction.client, "permission_manager", None)
    if manager is not None and manager.has_capability(
        interaction.user, interaction.guild_id, MANAGER,
    ):
        return True
    await interaction.response.send_message(
        "❌ 이 명령은 `manager` 또는 `admin` 권한이 필요합니다.",
        ephemeral=True,
    )
    return False
