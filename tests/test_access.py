import os
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from tests.discord_stub import install_discord_stub


install_discord_stub()

from extensions.access.cog import PermissionCog
from extensions.access.service import ADMIN, DESKTOP_POWER, PermissionManager
from extensions.access.settings import AccessSettings
from extensions.access.store import PermissionStore


class FakeGuild:
    def __init__(self, guild_id: int) -> None:
        self.id = guild_id
        self.roles = []
        self._next_role_id = 100

    async def create_role(self, *, name: str, reason: str):
        role = SimpleNamespace(
            id=self._next_role_id,
            name=name,
            mention=f"@{name}",
            reason=reason,
        )
        self._next_role_id += 1
        self.roles.append(role)
        return role


class AccessSettingsTests(unittest.TestCase):
    def test_settings_load_discord_ids(self) -> None:
        environment = {
            "BOT_GUILD_IDS": "123, 234",
            "BOT_OWNER_IDS": "456, 789",
            "BOT_PERMISSION_DB_PATH": "custom/permissions.sqlite3",
        }

        with patch.dict(os.environ, environment, clear=True):
            settings = AccessSettings.from_environment()

        self.assertEqual(settings.guild_ids, frozenset({123, 234}))
        self.assertEqual(settings.owner_ids, frozenset({456, 789}))
        self.assertEqual(settings.database_path, "custom/permissions.sqlite3")

    def test_settings_require_an_owner(self) -> None:
        with patch.dict(os.environ, {"BOT_GUILD_IDS": "123"}, clear=True):
            with self.assertRaises(RuntimeError):
                AccessSettings.from_environment()

    def test_legacy_single_guild_setting_is_supported(self) -> None:
        environment = {
            "BOT_GUILD_ID": "123",
            "BOT_OWNER_IDS": "456",
        }

        with patch.dict(os.environ, environment, clear=True):
            settings = AccessSettings.from_environment()

        self.assertEqual(settings.guild_ids, frozenset({123}))


class PermissionManagerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.settings = AccessSettings(
            guild_ids=frozenset({123, 234}),
            owner_ids=frozenset({1}),
            database_path=":memory:",
        )
        self.store = PermissionStore(":memory:")
        self.addCleanup(self.store.close)
        self.manager = PermissionManager(self.settings, self.store)

    async def test_setup_creates_and_persists_permission_roles(self) -> None:
        guild = FakeGuild(123)

        results = await self.manager.setup_roles(guild)

        self.assertEqual(len(results), 2)
        self.assertEqual(len(guild.roles), 2)
        self.assertEqual(self.store.get_role_id(123, ADMIN), 100)
        self.assertEqual(self.store.get_role_id(123, DESKTOP_POWER), 101)

        second_results = await self.manager.setup_roles(guild)
        self.assertEqual(len(guild.roles), 2)
        self.assertTrue(all("준비됨" in result for result in second_results))

    def test_environment_owner_has_every_capability(self) -> None:
        owner = SimpleNamespace(id=1, roles=[])

        self.assertTrue(self.manager.has_capability(owner, 123, ADMIN))
        self.assertTrue(self.manager.has_capability(owner, 123, DESKTOP_POWER))

    def test_admin_role_has_every_capability(self) -> None:
        self.store.set_role_id(123, ADMIN, 10)
        admin = SimpleNamespace(id=2, roles=[SimpleNamespace(id=10)])

        self.assertTrue(self.manager.has_capability(admin, 123, ADMIN))
        self.assertTrue(self.manager.has_capability(admin, 123, DESKTOP_POWER))

    def test_desktop_role_does_not_grant_admin(self) -> None:
        self.store.set_role_id(123, DESKTOP_POWER, 20)
        operator = SimpleNamespace(id=2, roles=[SimpleNamespace(id=20)])

        self.assertTrue(self.manager.has_capability(operator, 123, DESKTOP_POWER))
        self.assertFalse(self.manager.has_capability(operator, 123, ADMIN))

    def test_permissions_are_rejected_outside_configured_guild(self) -> None:
        owner = SimpleNamespace(id=1, roles=[])

        self.assertFalse(self.manager.has_capability(owner, 999, ADMIN))

    def test_permissions_are_allowed_in_second_configured_guild(self) -> None:
        owner = SimpleNamespace(id=1, roles=[])

        self.assertTrue(self.manager.has_capability(owner, 234, ADMIN))

    def test_role_permissions_are_independent_for_each_guild(self) -> None:
        self.store.set_role_id(123, ADMIN, 10)
        self.store.set_role_id(234, ADMIN, 20)
        first_guild_admin = SimpleNamespace(id=2, roles=[SimpleNamespace(id=10)])

        self.assertTrue(self.manager.has_capability(first_guild_admin, 123, ADMIN))
        self.assertFalse(self.manager.has_capability(first_guild_admin, 234, ADMIN))


class PermissionCogTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.cog = object.__new__(PermissionCog)
        self.cog.manager = Mock()
        self.cog.manager.is_configured_guild.return_value = True
        self.cog.manager.is_admin.return_value = True

        self.interaction = Mock()
        self.interaction.guild_id = 123
        self.interaction.user.id = 1
        self.interaction.response.defer = AsyncMock()
        self.interaction.response.send_message = AsyncMock()
        self.interaction.followup.send = AsyncMock()

    async def test_admin_can_grant_admin_to_another_user(self) -> None:
        admin_role = SimpleNamespace(id=10)
        target = Mock()
        target.id = 2
        target.mention = "@alt"
        target.add_roles = AsyncMock()
        self.cog.manager.role_for.return_value = admin_role

        await PermissionCog.grant.callback(
            self.cog,
            self.interaction,
            target,
            ADMIN,
        )

        target.add_roles.assert_awaited_once_with(
            admin_role,
            reason="Granted by Discord user 1",
        )
        self.interaction.response.defer.assert_awaited_once_with(
            thinking=True,
            ephemeral=True,
        )
        message = self.interaction.followup.send.await_args.args[0]
        self.assertIn("admin", message)
        self.assertIn("모든 봇 권한", message)

    async def test_environment_owner_admin_cannot_be_revoked(self) -> None:
        owner = Mock()
        owner.id = 1
        owner.remove_roles = AsyncMock()
        self.cog.manager.is_owner.return_value = True

        await PermissionCog.revoke.callback(
            self.cog,
            self.interaction,
            owner,
            ADMIN,
        )

        owner.remove_roles.assert_not_awaited()
        message = self.interaction.response.send_message.await_args.args[0]
        self.assertIn("회수할 수 없습니다", message)


if __name__ == "__main__":
    unittest.main()
