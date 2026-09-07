import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from tests.discord_stub import install_discord_stub


install_discord_stub()

from extensions.system import SystemCog


class SystemCogPrivacyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.interaction = Mock()
        self.interaction.response.defer = AsyncMock()
        self.interaction.response.send_message = AsyncMock()
        self.interaction.followup.send = AsyncMock()
        self.interaction.guild_id = 123
        self.interaction.user.id = 456
        self.interaction.client.permission_manager.has_capability.return_value = True

    async def test_desktop_on_does_not_return_command_output(self) -> None:
        command_output = "Sending magic packet to AA:BB:CC:DD:EE:FF"

        with (
            patch("extensions.system.WOL_MAC_ADDRESS", "AA:BB:CC:DD:EE:FF"),
            patch(
                "extensions.system._run_command",
                AsyncMock(return_value=(0, command_output, "")),
            ),
        ):
            await SystemCog.desktop_on.callback(SystemCog(), self.interaction)

        message = self.interaction.followup.send.await_args.args[0]
        self.assertEqual(message, "📡 Wake on LAN 패킷을 전송했습니다.")
        self.assertNotIn("AA:BB:CC:DD:EE:FF", message)

    async def test_desktop_on_does_not_return_error_details(self) -> None:
        private_error = "Invalid MAC AA:BB:CC:DD:EE:FF"

        with (
            patch("extensions.system.WOL_MAC_ADDRESS", "AA:BB:CC:DD:EE:FF"),
            patch(
                "extensions.system._run_command",
                AsyncMock(return_value=(1, "", private_error)),
            ),
        ):
            await SystemCog.desktop_on.callback(SystemCog(), self.interaction)

        message = self.interaction.followup.send.await_args.args[0]
        self.assertIn("Wake on LAN 요청에 실패했습니다", message)
        self.assertNotIn(private_error, message)
        self.assertNotIn("AA:BB:CC:DD:EE:FF", message)

    async def test_desktop_on_does_not_return_invalid_configuration(self) -> None:
        invalid_address = "private-mac-value"

        with (
            patch("extensions.system.WOL_MAC_ADDRESS", invalid_address),
            patch("extensions.system._run_command", AsyncMock()) as run_command,
        ):
            await SystemCog.desktop_on.callback(SystemCog(), self.interaction)

        run_command.assert_not_awaited()
        message = self.interaction.followup.send.await_args.args[0]
        self.assertIn("Wake on LAN 요청에 실패했습니다", message)
        self.assertNotIn(invalid_address, message)

    async def test_desktop_on_denies_users_without_permission(self) -> None:
        self.interaction.client.permission_manager.has_capability.return_value = False

        with patch("extensions.system._run_command", AsyncMock()) as run_command:
            await SystemCog.desktop_on.callback(SystemCog(), self.interaction)

        run_command.assert_not_awaited()
        self.interaction.response.defer.assert_not_awaited()
        self.interaction.response.send_message.assert_awaited_once()
        args, kwargs = self.interaction.response.send_message.await_args
        self.assertIn("desktop_power", args[0])
        self.assertTrue(kwargs["ephemeral"])

    async def test_desktop_on_fails_closed_without_permission_extension(self) -> None:
        self.interaction.client = SimpleNamespace()

        with patch("extensions.system._run_command", AsyncMock()) as run_command:
            await SystemCog.desktop_on.callback(SystemCog(), self.interaction)

        run_command.assert_not_awaited()
        self.interaction.response.send_message.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
