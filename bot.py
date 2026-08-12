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


@bot.tree.command(name="ping", description="봇의 응답 상태를 확인합니다.")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!")


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


@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")


@bot.command()
async def who(ctx):
    result = subprocess.run(
        ["whoami"],
        capture_output=True,
        text=True
    )

    await ctx.send(f"Current Bot Run Account : `{result.stdout.strip()}`")


@bot.command()
async def status(ctx):

    result = subprocess.run(
        ["sudo", STATUS_SCRIPT],
        capture_output=True,
        text=True
    )

    status = result.stdout.strip()

    if status == "RUNNING":
        await ctx.send("🟢 Palworld server is running")

    elif status == "STOPPED":
        await ctx.send("🔴 Palworld server is shutdown")

    else:
        await ctx.send(f"⚠️ Status check failed\n```{result.stderr}```")


@bot.command()
async def start(ctx):
    guild_id = ctx.guild.id

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
                "ctx": ctx,
                "process": process
            }

        await ctx.send("🚀 Starting Palworld server")

    elif status == "ALREADY_RUNNING":
        await ctx.send("🟡 Server is already running")

    else:
        await ctx.send(
            f"❌ Failed to start the server\n```{result.stderr}```"
        )


@bot.command()
async def stop(ctx):
    guild_id = ctx.guild.id

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
        await ctx.send("🛑 Shut down the palworld server")

    elif status == "ALREADY_STOPPED":
        await ctx.send("🔴 Server is already shut down")

    elif status == "FAILED":
        await ctx.send("❌ Failed to shut down the server")

    else:
        await ctx.send(
            f"⚠️ Unknown error\n```{result.stderr}```"
        )


@bot.command()
async def players(ctx):
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

        await ctx.send(message)

    except Exception as e:
        await ctx.send(
            "❌ Failed to get player list\n"
            f"```{e}```"
        )


@bot.command()
async def desktop_on(ctx):
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

        await ctx.send(
            f"📡 Wake on LAN 패킷을 전송했습니다.\n```{result.stdout}```"
        )

    except Exception as e:
        await ctx.send(f"❌ 오류 발생\n```{e}```")





# slash apply construct





bot.run(DISCORD_TOKEN)
