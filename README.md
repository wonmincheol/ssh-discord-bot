# 🎮 Palworld Server Control Discord Bot

A Discord bot for managing a **Palworld Dedicated Server** running on **Ubuntu Server**.

This project allows users to **start, stop, monitor, and manage** a self-hosted Palworld server directly from Discord without SSH access.

Designed for personal or small-group servers running on a Linux mini PC.

---

## ✨ Features

The bot uses the prefix `!`.

| Command    | Description                                                                          |
| ---------- | ------------------------------------------------------------------------------------ |
| `!ping`    | Test whether the Discord bot is online.                                              |
| `!who`     | Display the Linux account that the bot is currently running as (`whoami`).           |
| `!status`  | Check whether the Palworld server is currently running.                              |
| `!start`   | Start the Palworld server. If already running, duplicate execution is prevented.     |
| `!stop`    | Safely stop the Palworld server.                                                     |
| `!players` | Display the current online player list and player count using the Palworld REST API. |

---

## 🚀 Auto Shutdown

To reduce unnecessary power consumption, the bot can automatically stop the server when nobody is playing.

When the server starts:

- `auto_shutdown.py` starts automatically in the background.
- The bot periodically checks the online player list.
- If no players are connected for the configured amount of time, the server is safely shut down.
- The monitoring interval and timeout are configurable in `config.py`.

---

## 📁 Project Structure

```
discord-bot/
├── bot.py
├── auto_shutdown.py
├── config.py
├── requirements.txt
├── README.md
└── server-control/
    ├── start-palworld.sh
    ├── stop-palworld.sh
    └── status-palworld.sh
```

---

## ⚙️ Configuration

Edit **config.py** before running the bot.

```python
from datetime import timedelta

# =========================
# Discord
# =========================
DISCORD_TOKEN = "YOUR_DISCORD_BOT_TOKEN"

# =========================
# Palworld REST API
# =========================
PALWORLD_API_URL = "http://127.0.0.1:8212"
PALWORLD_API_USER = "admin"
PALWORLD_API_PASSWORD = "YOUR_ADMIN_PASSWORD"

# =========================
# Server Control Scripts
# =========================
SCRIPT_PATH = "/data/discord-bot/server-control"

START_SCRIPT = f"{SCRIPT_PATH}/start-palworld.sh"
STOP_SCRIPT = f"{SCRIPT_PATH}/stop-palworld.sh"
STATUS_SCRIPT = f"{SCRIPT_PATH}/status-palworld.sh"

# =========================
# Auto Shutdown
# =========================
AUTO_SHUTDOWN_ENABLED = True

# Shutdown timeout when no players are online
AUTO_SHUTDOWN_TIME = timedelta(hours=1)

# Player check interval (seconds)
CHECK_INTERVAL = 60
```

### Configuration Variables

| Variable                | Description                          |
| ----------------------- | ------------------------------------ |
| `DISCORD_TOKEN`         | Discord Bot Token                    |
| `PALWORLD_API_URL`      | Palworld REST API URL                |
| `PALWORLD_API_USER`     | REST API Username                    |
| `PALWORLD_API_PASSWORD` | REST API Password                    |
| `START_SCRIPT`          | Server start script                  |
| `STOP_SCRIPT`           | Server stop script                   |
| `STATUS_SCRIPT`         | Server status script                 |
| `AUTO_SHUTDOWN_ENABLED` | Enable or disable automatic shutdown |
| `AUTO_SHUTDOWN_TIME`    | Time before automatic shutdown       |
| `CHECK_INTERVAL`        | Player check interval                |

---

## 📋 Prerequisites

- Ubuntu Server
- Python 3.8+
- Palworld Dedicated Server
- Palworld REST API enabled
- Discord Bot Token

---

## 📦 Installation

Clone the repository.

```bash
git clone https://github.com/wonmincheol/ssh-discord-bot

```

Install the required packages.

```bash
pip install -r requirements.txt
```

If you don't have a requirements file yet, install manually.

```bash
pip install discord.py requests
```

---

## 🔐 Sudo Configuration

The bot executes shell scripts using `sudo`.

