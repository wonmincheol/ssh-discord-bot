"""Minimal discord.py boundary used only when the dependency is unavailable."""

import sys
from types import ModuleType, SimpleNamespace


def install_discord_stub() -> None:
    try:
        __import__("discord")
        return
    except ModuleNotFoundError:
        pass

    class Command:
        def __init__(self, callback):
            self.callback = callback

    def command(**_kwargs):
        return Command

    def guild_only():
        def decorator(value):
            return value

        return decorator

    class Cog:
        pass

    class GroupCog(Cog):
        def __init_subclass__(cls, **_kwargs):
            super().__init_subclass__()

    class Bot:
        pass

    discord = ModuleType("discord")
    discord.Interaction = object
    discord.Member = object
    discord.Guild = object
    discord.HTTPException = type("HTTPException", (Exception,), {})
    discord.NotFound = type("NotFound", (Exception,), {})
    discord.Forbidden = type("Forbidden", (Exception,), {})
    discord.app_commands = SimpleNamespace(command=command, guild_only=guild_only)

    discord_ext = ModuleType("discord.ext")
    discord_ext.commands = SimpleNamespace(Cog=Cog, GroupCog=GroupCog, Bot=Bot)

    sys.modules["discord"] = discord
    sys.modules["discord.ext"] = discord_ext
