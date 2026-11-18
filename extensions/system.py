"""Commands for controlling and inspecting the mini PC itself."""

import asyncio
import logging
import os
import re
import sqlite3

import discord
from discord import app_commands
from discord.ext import commands

from extensions.access.checks import require_manager
from extensions.access.service import DESKTOP_POWER, PermissionManager
from extensions.desktop.service import DesktopService


COMMAND_TIMEOUT = 15
WOL_BROADCAST_ADDRESS = os.getenv("WOL_BROADCAST_ADDRESS", "172.30.1.255")
WOL_MAC_ADDRESS = os.getenv("WOL_MAC_ADDRESS", "").strip()

logger = logging.getLogger(__name__)

DESKTOP_OFF_MESSAGES = {
    "REQUESTED": "🖥️ 데스크탑이 종료 요청을 수락했습니다. 실제 전원 종료 완료는 별도로 확인하세요.",
    "ALREADY_REQUESTED": "⏳ 현재 부팅에서 이미 종료를 요청했습니다. 중복 전송하지 않았습니다. 데스크탑 상태를 확인하세요.",
    "BUSY": "⏳ 데스크탑 제어 작업이 진행 중입니다. 잠시 후 다시 확인하세요.",
    "CONFIG_ERROR": "❌ 데스크탑 SSH 설정이 없거나 올바르지 않습니다. 봇 관리자에게 문의하세요.",
    "SSH_MISSING": "❌ 봇 실행 환경에 SSH 클라이언트가 없습니다. 봇 관리자에게 문의하세요.",
    "HOST_KEY_ERROR": "❌ 데스크탑의 SSH 호스트 키를 확인하지 못해 연결을 차단했습니다. 봇 관리자에게 문의하세요.",
    "AUTH_ERROR": "❌ 데스크탑 SSH 인증에 실패했습니다. 봇 관리자에게 문의하세요.",
    "CONNECTION_FAILED": "❌ 데스크탑에 연결하지 못했습니다. 전원과 네트워크 상태를 확인하세요.",
    "CHECK_FAILED": "❌ 데스크탑 연결 점검에 실패하여 종료 요청을 보내지 않았습니다. 봇 관리자에게 문의하세요.",
    "REJECTED": "❌ 데스크탑이 종료 요청을 거부했습니다. 종료 권한과 데스크탑 상태를 확인하세요.",
    "SHUTDOWN_PRIVILEGE_MISSING": "❌ Windows 종료 작업에 필요한 권한이 없습니다 (오류 1314). 봇 관리자에게 문의하세요.",
    "SHUTDOWN_ACCESS_DENIED": "❌ Windows가 종료 명령의 접근을 거부했습니다 (오류 5). 봇 관리자에게 문의하세요.",
    "WINDOWS_SHUTTING_DOWN": "⏳ Windows가 이미 종료 처리 중입니다. 실제 전원 상태를 확인하세요.",
    "BOOT_CHANGED": "⚠️ 점검 도중 Windows 부팅 상태가 바뀌어 종료 요청을 취소했습니다. 현재 데스크탑 상태를 확인하세요.",
    "UNKNOWN": "⚠️ 종료 요청의 처리 결과를 확인하지 못했습니다. 요청이 전달되었을 수 있어 자동 재시도하지 않습니다. 데스크탑 상태를 확인하세요.",
}

_MAC_ADDRESS_PATTERN = re.compile(r"^(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")
_PANEL_CONTENT = "**데스크탑 전원**\n아래 버튼으로 데스크탑을 켤 수 있습니다."
_WAKE_BUTTON_ID = "desktop_panel:wake"


def _wol_mac_address() -> str:
    """Return the configured MAC address without ever including it in errors."""
    compact_address = WOL_MAC_ADDRESS.replace(":", "").replace("-", "")
    if (
        not _MAC_ADDRESS_PATTERN.fullmatch(WOL_MAC_ADDRESS)
        or compact_address == "000000000000"
    ):
        raise RuntimeError("WOL_MAC_ADDRESS is missing or invalid")
    return WOL_MAC_ADDRESS


async def _run_command(*args: str) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=COMMAND_TIMEOUT,
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()
        raise RuntimeError(f"Command timed out after {COMMAND_TIMEOUT} seconds")

    return (
        process.returncode or 0,
        stdout.decode(errors="replace").strip(),
        stderr.decode(errors="replace").strip(),
    )


class DesktopWakeButton(discord.ui.DynamicItem[discord.ui.Button], template=_WAKE_BUTTON_ID):
    def __init__(self) -> None:
        super().__init__(discord.ui.Button(
            label="데스크탑 켜기", style=discord.ButtonStyle.success, custom_id=_WAKE_BUTTON_ID,
        ))

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):
        return cls()

    async def callback(self, interaction: discord.Interaction) -> None:
        cog = interaction.client.get_cog("SystemCog")
        if cog is not None:
            await cog.wake_from_panel(interaction)