Grant passwordless permission for the required scripts.

Open sudoers.

```bash
sudo visudo
```

Example:

```text
discordbot ALL=(ALL) NOPASSWD: /data/discord-bot/server-control/start-palworld.sh
discordbot ALL=(ALL) NOPASSWD: /data/discord-bot/server-control/stop-palworld.sh
discordbot ALL=(ALL) NOPASSWD: /data/discord-bot/server-control/status-palworld.sh
```

Replace `discordbot` with the Linux user that actually runs the bot.

---

## ▶️ Running the Bot

Run normally.

```bash
python bot.py
```

---

## 🔧 Palworld Server Requirements

This bot uses the **Palworld REST API**.

The server must be configured with:

- REST API enabled
- Admin password configured
- REST API port open (default: `8212`)

---

## 📷 Example

```text
!status

✅ Palworld Server is Running
```

```text
!players

👥 Players Online (3)

- Alice
- Bob
- Charlie
```

```text
!start

🚀 Starting Palworld Server...
```

```text
!stop

🛑 Stopping Palworld Server...
```

---

## 💡 Future Plans

- Discord Slash Commands
- Server restart command
- Automatic server update
- Scheduled server start
- Rich Embed UI
- Server performance monitoring (CPU / Memory)
- Discord permission management
- Multi-server support

---

## 📄 License

This project is released under the MIT License.

Feel free to use and modify it for your own server.

---

# 🎮 Palworld Server Control Discord Bot

Ubuntu Server에서 실행 중인 **Palworld Dedicated Server**를 Discord를 통해 제어할 수 있는 디스코드 봇입니다.

SSH에 직접 접속하지 않아도 Discord 명령어만으로 서버를 시작, 종료, 상태 확인 및 접속 플레이어 조회가 가능합니다.

개인 미니 PC 환경에서 여러 명이 함께 사용하는 펠월드 서버를 보다 편리하게 관리하기 위해 제작되었습니다.

---

# ✨ 주요 기능

봇의 Prefix는 `!`를 사용합니다.

| 명령어     | 설명                                                                   |
| ---------- | ---------------------------------------------------------------------- |
| `!ping`    | 봇이 정상적으로 동작하는지 확인합니다.                                 |
| `!who`     | 현재 봇이 어떤 Linux 계정으로 실행되고 있는지 확인합니다. (`whoami`)   |
| `!status`  | 현재 펠월드 서버의 실행 여부를 확인합니다.                             |
| `!start`   | 펠월드 서버를 시작합니다. 이미 실행 중인 경우 중복 실행되지 않습니다.  |
| `!stop`    | 펠월드 서버를 안전하게 종료합니다.                                     |
| `!players` | 현재 접속 중인 플레이어 목록과 총 인원수를 조회합니다. (REST API 사용) |

---

# 🚀 자동 종료(Auto Shutdown)

불필요한 서버 구동 시간을 줄이기 위해 자동 종료 기능을 제공합니다.

서버가 시작되면

- `auto_shutdown.py`가 자동으로 백그라운드에서 실행됩니다.
- 일정 주기마다 접속 중인 플레이어를 확인합니다.
- 설정된 시간 동안 플레이어가 한 명도 접속하지 않으면 서버를 자동으로 종료합니다.
- 종료 시간 및 확인 주기는 `config.py`에서 자유롭게 변경할 수 있습니다.

---

# 📁 프로젝트 구조

```text
discord-bot/
├── bot.py
├── auto_shutdown.py
├── config.py
├── requirements.txt
├── README.md
└── server-control/
    ├── start-palworld.sh
    ├── stop-palworld.sh
    └── status-palworld.sh
```

---

# ⚙️ 설정 방법

실행 전에 `config.py`를 자신의 환경에 맞게 수정해야 합니다.

