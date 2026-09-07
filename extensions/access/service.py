"""Permission decisions independent from Discord command presentation."""

from collections.abc import Iterable
from typing import Any

from .settings import AccessSettings
from .store import PermissionStore


ADMIN = "admin"
DESKTOP_POWER = "desktop_power"
CAPABILITIES = (ADMIN, DESKTOP_POWER)

ROLE_NAMES = {
    ADMIN: "Bot • Admin",
    DESKTOP_POWER: "Bot • Desktop Power",
}


class PermissionManager:
    def __init__(self, settings: AccessSettings, store: PermissionStore) -> None:
        self.settings = settings
        self.store = store

    def is_configured_guild(self, guild_id: int | None) -> bool:
        return guild_id in self.settings.guild_ids

    def is_owner(self, user_id: int) -> bool:
        return user_id in self.settings.owner_ids

    @staticmethod
    def _role_ids(member: Any) -> set[int]:
        return {int(role.id) for role in getattr(member, "roles", ())}

    def has_capability(
        self,
        member: Any,
        guild_id: int | None,
        capability: str,
    ) -> bool:
        if not self.is_configured_guild(guild_id):
            return False
        if self.is_owner(int(member.id)):
            return True

        role_ids = self._role_ids(member)
        admin_role_id = self.store.get_role_id(guild_id, ADMIN)
        if admin_role_id is not None and admin_role_id in role_ids:
            return True

        role_id = self.store.get_role_id(guild_id, capability)
        return role_id is not None and role_id in role_ids

    def is_admin(self, member: Any, guild_id: int | None) -> bool:
        return self.has_capability(member, guild_id, ADMIN)

    def role_for(self, guild: Any, capability: str) -> Any | None:
        role_id = self.store.get_role_id(int(guild.id), capability)
        if role_id is None:
            return None
        return next((role for role in guild.roles if int(role.id) == role_id), None)

    async def setup_roles(self, guild: Any) -> list[str]:
        results: list[str] = []
        for capability in CAPABILITIES:
            role = self.role_for(guild, capability)
            if role is None:
                role = await guild.create_role(
                    name=ROLE_NAMES[capability],
                    reason="Discord bot permission setup",
                )
                self.store.set_role_id(int(guild.id), capability, int(role.id))
                results.append(f"{ROLE_NAMES[capability]}: 생성됨")
            else:
                results.append(f"{ROLE_NAMES[capability]}: 준비됨")
        return results

    def configured_capabilities(self, guild: Any) -> Iterable[tuple[str, Any | None]]:
        for capability in CAPABILITIES:
            yield capability, self.role_for(guild, capability)
