# Mini PC Remote Control Discord Bot

Discord 슬래시 명령으로 개인 미니 PC를 원격 관리하는 봇입니다. Palworld 지원은
코어와 분리된 선택형 확장 모듈로 제공됩니다.

## Discord 명령어

공통 명령:

| 명령 | 설명 |
| --- | --- |
| `/ping` | 봇 응답 확인 |
| `/who` | 봇 실행 계정 확인 |
| `/desktop_on` | Wake on LAN 패킷 전송 |

Palworld 확장을 활성화했을 때:

| 명령 | 설명 |
| --- | --- |
| `/palworld status` | 서버 상태 확인 |
| `/palworld start` | 서버 시작 및 자동 종료 감시 시작 |
| `/palworld stop` | 서버 종료 및 자동 종료 감시 중단 |
| `/palworld players` | 접속 플레이어 조회 |

기존 `/status`, `/start`, `/stop`, `/players`는 기능 구분을 위해
`/palworld ...` 하위 명령으로 변경되었습니다.

## 프로젝트 구조

```text
ssh-discord-bot/
├── bot.py                         # Discord 연결 및 확장 로딩
├── config.py                      # 봇 공통 설정
├── deploy/
│   └── discord-bot.service       # 저장소에서 관리하는 systemd 원본
├── extensions/
│   ├── system.py                 # 미니 PC 공통 명령
│   └── palworld/                 # 제거 가능한 Palworld 확장
│       ├── cog.py                # Discord 명령 및 자동 종료
│       ├── service.py            # REST API 및 서버 제어
│       ├── settings.py           # Palworld 설정
│       └── server-control/       # 시작·종료·상태 스크립트
├── .env.example                  # 공개 가능한 설정 예제
└── requirements.txt
```

`bot.py`는 Palworld를 직접 참조하지 않습니다. 활성화할 기능은 `.env`의
`BOT_EXTENSIONS`로 선택합니다.

## 미니 PC 설치

아래 절차는 다음 환경을 기준으로 합니다.

- 운영체제: Ubuntu Server
- 프로젝트 경로: `/data/ssh-discord-bot`
- 서비스 실행 계정: `discordbot`
- Python: 3.10 이상
- systemd 서비스 이름: `discord-bot`

경로나 계정이 다르면 명령과 서비스 파일을 실제 환경에 맞게 변경하세요.

### 1. 시스템 패키지 설치

```bash
sudo apt update
sudo apt install git python3 python3-venv wakeonlan
```

`wakeonlan`을 사용하지 않는다면 해당 패키지는 생략할 수 있습니다.

서비스 계정이 없다면 생성합니다. 이미 존재한다면 이 명령은 실행하지 않습니다.

```bash
id discordbot
sudo useradd --system --create-home --shell /usr/sbin/nologin discordbot
```

### 2. 저장소 설치

처음 설치하는 경우:

```bash
sudo mkdir -p /data
sudo git clone https://github.com/wonmincheol/ssh-discord-bot.git /data/ssh-discord-bot
sudo chown -R discordbot:discordbot /data/ssh-discord-bot
cd /data/ssh-discord-bot
```

이미 저장소가 있다면 해당 디렉터리로 이동하면 됩니다.

```bash
cd /data/ssh-discord-bot
```

### 3. Python 가상환경 설정

가상환경은 프로젝트 내부의 `.venv`에 생성합니다. systemd도 이 가상환경의
Python을 직접 실행합니다.

```bash
sudo -u discordbot python3 -m venv /data/ssh-discord-bot/.venv
sudo -u discordbot /data/ssh-discord-bot/.venv/bin/python -m pip install --upgrade pip
sudo -u discordbot /data/ssh-discord-bot/.venv/bin/python -m pip install -r /data/ssh-discord-bot/requirements.txt
```

셸에서 `source .venv/bin/activate`를 실행할 필요는 없습니다. 서비스와 관리
명령에서 `.venv/bin/python` 경로를 직접 사용하므로 어떤 Python이 실행되는지
명확하게 유지됩니다.

### 4. 비밀 설정 작성

공개 가능한 예제를 복사한 뒤 자신의 Discord 토큰과 서버 설정을 입력합니다.

```bash
sudo -u discordbot cp /data/ssh-discord-bot/.env.example /data/ssh-discord-bot/.env
sudoedit /data/ssh-discord-bot/.env
sudo chown discordbot:discordbot /data/ssh-discord-bot/.env
sudo chmod 600 /data/ssh-discord-bot/.env
```

최소한 다음 값을 실제 값으로 바꿔야 합니다.

```dotenv
DISCORD_TOKEN=replace-with-your-discord-bot-token
PALWORLD_API_PASSWORD=replace-with-your-palworld-admin-password
```

`.env`, `.env.*`, 개인 키와 `secrets/` 디렉터리는 `.gitignore`에 포함되어
Git에 올라가지 않습니다. `.env.example`에는 실제 비밀값을 입력하지 마세요.

> 비밀값을 한 번이라도 Git에 커밋했다면 `.gitignore`만으로는 보호되지 않습니다.
> 해당 토큰이나 비밀번호를 폐기하고 새 값으로 재발급해야 합니다.

### 5. Palworld 제어 sudo 권한 설정

Palworld 확장을 사용할 때만 필요합니다. `sudo visudo`를 이용하면 문법 오류로
sudo 설정이 손상되는 일을 방지할 수 있습니다.

```bash
sudo visudo -f /etc/sudoers.d/discord-bot
```

다음 내용을 입력합니다.

