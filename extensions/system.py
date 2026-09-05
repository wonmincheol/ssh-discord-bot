"""Commands for controlling and inspecting the mini PC itself."""

import asyncio
import os

import discord
from discord import app_commands
from discord.ext import commands


COMMAND_TIMEOUT = 15
WOL_BROADCAST_ADDRESS = os.getenv("WOL_BROADCAST_ADDRESS", "172.30.1.255")
WOL_MAC_ADDRESS = os.getenv("WOL_MAC_ADDRESS", "10:FF:E0:C0:F2:06")


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

    @app_commands.command(name="who", description="봇이 사용 중인 계정을 확인합니다.")
    async def who(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        try:
            returncode, stdout, stderr = await _run_command("whoami")
            if returncode != 0:
                raise RuntimeError(stderr or "whoami failed")
            await interaction.followup.send(f"Current Bot Run Account: `{stdout}`")
        except Exception as error:
            await interaction.followup.send(f"❌ 계정 확인 실패\n```{error}```")

    @app_commands.command(name="desktop_on", description="데스크탑을 원격 실행합니다.")
    async def desktop_on(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        try:
            returncode, stdout, stderr = await _run_command(
                "wakeonlan",
                "-i",
                WOL_BROADCAST_ADDRESS,
                WOL_MAC_ADDRESS,
            )
            if returncode != 0:
                raise RuntimeError(stderr or "wakeonlan failed")
            details = f"\n```{stdout}```" if stdout else ""
            await interaction.followup.send(
                f"📡 Wake on LAN 패킷을 전송했습니다.{details}"
            )
        except Exception as error:
            await interaction.followup.send(f"❌ Wake on LAN 실패\n```{error}```")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SystemCog())
