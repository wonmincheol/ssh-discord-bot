# Mini PC Remote Control Discord Bot

개인 미니 PC를 Discord 슬래시 명령으로 원격 관리하는 봇입니다. Palworld 지원은
코어 기능이 아니라 **선택 가능한 확장 모듈**로 제공됩니다.

## 구조

```text
ssh-discord-bot/
├── bot.py                         # 확장 로딩과 Discord 연결만 담당
├── config.py                      # 봇 코어 설정
├── extensions/
│   ├── system.py                 # 미니 PC 공통 명령
│   └── palworld/                 # 제거 가능한 Palworld 확장
│       ├── __init__.py           # 확장 진입점
│       ├── cog.py                # Discord 명령과 자동 종료 수명주기
│       ├── service.py            # REST API와 서버 제어 실행
│       ├── settings.py           # Palworld 전용 설정
│       └── server-control/       # 시작/종료/상태 셸 스크립트
└── requirements.txt
```

`bot.py`는 Palworld를 직접 import하지 않습니다. 사용할 확장은
`BOT_EXTENSIONS` 환경 변수로 선택합니다.

## 명령어

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

기존 최상위 `/status`, `/start`, `/stop`, `/players`는 기능 경계를 명확히 하기
위해 `/palworld ...` 하위 명령으로 변경되었습니다.

## 요구 사항

- Ubuntu Server
- Python 3.10 이상
- `wakeonlan` (Wake on LAN 명령을 사용할 경우)
- Palworld Dedicated Server와 활성화된 REST API (Palworld 확장을 사용할 경우)

```bash
python3 -m pip install -r requirements.txt
```

## 설정

공개 가능한 예제 설정을 복사한 뒤 자신의 값으로 채웁니다.

```bash
cp .env.example .env
nano .env
```

`.env`에는 Discord 토큰과 Palworld 관리자 비밀번호 같은 실제 비밀값을 넣습니다.
이 파일과 `.env.*`, 개인 키 및 `secrets/` 디렉터리는 `.gitignore`로 제외되어
Git에 올라가지 않습니다. `.env.example`에는 자리표시자만 유지해야 합니다.

환경 변수를 직접 관리하는 systemd, Docker 등의 환경에서는 `.env` 대신 같은
이름의 환경 변수를 주입해도 됩니다. 환경 변수가 `.env`보다 우선합니다.

> 비밀값을 한 번이라도 커밋했다면 `.gitignore`에 추가하는 것만으로는 안전해지지
> 않습니다. 해당 토큰이나 비밀번호를 먼저 폐기·재발급해야 합니다.

실행:

```bash
python3 bot.py
```

## Palworld 없이 실행하기

Palworld 기능을 끄는 데 코드 수정은 필요하지 않습니다.

```bash
echo 'BOT_EXTENSIONS=extensions.system' >> .env
python3 bot.py
```

지원 자체를 프로젝트에서 제거하려면 다음 항목만 제거하면 됩니다.

- `extensions/palworld/` 디렉터리
- `BOT_EXTENSIONS`의 `extensions.palworld` 값
- 더 이상 다른 확장에서 사용하지 않는 경우 `requirements.txt`의 `requests`

## sudo 권한

Palworld 확장은 셸 스크립트를 `sudo`로 실행합니다. 실제 봇 실행 사용자 이름과
설치 경로에 맞게 `visudo`에서 정확한 파일만 허용하세요.

```text
discordbot ALL=(ALL) NOPASSWD: /bin/bash /data/ssh-discord-bot/extensions/palworld/server-control/start.sh
discordbot ALL=(ALL) NOPASSWD: /bin/bash /data/ssh-discord-bot/extensions/palworld/server-control/stop.sh
discordbot ALL=(ALL) NOPASSWD: /bin/bash /data/ssh-discord-bot/extensions/palworld/server-control/status.sh
```

## 새 기능 확장하기

새 기능은 `extensions/<기능명>/` 패키지 또는 단일 Cog 모듈로 만들고 비동기
`setup(bot)` 진입점을 제공하면 됩니다. 이후 해당 import 경로를
`BOT_EXTENSIONS`에 추가합니다. 이렇게 하면 Discord 연결부를 수정하지 않고도
게임 서버, 백업, 시스템 모니터링 같은 기능을 독립적으로 추가하거나 제거할 수
있습니다.

## License

MIT
