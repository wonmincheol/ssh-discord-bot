"""Issue fixed commands with pinned host keys and no automatic shutdown retry."""

import asyncio
import logging
import os
import re

from .settings import DesktopSettings, DesktopSettingsError


logger = logging.getLogger(__name__)
_READY = re.compile(r"DESKTOP_READY ([0-9]{10,20})")


class DesktopService:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._requested_boot: str | None = None

    async def _ssh(self, settings: DesktopSettings, command: str) -> tuple[int, str, str]:
        # Ignore user/system SSH config, agents, multiplexed sessions and proxies.
        # A configured key and known_hosts file are the only trust sources.
        process = await asyncio.create_subprocess_exec(
            "ssh", "-F", "none", "-T", "-n",
            "-o", "BatchMode=yes",
            "-o", "IdentitiesOnly=yes",
            "-o", "IdentityAgent=none",
            "-o", "PreferredAuthentications=publickey",
            "-o", "PasswordAuthentication=no",
            "-o", "StrictHostKeyChecking=yes",
            "-o", f'UserKnownHostsFile="{settings.known_hosts_file.as_posix()}"',
            "-o", "GlobalKnownHostsFile=none",
            "-o", "UpdateHostKeys=no",
            "-o", "ConnectionAttempts=1",
            "-o", "ConnectTimeout=5",
            "-o", "ServerAliveInterval=5",
            "-o", "ServerAliveCountMax=1",
            "-o", "ForwardAgent=no",
            "-o", "ClearAllForwardings=yes",
            "-i", str(settings.identity_file),
            "-p", str(settings.port), "-l", settings.user,
            settings.host, command,
            env=dict(os.environ, LC_ALL="C"),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), settings.command_timeout,
            )
        except (asyncio.TimeoutError, asyncio.CancelledError):
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
            await process.communicate()
            raise
        return (
            process.returncode,
            stdout.decode(errors="replace").strip(),
            stderr.decode(errors="replace").strip(),
        )

    @staticmethod
    def _connection_error(code: int, error: str) -> str | None:
        if code != 255:
            return None
        error = error.lower()
        if any(text in error for text in (
            "host key verification failed", "remote host identification has changed",
            "host key is known", "offending ",
        )):
            return "HOST_KEY_ERROR"
        if any(text in error for text in (
            "permission denied (", "no supported authentication methods available",
            "sign_and_send_pubkey: signing failed", "load key ",
        )):
            return "AUTH_ERROR"
        if any(text in error for text in (
            "could not resolve hostname", "connect to host ", "no route to host",
        )):
            return "CONNECTION_FAILED"
        # A reset/EOF may occur after delivery. Never classify it as powered off.
        return None

    async def _probe(self, settings: DesktopSettings) -> tuple[str, str | None]:
        code, output, error = await self._ssh(settings, "desktop-check")
        match = _READY.fullmatch(output)
        if code == 0 and match:
            return "READY", match[1]
        return self._connection_error(code, error) or "CHECK_FAILED", None

    async def _execute(self, *, shutdown: bool) -> str:
        if self._lock.locked():
            return "BUSY"
        async with self._lock:
            try:
                settings = DesktopSettings.from_environment()
            except (DesktopSettingsError, OSError, RuntimeError):
                return "CONFIG_ERROR"
            try:
                status, boot = await self._probe(settings)
            except FileNotFoundError:
                return "SSH_MISSING"
            except asyncio.TimeoutError:
                return "CONNECTION_FAILED"
            except OSError:
                return "CONNECTION_FAILED"
            if status != "READY" or not shutdown:
                return status
            if boot == self._requested_boot:
                return "ALREADY_REQUESTED"

            # If the reply is lost, repeating the request is unsafe. A new
            # Windows boot ID permits control again after the desktop restarts.
            self._requested_boot = boot
            try:
                code, output, error = await self._ssh(settings, f"desktop-off {boot}")
            except FileNotFoundError:
                self._requested_boot = None
                return "SSH_MISSING"
            except asyncio.TimeoutError:
                return "UNKNOWN"
            except OSError:
                return "UNKNOWN"
            if code == 0 and output == f"DESKTOP_SHUTDOWN_REQUESTED {boot}":
                return "REQUESTED"
            if code == 1 and output == f"DESKTOP_SHUTDOWN_REJECTED {boot}":
                if re.search(r"\bDESKTOP_BOOT_CHANGED\b", error):
                    self._requested_boot = None
                    return "BOOT_CHANGED"
                windows_error = re.search(r"\bDESKTOP_WINDOWS_ERROR (-?[0-9]{1,10})(?![0-9])", error)
                if windows_error:
                    error_code = int(windows_error[1])
                    logger.warning("Windows rejected desktop shutdown with error %d", error_code)
                    if error_code == 1115:
                        return "WINDOWS_SHUTTING_DOWN"
                    self._requested_boot = None
                    if error_code == 1314:
                        return "SHUTDOWN_PRIVILEGE_MISSING"
                    if error_code == 5:
                        return "SHUTDOWN_ACCESS_DENIED"
                self._requested_boot = None
                return "REJECTED"
            failure = self._connection_error(code, error)
            if failure is not None:
                self._requested_boot = None
                return failure
            return "UNKNOWN"

    async def check(self) -> str:
        """Check SSH and the restricted dispatcher without sending shutdown."""
        result = await self._execute(shutdown=False)
        logger.info("Desktop connection check result: %s", result)
        return result

    async def shutdown(self) -> str:
        result = await self._execute(shutdown=True)
        logger.info("Desktop shutdown request result: %s", result)
        return result
