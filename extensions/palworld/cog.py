"""Discord commands and lifecycle management for Palworld."""

import asyncio
import contextlib
import logging
from time import monotonic

import discord
from discord import app_commands
from discord.ext import commands

from .service import CommandResult, PalworldService
from .settings import PalworldSettings


logger = logging.getLogger(__name__)


class PalworldCog(
    commands.GroupCog,
    group_name="palworld",
    group_description="Palworld 전용 서버를 관리합니다.",
):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.settings = PalworldSettings.from_environment()
        self.service = PalworldService(self.settings)
        self._auto_shutdown_task: asyncio.Task | None = None

    async def cog_unload(self) -> None:
        await self._cancel_auto_shutdown()

    @app_commands.command(name="status", description="서버 상태를 확인합니다.")
    async def status(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        try:
            result = await self.service.status()
            if result.returncode == 0 and result.stdout == "RUNNING":
                message = "🟢 Palworld server is running"
            elif result.returncode == 0 and result.stdout == "STOPPED":
                message = "🔴 Palworld server is shut down"
            else:
                message = self._failure_message("Status check failed", result)
        except Exception as error:
            message = f"⚠️ Status check failed\n```{error}```"
        await interaction.followup.send(message)

    @app_commands.command(name="start", description="서버를 실행합니다.")
    async def start(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        try:
            result = await self.service.start()
            if result.returncode == 0 and result.stdout == "STARTED":
                self._start_auto_shutdown(interaction.channel_id)
                message = "🚀 Starting Palworld server"
            elif result.returncode == 0 and result.stdout == "ALREADY_RUNNING":
                self._start_auto_shutdown(interaction.channel_id)
                message = "🟡 Server is already running"
            else:
                message = self._failure_message("Failed to start the server", result)
        except Exception as error:
            message = f"❌ Failed to start the server\n```{error}```"
        await interaction.followup.send(message)

    @app_commands.command(name="stop", description="서버를 종료합니다.")
    async def stop(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        await self._cancel_auto_shutdown()
        try:
            result = await self.service.stop()
            if result.returncode == 0 and result.stdout == "STOPPED":
                message = "🛑 Shut down the Palworld server"
            elif result.returncode == 0 and result.stdout == "ALREADY_STOPPED":
                message = "🔴 Server is already shut down"
            else:
                message = self._failure_message("Failed to shut down the server", result)
        except Exception as error:
            message = f"❌ Failed to shut down the server\n```{error}```"
        await interaction.followup.send(message)

    @app_commands.command(name="players", description="접속 중인 플레이어를 확인합니다.")
    async def players(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        try:
            players = await self.service.get_players()
            if not players:
                message = "👥 **Active players (0)**\n\nNo players are currently online."
            else:
                names = "\n".join(
                    f"• {player.get('name', 'Unknown')}" for player in players
                )
                message = f"👥 **Active players ({len(players)})**\n\n{names}"
        except Exception as error:
            message = f"❌ Failed to get player list\n```{error}```"
        await interaction.followup.send(message)

    def _start_auto_shutdown(self, channel_id: int) -> None:
        if not self.settings.auto_shutdown_enabled:
            return
        if self._auto_shutdown_task and not self._auto_shutdown_task.done():
            return
        self._auto_shutdown_task = asyncio.create_task(
            self._monitor_empty_server(channel_id),
            name="palworld-auto-shutdown",
        )

    async def _cancel_auto_shutdown(self) -> None:
        task = self._auto_shutdown_task
        self._auto_shutdown_task = None
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _monitor_empty_server(self, channel_id: int) -> None:
        empty_since: float | None = None
        try:
            while True:
                try:
                    players = await self.service.get_players()
                    if players:
                        empty_since = None
                    elif empty_since is None:
                        empty_since = monotonic()
                    elif monotonic() - empty_since >= self.settings.auto_shutdown_after.total_seconds():
                        result = await self.service.stop()
                        if result.returncode == 0 and result.stdout in {
                            "STOPPED",
                            "ALREADY_STOPPED",
                        }:
                            await self._notify(
                                channel_id,
                                "🛑 No players were online, so the Palworld server "
                                "was shut down automatically.",
                            )
                        else:
                            await self._notify(
                                channel_id,
                                self._failure_message("Automatic shutdown failed", result),
                            )
                        return
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("Palworld auto-shutdown check failed")

                await asyncio.sleep(self.settings.check_interval)
        finally:
            self._auto_shutdown_task = None

    async def _notify(self, channel_id: int, message: str) -> None:
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            with contextlib.suppress(discord.HTTPException, discord.NotFound):
                channel = await self.bot.fetch_channel(channel_id)
        if channel is not None and hasattr(channel, "send"):
            await channel.send(message)

    @staticmethod
    def _failure_message(summary: str, result: CommandResult) -> str:
        details = result.stderr or result.stdout or f"exit code {result.returncode}"
        return f"❌ {summary}\n```{details}```"
