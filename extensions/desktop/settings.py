"""Optional desktop settings, validated only when desktop control is used."""

from dataclasses import dataclass
import ipaddress
import os
from pathlib import Path
import re


class DesktopSettingsError(ValueError):
    """Configuration errors contain setting names, never their values."""


@dataclass(frozen=True)
class DesktopSettings:
    host: str
    user: str
    identity_file: Path
    known_hosts_file: Path
    port: int = 22
    command_timeout: int = 15

    @classmethod
    def from_environment(cls) -> "DesktopSettings":
        def required(name: str) -> str:
            value = os.getenv(name, "").strip()
            if not value:
                raise DesktopSettingsError(f"{name} is required")
            return value

        host = required("DESKTOP_SSH_HOST")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if len(host) > 253 or not all(
                re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
                for label in host.split(".")
            ):
                raise DesktopSettingsError("DESKTOP_SSH_HOST is invalid") from None
        else:
            if address.is_unspecified or address.is_multicast or address.is_loopback:
                raise DesktopSettingsError("DESKTOP_SSH_HOST must identify the desktop")

        user = required("DESKTOP_SSH_USER")
        if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}", user):
            raise DesktopSettingsError("DESKTOP_SSH_USER must be a local account name")

        def file_path(name: str) -> Path:
            value = required(name)
            # OpenSSH expands some characters even without a shell.
            if any(character in value for character in '\r\n\x00"$%'):
                raise DesktopSettingsError(f"{name} contains unsupported characters")
            path = Path(value).expanduser()
            if not path.is_absolute() or not path.is_file():
                raise DesktopSettingsError(f"{name} must be an existing absolute file path")
            return path

        def integer(name: str, default: str, lower: int, upper: int) -> int:
            try:
                value = int(os.getenv(name, default))
            except ValueError:
                raise DesktopSettingsError(f"{name} must be an integer") from None
            if not lower <= value <= upper:
                raise DesktopSettingsError(f"{name} must be between {lower} and {upper}")
            return value

        return cls(
            host=host,
            user=user,
            identity_file=file_path("DESKTOP_SSH_IDENTITY_FILE"),
            known_hosts_file=file_path("DESKTOP_SSH_KNOWN_HOSTS_FILE"),
            port=integer("DESKTOP_SSH_PORT", "22", 1, 65535),
            command_timeout=integer("DESKTOP_SSH_TIMEOUT", "15", 5, 60),
        )
