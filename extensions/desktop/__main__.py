"""Read-only deployment check: python -m extensions.desktop check."""

import argparse
import asyncio

from dotenv import load_dotenv

from .service import DesktopService


def main() -> int:
    parser = argparse.ArgumentParser(description="Check desktop SSH without shutting it down")
    parser.add_argument("action", choices=("check",))
    parser.parse_args()
    load_dotenv()
    result = asyncio.run(DesktopService().check())
    print(result)
    return 0 if result == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
