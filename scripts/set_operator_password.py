"""운영자 비밀번호를 해시로 저장한다. 원문은 출력하거나 저장소에 적지 않는다.

uv run python scripts/set_operator_password.py 로그인아이디

비밀번호는 묻거나, OPERATOR_PASSWORD 환경 변수로 받는다.
"""

import getpass
import os
import sys

import _bootstrap  # noqa: F401

from services.operator_password import hash_password
from services.supabase_client import get_operator_by_login_id, update_operator_password


def main() -> int:
    if len(sys.argv) != 2:
        print("사용법: uv run python scripts/set_operator_password.py 로그인아이디")
        return 1
    login_id = sys.argv[1].strip()
    password = os.getenv("OPERATOR_PASSWORD") or getpass.getpass("비밀번호: ")
    if os.getenv("OPERATOR_PASSWORD"):
        again = password
    else:
        again = getpass.getpass("비밀번호 확인: ")
    if password != again or len(password) < 8:
        print("비밀번호가 서로 다르거나 8자보다 짧습니다.")
        return 1
    operator = get_operator_by_login_id(login_id)
    if not operator:
        print("로그인 아이디가 없습니다.")
        return 1
    update_operator_password(int(operator["operator_id"]), hash_password(password))
    print("저장했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
