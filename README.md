# Mini PC Remote Control Discord Bot

Discord 슬래시 명령으로 개인 미니 PC를 원격 관리하는 봇입니다. Palworld, Tarkov, Factorio 지원은
코어와 분리된 선택형 확장 모듈로 제공됩니다.

## Discord 명령어

공통 명령:

| 명령 | 설명 |
| --- | --- |
| `/ping` | 봇 응답 확인 |
| `/desktop_on` | Wake on LAN 패킷 전송 (`admin`, `manager` 또는 `desktop_power` 필요) |

Factorio 확장을 활성화했을 때 (별도 봇 권한 없이 서버 멤버 누구나 사용 가능):

| 명령 | 설명 |
| --- | --- |
| `/factorio` | 서버 주소, 비밀번호, 게임 버전, 필수 DLC, 모드 동기화 및 접속 방법 확인 |

권한 관리 명령은 `.env` 소유자와 `Bot • Admin` 역할 보유자만 사용할 수 있습니다.

| 명령 | 설명 |
| --- | --- |
| `/permission setup` | 봇 권한 역할 생성·복구 |
| `/permission grant` | 사용자에게 `admin`, `manager` 또는 `desktop_power` 부여 |
| `/permission revoke` | 사용자의 권한 회수 |
| `/permission show` | 사용자의 봇 권한 확인 |
| `/permission list` | 사용 가능한 권한과 역할 상태 확인 |

Palworld 확장을 활성화했을 때 (`manager` 또는 `admin` 필요):

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
│   ├── access/                   # Discord 역할 기반 명령 권한 관리
│   ├── system.py                 # 미니 PC 공통 명령
│   ├── factorio.py               # Factorio 서버 접속 정보 안내
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
`.env.example`과 `.env`처럼 이름이 `.`으로 시작하는 파일은 Ubuntu에서 숨김
파일로 취급되므로 일반 `ls` 명령에는 표시되지 않습니다. `ls -la`를 사용하면
숨김 파일까지 확인할 수 있습니다.

```bash
cd /data/ssh-discord-bot
ls -la
```

복사 전에는 `.env.example`만 있고, 복사 후에는 `.env`도 함께 표시되어야 합니다.

```bash
sudo -u discordbot cp /data/ssh-discord-bot/.env.example /data/ssh-discord-bot/.env
sudoedit /data/ssh-discord-bot/.env
sudo chown discordbot:discordbot /data/ssh-discord-bot/.env
sudo chmod 600 /data/ssh-discord-bot/.env
ls -la /data/ssh-discord-bot/.env*
```

최소한 다음 값을 실제 값으로 바꿔야 합니다.

```dotenv
DISCORD_TOKEN=replace-with-your-discord-bot-token
BOT_GUILD_IDS=000000000000000000,111111111111111111
BOT_OWNER_IDS=000000000000000000
WOL_MAC_ADDRESS=00:00:00:00:00:00
PALWORLD_API_PASSWORD=replace-with-your-palworld-admin-password
```

`BOT_GUILD_IDS`에는 봇을 사용할 Discord 서버 ID들을 쉼표로 구분해 입력하고,
`BOT_OWNER_IDS`에는 복구 권한을 가질 본계정의 사용자 ID를 입력합니다. 소유자가
여러 명이면 마찬가지로 쉼표로 구분합니다. 사용자 이름이 아니라 Discord 개발자
모드에서 복사한 숫자 ID를 사용해야 합니다. 기존 단일 `BOT_GUILD_ID` 설정도
호환되지만 새 설정에서는 `BOT_GUILD_IDS`를 사용하세요.

`WOL_MAC_ADDRESS`는 `/desktop_on`을 사용할 때 필수입니다. 이 값과 외부 명령의
원문 출력은 Discord 응답에 표시되지 않으며, 실제 주소는 `.env`에만 보관하세요.