class SystemCog(commands.Cog):
    desktop_panel = app_commands.Group(
        name="desktop_panel", description="데스크탑 켜기 패널을 관리합니다.", guild_only=True,
    )

    def __init__(self) -> None:
        self.desktop_service = DesktopService()
        self._panel_lock = asyncio.Lock()

    @app_commands.command(name="ping", description="봇의 응답 상태를 확인합니다.")
    async def ping(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("Pong!")

    @app_commands.command(name="desktop_on", description="데스크탑을 원격 실행합니다.")
    async def desktop_on(self, interaction: discord.Interaction) -> None:
        await self._wake_desktop(interaction)

    async def _wake_desktop(self, interaction: discord.Interaction, *, from_panel: bool = False) -> None:
        permission_manager = getattr(interaction.client, "permission_manager", None)
        if permission_manager is None or not permission_manager.has_capability(
            interaction.user,
            interaction.guild_id,
            DESKTOP_POWER,
        ):
            logger.warning(
                "Unauthorized Wake on LAN request: guild=%s user=%s",
                interaction.guild_id,
                interaction.user.id,
            )
            denial = (
                "이 버튼을 사용하려면 `desktop_power`, `manager` 또는 `admin` 권한이 필요합니다."
                if from_panel else
                "❌ `/desktop_on` 명령은 `desktop_power`, `manager` 또는 `admin` 권한이 필요합니다."
            )
            await interaction.response.send_message(denial, ephemeral=True)
            return

        await interaction.response.defer(thinking=True, ephemeral=from_panel)
        try:
            returncode, _stdout, _stderr = await _run_command(
                "wakeonlan",
                "-i",
                WOL_BROADCAST_ADDRESS,
                _wol_mac_address(),
            )
            if returncode != 0:
                logger.error("wakeonlan failed with exit code %d", returncode)
                raise RuntimeError("wakeonlan failed")
            message = "Wake on LAN 패킷을 전송했습니다."
            if not from_panel:
                message = "📡 " + message
        except Exception:
            logger.exception("Wake on LAN command failed")
            message = "Wake on LAN 요청에 실패했습니다. 자세한 내용은 봇 관리자에게 문의하세요."
            if not from_panel:
                message = "❌ " + message
        await interaction.followup.send(message, ephemeral=from_panel)

    async def wake_from_panel(self, interaction: discord.Interaction) -> None:
        manager = getattr(interaction.client, "permission_manager", None)
        guild_id = interaction.guild_id
        panel = None
        if guild_id is not None and manager is not None and manager.is_configured_guild(guild_id):
            try:
                panel = manager.store.get_desktop_panel(guild_id)
            except sqlite3.Error:
                logger.exception("Failed to read desktop panel registration: guild=%s", guild_id)
        if interaction.message is None or panel != (interaction.channel_id, interaction.message.id):
            await interaction.response.send_message("현재 등록된 데스크탑 패널이 아닙니다.", ephemeral=True)
            return
        await self._wake_desktop(interaction, from_panel=True)

    async def _panel_owner(self, interaction: discord.Interaction) -> PermissionManager | None:
        manager = getattr(interaction.client, "permission_manager", None)
        if manager is None or not manager.is_configured_guild(interaction.guild_id):
            await interaction.response.send_message("이 서버에서는 데스크탑 패널을 설정할 수 없습니다.", ephemeral=True)
            return None
        if not manager.is_owner(interaction.user.id):
            await interaction.response.send_message("봇 소유자만 데스크탑 패널을 관리할 수 있습니다.", ephemeral=True)
            return None
        return manager

    @staticmethod
    async def _delete_panel_message(bot, guild_id: int, panel: tuple[int, int]) -> bool:
        channel_id, message_id = panel
        channel = bot.get_partial_messageable(channel_id, guild_id=guild_id)
        try:
            await channel.get_partial_message(message_id).delete()
        except discord.NotFound:
            pass
        except discord.HTTPException:
            logger.warning("Could not delete inactive desktop panel: guild=%s message=%s", guild_id, message_id)
            return False
        return True

    @desktop_panel.command(name="set", description="이 서버의 지정 채널에 데스크탑 켜기 패널을 설치합니다.")
    @app_commands.describe(channel="켜기 버튼을 표시할 텍스트 채널")
    async def set_desktop_panel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        guild_id = interaction.guild_id
        manager = await self._panel_owner(interaction)
        if manager is None or guild_id is None:
            return
        if channel.guild.id != guild_id:
            await interaction.response.send_message("현재 서버의 텍스트 채널을 선택하세요.", ephemeral=True)
            return
        await interaction.response.defer(thinking=True, ephemeral=True)
        async with self._panel_lock:
            try:
                result = await self._install_panel(interaction.client, guild_id, manager, channel)
            except discord.HTTPException:
                logger.warning("Could not post or update desktop panel: guild=%s channel=%s", guild_id, channel.id)
                result = "패널을 표시하지 못했습니다. 선택한 채널에서 봇의 메시지 전송 권한을 확인하세요."
            except sqlite3.Error:
                logger.exception("Failed to save desktop panel registration: guild=%s", guild_id)
                result = "패널 설정을 저장하지 못했습니다. 봇 관리자에게 문의하세요."
        await interaction.followup.send(result, ephemeral=True)

    async def _install_panel(self, bot, guild_id: int, manager: PermissionManager, channel: discord.TextChannel) -> str:
        previous = manager.store.get_desktop_panel(guild_id)
        view = discord.ui.View(timeout=None)
        view.add_item(DesktopWakeButton())
        message = None
        if previous is not None and previous[0] == channel.id:
            try:
                message = await channel.get_partial_message(previous[1]).edit(content=_PANEL_CONTENT, view=view)
            except discord.NotFound:
                pass
        if message is None:
            message = await channel.send(_PANEL_CONTENT, view=view)
            try:
                manager.store.set_desktop_panel(guild_id, channel.id, message.id)
            except sqlite3.Error:
                await self._delete_panel_message(bot, guild_id, (channel.id, message.id))
                raise

        result = f"[데스크탑 켜기 패널]({message.jump_url})을 {channel.mention}에 등록했습니다."
        if previous is not None and previous != (channel.id, message.id):
            if not await self._delete_panel_message(bot, guild_id, previous):
                result += "\n이전 패널은 비활성화했습니다. 메시지는 채널에서 직접 삭제할 수 있습니다."
        if not message.pinned:
            try:
                await message.pin()
            except discord.HTTPException:
                logger.warning("Could not pin desktop panel: guild=%s message=%s", guild_id, message.id)
                result += "\n자동으로 고정하지 못했습니다. 패널 메시지를 채널에서 직접 고정할 수 있습니다."
        return result

    @desktop_panel.command(name="remove", description="이 서버에 등록된 데스크탑 켜기 패널을 삭제합니다.")
    async def remove_desktop_panel(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        manager = await self._panel_owner(interaction)
        if manager is None or guild_id is None:
            return
        await interaction.response.defer(thinking=True, ephemeral=True)
        async with self._panel_lock:
            try:
                panel = manager.store.get_desktop_panel(guild_id)
                if panel is None:
                    result = "이 서버에 등록된 데스크탑 패널이 없습니다."
                else:
                    manager.store.remove_desktop_panel(guild_id)
                    if await self._delete_panel_message(interaction.client, guild_id, panel):
                        result = "데스크탑 패널을 삭제했습니다."
                    else:
                        result = "패널을 비활성화했습니다. 메시지는 채널에서 직접 삭제할 수 있습니다."
            except sqlite3.Error:
                logger.exception("Failed to remove desktop panel registration: guild=%s", guild_id)
                result = "패널 설정을 삭제하지 못했습니다. 봇 관리자에게 문의하세요."
        await interaction.followup.send(result, ephemeral=True)

    @app_commands.command(name="desktop_off", description="작업을 저장한 뒤 데스크탑을 원격 종료합니다.")
    @app_commands.guild_only()
    async def desktop_off(self, interaction: discord.Interaction, confirm: bool = False) -> None:
        if not await require_manager(interaction):
            return
        if not confirm:
            await interaction.response.send_message(
                "데스크탑의 작업을 저장하고 종료할 준비가 되었는지 확인한 뒤 "
                "`/desktop_off confirm:True`를 실행하세요.", ephemeral=True,
            )
            return
        await interaction.response.defer(thinking=True, ephemeral=False)
        logger.info("Desktop shutdown requested: guild=%s user=%s", interaction.guild_id, interaction.user.id)
        try:
            result = await self.desktop_service.shutdown()
            message = DESKTOP_OFF_MESSAGES[result]
        except Exception:
            # Exception messages may contain connection details or key paths.
            logger.error("Unexpected desktop shutdown failure; delivery may be uncertain")
            message = DESKTOP_OFF_MESSAGES["UNKNOWN"]
        await interaction.followup.send(message, ephemeral=False)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SystemCog())
    bot.add_dynamic_items(DesktopWakeButton)


async def teardown(bot: commands.Bot) -> None:
    bot.remove_dynamic_items(DesktopWakeButton)
