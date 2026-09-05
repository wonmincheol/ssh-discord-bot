import logging

import discord
from discord.ext import commands

from config import DISCORD_TOKEN, EXTENSIONS


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class RemoteControlBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=discord.Intents.default())

    async def setup_hook(self) -> None:
        for extension in EXTENSIONS:
            await self.load_extension(extension)
            logger.info("Loaded extension: %s", extension)

        synced = await self.tree.sync()
        logger.info("Synced %d application commands", len(synced))

    async def on_ready(self) -> None:
        logger.info("Logged in as %s", self.user)


if __name__ == "__main__":
    RemoteControlBot().run(DISCORD_TOKEN)
