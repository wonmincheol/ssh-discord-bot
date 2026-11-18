import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from tests.discord_stub import install_discord_stub


install_discord_stub()

import discord

from extensions.access.service import ADMIN, DESKTOP_POWER, PermissionManager
from extensions.access.settings import AccessSettings
from extensions.access.store import PermissionStore
from extensions.system import DesktopWakeButton, SystemCog


class DesktopPanelTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.store = PermissionStore(":memory:")
        self.addCleanup(self.store.close)
        settings = AccessSettings(frozenset({10, 20}), frozenset({1}), ":memory:")
        self.manager = PermissionManager(settings, self.store)
        self.store.set_role_id(10, ADMIN, 100)
        self.store.set_role_id(10, DESKTOP_POWER, 200)
        self.cog = SystemCog()
        self.bot = Mock(permission_manager=self.manager)
        self.bot.get_cog.return_value = self.cog
        self.delete_message = AsyncMock()
        self.bot.get_partial_messageable.return_value.get_partial_message.return_value.delete = self.delete_message

    def interaction(self, *, guild=10, channel=30, message=40, user=1, roles=()):
        return SimpleNamespace(
            guild_id=guild,
            channel_id=channel,
            message=SimpleNamespace(id=message),
            user=SimpleNamespace(id=user, roles=[SimpleNamespace(id=role) for role in roles]),
            client=self.bot,
            response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
        )

    def channel(self, channel_id=30, message_id=40, guild_id=10):
        message = SimpleNamespace(id=message_id, pinned=False, pin=AsyncMock(), jump_url="https://discord.com/channels/10/30/40")
        return SimpleNamespace(
            id=channel_id,
            guild=SimpleNamespace(id=guild_id),
            mention=f"<#{channel_id}>",
            send=AsyncMock(return_value=message),
            get_partial_message=Mock(return_value=SimpleNamespace(edit=AsyncMock(return_value=message))),
        )

    async def test_only_owner_can_manage_panels_in_allowed_guilds(self) -> None:
        channel = self.channel()
        self.store.set_desktop_panel(10, 30, 40)
        for interaction in (
            self.interaction(user=2, roles=(100,)),
            self.interaction(guild=99),
            self.interaction(guild=None),
        ):
            await SystemCog.set_desktop_panel.callback(self.cog, interaction, channel)
            await SystemCog.remove_desktop_panel.callback(self.cog, interaction)
            self.assertEqual(interaction.response.send_message.await_count, 2)
        channel.send.assert_not_awaited()
        channel.get_partial_message.assert_not_called()
        self.delete_message.assert_not_awaited()
        self.assertEqual(self.store.get_desktop_panel(10), (30, 40))

        other_guild_channel = self.channel(guild_id=20)
        await SystemCog.set_desktop_panel.callback(self.cog, self.interaction(), other_guild_channel)
        other_guild_channel.send.assert_not_awaited()

    async def test_install_refresh_move_and_remove_panel(self) -> None:
        channel = self.channel()
        await SystemCog.set_desktop_panel.callback(self.cog, self.interaction(), channel)
        self.assertEqual(self.store.get_desktop_panel(10), (30, 40))
        channel.send.return_value.pin.assert_awaited_once()
        channel.send.return_value.pinned = True

        await SystemCog.set_desktop_panel.callback(self.cog, self.interaction(), channel)
        channel.send.assert_awaited_once()
        channel.get_partial_message.assert_called_once_with(40)
        channel.get_partial_message.return_value.edit.assert_awaited_once()

        new_channel = self.channel(channel_id=31, message_id=41)
        # Discord no longer lets the bot access the previous channel.
        self.delete_message.side_effect = discord.Forbidden(Mock(status=403, reason="Forbidden"), "")
        interaction = self.interaction()
        await SystemCog.set_desktop_panel.callback(self.cog, interaction, new_channel)
        self.assertEqual(self.store.get_desktop_panel(10), (31, 41))
        self.assertIn("이전 패널은 비활성화", interaction.followup.send.await_args.args[0])

        with patch("extensions.system._run_command", AsyncMock()) as run_command:
            await DesktopWakeButton().callback(self.interaction())
            run_command.assert_not_awaited()

        await SystemCog.remove_desktop_panel.callback(self.cog, self.interaction())
        self.assertIsNone(self.store.get_desktop_panel(10))
        self.assertEqual(self.delete_message.await_count, 2)

    async def test_only_current_panel_and_users_with_wake_permission_send_wol(self) -> None:
        self.store.set_desktop_panel(10, 30, 40)
        button = DesktopWakeButton()
        with (
            patch("extensions.system.WOL_MAC_ADDRESS", "AA:BB:CC:DD:EE:FF"),
            patch("extensions.system._run_command", AsyncMock(return_value=(0, "", ""))) as run_command,
        ):
            for interaction in (
                self.interaction(guild=20),
                self.interaction(guild=None),
                self.interaction(channel=31),
                self.interaction(message=41),
                self.interaction(user=2),
            ):
                await button.callback(interaction)
                self.assertTrue(interaction.response.send_message.await_args.kwargs["ephemeral"])
            run_command.assert_not_awaited()

            authorized = self.interaction(user=2, roles=(200,))
            await button.callback(authorized)
            run_command.assert_awaited_once()
            self.assertTrue(authorized.followup.send.await_args.kwargs["ephemeral"])

            slash = self.interaction(guild=20, channel=99)
            await SystemCog.desktop_on.callback(self.cog, slash)
            self.assertEqual(run_command.await_count, 2)
            self.assertFalse(slash.followup.send.await_args.kwargs["ephemeral"])
