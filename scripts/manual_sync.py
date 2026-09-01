"""로컬에서 수동으로 공공데이터 동기화를 실행한다."""

import argparse

import _bootstrap  # noqa: F401

from services.public_data_sync import sync_village_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo-only", action="store_true", help="공공 API 없이 시연 시드만 로드")
    args = parser.parse_args()

    if args.demo_only:
        from scripts.load_demo_seed import load_demo_seed

        print(load_demo_seed())
    else:
        print(sync_village_data(use_demo_fallback=True))
