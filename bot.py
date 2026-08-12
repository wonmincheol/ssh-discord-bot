import discord
import subprocess
import sys
import asyncio
from palworld_api import get_players
from discord.ext import commands
from discord import app_commands
from config import DISCORD_TOKEN
from config import STATUS_SCRIPT
from config import START_SCRIPT
from config import STOP_SCRIPT


server_sessions = {}


bot = commands.Bot(
    command_prefix="!", 
    intents=discord.Intents.default()
)




@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"{bot.user} Login sucess!")
    bot.loop.create_task(
        monitor_auto_shutdown()
    )




async def monitor_auto_shutdown():
    # print("monitor start")
    while True:
        # print(server_sessions)
        for guild_id, session in list(server_sessions.items()):

            process = session["process"]

            if process.poll() is not None:

                output = process.stdout.read()

                if "AUTO_SHUTDOWN" in output:

                    await session["ctx"].send(
                        "🛑 The server shut down automatically because there was no player for an hour."
                    )

                    del server_sessions[guild_id]

        await asyncio.sleep(3)

@bot.tree.command(name="ping", description="봇의 응답 상태를 확인합니다.")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!")


@bot.tree.command(name="who", description="봇이 사용중인 계정을 확인합니다.")
async def who(interaction: discord.Interaction):
    result = subprocess.run(
        ["whoami"],
        capture_output=True,
        text=True
    )

    await interaction.response.send_message(f"Current Bot Run Account : `{result.stdout.strip()}`")


@bot.tree.command(name="status", description="팰월드 서버 상태를 확인합니다.")
async def status(interaction: discord.Interaction):

    result = subprocess.run(
        ["sudo", STATUS_SCRIPT],
        capture_output=True,
        text=True
    )

    status = result.stdout.strip()

    if status == "RUNNING":
        await interaction.response.send_message("🟢 Palworld server is running")

    elif status == "STOPPED":
        await interaction.response.send_message("🔴 Palworld server is shutdown")

    else:
        await interaction.response.send_message(f"⚠️ Status check failed\n```{result.stderr}```")


@bot.tree.command(name="start", description="팰월드 서버를 실행합니다.")
async def start(interaction: discord.Interaction):
    guild_id = interaction.guild.id

    result = subprocess.run(
        ["sudo", START_SCRIPT],
        capture_output=True,
        text=True
    )

    status = result.stdout.strip()

    if status == "STARTED":
        # auto_shutdown.py가 이미 실행 중이 아니라면 실행
        session = server_sessions.get(guild_id)

        if session is None or session["process"].poll() is not None:

            process = subprocess.Popen(
                [
                    sys.executable,
                    "/data/discord-bot/auto_shutdown.py"
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )

            server_sessions[guild_id] = {
                "interaction": interaction,
                "process": process
            }

        await interaction.response.send_message("🚀 Starting Palworld server")

    elif status == "ALREADY_RUNNING":
        await interaction.response.send_message("🟡 Server is already running")

    else:
        await interaction.response.send_message(
            f"❌ Failed to start the server\n```{result.stderr}```"
        )


@bot.tree.command(name="stop", description="팰월드 서버를 종료합니다.")
async def stop(interaction: discord.Interaction):
    guild_id = interaction.guild.id

    session = server_sessions.get(guild_id)

    if session:

        process = session["process"]

        if process.poll() is None:
            process.terminate()

        del server_sessions[guild_id]

    result = subprocess.run(
        ["sudo", STOP_SCRIPT],
        capture_output=True,
        text=True
    )

    status = result.stdout.strip()

    if status == "STOPPED":
        await interaction.response.send_message("🛑 Shut down the palworld server")

    elif status == "ALREADY_STOPPED":
        await interaction.response.send_message("🔴 Server is already shut down")

    elif status == "FAILED":
        await interaction.response.send_message("❌ Failed to shut down the server")

    else:
        await interaction.response.send_message(
            f"⚠️ Unknown error\n```{result.stderr}```"
        )


@bot.tree.command(name="players", description="팰월드 서버에 접속한 유저를 확인합니다.")
async def players(interaction: discord.Interaction):
    try:
        players = get_players()

        # 접속자가 없는 경우
        if len(players) == 0:
            await ctx.send(
                "👥 **Active Player (0 person)**\n\n"
                "No active players are currently active"
            )
            return

        # 플레이어 목록 생성
        message = f"👥 **Active Player ({len(players)}person)**\n\n"

        for player in players:
            message += f"• {player['name']}\n"

        await interaction.response.send_message(message)

    except Exception as e:
        await interaction.response.send_message(
            "❌ Failed to get player list\n"
            f"```{e}```"
        )


@bot.tree.command(name="desktop_on", description="데스크탑을 원격 실행합니다.")
async def desktop_on(interaction: discord.Interaction):
    """데스크탑 Wake on LAN"""

    try:
        result = subprocess.run(
            [
                "wakeonlan",
                "-i",
                "172.30.1.255",
                "10:FF:E0:C0:F2:06"
            ],
            capture_output=True,
            text=True
        )

        await interaction.response.send_message(
            f"📡 Wake on LAN 패킷을 전송했습니다.\n```{result.stdout}```"
        )

    except Exception as e:
        await interaction.response.send_message(f"❌ 오류 발생\n```{e}```")





# slash apply construct





bot.run(DISCORD_TOKEN)
