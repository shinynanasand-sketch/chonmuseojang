"""V001 시연 로그인·예약·후기를 Supabase 또는 인메모리에 넣는다."""

import _bootstrap  # noqa: F401

import config  # noqa: F401
from services.demo_fixtures import load_demo_fixtures


if __name__ == "__main__":
    result = load_demo_fixtures()
    print(
        "login_id={login_id} pending={pending_booking_id} "
        "confirmed={confirmed_booking_id} review={review_id}".format(**result)
    )
