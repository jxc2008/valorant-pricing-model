"""Operator-gated Kalshi auth smoke test (RESEARCH Pitfall 8 mitigation).

Signs a GET /trade-api/v2/exchange/status request with the operator's
`.env` credentials and asserts a 200 response. Run ONCE after first
checkout to verify the .env works:

    python scripts/kalshi_auth_smoke.py

The dry-run wrapper in production code shortcuts ALL Kalshi calls in
dev (KALSHI_KEY_PATH not in .env), so the auth signing path never
runs in production code paths until --live mode. This script gives
operators a no-`--live` way to validate auth.

Exit codes:
    0 — success (signed request returned 200)
    1 — .env missing or KALSHI_KEY_ID / KALSHI_KEY_PATH not set
    2 — non-200 response (auth failure or Kalshi-side issue)
"""
from __future__ import annotations

import asyncio
import os
import sys

import aiohttp
from dotenv import load_dotenv

from src.config.constants import KALSHI_BASE_URL
from src.quoting.kalshi_auth import load_private_key, sign_request


async def _run() -> int:
    load_dotenv()
    key_id = os.getenv("KALSHI_KEY_ID")
    key_path = os.getenv("KALSHI_KEY_PATH")
    if not key_id or not key_path:
        print(
            "ERROR: KALSHI_KEY_ID and KALSHI_KEY_PATH must be in .env",
            file=sys.stderr,
        )
        return 1

    private_key = load_private_key(key_path)
    path = "/trade-api/v2/exchange/status"
    headers = sign_request(key_id, private_key, "GET", path)
    async with aiohttp.ClientSession() as session:
        async with session.get(KALSHI_BASE_URL + "/exchange/status", headers=headers) as r:
            if r.status == 200:
                body = await r.json()
                print(f"OK status={r.status} body={body}")
                return 0
            print(f"FAIL status={r.status} body={await r.text()}", file=sys.stderr)
            return 2


if __name__ == "__main__":
    sys.exit(asyncio.run(_run()))
