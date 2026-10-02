"""KAKAO_* 환경변수를 Vercel Production에 동기화한다.

.env / .env.local 에 값이 있는 키만 등록합니다. 비어 있으면 건너뜁니다.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / ".env.local", override=False)

KEYS = ("KAKAO_REST_API_KEY", "KAKAO_ADMIN_KEY", "KAKAO_EVENT_API_URL")
SCOPE = "team_xm1wel3gmuxdekRGDRZ5TZBc"


def main() -> int:
    added = 0
    skipped = 0
    for key in KEYS:
        value = (os.getenv(key) or "").strip()
        if not value:
            print(f"  [SKIP] {key} - .env.local has no value")
            skipped += 1
            continue
        cmd = [
            "npx",
            "vercel",
            "env",
            "add",
            key,
            "production",
            "--value",
            value,
            "--yes",
            "--sensitive",
            "--scope",
            SCOPE,
            "--force",
        ]
        print(f"  [ADD] {key}")
        result = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=(os.name == "nt"),
        )
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "")[-500:]
            print(err)
            print(f"  [FAIL] {key}")
            return 1
        added += 1

    # EVENT_API_URL may already exist on Vercel from prior deploy
    print(f"\nDone: added {added}, skipped {skipped}")
    if skipped == len(KEYS):
        print("No Kakao keys to push. Skill webhooks still work without them.")
        return 0
    if skipped:
        print(
            "Fill KAKAO_REST_API_KEY / KAKAO_ADMIN_KEY in .env.local, then re-run this script."
        )
        print("Skill webhooks still work without keys (notifications skipped).")
    if added:
        print("Redeploy with: npx vercel --prod --yes --scope", SCOPE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
