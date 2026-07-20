import time
import datetime
import subprocess

from config import (
    AUTO_SHUTDOWN_ENABLED,
    AUTO_SHUTDOWN_TIME,
    CHECK_INTERVAL,
    STOP_SCRIPT
)

from palworld_api import get_players

empty_since = None

print("Auto Shutdown Monitor 시작")

while True:

    try:
        players = get_players()

        # 플레이어가 있음
        if len(players) > 0:

            if empty_since is not None:
                print("플레이어 접속 확인 - 타이머 초기화")

            empty_since = None

        # 플레이어가 없음
        else:

            if empty_since is None:

                empty_since = datetime.datetime.now()

                print(f"플레이어 없음 - 타이머 시작 ({empty_since})")

            else:

                elapsed = datetime.datetime.now() - empty_since

                print(f"플레이어 없음 {elapsed}")

                if (
                    AUTO_SHUTDOWN_ENABLED
                    and elapsed >= AUTO_SHUTDOWN_TIME
                ):

                    print("자동 종료 실행")

                    result = subprocess.run(
                        ["sudo", STOP_SCRIPT]
                    )
                    if result.returncode == 0:
                        print("AUTO_SHUTDOWN",flush=True)
                        break
                    else:
                        print("AUTO_SHUTDOWN_FAILED",flush=True)

                    break

    except Exception as e:

        print(f"[ERROR] {e}")

    time.sleep(CHECK_INTERVAL)
