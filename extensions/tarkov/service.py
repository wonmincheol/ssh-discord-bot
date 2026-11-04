"""Control the local mini PC's existing tmux session without killing it."""

import asyncio
import os

from .settings import TarkovSettings


class TarkovService:
    def __init__(self, settings: TarkovSettings) -> None:
        self.settings = settings
        self._lock = asyncio.Lock()
        self._stop_requested = False

    async def _tmux(self, *args: str) -> tuple[int, str, str]:
        command = ["/usr/bin/tmux", *args]
        if self.settings.user:
            command = ["sudo", "-n", "-H", "-u", self.settings.user, *command]
        environment = dict(os.environ, LC_ALL="C")
        # Always use the user's default socket, even if the bot was launched
        # from inside a different tmux server.
        environment.pop("TMUX", None)
        environment.pop("TMUX_TMPDIR", None)
        process = await asyncio.create_subprocess_exec(
            *command, env=environment,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), self.settings.command_timeout,
            )
        except (asyncio.TimeoutError, asyncio.CancelledError):
            if process.returncode is None:
                process.kill()
            await process.communicate()
            raise
        return process.returncode, stdout.decode(errors="replace").strip(), stderr.decode(errors="replace").strip()

    async def _exists(self) -> bool:
        code, _, error = await self._tmux("has-session", "-t", "=tarkov")
        if code == 0:
            return True
        # A sudo/socket permission failure must never be mistaken for a stopped
        # server. Only known tmux absence messages are accepted.
        absent = (
            error in {"can't find session: tarkov", "can't find session: =tarkov"}
            or error.startswith("no server running on ")
            or (error.startswith("error connecting to ") and error.endswith("(No such file or directory)"))
        )
        if code == 1 and absent:
            self._stop_requested = False
            return False
        raise RuntimeError(f"tmux status failed ({code}): {error}")

    async def status(self) -> str:
        if not await self._exists():
            return "STOPPED"
        return "STOPPING" if self._stop_requested else "RUNNING"

    async def start(self) -> str:
        if self._lock.locked():
            return "BUSY"
        async with self._lock:
            if await self._exists():
                return "STOPPING" if self._stop_requested else "ALREADY_RUNNING"
            code, _, error = await self._tmux(
                "new-session", "-d", "-s", "tarkov", "-c", "/data/tarkov",
                "/data/tarkov/start-server.sh",
            )
            if code != 0:
                raise RuntimeError(f"tmux start failed ({code}): {error}")
            # This detects immediate exits, not game readiness.
            await asyncio.sleep(1)
            if not await self._exists():
                raise RuntimeError("Tarkov exited immediately after launch")
            return "STARTED"

    async def stop(self) -> str:
        if self._lock.locked():
            return "BUSY"
        async with self._lock:
            if not await self._exists():
                return "ALREADY_STOPPED"
            if not self._stop_requested:
                code, panes, error = await self._tmux(
                    "list-panes", "-s", "-t", "=tarkov", "-F", "#{pane_dead}",
                )
                if code != 0 or panes != "0":
                    raise RuntimeError(f"Expected one live Tarkov pane: {panes}; {error}")
                # Mark before sending: if the client times out, delivery may
                # have succeeded. Never repeat Ctrl+C during a pending shutdown.
                self._stop_requested = True
                # send-keys takes a pane target, so the session needs a colon.
                code, _, error = await self._tmux("send-keys", "-t", "=tarkov:", "C-c")
                if code != 0:
                    # An explicit failure did not deliver the interrupt. Allow
                    # retry after fixing the target or sudo permissions.
                    self._stop_requested = False
                    raise RuntimeError(f"tmux stop failed ({code}): {error}")
            deadline = asyncio.get_running_loop().time() + self.settings.stop_timeout
            while await self._exists():
                if asyncio.get_running_loop().time() >= deadline:
                    return "STOP_TIMEOUT"
                await asyncio.sleep(self.settings.poll_interval)
            return "STOPPED"