```text
discordbot ALL=(ALL) NOPASSWD: /bin/bash /data/ssh-discord-bot/extensions/palworld/server-control/start.sh
discordbot ALL=(ALL) NOPASSWD: /bin/bash /data/ssh-discord-bot/extensions/palworld/server-control/stop.sh
discordbot ALL=(ALL) NOPASSWD: /bin/bash /data/ssh-discord-bot/extensions/palworld/server-control/status.sh
```

실행 계정이나 설치 경로를 변경했다면 이 설정도 동일하게 변경해야 합니다.

### 6. systemd 서비스 설치

서비스 파일은 두 위치에서 서로 다른 역할을 갖습니다.

| 위치 | 역할 |
| --- | --- |
| `/data/ssh-discord-bot/deploy/discord-bot.service` | Git으로 버전 관리하는 서비스 원본 |
| `/etc/systemd/system/discord-bot.service` | systemd가 실제로 읽는 운영 파일 |

저장소의 서비스 원본은 다음 경로를 사용합니다.

```ini
User=discordbot
WorkingDirectory=/data/ssh-discord-bot
EnvironmentFile=/data/ssh-discord-bot/.env
ExecStart=/data/ssh-discord-bot/.venv/bin/python -u /data/ssh-discord-bot/bot.py
```

실제 환경과 일치하는지 확인한 후 systemd 위치에 설치합니다.

```bash
cd /data/ssh-discord-bot
sudo install -m 0644 deploy/discord-bot.service /etc/systemd/system/discord-bot.service
sudo systemctl daemon-reload
sudo systemctl enable --now discord-bot
```

기존 `/etc/systemd/system/discord-bot.service`가 이미 위와 동일하게 `.venv`와
`.env`를 사용한다면 덮어쓸 필요가 없습니다. 내용을 수정했을 때만
`daemon-reload`와 재시작을 수행하면 됩니다.

### 7. 최초 실행 확인

```bash
sudo systemctl status discord-bot --no-pager -l
sudo journalctl -u discord-bot -n 100 --no-pager
```

Discord에서 `/ping`을 실행해 `Pong!` 응답이 오면 설치가 완료된 것입니다.

## 봇 실행 및 관리

### systemctl 명령

| 작업 | 명령 |
| --- | --- |
| 시작 | `sudo systemctl start discord-bot` |
| 중지 | `sudo systemctl stop discord-bot` |
| 재시작 | `sudo systemctl restart discord-bot` |
| 상태 확인 | `sudo systemctl status discord-bot` |
| 부팅 자동 실행 활성화 | `sudo systemctl enable discord-bot` |
| 부팅 자동 실행 해제 | `sudo systemctl disable discord-bot` |
| 자동 실행 해제 및 즉시 중지 | `sudo systemctl disable --now discord-bot` |

`disable`만 실행하면 현재 실행 중인 봇은 중지되지 않습니다. 즉시 중지까지 하려면
`disable --now`를 사용합니다.

### 로그 확인

실시간 로그:

```bash
sudo journalctl -u discord-bot -f
```

최근 로그 100줄:

```bash
sudo journalctl -u discord-bot -n 100 --no-pager
```

### 코드 업데이트

```bash
sudo systemctl stop discord-bot
sudo -u discordbot git -C /data/ssh-discord-bot pull --ff-only
sudo -u discordbot /data/ssh-discord-bot/.venv/bin/python -m pip install -r /data/ssh-discord-bot/requirements.txt
sudo systemctl start discord-bot
sudo systemctl status discord-bot --no-pager -l
```

업데이트에 `deploy/discord-bot.service` 변경이 포함되었다면 운영 파일도 다시
설치해야 합니다.

```bash
sudo install -m 0644 /data/ssh-discord-bot/deploy/discord-bot.service /etc/systemd/system/discord-bot.service
sudo systemctl daemon-reload
sudo systemctl restart discord-bot
```

### 설정 변경

`.env`를 수정한 후 서비스를 재시작합니다.

```bash
sudoedit /data/ssh-discord-bot/.env
sudo systemctl restart discord-bot
```

## Palworld 확장 선택

### Palworld 없이 실행

`.env`에서 다음과 같이 공통 시스템 확장만 지정합니다.

```dotenv
BOT_EXTENSIONS=extensions.system
```

변경 후 서비스를 재시작합니다.

```bash
sudo systemctl restart discord-bot
```

Palworld 지원 자체를 저장소에서 제거하려면 다음 항목만 제거하면 됩니다.

- `extensions/palworld/` 디렉터리
- `BOT_EXTENSIONS`의 `extensions.palworld`
- 다른 확장에서 사용하지 않는 경우 `requirements.txt`의 `requests`

### Palworld 다시 활성화

`.env`에서 두 확장을 지정하고 서비스를 재시작합니다.

```dotenv
BOT_EXTENSIONS=extensions.system,extensions.palworld
```

```bash
sudo systemctl restart discord-bot
```

## 문제 해결

- `status=203/EXEC`: `.venv/bin/python` 경로가 없거나 실행 권한이 없는지 확인합니다.
- `status=217/USER`: 서비스의 `User` 계정이 실제로 존재하는지 확인합니다.
- `.env` 관련 오류: 파일 존재 여부, 소유자와 `600` 권한을 확인합니다.
- Palworld 명령의 sudo 오류: `/etc/sudoers.d/discord-bot`의 계정과 경로를 확인합니다.
- 명령 변경이 Discord에 보이지 않음: 봇 로그에서 application command 동기화 오류를 확인합니다.

## 새 기능 확장하기

새 기능은 `extensions/<기능명>/` 패키지 또는 단일 Cog 모듈로 만들고 비동기
`setup(bot)` 진입점을 제공합니다. 이후 import 경로를 `BOT_EXTENSIONS`에
추가하면 Discord 연결부를 수정하지 않고 기능을 추가하거나 제거할 수 있습니다.

## License

MIT
