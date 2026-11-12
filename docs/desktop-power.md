# Windows 데스크탑 원격 종료

`/desktop_off confirm:True`는 미니 PC의 봇에서 데스크탑으로 SSH 접속하여
종료 전용 SYSTEM 작업을 실행합니다. 고정된 실행 프로그램이 부팅 ID를 다시
확인한 후 로컬 `InitiateSystemShutdownExW` API를 호출합니다. 앱 강제 종료와
재부팅은 모두 `false`입니다. 명령은 허용된 Discord 서버의 소유자,
`admin`, `manager`만 사용할 수 있습니다. `desktop_power`는 켜기 전용입니다.

아래 예제는 Windows 10/11, 기본 Windows 경로 `C:\Windows`, 데스크탑 전용
로컬 일반 계정 `desktopbot`, Ubuntu의 봇 계정 `discordbot`을 기준으로 합니다.
IP와 경로는 실제 환경에 맞게 바꾸세요. 데스크탑 IP는 DHCP 예약을 권장합니다.

최종 실행 경로는 `Discord → 미니 PC의 SSH 클라이언트 → DesktopPower.ps1 →
종료 전용 SYSTEM 작업 → 로컬 Windows 종료 API`입니다. SSH 계정은 작업의
읽기·실행만 담당하며, 일반 셸이나 임의 명령 실행 기능은 제공하지 않습니다.

## 1. 미니 PC에서 전용 키 준비

개인 키는 미니 PC에만 두고 공개 키만 Windows에 등록합니다. 기존 개인용 SSH
키를 재사용하지 않습니다. 다음 명령은 최초 설치 시 한 번 실행합니다.

```bash
sudo apt install openssh-client
sudo install -d -m 700 -o discordbot -g discordbot /data/ssh-discord-bot/secrets
sudo -u discordbot ssh-keygen -t ed25519 -N '' -f /data/ssh-discord-bot/secrets/desktop_ed25519
sudo -u discordbot cat /data/ssh-discord-bot/secrets/desktop_ed25519.pub
```

이미 키가 있으면 덮어쓰지 마세요. 무인 서비스용 키는 암호 없이 생성하므로
파일 접근을 봇 계정에 한정합니다. `secrets/`는 Git에서 제외되어 있습니다.

## 2. Windows에서 SSH와 전용 계정 준비

데스크탑에서 **관리자 PowerShell**을 열어 확인·설치합니다.

```powershell
Get-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Set-Service -Name sshd -StartupType Automatic
Start-Service -Name sshd
```

이미 설치되어 있으면 설치 명령은 생략합니다. 공개 키 인증을 지원하는
**로컬 일반 사용자** `desktopbot`을 만들고 Administrators 그룹에 넣지 마세요.

