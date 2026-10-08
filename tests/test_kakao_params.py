from models.kakao_schemas import KakaoSkillRequest
from services.kakao_params import (
    booking_id_from_params,
    param_origin,
    parse_sys_date,
    parse_sys_number,
    representative,
)


def test_parse_sys_number_accepts_plain_json_and_object():
    assert parse_sys_number(None) is None
    assert parse_sys_number("") is None
    assert parse_sys_number("7") == 7
    assert parse_sys_number(7) == 7
    assert parse_sys_number('{"amount":7,"unit":"번"}') == 7
    assert parse_sys_number({"amount": 7, "unit": "번"}) == 7
    assert parse_sys_number("7번") is None
    assert parse_sys_number("{") is None


def test_parse_sys_date_accepts_plain_and_json():
    assert parse_sys_date("2026-10-08") == "2026-10-08"
    assert parse_sys_date('{"date":"2026-10-08"}') == "2026-10-08"
    assert parse_sys_date('{"value":"2026-10-08"}') == "2026-10-08"
    assert parse_sys_date({"date": "2026-10-08"}) == "2026-10-08"
    assert parse_sys_date("내일") is None
    assert parse_sys_date("{") is None


def test_booking_id_uses_representative_not_origin():
    params = {"booking_id": '{"amount":7,"unit":"번"}'}
    detail = {"booking_id": {"origin": "7번", "value": params["booking_id"]}}
    assert representative(params, "booking_id") == params["booking_id"]
    assert param_origin(detail, "booking_id") == "7번"
    assert booking_id_from_params(params) == 7
    assert booking_id_from_params({}) is None


def test_skill_request_keeps_intent_and_detail_params():
    payload = KakaoSkillRequest.model_validate(
        {
            "intent": {"name": "예약승인"},
            "action": {
                "params": {"booking_id": "7"},
                "detailParams": {"booking_id": {"origin": "7번"}},
            },
        }
    )
    assert payload.intent.name == "예약승인"
    assert payload.action.detailParams["booking_id"]["origin"] == "7번"
