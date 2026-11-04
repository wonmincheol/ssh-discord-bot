"""Manager-accessible Discord commands for SPT + Fika."""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from extensions.access.checks import require_manager

from .service import TarkovService
from .settings import TarkovSettings


logger = logging.getLogger(__name__)

MESSAGES = {
    "RUNNING": "🟢 Tarkov tmux 세션이 실행 중입니다. 게임 접속 준비 여부는 서버 콘솔에서 확인하세요.",
    "STARTED": "🚀 Tarkov 서버를 시작했습니다. 게임 접속 준비까지 잠시 기다려 주세요.",
    "ALREADY_RUNNING": "🟡 Tarkov 세션이 이미 실행 중입니다.",
    "STOPPED": "🔴 Tarkov tmux 세션이 종료되었습니다.",
    "ALREADY_STOPPED": "🔴 Tarkov 세션이 이미 종료된 상태입니다.",
    "STOPPING": "⏳ 종료 요청 후 대기 중입니다. `/tarkov status`로 상태를 확인하세요.",
    "BUSY": "⏳ 서버 제어 작업이 진행 중입니다. 잠시 후 다시 시도하세요.",
    "STOP_TIMEOUT": "⚠️ Ctrl+C를 전달했지만 제한 시간 내에 세션 종료를 확인하지 못했습니다. "
                    "강제 종료하지 않았습니다. 서버 콘솔을 확인하세요.",
}


class TarkovCog(commands.GroupCog, group_name="tarkov", group_description="SPT + Fika 서버를 관리합니다."):
    def __init__(self, bot: commands.Bot) -> None:
        self.service = TarkovService(TarkovSettings.from_environment())

    async def _allowed(self, interaction: discord.Interaction) -> bool:
        return await require_manager(interaction)

    async def _execute(self, interaction: discord.Interaction, action: str) -> None:
        await interaction.response.defer(thinking=True)
        try:
            result = await getattr(self.service, action)()
            message = MESSAGES[result]
        except Exception:
            logger.exception("Tarkov %s failed", action)
            message = "❌ Tarkov 서버 제어에 실패했습니다. 봇 관리자 로그를 확인하세요."
        await interaction.followup.send(message)

    @app_commands.command(name="start", description="Tarkov 서버를 실행합니다.")
    @app_commands.guild_only()
    async def start(self, interaction: discord.Interaction) -> None:
        if await self._allowed(interaction):
            await self._execute(interaction, "start")

    @app_commands.command(name="stop", description="모두 레이드와 게임을 종료한 뒤 서버를 종료합니다.")
    @app_commands.guild_only()
    async def stop(self, interaction: discord.Interaction, everyone_finished: bool = False) -> None:
        if not await self._allowed(interaction):
            return
        if not everyone_finished:
            await interaction.response.send_message(
                "모두 레이드를 마치고 게임을 종료했는지 확인한 뒤 "
                "`/tarkov stop everyone_finished:True`를 실행하세요.", ephemeral=True,
            )
            return
        await self._execute(interaction, "stop")

    @app_commands.command(name="status", description="Tarkov tmux 세션 상태를 확인합니다.")
    @app_commands.guild_only()
    async def status(self, interaction: discord.Interaction) -> None:
        if await self._allowed(interaction):
            await self._execute(interaction, "status")