`.env`, `.env.*`, 개인 키와 `secrets/` 디렉터리는 `.gitignore`에 포함되어
Git에 올라가지 않습니다. `.env.example`에는 실제 비밀값을 입력하지 마세요.

> 비밀값을 한 번이라도 Git에 커밋했다면 `.gitignore`만으로는 보호되지 않습니다.
> 해당 토큰이나 비밀번호를 폐기하고 새 값으로 재발급해야 합니다.

### 5. Discord 권한 역할 설정

봇을 서버에 초대할 때 **역할 관리(Manage Roles)** 권한을 부여합니다. Discord
서버의 역할 설정에서 봇 역할이 봇이 생성할 권한 역할보다 위에 있어야 합니다.
봇에 Discord의 전체 관리자 권한을 부여할 필요는 없습니다.

봇을 시작한 뒤 `.env`에 등록한 본계정으로 **각 서버에서** 다음 순서대로
실행합니다.

1. `/permission setup`
2. `/permission grant user:@부계정 permission:admin`

이후 부계정의 `Bot • Admin` 역할이 유지되는 동안 본계정과 동일하게 모든 봇
명령과 권한 관리 명령을 사용할 수 있습니다. `.env` 소유자 권한은 Discord에서
회수할 수 없으므로 역할이 삭제되거나 설정이 손상되어도 복구할 수 있습니다.

권한 데이터베이스는 기본적으로 `data/permissions.sqlite3`에 생성됩니다. 역할
ID만 저장하며 실제 권한 보유자는 Discord 역할로 관리됩니다.

### 공통 운영 권한: manager

`manager`는 게임별 권한을 따로 만들지 않고 운영 기능을 사용할 수 있는 공통
권한입니다. 새 운영 기능도 이 권한을 사용합니다.

| 권한 | 역할 | 허용 범위 |
| --- | --- | --- |
| `admin` | `Bot • Admin` | 모든 기능과 사용자 권한 부여·회수 |
| `manager` | `Bot • Manager` | Tarkov·Palworld 모든 명령, 데스크탑 켜기 |
| `desktop_power` | `Bot • Desktop Power` | 데스크탑 켜기만 허용 |

업데이트 후 소유자 또는 기존 봇 관리자가 각 Discord 서버에서 실행합니다.

```text
/permission setup
/permission grant user:@사용자 permission:manager
```

`setup`은 기존 역할과 보유자를 유지하면서 Manager 역할을 추가합니다.
회수는 `/permission revoke user:@사용자 permission:manager`를 사용합니다.
기존 `admin` 보유자와 `.env` 소유자는 manager를 별도로 받을 필요가 없습니다.
Manager는 `/permission` 명령으로 다른 사용자에게 권한을 부여할 수 없습니다.
기존에 권한 검사 없이 사용 가능했던 Palworld 명령도 이제 운영 권한이 필요합니다.

### 6. Palworld 제어 sudo 권한 설정

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

### 7. systemd 서비스 설치

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