Windows Update 경로 대신 Microsoft의 별도 MSI를 선택할 수도 있습니다.
[공식 배포 페이지](https://github.com/PowerShell/Win32-OpenSSH/releases)에서 받은
파일의 공개 SHA-256과 Microsoft 서명을 확인한 뒤 `ADDLOCAL=Server`로 서버
기능만 설치합니다. 10.4.0.0 배포는 Preview로 표시되며 별도 수동 업데이트가
필요합니다. [Microsoft 설치 안내](https://learn.microsoft.com/en-us/troubleshoot/windows-server/system-management-components/upgrade-in-box-openssh-to-latest-openssh-release)를
참고하세요. 기본 구성요소 설치가 진행 중이면 완료·중단 상태를 먼저 확인하고
전환합니다. 설치 요청 프로세스를 끝내도 Windows 백그라운드 설치가 계속되어
서비스·방화벽 설정을 덮어쓸 수 있습니다.

MSI 설치에서는 아래 `sshd.exe`와 `ssh-keygen.exe`의 경로를 실제 설치 폴더
(`C:\Program Files\OpenSSH` 등)로 바꿔 사용하세요. PowerShell과 종료 스크립트의
경로는 동일합니다.

```powershell
# 별도 MSI를 선택한 경우의 예. 기본 설치와 동시에 실행하지 않습니다.
Get-AuthenticodeSignature -LiteralPath '.\OpenSSH-Win64-v10.4.0.0.msi'
msiexec.exe /i .\OpenSSH-Win64-v10.4.0.0.msi ADDLOCAL=Server /qn /norestart
```

```powershell
$desktopPassword = Read-Host 'desktopbot 계정의 임의의 긴 비밀번호' -AsSecureString
New-LocalUser -Name desktopbot -Password $desktopPassword -Description 'Discord desktop shutdown only'
Add-LocalGroupMember -SID 'S-1-5-32-545' -Member desktopbot
```

계정이 이미 있으면 재생성하지 않습니다. `S-1-5-32-545`는 일반 사용자(Users)
그룹입니다. 이 그룹은 부팅 정보 조회 등 기본 Windows 접근에 필요하며,
Administrators 그룹에는 추가하지 않습니다. 실제 종료는 SYSTEM 작업이 수행하므로
SSH 계정에 `시스템 종료`나 `원격 시스템에서 강제로 시스템 종료` 권한을 별도로
추가하지 않습니다. 이전 직접 종료 구성에서 이 계정에 따로 추가한 종료 권한은
작업 설치를 확인한 뒤 제거할 수 있습니다. 그룹의 기본 권한이나 다른 계정의
사용자 권한은 변경하지 않습니다.

부팅 ID는 WMI의 `Win32_OperatingSystem.LastBootUpTime`에서 조회합니다. 저장소
루트의 관리자 PowerShell에서 다음을 실행하여 전용 계정에 `root/cimv2` 조회
권한(`Enable Account`와 SSH 네트워크 로그온용 `Remote Enable`)을 부여합니다.
기존 ACL을 유지하며 해당 계정에만 추가하고, 메서드 실행·보안 변경 권한은
추가하지 않습니다. WMI 네트워크 포트를 방화벽에서 열지 않습니다.

```powershell
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\deploy\windows\Grant-DesktopBootQueryAccess.ps1 -AccountName desktopbot
```

공개 키 등록용 디렉터리를 만들고 위에서 출력한 공개 키 한 줄을 등록합니다.
아래 `ssh-ed25519 AAAA...`는 실제 공개 키로 바꾸세요.

```powershell
$desktopAccount = "$env:COMPUTERNAME\desktopbot"
$desktopSshPath = 'C:\Users\desktopbot\.ssh'
New-Item -ItemType Directory -Path $desktopSshPath -Force
Set-Content -LiteralPath "$desktopSshPath\authorized_keys" -Encoding ascii -Value 'ssh-ed25519 AAAA... desktop-power'
icacls.exe $desktopSshPath /inheritance:r /grant:r "${desktopAccount}:(OI)(CI)F" '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F'
icacls.exe "$desktopSshPath\authorized_keys" /inheritance:r /grant:r "${desktopAccount}:F" '*S-1-5-18:F' '*S-1-5-32-544:F'
```

## 3. 종료 전용 명령 설치 및 SSH 제한

저장소의 `deploy/windows/DesktopPower.ps1`을 데스크탑에 설치합니다.
관리자 PowerShell에서 저장소 루트로 이동한 뒤 실행하세요.

```powershell
$desktopControlPath = 'C:\ProgramData\DiscordBot'
New-Item -ItemType Directory -Path $desktopControlPath -Force
icacls.exe $desktopControlPath /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' "${desktopAccount}:(OI)(CI)RX"
Copy-Item -LiteralPath '.\deploy\windows\DesktopPower.ps1' -Destination "$desktopControlPath\DesktopPower.ps1"
icacls.exe "$desktopControlPath\DesktopPower.ps1" /inheritance:r /grant:r '*S-1-5-18:F' '*S-1-5-32-544:F' "${desktopAccount}:RX"
```

네이티브 API와 종료 작업을 설치합니다. SYSTEM으로 실행되는 작업을 등록하는
변경이므로 관리자 승인 후 실행하세요. 계정에 부여되는 작업 권한은 읽기·실행
뿐이며, 작업 정의·실행 파일·결과 디렉터리를 수정할 수 없습니다.

```powershell
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\deploy\windows\Install-DesktopShutdownApi.ps1 -AccountName desktopbot
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\deploy\windows\Install-DesktopShutdownTask.ps1 -AccountName desktopbot
Copy-Item -LiteralPath '.\deploy\windows\DesktopShutdownTask.ps1' -Destination "$desktopControlPath\DesktopShutdownTask.ps1"
icacls.exe "$desktopControlPath\DesktopShutdownTask.ps1" /inheritance:r /grant:r '*S-1-5-18:F' '*S-1-5-32-544:F' "${desktopAccount}:RX"
```

작업 이름은 `\SshDiscordBotDesktopPower\DesktopShutdown`입니다. 시간·부팅
트리거가 없고 요청할 때만 실행됩니다. 실행 대상은 관리자 소유의
`DesktopShutdownWorker.exe` 한 개이며, 인자는 숫자 부팅 ID와 32자리 요청 ID만
받습니다. 임의 명령이나 경로는 받지 않습니다. 설치 검증은 일부러 다른 부팅
ID를 전달하여 종료 호출 전에 차단되는지 확인합니다. 실제 전원을 끄지 않습니다.

컴파일에 쓰이는 `DesktopShutdown.cs`, `DesktopShutdownWorker.cs`와 설치
스크립트도 저장소에서 함께 관리합니다. DLL·실행 파일은 설치 과정에서 생성하며
SSH 계정이 수정할 수 없어야 합니다.

일반 계정이 스크립트나 그 디렉터리를 수정할 수 없어야 합니다. 이미 존재하는
경로는 명시적 쓰기 권한과 소유자도 확인하세요. 전용 새 디렉터리를 권장합니다.

`C:\ProgramData\ssh\sshd_config`를 백업하고
`deploy/windows/sshd_config.desktop.example`의 `Match User desktopbot` 블록을
추가합니다. PowerShell에서 편집기를 열 때는 `vi`를 사용합니다.

```powershell
Copy-Item -LiteralPath 'C:\ProgramData\ssh\sshd_config' -Destination "C:\ProgramData\ssh\sshd_config.backup-$(Get-Date -Format yyyyMMddHHmmss)"
vi C:\ProgramData\ssh\sshd_config
```

전용 계정은 공개 키로만 접속하고, 셸·SFTP 요청도 `ForceCommand`로 종료 전용
스크립트에 전달됩니다. 스크립트는 `desktop-check`, 읽기 전용
`desktop-diagnose`, `desktop-off <부팅 ID>`만 처리하며 그 외 요청은 거부합니다.
`desktop-diagnose`는 `DESKTOP_DIAGNOSTICS BROKER_FOUND=1` 또는 `0`을 출력합니다.
`1`은 고정 종료 작업 정의를 읽어 확인했다는 뜻이며 실제 실행 성공이나 전원
꺼짐을 뜻하지 않습니다. SSH 세션의 직접 종료 권한을 점검하거나 네이티브 API를
불러오지 않고 작업 정의만 조회합니다. 포트 포워딩, 에이전트 전달, 터미널도
차단합니다. `ExecutionPolicy Bypass`는 이 강제 실행 프로세스에만 적용되며
시스템의 실행 정책을 변경하지 않습니다.

기존 `AllowUsers`나 `AllowGroups` 제한이 있으면 전용 계정도 허용되어야 합니다.
설정 문법 검사에 성공한 뒤 SSH 서비스를 다시 시작합니다.

```powershell
& "$env:SystemRoot\System32\OpenSSH\sshd.exe" -t
if ($LASTEXITCODE -eq 0) { Restart-Service -Name sshd }
```

데스크탑의 SSH 방화벽 규칙을 미니 PC의 고정 IP로 제한합니다. 아래 주소는
예제입니다. 기존에 SSH를 다른 용도로 사용한다면 기존 접근 경로도 고려하세요.

```powershell
$desktopSshServer = "$env:SystemRoot\System32\OpenSSH\sshd.exe"
# MSI를 선택했다면 실제 경로로 변경: C:\Program Files\OpenSSH\sshd.exe
Set-NetFirewallRule -Name OpenSSH-Server-In-TCP -Enabled True -Direction Inbound -Action Allow -Profile Any -Program $desktopSshServer -Protocol TCP -LocalPort 22 -RemoteAddress '192.168.1.10'
```

SSH 22번 포트는 공유기에서 외부로 포워딩하지 않습니다. 다른 허용 규칙이
동일 포트를 열고 있는지도 확인하세요.

## 4. 호스트 키 검증 및 봇 설정

Windows에서 SSH 호스트 공개 키 지문을 확인합니다.

```powershell
& "$env:SystemRoot\System32\OpenSSH\ssh-keygen.exe" -lf C:\ProgramData\ssh\ssh_host_ed25519_key.pub
```

미니 PC에서 후보 키를 수집합니다. `192.168.1.20`은 데스크탑 주소 예제입니다.
`ssh-keyscan` 출력 자체는 신뢰 근거가 아니며, **Windows에서 직접 확인한
SHA256 지문과 일치할 때만** 전용 `known_hosts`로 등록합니다.

```bash
sudo -u discordbot sh -c 'ssh-keyscan -t ed25519 -p 22 192.168.1.20 > /data/ssh-discord-bot/secrets/desktop_known_hosts.candidate'
sudo -u discordbot ssh-keygen -lf /data/ssh-discord-bot/secrets/desktop_known_hosts.candidate
# 두 장치의 지문이 일치하는지 확인한 후에만 실행:
sudo -u discordbot mv /data/ssh-discord-bot/secrets/desktop_known_hosts.candidate /data/ssh-discord-bot/secrets/desktop_known_hosts
sudo chmod 600 /data/ssh-discord-bot/secrets/desktop_ed25519 /data/ssh-discord-bot/secrets/desktop_known_hosts
```

봇 `.env`에 다음을 설정합니다. `.env`를 편집할 때는 `sudo vi`를 사용하세요.

```dotenv
DESKTOP_SSH_HOST=192.168.1.20
DESKTOP_SSH_PORT=22
DESKTOP_SSH_USER=desktopbot
DESKTOP_SSH_IDENTITY_FILE=/data/ssh-discord-bot/secrets/desktop_ed25519
DESKTOP_SSH_KNOWN_HOSTS_FILE=/data/ssh-discord-bot/secrets/desktop_known_hosts
DESKTOP_SSH_TIMEOUT=15
```

키와 호스트 키 파일은 기존의 절대 파일 경로여야 합니다. Windows 사용자명은
공백 없는 로컬 계정명을 사용합니다. 사용자·시스템 SSH 설정은 읽지 않으며
지정된 키와 호스트 키만 사용합니다. 설정이 없거나 잘못되어도 다른 봇 기능은
계속 로드되고, `/desktop_off` 실행 시 설정 오류로 안내합니다.

## 5. 읽기 전용 점검과 실사용 검증

봇을 재시작하기 전에 봇 계정으로 점검합니다. 이 명령은 종료 요청을 보내지
않으며 Discord 토큰도 필요하지 않습니다.

```bash
cd /data/ssh-discord-bot
sudo -u discordbot /data/ssh-discord-bot/.venv/bin/python -m extensions.desktop check
```

`READY`와 종료 코드 0이면 공개 키 인증, 호스트 키 검증, 부팅 ID 조회,
전용 디스패처 응답까지 성공한 것입니다. 실제 종료 권한과 물리적인 전원 종료는
이 점검만으로 검증되지 않습니다. 기존 설치 절차에 따라 코드를 반영하고
`discord-bot` 서비스만 재시작하여 Discord 명령을 동기화합니다.

1. 데스크탑의 모든 작업을 저장합니다.
2. `/desktop_off`를 확인값 없이 실행하여 종료되지 않는지 확인합니다.
3. 일반 사용자와 `desktop_power` 전용 사용자의 종료 요청이 차단되는지 확인합니다.
4. 소유자·`admin`·`manager`로 `/desktop_off confirm:True`를 실행합니다.
5. 응답과 별개로 데스크탑 전원이 실제로 꺼졌는지 확인합니다.
6. 기존 `/desktop_on`으로 다시 켜지는지 확인합니다. 종료 후 WOL은 BIOS,
   네트워크 카드 전원 관리 등 실제 장치 설정에 따라 별도로 검증해야 합니다.

앱의 저장 확인 등으로 정상 종료가 막힐 수 있습니다. 종료 API에는 강제 앱 종료와
재부팅을 모두 `false`로 명시하고, 호출 후 기존 토큰 권한 상태를 복원합니다.
종료 요청의 수락은 저장 성공이나 전원 종료 완료를 의미하지 않습니다.

종료 API의 권한 활성화·복원은 SYSTEM worker 내부에서 수행합니다. SSH 계정은
고정 작업의 읽기·실행만 담당합니다. 실행 파일과 작업 정의의 쓰기 권한을 일반
사용자에게 열지 마세요.

## 설치 자료와 결과 보관

재설치는 이 문서와 `deploy/windows/`의 설치 스크립트를 기준으로 합니다.
개발 중 만든 일회성 반영·진단 스크립트와 오래된 설치 자료는 운영 절차로
재사용하지 않습니다.

`C:\ProgramData\DiscordBot\results`의 요청 결과는 실행 중인 디스패처가 읽으므로
진행 중인 요청의 파일을 옮기거나 지우지 않습니다. 정기 점검 시 진행 중인 작업이
없는 것을 확인하고 최근 성공·점검 결과를 남긴 뒤 오래된 결과와 설치 백업을
관리자 전용 보관 경로로 옮길 수 있습니다. 자동 정리 작업은 등록하지 않습니다.

## 결과와 중복 실행 처리

| 결과 | 의미 |
| --- | --- |
| `READY` | 종료 없는 연결 점검 성공 |
| `CONFIG_ERROR` | 필수 설정·키 파일·호스트 키 파일 확인 필요 |
| `SSH_MISSING` | 봇 환경의 OpenSSH 클라이언트 확인 필요 |
| `HOST_KEY_ERROR` | 신뢰할 수 있는 경로로 호스트 키 확인 필요 |
| `AUTH_ERROR` | 전용 계정·공개 키·파일 권한 확인 필요 |
| `CONNECTION_FAILED` | 데스크탑 접속 실패; 전원 꺼짐으로 단정할 수 없음 |
| `CHECK_FAILED` | 전용 스크립트나 부팅 ID 조회 실패; 종료 요청 미전송 |
| `REQUESTED` | Windows가 종료 명령을 수락했다는 응답 수신 |
| `REJECTED` | Windows 종료 명령 실패 또는 점검 후 부팅 ID 변경 |
| `SHUTDOWN_PRIVILEGE_MISSING` | Windows가 필수 권한 부족 오류 1314를 반환 |
| `SHUTDOWN_ACCESS_DENIED` | Windows가 접근 거부 오류 5를 반환 |
| `WINDOWS_SHUTTING_DOWN` | Windows가 종료 처리 중 오류 1115를 반환; 재전송 차단 유지 |
| `BOOT_CHANGED` | 점검과 요청 사이에 부팅 ID가 달라져 실행하지 않음 |
| `UNKNOWN` | 요청 후 시간 초과·연결 끊김 등으로 처리 결과 불명 |
| `ALREADY_REQUESTED` | 같은 Windows 부팅에 이미 요청하여 재전송 차단 |
| `BUSY` | 다른 데스크탑 작업 처리 중 |

요청 전에 부팅 ID를 확인하고, 요청 직전에 중복 방지 기록을 남깁니다. 응답이
유실되어도 같은 부팅에는 종료 요청을 재전송하지 않습니다. 재부팅 후 다른
부팅 ID가 확인되면 다시 사용할 수 있습니다. 명시적인 거부·접속 전 오류는
수정 후 다시 요청할 수 있습니다. 중복 방지 기록은 **봇 프로세스 메모리**에
있으므로 봇을 재시작하면 초기화됩니다. 결과 불명 상태에서 재시작했다면 먼저
데스크탑 상태를 직접 확인하세요. 읽기 전용 점검은 이 기록을 초기화하지 않습니다.

Discord 응답은 요청자에게만 보이며 SSH 원문, 주소, 계정명, 키 경로는 포함하지
않습니다. 봇 로그에는 요청자의 Discord ID와 정해진 결과 코드만 기록합니다.
Windows가 종료를 거부하면 숫자 오류 코드도 기록합니다. SSH 원문이나 Windows
오류 원문을 Discord로 반환하지 않습니다. 오류 번호를 받기 전에는 권한 부족,
부팅 상태 변경, 다른 Windows 거부 사유 중 하나로 단정하지 마세요.

## 검증 기록

- 2026-11-11: 운영 환경에서 사용자가 Discord의 `/desktop_off confirm:True`로
  실제 종료하고 `/desktop_on`으로 WOL 재기동하는 것을 확인했습니다.
- 2026-11-13: SSH 직접 종료 방식의 권한 진단을 제거하고, 전용 계정에 별도로
  부여했던 직접 종료 권한을 회수했습니다. 최종 진단은 작업 정의만 조회합니다.
- 정리 전후에 오래된 부팅 ID를 전달하여 SYSTEM worker가 종료 호출 전에
  `BOOT_CHANGED`로 차단되는지 확인했습니다. DLL·worker·작업 호출 helper는
  변경하지 않았습니다. 이 점검에서는 실제 종료를 요청하지 않았습니다.

위 기록은 해당 운영 환경에서의 검증 결과입니다. 다른 데스크탑에 설치할 때는
읽기 전용 점검과 실제 종료·WOL 검증을 각각 수행하세요.

공식 참고: [Windows OpenSSH 키 인증](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_keymanagement),
[Windows OpenSSH 설정](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_server_configuration),
[Windows shutdown](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/shutdown),
[로컬 종료 API](https://learn.microsoft.com/en-us/windows/win32/api/winreg/nf-winreg-initiatesystemshutdownexw),
[Task Scheduler 실행 권한](https://learn.microsoft.com/en-us/windows/win32/taskschd/taskfolder-registertaskdefinition),
[OpenSSH 클라이언트 설정](https://man.openbsd.org/ssh_config).
