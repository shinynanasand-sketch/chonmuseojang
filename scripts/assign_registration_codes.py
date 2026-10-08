"""비어 있는 registration_code를 채우고, GB-001을 뺀 엔티티 CSV를 쓴다."""

from pathlib import Path

import _bootstrap  # noqa: F401

import config  # noqa: F401
from services.registration_codes import V001_CODE, plan_registration_codes
from services.supabase_client import list_villages, set_registration_code

OUT = Path(__file__).resolve().parents[1] / "exports" / "registration_code.csv"


def main() -> None:
    villages = list_villages()
    planned = plan_registration_codes(villages)
    for village_id, code in planned:
        set_registration_code(village_id, code)
    codes = {
        str(village.get("registration_code") or "").strip()
        for village in villages
        if str(village.get("registration_code") or "").strip()
    }
    codes.update(code for _, code in planned)
    codes.discard(V001_CODE)
    lines = sorted(codes)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8-sig")
    print(f"saved {len(planned)}")
    print(f"csv {len(lines)} {OUT}")


if __name__ == "__main__":
    main()