### 8. 최초 실행 확인

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
BOT_EXTENSIONS=extensions.access,extensions.system
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
BOT_EXTENSIONS=extensions.access,extensions.system,extensions.palworld
```

```bash
sudo systemctl restart discord-bot
```

## Factorio 접속 정보

`/factorio`는 등록된 서버 접속 정보를 표시합니다. 서버 상태를 조회하거나
게임 서버를 제어하지 않습니다.

기존 `.env`의 `BOT_EXTENSIONS` 목록에 `extensions.factorio`를 추가하고,
다음 설정을 넣습니다. 비밀번호는 실제 서버 비밀번호로 바꿉니다.

```dotenv
FACTORIO_SERVER_ADDRESS=mincheol.duckdns.org:34197
FACTORIO_SERVER_PASSWORD=replace-with-your-factorio-server-password
FACTORIO_GAME_VERSION="2.1.24 정식"
FACTORIO_REQUIRED_DLC="스페이스 에이지"
```

```bash
sudo systemctl restart discord-bot
```

봇이 시작하면서 `/factorio` 명령을 Discord에 동기화합니다. 게임 버전이나
비밀번호가 바뀌면 `.env`를 수정하고 봇을 재시작하세요. 모드 동기화와
`멀티플레이 → 주소로 접속` 안내도 함께 표시됩니다.

## Tarkov SPT + Fika 제어

봇을 **Tarkov 서버와 같은 미니 PC에서 실행**하는 방식입니다. 봇이 SSH에
접속하는 것은 아니며, 기존 `tarkov` tmux 세션을 직접 제어합니다.
`/data/tarkov/start-server.sh`가 실행 가능한 상태여야 합니다.

| 명령 | 설명 |
| --- | --- |
| `/tarkov start` | 기존 세션이 없을 때 서버 시작 |
| `/tarkov stop everyone_finished:True` | Ctrl+C 전달 후 세션 종료 대기 |
| `/tarkov status` | tmux 세션 상태 확인 (게임 접속 가능 여부와는 다름) |

세 명령 모두 허용된 Discord 서버의 `.env` 소유자, `Bot • Admin` 또는 `Bot • Manager` 역할이
필요합니다. 접속자나 레이드 진행 상태는 자동으로 확인하지 않습니다.
**모두 레이드와 게임을 종료한 뒤** `everyone_finished:True`로 종료를 요청하세요.

### 기존 SSH 계정 확인 및 확장 활성화

지금 서버를 실행한 SSH 계정에서 다음을 확인합니다.

```bash
whoami
command -v tmux
tmux ls
```

기본 소켓에 `tarkov` 세션이 보여야 하고 tmux 경로는 `/usr/bin/tmux`를
사용합니다. 사용자 지정 `tmux -L`/`-S` 소켓은 지원하지 않습니다.
`tmux`가 없다면 `sudo apt install tmux`로 설치합니다.

`.env`에 다음을 설정합니다. `your_ssh_user`는 위 `whoami` 결과로 바꿉니다.

```dotenv
BOT_EXTENSIONS=extensions.access,extensions.system,extensions.palworld,extensions.tarkov
TARKOV_USER=your_ssh_user
TARKOV_STOP_TIMEOUT=120
```

Palworld를 사용하지 않는다면 목록에서 `extensions.palworld`를 빼도 됩니다.
봇 실행 계정과 tmux 실행 계정이 같을 때만 `TARKOV_USER=`를 비워 두세요.
tmux는 계정별로 분리되므로 다른 계정으로 설정하면 기존 서버를 찾지 못합니다.

### 봇 계정에 필요한 tmux 명령 허용

기존 설치처럼 봇은 `discordbot`, Tarkov는 다른 SSH 계정으로 실행한다면:

```bash
sudo visudo -f /etc/sudoers.d/discord-bot-tarkov
```

아래 네 줄의 `your_ssh_user`를 실제 계정으로 바꿔 입력합니다. 봇 계정도
다르다면 `discordbot`을 바꿉니다. sudoers에서 `#`를 인자로 쓰기 위해
마지막 줄의 `\#`는 그대로 유지하세요.

```sudoers
discordbot ALL=(your_ssh_user) NOPASSWD: /usr/bin/tmux has-session -t =tarkov
discordbot ALL=(your_ssh_user) NOPASSWD: /usr/bin/tmux new-session -d -s tarkov -c /data/tarkov /data/tarkov/start-server.sh
discordbot ALL=(your_ssh_user) NOPASSWD: /usr/bin/tmux send-keys -t =tarkov\: C-c
discordbot ALL=(your_ssh_user) NOPASSWD: /usr/bin/tmux list-panes -s -t =tarkov -F \#{pane_dead}
```

기존 세션이 실행 중일 때 아래 명령으로 접근을 확인합니다. 성공하면 출력
없이 종료 코드 0을 반환합니다. 이 명령은 게임 서버를 변경하지 않습니다.

