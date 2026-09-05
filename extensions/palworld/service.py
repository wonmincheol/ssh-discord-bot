"""Palworld process and REST API access without Discord dependencies."""

import asyncio
from dataclasses import dataclass

import requests

from .settings import PalworldSettings


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class PalworldService:
    def __init__(self, settings: PalworldSettings) -> None:
        self.settings = settings

    async def status(self) -> CommandResult:
        return await self._run_script(self.settings.status_script)

    async def start(self) -> CommandResult:
        return await self._run_script(self.settings.start_script)

    async def stop(self) -> CommandResult:
        return await self._run_script(self.settings.stop_script)

    async def get_players(self) -> list[dict]:
        return await asyncio.to_thread(self._get_players_sync)

    def _get_players_sync(self) -> list[dict]:
        if not self.settings.api_password:
            raise RuntimeError("PALWORLD_API_PASSWORD is not configured")

        response = requests.get(
            f"{self.settings.api_url}/v1/api/players",
            auth=(self.settings.api_user, self.settings.api_password),
            timeout=5,
        )
        response.raise_for_status()
        players = response.json().get("players", [])
        if not isinstance(players, list):
            raise ValueError("Palworld API returned an invalid players value")
        return players

    async def _run_script(self, script: str) -> CommandResult:
        process = await asyncio.create_subprocess_exec(
            "sudo",
            "/bin/bash",
            script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.settings.command_timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            raise RuntimeError(
                f"Server control command timed out after "
                f"{self.settings.command_timeout:g} seconds"
            )

        return CommandResult(
            returncode=process.returncode or 0,
            stdout=stdout.decode(errors="replace").strip(),
            stderr=stderr.decode(errors="replace").strip(),
        )
