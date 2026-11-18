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

    def describe(**_kwargs):
        return lambda value: value

    class Group:
        def __init__(self, **_kwargs):
            pass

        def command(self, **_kwargs):
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

    class DynamicItem:
        def __class_getitem__(cls, _item_type):
            return cls

        def __init_subclass__(cls, **_kwargs):
            super().__init_subclass__()

        def __init__(self, item):
            self.item = item

    class View:
        def __init__(self, **_kwargs):
            self.children = []

        def add_item(self, item):
            self.children.append(item)

    discord = ModuleType("discord")
    discord.Interaction = object
    discord.Member = object
    discord.Guild = object
    discord.TextChannel = object
    discord.HTTPException = type("HTTPException", (Exception,), {})
    discord.NotFound = type("NotFound", (discord.HTTPException,), {})
    discord.Forbidden = type("Forbidden", (discord.HTTPException,), {})
    discord.app_commands = SimpleNamespace(command=command, describe=describe, guild_only=guild_only, Group=Group)
    discord.ui = SimpleNamespace(Button=SimpleNamespace, DynamicItem=DynamicItem, View=View)
    discord.ButtonStyle = SimpleNamespace(success=object())

    discord_ext = ModuleType("discord.ext")
    discord_ext.commands = SimpleNamespace(Cog=Cog, GroupCog=GroupCog, Bot=Bot)

    sys.modules["discord"] = discord
    sys.modules["discord.ext"] = discord_ext