```bash
sudo -u discordbot sudo -n -H -u your_ssh_user /usr/bin/tmux has-session -t =tarkov
sudo systemctl restart discord-bot
```

Discord에서 `/tarkov status`로 확인한 뒤 시작·종료 명령을 사용할 수 있습니다.
봇 재시작 자체는 Tarkov 시작·종료 명령을 실행하지 않습니다.

### 종료와 재부팅 시 동작

서버는 기존 명령처럼 **단일 창·단일 pane에서 실행하고, 서버 프로세스가
끝나면 세션도 종료되는 구조**여야 합니다. 시작 스크립트가 백그라운드로
서버를 분리하거나 종료 후 셸을 남기는 구조는 지원하지 않습니다.
`remain-on-exit`도 꺼져 있어야 합니다. 시작할 때 작업 디렉터리는
`/data/tarkov`로 지정합니다.

종료 명령은 Ctrl+C를 전달하고 기본 120초간 세션 종료를 기다립니다.
종료 확인은 저장 성공을 검증하는 것이 아니므로 서버의 정상 저장 처리는
기존 Ctrl+C 종료 동작에 의존합니다. 대기 시간은 1~600초로 설정할 수 있습니다.
시간이 초과되어도 `kill-session`이나 강제 종료를 실행하지 않습니다.
같은 봇 실행 중에는 `/tarkov stop`을 다시 호출해도 Ctrl+C를 재전송하지 않고
종료 확인만 반복합니다. 이 기록은 메모리에 있으므로 종료 대기 중 봇을
재시작했다면 콘솔 상태를 먼저 확인하세요.

서버 콘솔 확인은 기존 SSH 계정에서 `tmux attach -t tarkov`, 서버를 켜둔 채
나오기는 `Ctrl+B` 후 `D`를 사용합니다. 미니 PC 재부팅 후 봇이 자동 실행되어도
게임 서버는 자동으로 시작하지 않으며 `/tarkov start`를 실행해야 합니다.
tmux 명령 동작은 [공식 tmux 매뉴얼](https://man.openbsd.org/tmux)을 참고하세요.

## 문제 해결

- `status=203/EXEC`: `.venv/bin/python` 경로가 없거나 실행 권한이 없는지 확인합니다.
- `status=217/USER`: 서비스의 `User` 계정이 실제로 존재하는지 확인합니다.
- `.env` 관련 오류: 파일 존재 여부, 소유자와 `600` 권한을 확인합니다.
- `/desktop_on` 권한 오류: `extensions.access`가 `extensions.system`보다 먼저
  로드되는지와 `/permission setup` 실행 여부를 확인합니다.
- 역할 부여 오류: 봇에 역할 관리 권한이 있는지, 봇 역할이 권한 역할보다 위인지 확인합니다.
- `/permission setup` 역할 생성 오류: 명령 실행자의 권한이 아니라 **봇 역할**의
  `역할 관리(Manage Roles)` 권한을 서버 설정에서 확인합니다.
- Palworld 명령의 sudo 오류: `/etc/sudoers.d/discord-bot`의 계정과 경로를 확인합니다.
- 명령 변경이 Discord에 보이지 않음: 봇 로그에서 application command 동기화 오류를 확인합니다.

## 새 기능 확장하기

새 기능은 `extensions/<기능명>/` 패키지 또는 단일 Cog 모듈로 만들고 비동기
`setup(bot)` 진입점을 제공합니다. 이후 import 경로를 `BOT_EXTENSIONS`에
추가하면 Discord 연결부를 수정하지 않고 기능을 추가하거나 제거할 수 있습니다.

새 운영 명령은 `extensions.access.checks.require_manager(interaction)`를
작업 실행 전에 호출하고, 결과가 `False`이면 반환합니다. 공통 `manager`
권한을 재사용하므로 기능마다 역할을 추가할 필요가 없습니다. 권한 확장이
로드되지 않았거나 허용된 Discord 서버가 아니면 운영 명령은 차단됩니다.

## License

MIT