```python
from datetime import timedelta

# =========================
# Discord 설정
# =========================
DISCORD_TOKEN = "YOUR_DISCORD_BOT_TOKEN"

# =========================
# Palworld REST API
# =========================
PALWORLD_API_URL = "http://127.0.0.1:8212"
PALWORLD_API_USER = "admin"
PALWORLD_API_PASSWORD = "YOUR_ADMIN_PASSWORD"

# =========================
# 서버 제어 스크립트
# =========================
SCRIPT_PATH = "/data/discord-bot/server-control"

START_SCRIPT = f"{SCRIPT_PATH}/start-palworld.sh"
STOP_SCRIPT = f"{SCRIPT_PATH}/stop-palworld.sh"
STATUS_SCRIPT = f"{SCRIPT_PATH}/status-palworld.sh"

# =========================
# 자동 종료 설정
# =========================
AUTO_SHUTDOWN_ENABLED = True

# 플레이어가 없을 경우 자동 종료까지 대기 시간
AUTO_SHUTDOWN_TIME = timedelta(hours=1)

# 플레이어 확인 주기 (초)
CHECK_INTERVAL = 60
```

## 설정 변수

| 변수                    | 설명                     |
| ----------------------- | ------------------------ |
| `DISCORD_TOKEN`         | Discord Bot Token        |
| `PALWORLD_API_URL`      | Palworld REST API 주소   |
| `PALWORLD_API_USER`     | REST API 관리자 계정     |
| `PALWORLD_API_PASSWORD` | REST API 비밀번호        |
| `START_SCRIPT`          | 서버 시작 스크립트       |
| `STOP_SCRIPT`           | 서버 종료 스크립트       |
| `STATUS_SCRIPT`         | 서버 상태 확인 스크립트  |
| `AUTO_SHUTDOWN_ENABLED` | 자동 종료 기능 사용 여부 |
| `AUTO_SHUTDOWN_TIME`    | 자동 종료까지 대기 시간  |
| `CHECK_INTERVAL`        | 플레이어 확인 주기       |

---

# 📋 요구 사항

- Ubuntu Server
- Python 3.8 이상
- Palworld Dedicated Server
- Palworld REST API 활성화
- Discord Bot Token

---

# 📦 설치 방법

프로젝트를 내려받습니다.

```bash
git clone https://github.com/wonmincheol/ssh-discord-bot
```

필요한 라이브러리를 설치합니다.

```bash
pip install -r requirements.txt
```

requirements.txt가 없다면

```bash
pip install discord.py requests
```

를 실행하면 됩니다.

---

# 🔐 sudo 권한 설정

봇은 서버 제어를 위해 `sudo`를 통해 쉘 스크립트를 실행합니다.

비밀번호 입력 없이 실행할 수 있도록 sudo 권한을 부여해야 합니다.

```bash
sudo visudo
```

예시

```text
discordbot ALL=(ALL) NOPASSWD: /data/discord-bot/server-control/start-palworld.sh
discordbot ALL=(ALL) NOPASSWD: /data/discord-bot/server-control/stop-palworld.sh
discordbot ALL=(ALL) NOPASSWD: /data/discord-bot/server-control/status-palworld.sh
```

※ `discordbot`은 실제 봇을 실행하는 Linux 계정명으로 변경하세요.

---

# ▶️ 실행 방법

```bash
python bot.py
```

---

# 🔧 Palworld 서버 설정

이 프로젝트는 **Palworld REST API**를 이용합니다.

서버에서 다음 항목이 활성화되어 있어야 합니다.

- REST API 활성화
- 관리자(Admin) 비밀번호 설정
- REST API 포트 개방 (기본 8212)

---

# 📷 실행 예시

```text
!status

✅ Palworld 서버가 실행 중입니다.
```

```text
!players

👥 현재 접속자 (3명)

- Alice
- Bob
- Charlie
```

```text
!start

🚀 Starting Palworld server
```

```text
!stop

🛑 Shut down the palworld server
```

---

# 💡 앞으로 추가 예정인 기능

- Slash Command 지원
- 서버 재시작 명령어
- 서버 자동 업데이트
- 예약 실행 기능
- Discord Embed UI 개선
- CPU / 메모리 사용량 조회
- Discord 권한 관리
- 다중 서버 지원

---

# 📄 License

MIT License

개인 또는 소규모 서버에서 자유롭게 사용 및 수정할 수 있습니다.
