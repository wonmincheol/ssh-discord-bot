import os
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch

# The service is tested with a mocked HTTP boundary, so the tests do not need
# the optional runtime dependency to be installed in the test interpreter.
if "requests" not in sys.modules:
    requests_stub = ModuleType("requests")
    requests_stub.get = Mock()
    sys.modules["requests"] = requests_stub

from extensions.palworld.service import PalworldService
from extensions.palworld.settings import PalworldSettings


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
        settings = PalworldSettings.from_environment()
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
        service = PalworldService(PalworldSettings.from_environment())
        response = Mock()
        response.json.return_value = {"players": "not-a-list"}

        with patch("extensions.palworld.service.requests.get", return_value=response):
            with self.assertRaises(ValueError):
                service._get_players_sync()


if __name__ == "__main__":
    unittest.main()
