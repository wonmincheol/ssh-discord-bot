"""Read-only Factorio server connection information."""

import os

import discord
from discord import app_commands
from discord.ext import commands


class FactorioCog(commands.Cog):
    @app_commands.command(name="factorio", description="Factorio 서버 접속 정보를 확인합니다.")
    @app_commands.guild_only()
    async def factorio(self, interaction: discord.Interaction) -> None:
        address = os.getenv("FACTORIO_SERVER_ADDRESS", "mincheol.duckdns.org:34197")
        password = os.getenv("FACTORIO_SERVER_PASSWORD", "").strip()
        version = os.getenv("FACTORIO_GAME_VERSION", "2.1.24 정식")
        dlc = os.getenv("FACTORIO_REQUIRED_DLC", "스페이스 에이지")
        password_info = f"`{password}`" if password else "미설정 (봇 관리자에게 문의하세요.)"

        await interaction.response.send_message(
            "**Factorio 서버 접속 정보**\n"
            f"• **서버 주소**: `{address}`\n"
            f"• **비밀번호**: {password_info}\n"
            f"• **게임 버전**: **{version}**\n"
            f"• **필수 DLC**: **{dlc}**\n"
            "• **모드**: 서버 접속 시 모드를 동기화하세요.\n"
            "• **접속 방법**: 멀티플레이 → 주소로 접속"
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FactorioCog())
