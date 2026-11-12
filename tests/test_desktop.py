import asyncio
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from tests.discord_stub import install_discord_stub

install_discord_stub()

from extensions.access.service import ADMIN, DESKTOP_POWER, MANAGER, PermissionManager
from extensions.access.settings import AccessSettings
from extensions.access.store import PermissionStore
from extensions.desktop.service import DesktopService
from extensions.desktop.settings import DesktopSettings, DesktopSettingsError
from extensions.system import DESKTOP_OFF_MESSAGES, SystemCog


BOOT = "638983000000000000"
NEXT_BOOT = "638983100000000000"


class DesktopSettingsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.key = Path(self.directory.name) / "desktop key"
        self.hosts = Path(self.directory.name) / "known hosts"
        self.key.touch()
        self.hosts.touch()
        self.environment = {
            "DESKTOP_SSH_HOST": "192.168.1.20",
            "DESKTOP_SSH_USER": "desktopbot",
            "DESKTOP_SSH_IDENTITY_FILE": str(self.key),
            "DESKTOP_SSH_KNOWN_HOSTS_FILE": str(self.hosts),
        }

    def test_loads_optional_defaults_and_custom_port(self):
        with patch.dict(os.environ, self.environment, clear=True):
            settings = DesktopSettings.from_environment()
        self.assertEqual(settings.identity_file, self.key)
        self.assertEqual(settings.port, 22)
        self.assertEqual(settings.command_timeout, 15)
        for host in ("desktop.local", "2001:db8::20"):
            with patch.dict(os.environ, dict(self.environment, DESKTOP_SSH_HOST=host, DESKTOP_SSH_PORT="2222"), clear=True):
                self.assertEqual(DesktopSettings.from_environment().port, 2222)

    def test_rejects_missing_unsafe_or_invalid_settings_without_echoing_values(self):
        invalid = {
            "DESKTOP_SSH_HOST": ("", "-oProxyCommand=private", "host;private", "127.0.0.1", "::", "224.0.0.1"),
            "DESKTOP_SSH_USER": ("", "-private", "user@private", "user;private"),
            "DESKTOP_SSH_PORT": ("0", "65536", "private"),
            "DESKTOP_SSH_TIMEOUT": ("0", "61", "nan", "private"),
            "DESKTOP_SSH_IDENTITY_FILE": ("relative-private", str(self.key) + "-missing", 'C:/private%file'),
            "DESKTOP_SSH_KNOWN_HOSTS_FILE": ("", "relative-private", str(self.hosts) + '"private'),
        }
        for name, values in invalid.items():
            for value in values:
                with self.subTest(name=name, value=value), patch.dict(
                    os.environ, dict(self.environment, **{name: value}), clear=True,
                ):
                    with self.assertRaises(DesktopSettingsError) as raised:
                        DesktopSettings.from_environment()
                    self.assertNotIn("private", str(raised.exception))


class DesktopServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = DesktopService()
        self.settings = DesktopSettings("192.168.1.20", "desktopbot", Path("/key"), Path("/known hosts"))
        settings_patch = patch("extensions.desktop.service.DesktopSettings.from_environment", return_value=self.settings)
        settings_patch.start()
        self.addCleanup(settings_patch.stop)

    def ready(self, boot=BOOT):
        return 0, f"DESKTOP_READY {boot}", ""

    async def test_read_only_check_never_dispatches_shutdown(self):
        self.service._ssh = AsyncMock(return_value=self.ready())
        self.assertEqual(await self.service.check(), "READY")
        self.service._ssh.assert_awaited_once_with(self.settings, "desktop-check")

    async def test_accepted_shutdown_is_not_repeated_until_new_windows_boot(self):
        self.service._ssh = AsyncMock(side_effect=[
            self.ready(), (0, f"DESKTOP_SHUTDOWN_REQUESTED {BOOT}", ""),
            self.ready(), self.ready(NEXT_BOOT),
            (0, f"DESKTOP_SHUTDOWN_REQUESTED {NEXT_BOOT}", ""),
        ])
        self.assertEqual(await self.service.shutdown(), "REQUESTED")
        self.assertEqual(await self.service.shutdown(), "ALREADY_REQUESTED")
        self.assertEqual(await self.service.shutdown(), "REQUESTED")
        commands = [call.args[1] for call in self.service._ssh.await_args_list]
        self.assertEqual(commands.count(f"desktop-off {BOOT}"), 1)
        self.assertEqual(commands.count(f"desktop-off {NEXT_BOOT}"), 1)

    async def test_uncertain_delivery_is_never_automatically_retried(self):
        for reply in (asyncio.TimeoutError(), OSError("private"),
                      (255, "", "Connection reset by private"),
                      (0, "", ""), (0, f"DESKTOP_SHUTDOWN_REQUESTED {NEXT_BOOT}", "")):
            with self.subTest(reply=reply):
                self.service = DesktopService()
                self.service._ssh = AsyncMock(side_effect=[self.ready(), reply, self.ready()])
                self.assertEqual(await self.service.shutdown(), "UNKNOWN")
                self.assertEqual(await self.service.shutdown(), "ALREADY_REQUESTED")
                commands = [call.args[1] for call in self.service._ssh.await_args_list]
                self.assertEqual(commands.count(f"desktop-off {BOOT}"), 1)

    async def test_explicit_windows_rejection_can_be_retried(self):
        self.service._ssh = AsyncMock(side_effect=[
            self.ready(), (1, f"DESKTOP_SHUTDOWN_REJECTED {BOOT}", ""),
            self.ready(), (0, f"DESKTOP_SHUTDOWN_REQUESTED {BOOT}", ""),
        ])
        self.assertEqual(await self.service.shutdown(), "REJECTED")
        self.assertEqual(await self.service.shutdown(), "REQUESTED")

    async def test_rejection_diagnostics_distinguish_privilege_boot_and_windows_state(self):
        for error, expected, pending in (
            ("DESKTOP_WINDOWS_ERROR 1314", "SHUTDOWN_PRIVILEGE_MISSING", False),
            ("DESKTOP_WINDOWS_ERROR 5", "SHUTDOWN_ACCESS_DENIED", False),
            ("Native localized error\r\nDESKTOP_WINDOWS_ERROR 5\r\n#< CLIXML\n<Objs/>", "SHUTDOWN_ACCESS_DENIED", False),
            ("DESKTOP_WINDOWS_ERROR 1115", "WINDOWS_SHUTTING_DOWN", True),
            ("DESKTOP_BOOT_CHANGED", "BOOT_CHANGED", False),
            ("#< CLIXML\n<Objs/>\nDESKTOP_BOOT_CHANGED\n", "BOOT_CHANGED", False),
            ("DESKTOP_WINDOWS_ERROR 87", "REJECTED", False),
            ("private-error", "REJECTED", False),
        ):
            with self.subTest(error=error):
                service = DesktopService()
                service._ssh = AsyncMock(side_effect=[self.ready(), (1, f"DESKTOP_SHUTDOWN_REJECTED {BOOT}", error)])
                self.assertEqual(await service.shutdown(), expected)
                self.assertEqual(service._requested_boot, BOOT if pending else None)

    async def test_bad_probe_and_preconnection_failures_never_send_shutdown(self):
        cases = [
            ((255, "", "Host key verification failed."), "HOST_KEY_ERROR"),
            ((255, "", "Permission denied (publickey)."), "AUTH_ERROR"),
            ((255, "", "ssh: connect to host private port 22: Connection refused"), "CONNECTION_FAILED"),
            ((255, "", "Connection reset by private"), "CHECK_FAILED"),
            ((0, "unexpected output", ""), "CHECK_FAILED"),
            ((1, f"DESKTOP_READY {BOOT}", ""), "CHECK_FAILED"),
            (FileNotFoundError("private"), "SSH_MISSING"),
            (asyncio.TimeoutError(), "CONNECTION_FAILED"),
        ]
        for reply, expected in cases:
            with self.subTest(expected=expected):
                self.service._ssh = AsyncMock(side_effect=[reply])
                self.assertEqual(await self.service.shutdown(), expected)
                self.service._ssh.assert_awaited_once_with(self.settings, "desktop-check")
                self.assertIsNone(self.service._requested_boot)

    async def test_missing_configuration_does_not_start_ssh(self):
        self.service._ssh = AsyncMock()
        with patch("extensions.desktop.service.DesktopSettings.from_environment", side_effect=DesktopSettingsError("private")):
            self.assertEqual(await self.service.shutdown(), "CONFIG_ERROR")
        self.service._ssh.assert_not_awaited()

    async def test_concurrent_requests_are_rejected_without_queuing(self):
        self.service._ssh = AsyncMock()
        async with self.service._lock:
            self.assertEqual(await self.service.shutdown(), "BUSY")
            self.assertEqual(await self.service.check(), "BUSY")
        self.service._ssh.assert_not_awaited()

    async def test_cancelled_dispatch_is_not_repeated(self):
        self.service._ssh = AsyncMock(side_effect=[self.ready(), asyncio.CancelledError(), self.ready()])
        with self.assertRaises(asyncio.CancelledError):
            await self.service.shutdown()
        self.assertEqual(await self.service.shutdown(), "ALREADY_REQUESTED")

    async def test_ssh_enforces_host_verification_and_uses_no_local_shell(self):
        process = Mock(returncode=0, communicate=AsyncMock(return_value=(b"ok", b"")))
        with patch("extensions.desktop.service.asyncio.create_subprocess_exec", AsyncMock(return_value=process)) as spawn:
            await self.service._ssh(self.settings, "desktop-check")
        arguments = spawn.call_args.args
        for option in ("StrictHostKeyChecking=yes", "BatchMode=yes", "IdentitiesOnly=yes",
                       "PasswordAuthentication=no", "IdentityAgent=none", "ConnectionAttempts=1",
                       'UserKnownHostsFile="/known hosts"'):
            self.assertIn(option, arguments)
        self.assertEqual(arguments[:4], ("ssh", "-F", "none", "-T"))
        self.assertEqual(arguments[-2:], (self.settings.host, "desktop-check"))
        self.assertNotIn("shell", spawn.call_args.kwargs)

    async def test_ssh_timeout_and_cancellation_reap_the_client(self):
        for failure in (asyncio.TimeoutError(), asyncio.CancelledError()):
            process = Mock(returncode=None, communicate=AsyncMock(side_effect=[failure, (b"", b"")]))
            with patch("extensions.desktop.service.asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
                with self.assertRaises(type(failure)):
                    await self.service._ssh(self.settings, "desktop-check")
            process.kill.assert_called_once()
            self.assertEqual(process.communicate.await_count, 2)


class DesktopCommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.cog = SystemCog()
        self.cog.desktop_service.shutdown = AsyncMock(return_value="REQUESTED")
        self.interaction = Mock(guild_id=123)
        self.interaction.user.id = 1
        self.interaction.response.send_message = AsyncMock()
        self.interaction.response.defer = AsyncMock()
        self.interaction.followup.send = AsyncMock()
        self.interaction.client.permission_manager.has_capability.return_value = True

    async def test_confirmation_defaults_to_no_execution(self):
        await SystemCog.desktop_off.callback(self.cog, self.interaction)
        self.cog.desktop_service.shutdown.assert_not_awaited()
        self.assertTrue(self.interaction.response.send_message.await_args.kwargs["ephemeral"])

    async def test_results_are_private_and_never_claim_power_is_off(self):
        for result in DESKTOP_OFF_MESSAGES:
            self.cog.desktop_service.shutdown.return_value = result
            await SystemCog.desktop_off.callback(self.cog, self.interaction, confirm=True)
            self.assertTrue(self.interaction.response.defer.await_args.kwargs["ephemeral"])
            message = self.interaction.followup.send.await_args.args[0]
            self.assertEqual(message, DESKTOP_OFF_MESSAGES[result])
            self.assertNotIn("종료되었습니다", message)
            self.assertTrue(self.interaction.followup.send.await_args.kwargs["ephemeral"])

    async def test_unexpected_exception_does_not_expose_connection_details(self):
        self.cog.desktop_service.shutdown.side_effect = RuntimeError("private-ip-and-key-path")
        await SystemCog.desktop_off.callback(self.cog, self.interaction, confirm=True)
        self.assertEqual(self.interaction.followup.send.await_args.args[0], DESKTOP_OFF_MESSAGES["UNKNOWN"])

    async def test_permissions_allow_managers_but_not_desktop_power_or_wrong_guild(self):
        store = PermissionStore(":memory:")
        self.addCleanup(store.close)
        manager = PermissionManager(AccessSettings(
            guild_ids=frozenset({123}), owner_ids=frozenset({1}), database_path=":memory:",
        ), store)
        for capability, role in ((ADMIN, 10), (MANAGER, 20), (DESKTOP_POWER, 30)):
            store.set_role_id(123, capability, role)
        for user, guild, allowed in (
            (SimpleNamespace(id=1, roles=[]), 123, True),
            (SimpleNamespace(id=2, roles=[SimpleNamespace(id=10)]), 123, True),
            (SimpleNamespace(id=2, roles=[SimpleNamespace(id=20)]), 123, True),
            (SimpleNamespace(id=2, roles=[SimpleNamespace(id=30)]), 123, False),
            (SimpleNamespace(id=2, roles=[]), 123, False),
            (SimpleNamespace(id=1, roles=[]), 999, False),
            (SimpleNamespace(id=1, roles=[]), None, False),
        ):
            with self.subTest(user=user, guild=guild):
                self.cog.desktop_service.shutdown.reset_mock()
                self.interaction.client.permission_manager = manager
                self.interaction.user, self.interaction.guild_id = user, guild
                await SystemCog.desktop_off.callback(self.cog, self.interaction, confirm=True)
                self.assertEqual(self.cog.desktop_service.shutdown.await_count, int(allowed))
        self.interaction.client = SimpleNamespace()
        self.cog.desktop_service.shutdown.reset_mock()
        await SystemCog.desktop_off.callback(self.cog, self.interaction, confirm=True)
        self.cog.desktop_service.shutdown.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
