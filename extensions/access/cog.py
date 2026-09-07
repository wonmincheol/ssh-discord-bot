"""Discord commands for role-backed bot permissions."""

import logging
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from .service import ADMIN, CAPABILITIES, PermissionManager
from .settings import AccessSettings
from .store import PermissionStore


logger = logging.getLogger(__name__)
PermissionName = Literal["admin", "desktop_power"]


class PermissionCog(
    commands.GroupCog,
    group_name="permission",
    group_description="봇 명령어 사용 권한을 관리합니다.",
):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        settings = AccessSettings.from_environment()
        self.manager = PermissionManager(
            settings,
            PermissionStore(settings.database_path),
        )
        bot.permission_manager = self.manager

    async def cog_unload(self) -> None:
        if getattr(self.bot, "permission_manager", None) is self.manager:
            del self.bot.permission_manager
        self.manager.store.close()

    async def _require_admin(self, interaction: discord.Interaction) -> bool:
        guild_id = interaction.guild_id
        if not self.manager.is_configured_guild(guild_id):
            await interaction.response.send_message(
                "❌ 이 서버에서는 봇 권한을 관리할 수 없습니다.",
                ephemeral=True,
            )
            return False
        if not self.manager.is_admin(interaction.user, guild_id):
            await interaction.response.send_message(
                "❌ 봇 관리자 권한이 필요합니다.",
                ephemeral=True,
            )
            return False
        return True

    @staticmethod
    def _bot_can_manage_roles(guild: discord.Guild) -> bool:
        bot_member = guild.me
        return bool(
            bot_member is not None
            and bot_member.guild_permissions.manage_roles
        )

    @app_commands.command(name="setup", description="봇 권한 역할을 생성하거나 복구합니다.")
    @app_commands.guild_only()
    async def setup_permissions(self, interaction: discord.Interaction) -> None:
        if not await self._require_admin(interaction):
            return
        if not self._bot_can_manage_roles(interaction.guild):
            await interaction.response.send_message(
                "❌ 봇 계정에 `역할 관리(Manage Roles)` 권한이 없습니다.\n"
                "서버 설정 → 역할 → 봇 역할 → 권한에서 `역할 관리`를 켠 뒤 "
                "다시 실행하세요.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            results = await self.manager.setup_roles(interaction.guild)
            await interaction.followup.send(
                "✅ 권한 역할 설정을 완료했습니다.\n" + "\n".join(results),
                ephemeral=True,
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Discord가 역할 생성을 거부했습니다. 봇 역할의 `역할 관리` "
                "권한을 다시 확인하세요.",
                ephemeral=True,
            )
        except Exception:
            logger.exception("Permission role setup failed")
            await interaction.followup.send(
                "❌ 권한 역할 설정에 실패했습니다. 관리자 로그를 확인하세요.",
                ephemeral=True,
            )

    @app_commands.command(name="grant", description="사용자에게 봇 권한을 부여합니다.")
    @app_commands.guild_only()
    async def grant(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        permission: PermissionName,
    ) -> None:
        if not await self._require_admin(interaction):
            return
        role = self.manager.role_for(interaction.guild, permission)
        if role is None:
            await interaction.response.send_message(
                "❌ 권한 역할이 준비되지 않았습니다. 먼저 `/permission setup`을 실행하세요.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            await user.add_roles(
                role,
                reason=f"Granted by Discord user {interaction.user.id}",
            )
            logger.info(
                "Permission granted: guild=%s actor=%s target=%s capability=%s",
                interaction.guild_id,
                interaction.user.id,
                user.id,
                permission,
            )
            warning = (
                "\n⚠️ 이 사용자는 이제 모든 봇 권한을 관리할 수 있습니다."
                if permission == ADMIN
                else ""
            )
            await interaction.followup.send(
                f"✅ {user.mention} 사용자에게 `{permission}` 권한을 부여했습니다.{warning}",
                ephemeral=True,
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ 역할을 부여할 수 없습니다. 봇의 역할 관리 권한과 역할 순서를 확인하세요.",
                ephemeral=True,
            )
        except Exception:
            logger.exception("Permission grant failed")
            await interaction.followup.send(
                "❌ 권한 부여에 실패했습니다. 관리자 로그를 확인하세요.",
                ephemeral=True,
            )

    @app_commands.command(name="revoke", description="사용자의 봇 권한을 회수합니다.")
    @app_commands.guild_only()
    async def revoke(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        permission: PermissionName,
    ) -> None:
        if not await self._require_admin(interaction):
            return
        if permission == ADMIN and self.manager.is_owner(int(user.id)):
            await interaction.response.send_message(
                "❌ `.env`에 등록된 소유자의 관리자 권한은 회수할 수 없습니다.",
                ephemeral=True,
            )
            return
        role = self.manager.role_for(interaction.guild, permission)
        if role is None:
            await interaction.response.send_message(
                "❌ 권한 역할이 준비되지 않았습니다. 먼저 `/permission setup`을 실행하세요.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            await user.remove_roles(
                role,
                reason=f"Revoked by Discord user {interaction.user.id}",
            )
            logger.info(
                "Permission revoked: guild=%s actor=%s target=%s capability=%s",
                interaction.guild_id,
                interaction.user.id,
                user.id,
                permission,
            )
            await interaction.followup.send(
                f"✅ {user.mention} 사용자의 `{permission}` 권한을 회수했습니다.",
                ephemeral=True,
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ 역할을 회수할 수 없습니다. 봇의 역할 관리 권한과 역할 순서를 확인하세요.",
                ephemeral=True,
            )
        except Exception:
            logger.exception("Permission revoke failed")
            await interaction.followup.send(
                "❌ 권한 회수에 실패했습니다. 관리자 로그를 확인하세요.",
                ephemeral=True,
            )

    @app_commands.command(name="show", description="사용자의 봇 권한을 확인합니다.")
    @app_commands.guild_only()
    async def show(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
    ) -> None:
        if not await self._require_admin(interaction):
            return
        permissions = [
            capability
            for capability in CAPABILITIES
            if self.manager.has_capability(user, interaction.guild_id, capability)
        ]
        owner = " (환경설정 소유자)" if self.manager.is_owner(int(user.id)) else ""
        details = ", ".join(f"`{name}`" for name in permissions) or "없음"
        await interaction.response.send_message(
            f"🔐 {user.mention}{owner}\n권한: {details}",
            ephemeral=True,
        )

    @app_commands.command(name="list", description="사용 가능한 봇 권한을 확인합니다.")
    @app_commands.guild_only()
    async def list_permissions(self, interaction: discord.Interaction) -> None:
        if not await self._require_admin(interaction):
            return
        lines = []
        for capability, role in self.manager.configured_capabilities(interaction.guild):
            state = role.mention if role is not None else "미설정"
            lines.append(f"• `{capability}` — {state}")
        await interaction.response.send_message(
            "🔐 사용 가능한 봇 권한\n" + "\n".join(lines),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PermissionCog(bot))
