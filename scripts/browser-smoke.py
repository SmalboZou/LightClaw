from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from lightclaw.infrastructure.browser.service import PlaywrightBrowserService


async def _run(url: str, headless: bool, profile_root: Path | None) -> dict[str, object]:
    service = PlaywrightBrowserService()
    try:
        session = await service.open_session(
            session_name="browser-smoke",
            headless=headless,
            start_url=url,
            persistent_profile=profile_root is not None,
            profile_root=profile_root,
        )
        snapshot = await service.snapshot(str(session["session_id"]))
        await service.close(str(session["session_id"]))
        return {
            "session": session,
            "snapshot": snapshot.to_payload(),
        }
    finally:
        await service.aclose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a Playwright browser smoke check.")
    parser.add_argument("--url", default="https://example.com", help="Page to open.")
    parser.add_argument("--headed", action="store_true", help="Run with a visible browser window.")
    parser.add_argument(
        "--profile-root",
        type=Path,
        default=None,
        help="Enable persistent context at the given profile root.",
    )
    args = parser.parse_args()

    payload = asyncio.run(
        _run(
            url=args.url,
            headless=not args.headed,
            profile_root=args.profile_root.resolve() if args.profile_root else None,
        )
    )
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
