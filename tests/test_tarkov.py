import asyncio
from dataclasses import replace
import os
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from tests.discord_stub import install_discord_stub

install_discord_stub()

from extensions.tarkov.cog import TarkovCog
from extensions.tarkov.service import TarkovService
from extensions.tarkov.settings import TarkovSettings


class TarkovServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = TarkovService(TarkovSettings(stop_timeout=0, poll_interval=0))

    async def test_only_known_absence_is_treated_as_stopped(self):
        for error in ["can't find session: =tarkov", "no server running on /tmp/tmux-1/default",
                      "error connecting to /tmp/tmux-1/default (No such file or directory)"]:
            self.service._tmux = AsyncMock(return_value=(1, "", error))
            self.assertEqual(await self.service.status(), "STOPPED")
        for error in ["sudo: a password is required", "error connecting to /tmp/tmux-1/default (Permission denied)"]:
            self.service._tmux = AsyncMock(return_value=(1, "", error))
            with self.assertRaises(RuntimeError):
                await self.service.start()
            self.service._tmux.assert_awaited_once()

    async def test_start_does_not_duplicate_existing_session(self):
        self.service._tmux = AsyncMock(return_value=(0, "", ""))
        self.assertEqual(await self.service.start(), "ALREADY_RUNNING")
        self.service._tmux.assert_awaited_once_with("has-session", "-t", "=tarkov")

    async def test_start_uses_server_directory_and_detects_immediate_exit(self):
        for alive in [True, False]:
            self.service._exists = AsyncMock(side_effect=[False, alive])
            self.service._tmux = AsyncMock(return_value=(0, "", ""))
            with patch("extensions.tarkov.service.asyncio.sleep", AsyncMock()):
                if alive:
                    self.assertEqual(await self.service.start(), "STARTED")
                else:
                    with self.assertRaises(RuntimeError):
                        await self.service.start()
            self.service._tmux.assert_awaited_once_with(
                "new-session", "-d", "-s", "tarkov", "-c", "/data/tarkov", "/data/tarkov/start-server.sh",
            )

    async def test_stop_waits_for_session_exit(self):
        self.service.settings = replace(self.service.settings, stop_timeout=1)
        self.service._tmux = AsyncMock(side_effect=[
            (0, "", ""), (0, "0", ""), (0, "", ""),
            (0, "", ""), (1, "", "can't find session: tarkov"),
        ])
        self.assertEqual(await self.service.stop(), "STOPPED")
        self.assertFalse(self.service._stop_requested)
        commands = [call.args for call in self.service._tmux.await_args_list]
        self.assertEqual(commands.count(("send-keys", "-t", "=tarkov:", "C-c")), 1)
        self.assertEqual(commands[-1], ("has-session", "-t", "=tarkov"))

    async def test_timeout_never_kills_or_resends_interrupt(self):
        async def tmux(*args):
            return (0, "0" if args[0] == "list-panes" else "", "")
        self.service._tmux = AsyncMock(side_effect=tmux)
        self.assertEqual(await self.service.stop(), "STOP_TIMEOUT")
        self.assertEqual(await self.service.stop(), "STOP_TIMEOUT")
        self.assertEqual(await self.service.start(), "STOPPING")
        commands = [call.args[0] for call in self.service._tmux.await_args_list]
        self.assertEqual(commands.count("send-keys"), 1)
        self.assertNotIn("kill-session", commands)
        self.assertNotIn("new-session", commands)

    async def test_rejected_interrupt_can_be_retried(self):
        self.service._tmux = AsyncMock(side_effect=[
            (0, "", ""), (0, "0", ""), (1, "", "can't find pane: =tarkov"),
            (0, "", ""), (0, "0", ""), (0, "", ""),
            (1, "", "can't find session: tarkov"),
        ])
        with self.assertRaises(RuntimeError):
            await self.service.stop()
        self.assertFalse(self.service._stop_requested)
        self.assertEqual(await self.service.stop(), "STOPPED")

    async def test_uncertain_interrupt_delivery_is_not_repeated(self):
        self.service._tmux = AsyncMock(side_effect=[
            (0, "", ""), (0, "0", ""), asyncio.TimeoutError,
            (0, "", ""), (0, "", ""),
        ])
        with self.assertRaises(asyncio.TimeoutError):
            await self.service.stop()
        self.assertTrue(self.service._stop_requested)
        self.assertEqual(await self.service.stop(), "STOP_TIMEOUT")
        commands = [call.args[0] for call in self.service._tmux.await_args_list]
        self.assertEqual(commands.count("send-keys"), 1)

    async def test_stopped_server_and_ambiguous_panes_are_not_interrupted(self):
        self.service._tmux = AsyncMock(return_value=(1, "", "can't find session: tarkov"))
        self.assertEqual(await self.service.stop(), "ALREADY_STOPPED")
        self.service._tmux.assert_awaited_once()
        for panes in ["0\n0", "1", ""]:
            self.service._tmux = AsyncMock(side_effect=[(0, "", ""), (0, panes, "")])
            with self.assertRaises(RuntimeError):
                await self.service.stop()
            self.assertEqual(self.service._tmux.await_count, 2)

    async def test_concurrent_operations_are_rejected(self):
        self.service._tmux = AsyncMock()
        async with self.service._lock:
            self.assertEqual(await self.service.start(), "BUSY")
            self.assertEqual(await self.service.stop(), "BUSY")
        self.service._tmux.assert_not_awaited()

    async def test_subprocess_uses_owner_and_default_socket(self):
        self.service.settings = replace(self.service.settings, user="gameowner")
        process = Mock(returncode=0)
        process.communicate = AsyncMock(return_value=(b"", b""))
        with patch.dict(os.environ, {"TMUX": "other-socket", "TMUX_TMPDIR": "/other"}), patch(
            "extensions.tarkov.service.asyncio.create_subprocess_exec", AsyncMock(return_value=process),
        ) as spawn:
            await self.service.status()
        self.assertEqual(spawn.call_args.args, (
            "sudo", "-n", "-H", "-u", "gameowner", "/usr/bin/tmux", "has-session", "-t", "=tarkov",
        ))
        self.assertNotIn("TMUX", spawn.call_args.kwargs["env"])
        self.assertNotIn("TMUX_TMPDIR", spawn.call_args.kwargs["env"])

    async def test_subprocess_timeout_reaps_client(self):
        process = Mock(returncode=None)
        process.communicate = AsyncMock(side_effect=[asyncio.TimeoutError, (b"", b"")])
        with patch("extensions.tarkov.service.asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
            with self.assertRaises(asyncio.TimeoutError):
                await self.service.status()
        process.kill.assert_called_once()
        self.assertEqual(process.communicate.await_count, 2)


class TarkovCogTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.cog = TarkovCog(Mock())
        self.cog.service = SimpleNamespace(start=AsyncMock(return_value="STARTED"), stop=AsyncMock(return_value="STOPPED"), status=AsyncMock(return_value="RUNNING"))
        self.interaction = Mock()
        self.interaction.response.send_message = AsyncMock()
        self.interaction.response.defer = AsyncMock()
        self.interaction.followup.send = AsyncMock()
        self.interaction.client.permission_manager.has_capability.return_value = True

    async def test_all_commands_fail_closed_without_permissions(self):
        for manager in [None, Mock(has_capability=Mock(return_value=False))]:
            self.interaction.client.permission_manager = manager
            for command in [TarkovCog.start, TarkovCog.stop, TarkovCog.status]:
                await command.callback(self.cog, self.interaction)
        for method in vars(self.cog.service).values():
            method.assert_not_awaited()
        self.interaction.response.defer.assert_not_awaited()

    async def test_stop_requires_finished_raids_acknowledgment(self):
        await TarkovCog.stop.callback(self.cog, self.interaction)
        self.cog.service.stop.assert_not_awaited()
        await TarkovCog.stop.callback(self.cog, self.interaction, everyone_finished=True)
        self.cog.service.stop.assert_awaited_once()

    async def test_start_defers_and_hides_private_errors(self):
        self.cog.service.start.side_effect = RuntimeError("private server path")
        with self.assertLogs("extensions.tarkov.cog", level="ERROR"):
            await TarkovCog.start.callback(self.cog, self.interaction)
        self.interaction.response.defer.assert_awaited_once()
        self.assertNotIn("private server path", self.interaction.followup.send.await_args.args[0])


class TarkovSettingsTests(unittest.TestCase):
    def test_timeout_is_bounded(self):
        for value in ["0", "601", "nan", "inf"]:
            with patch.dict(os.environ, {"TARKOV_STOP_TIMEOUT": value}):
                with self.assertRaises(ValueError):
                    TarkovSettings.from_environment()


if __name__ == "__main__":
    unittest.main()
