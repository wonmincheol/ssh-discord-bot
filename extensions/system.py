"""Commands for controlling and inspecting the mini PC itself."""

import asyncio
import logging
import os
import re

import discord
from discord import app_commands
from discord.ext import commands


COMMAND_TIMEOUT = 15
WOL_BROADCAST_ADDRESS = os.getenv("WOL_BROADCAST_ADDRESS", "172.30.1.255")
WOL_MAC_ADDRESS = os.getenv("WOL_MAC_ADDRESS", "").strip()

logger = logging.getLogger(__name__)

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
                "❌ `/desktop_on` 명령을 사용하려면 `desktop_power` 권한이 필요합니다.",
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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SystemCog())
