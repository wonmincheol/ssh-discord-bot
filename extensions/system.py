"""Commands for controlling and inspecting the mini PC itself."""

import asyncio
import logging
import os
import re

import discord
from discord import app_commands
from discord.ext import commands

from extensions.access.checks import require_manager
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


class SystemCog(commands.Cog):
    def __init__(self) -> None:
        self.desktop_service = DesktopService()

    @app_commands.command(name="ping", description="봇의 응답 상태를 확인합니다.")
    async def ping(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("Pong!")

    @app_commands.command(name="desktop_on", description="데스크탑을 원격 실행합니다.")
    async def desktop_on(self, interaction: discord.Interaction) -> None:
        permission_manager = getattr(interaction.client, "permission_manager", None)
        if permission_manager is None or not permission_manager.has_capability(
            interaction.user,
            interaction.guild_id,
            "desktop_power",
        ):
            logger.warning(
                "Unauthorized Wake on LAN request: guild=%s user=%s",
                interaction.guild_id,
                interaction.user.id,
            )
            await interaction.response.send_message(
                "❌ `/desktop_on` 명령은 `desktop_power`, `manager` 또는 `admin` 권한이 필요합니다.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)
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
            await interaction.followup.send("📡 Wake on LAN 패킷을 전송했습니다.")
        except Exception:
            logger.exception("Wake on LAN command failed")
            await interaction.followup.send(
                "❌ Wake on LAN 요청에 실패했습니다. 자세한 내용은 봇 관리자에게 문의하세요."
            )

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
