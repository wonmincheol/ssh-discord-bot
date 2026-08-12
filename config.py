# =========================
# Discord
# =========================

DISCORD_TOKEN = "DISCORD_TOKEN"

# =========================
# Palworld REST API
# =========================

PALWORLD_API_URL = "http://127.0.0.1:8212"
PALWORLD_API_USER = "admin"
PALWORLD_API_PASSWORD = "PALWORLD_API_PASSWORD"

# =========================
# Server Control Scripts
# =========================

SCRIPT_PATH = "/data/ssh-discord-bot/server-control"

START_SCRIPT = f"{SCRIPT_PATH}/start-palworld.sh"
STOP_SCRIPT = f"{SCRIPT_PATH}/stop-palworld.sh"
STATUS_SCRIPT = f"{SCRIPT_PATH}/status-palworld.sh"

import datetime

# Auto Shutdown Settings
AUTO_SHUTDOWN_ENABLED = True

# Wait time to end if player is not present
AUTO_SHUTDOWN_TIME = datetime.timedelta(hours=1)
# AUTO_SHUTDOWN_TIME = datetime.timedelta(minutes=5)
# Whether to check the player every few seconds
CHECK_INTERVAL = 60
