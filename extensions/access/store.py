"""Small SQLite store for guild capability-to-role mappings."""

from pathlib import Path
import sqlite3


class PermissionStore:
    def __init__(self, database_path: str) -> None:
        if database_path == ":memory:":
            self.database_path = database_path
        else:
            path = Path(database_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self.database_path = str(path)
        self._connection = sqlite3.connect(self.database_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return self._connection

    def close(self) -> None:
        self._connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS permission_roles (
                    guild_id INTEGER NOT NULL,
                    capability TEXT NOT NULL,
                    role_id INTEGER NOT NULL,
                    PRIMARY KEY (guild_id, capability)
                )
                """
            )

    def get_role_id(self, guild_id: int, capability: str) -> int | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT role_id
                FROM permission_roles
                WHERE guild_id = ? AND capability = ?
                """,
                (guild_id, capability),
            ).fetchone()
        return int(row[0]) if row else None

    def set_role_id(self, guild_id: int, capability: str, role_id: int) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO permission_roles (guild_id, capability, role_id)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id, capability)
                DO UPDATE SET role_id = excluded.role_id
                """,
                (guild_id, capability, role_id),
            )
