import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

_SPEC = importlib.util.spec_from_file_location(
    "set_operator_password", _SCRIPTS / "set_operator_password.py"
)
_MODULE = importlib.util.module_from_spec(_SPEC)
assert _SPEC is not None and _SPEC.loader is not None
_SPEC.loader.exec_module(_MODULE)


def test_source_lists_the_three_operator_passwords():
    entries = _MODULE.load_passwords()
    assert set(entries) == {"dosun9947", "owner_v002", "owner_v001"}
    assert all(len(password) >= 8 for password in entries.values())


def test_short_password_is_not_stored():
    from services.supabase_client import get_operator_by_login_id

    before = get_operator_by_login_id("owner_v001").get("password_hash")
    assert _MODULE.apply_passwords({"owner_v001": "12345"}) == 1
    assert get_operator_by_login_id("owner_v001").get("password_hash") == before


def test_listed_password_is_stored_as_a_hash():
    from services.operator_password import verify_password
    from services.supabase_client import get_operator_by_login_id, update_operator_password

    operator = get_operator_by_login_id("owner_v001")
    before = operator.get("password_hash")
    password = _MODULE.load_passwords()["owner_v001"]
    assert _MODULE.apply_passwords({"owner_v001": password}) == 0
    stored = get_operator_by_login_id("owner_v001").get("password_hash")
    assert stored != password
    assert verify_password(password, stored)
    if before:
        update_operator_password(int(operator["operator_id"]), before)
    else:
        update_operator_password(int(operator["operator_id"]), "")
