"""운영자 비밀번호를 해시로 저장한다. 원문은 출력하지 않는다.

비밀번호 문장은 scripts/operator_passwords.py에 있다.

uv run python scripts/set_operator_password.py
uv run python scripts/set_operator_password.py 로그인아이디
"""

import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from services.operator_password import hash_password
from services.supabase_client import get_operator_by_login_id, update_operator_password

_MIN_LENGTH = 8


def load_passwords() -> dict[str, str]:
    import importlib.util

    path = Path(__file__).with_name("operator_passwords.py")
    spec = importlib.util.spec_from_file_location("operator_passwords", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("비밀번호 파일을 열지 못했습니다.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {str(login_id): str(password) for login_id, password in module.PASSWORDS.items()}


def apply_passwords(entries: dict[str, str]) -> int:
    for login_id, password in entries.items():
        if len(password) < _MIN_LENGTH:
            print("비밀번호가 8자보다 짧습니다.")
            return 1
        operator = get_operator_by_login_id(login_id)
        if not operator:
            print("로그인 아이디가 없습니다.")
            return 1
        update_operator_password(int(operator["operator_id"]), hash_password(password))
    print("저장했습니다.")
    return 0


def main() -> int:
    if len(sys.argv) > 2:
        print("사용법: uv run python scripts/set_operator_password.py [로그인아이디]")
        return 1
    entries = load_passwords()
    if len(sys.argv) == 2:
        login_id = sys.argv[1].strip()
        if login_id not in entries:
            print("로그인 아이디가 없습니다.")
            return 1
        entries = {login_id: entries[login_id]}
    return apply_passwords(entries)


if __name__ == "__main__":
    raise SystemExit(main())
