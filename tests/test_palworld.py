import os
import sys
from dataclasses import replace
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from tests.discord_stub import install_discord_stub

# The service is tested with a mocked HTTP boundary, so the tests do not need
# the optional runtime dependency to be installed in the test interpreter.
if "requests" not in sys.modules:
    requests_stub = ModuleType("requests")
    requests_stub.get = Mock()
    sys.modules["requests"] = requests_stub

install_discord_stub()

from extensions.palworld.cog import PalworldCog
from extensions.palworld.service import CommandResult, PalworldService
from extensions.palworld.settings import PalworldSettings
from extensions.tarkov.cog import TarkovCog
from extensions.access.service import ADMIN, MANAGER, DESKTOP_POWER, PermissionManager
from extensions.access.settings import AccessSettings
from extensions.access.store import PermissionStore


class GameCommandPermissionsTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_game_commands_use_shared_manager_permission(self):
        store = PermissionStore(":memory:")
        self.addCleanup(store.close)
        manager = PermissionManager(AccessSettings(
            guild_ids=frozenset({123}), owner_ids=frozenset({1}), database_path=":memory:",
        ), store)
        for capability, role_id in [(ADMIN, 10), (MANAGER, 20), (DESKTOP_POWER, 30)]:
            store.set_role_id(123, capability, role_id)
        for cog_type, actions in [(PalworldCog, ("start", "stop", "status", "players")),
                                  (TarkovCog, ("start", "stop", "status"))]:
            for user_id, role_ids, guild_id, allowed in [
                (2, [20], 123, True), (2, [10], 123, True), (1, [], 123, True),
                (2, [], 123, False), (2, [30], 123, False),
                (2, [20], 999, False), (2, [20], None, False),
            ]:
                for action in actions:
                    with self.subTest(cog=cog_type.__name__, action=action, roles=role_ids, guild=guild_id):
                        cog = object.__new__(cog_type)
                        if cog_type is PalworldCog:
                            result = [] if action == "players" else CommandResult(
                                0, "STARTED" if action == "start" else "STOPPED", "",
                            )
                        else:
                            result = "STOPPED"
                        operation = AsyncMock(return_value=result)
                        cog.service = SimpleNamespace(**{("get_players" if action == "players" else action): operation})
                        cog._cancel_auto_shutdown = AsyncMock()
                        cog._start_auto_shutdown = Mock()
                        interaction = SimpleNamespace(
                            client=SimpleNamespace(permission_manager=manager), guild_id=guild_id,
                            user=SimpleNamespace(id=user_id, roles=[SimpleNamespace(id=r) for r in role_ids]),
                            response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
                            followup=SimpleNamespace(send=AsyncMock()), channel_id=123,
                        )
                        kwargs = {"everyone_finished": True} if cog_type is TarkovCog and action == "stop" else {}
                        await getattr(cog_type, action).callback(cog, interaction, **kwargs)
                        self.assertEqual(operation.await_count, int(allowed))
                        if not allowed:
                            interaction.response.defer.assert_not_awaited()
                            cog._cancel_auto_shutdown.assert_not_awaited()

    async def test_palworld_fails_closed_when_access_extension_is_missing(self):
        cog = object.__new__(PalworldCog)
        interaction = SimpleNamespace(client=SimpleNamespace(), response=SimpleNamespace(send_message=AsyncMock()))
        for action in ("start", "stop", "status", "players"):
            await getattr(PalworldCog, action).callback(cog, interaction)
        self.assertEqual(interaction.response.send_message.await_count, 4)


class PalworldSettingsTests(unittest.TestCase):
    def test_feature_settings_are_loaded_from_environment(self) -> None:
        environment = {
            "PALWORLD_API_URL": "http://game-server:9000/",
            "PALWORLD_API_USER": "operator",
            "PALWORLD_API_PASSWORD": "secret",
            "PALWORLD_SCRIPT_PATH": "/srv/palworld-control/",
            "PALWORLD_AUTO_SHUTDOWN_ENABLED": "false",
            "PALWORLD_AUTO_SHUTDOWN_SECONDS": "120",
            "PALWORLD_CHECK_INTERVAL": "5",
            "PALWORLD_COMMAND_TIMEOUT": "12",
        }

        with patch.dict(os.environ, environment, clear=True):
            settings = PalworldSettings.from_environment()

        self.assertEqual(settings.api_url, "http://game-server:9000")
        self.assertEqual(settings.api_user, "operator")
        self.assertEqual(settings.start_script, "/srv/palworld-control/start.sh")
        self.assertFalse(settings.auto_shutdown_enabled)
        self.assertEqual(settings.auto_shutdown_after.total_seconds(), 120)
        self.assertEqual(settings.check_interval, 5)
        self.assertEqual(settings.command_timeout, 12)


class PalworldServiceTests(unittest.TestCase):
    def test_get_players_uses_extension_settings(self) -> None:
        settings = replace(
            PalworldSettings.from_environment(),
            api_password="test-password",
        )
        service = PalworldService(settings)
        response = Mock()
        response.json.return_value = {"players": [{"name": "Lamball"}]}

        with patch("extensions.palworld.service.requests.get", return_value=response) as get:
            players = service._get_players_sync()

        self.assertEqual(players, [{"name": "Lamball"}])
        response.raise_for_status.assert_called_once_with()
        get.assert_called_once_with(
            f"{settings.api_url}/v1/api/players",
            auth=(settings.api_user, settings.api_password),
            timeout=5,
        )

    def test_invalid_players_payload_is_rejected(self) -> None:
        settings = replace(
            PalworldSettings.from_environment(),
            api_password="test-password",
        )
        service = PalworldService(settings)
        response = Mock()
        response.json.return_value = {"players": "not-a-list"}

        with patch("extensions.palworld.service.requests.get", return_value=response):
            with self.assertRaises(ValueError):
                service._get_players_sync()

    def test_player_api_requires_a_password(self) -> None:
        settings = replace(PalworldSettings.from_environment(), api_password="")
        service = PalworldService(settings)

        with self.assertRaises(RuntimeError):
            service._get_players_sync()


class PalworldMessagePrivacyTests(unittest.TestCase):
    def test_command_failure_does_not_return_raw_output(self) -> None:
        private_error = "connection failed at 192.168.0.10 using /private/path"
        result = CommandResult(returncode=1, stdout="", stderr=private_error)

        message = PalworldCog._failure_message("Status check failed", result)

        self.assertIn("Status check failed", message)
        self.assertNotIn(private_error, message)
        self.assertNotIn("192.168.0.10", message)


if __name__ == "__main__":
    unittest.main()
