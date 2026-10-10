from services.tourapi import fetch_nearby_attractions


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _Client:
    def __init__(self, payload, captured):
        self._payload = payload
        self._captured = captured

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, params=None):
        self._captured["url"] = url
        self._captured["params"] = params
        return _Response(self._payload)


def _payload():
    return {
        "response": {
            "header": {"resultCode": "0000", "resultMsg": "OK"},
            "body": {
                "items": {
                    "item": [
                        {
                            "title": "대흥사",
                            "addr1": "전라남도 해남군",
                            "contenttypeid": "12",
                            "areacode": "38",
                        },
                        {
                            "title": "해남식당",
                            "addr1": "전라남도 해남군",
                            "contenttypeid": "39",
                            "areacode": "38",
                        },
                        {
                            "title": "서울타워",
                            "addr1": "서울특별시",
                            "contenttypeid": "12",
                            "areacode": "1",
                        },
                    ]
                }
            },
        }
    }


def test_uses_public_data_key_and_base_endpoint(monkeypatch):
    captured = {}
    monkeypatch.delenv("TOUR_API_SERVICE_KEY", raising=False)
    monkeypatch.delenv("TOUR_API_ENDPOINT", raising=False)
    monkeypatch.setenv("PUBLIC_DATA_API_KEY", "shared-key")
    monkeypatch.setenv("TOUR_API_BASE", "https://apis.data.go.kr/B551011/KorService2")
    monkeypatch.setattr(
        "services.tourapi.httpx.Client",
        lambda timeout=10.0: _Client(_payload(), captured),
    )

    result = fetch_nearby_attractions(34.68, 126.66)

    assert captured["url"].endswith("/locationBasedList2")
    assert captured["params"]["serviceKey"] == "shared-key"
    assert result["status"] == "success"
    assert [item["title"] for item in result["attractions"]] == ["대흥사"]
    assert [item["title"] for item in result["restaurants"]] == ["해남식당"]


def test_keeps_representative_photo_and_distance(monkeypatch):
    payload = _payload()
    items = payload["response"]["body"]["items"]["item"]
    items[0]["firstimage"] = "https://example.test/daeheung.jpg"
    items[0]["dist"] = "1200"
    items[1]["firstimage"] = "  "
    items[1]["firstimage2"] = "https://example.test/food.jpg"
    items[1]["dist"] = "800.5"
    monkeypatch.setenv("TOUR_API_SERVICE_KEY", "shared-key")
    monkeypatch.setenv("TOUR_API_ENDPOINT", "https://example.test/tour")
    monkeypatch.setattr(
        "services.tourapi.httpx.Client",
        lambda timeout=10.0: _Client(payload, {}),
    )

    result = fetch_nearby_attractions(34.68, 126.66)

    attraction = result["attractions"][0]
    assert attraction["image_url"] == "https://example.test/daeheung.jpg"
    assert attraction["distance_m"] == 1200.0
    assert attraction["title"] == "대흥사"
    assert attraction["content_type"] == "관광지"
    restaurant = result["restaurants"][0]
    assert restaurant["image_url"] == "https://example.test/food.jpg"
    assert restaurant["distance_m"] == 800.5


def test_blank_photo_stays_empty(monkeypatch):
    payload = _payload()
    item = payload["response"]["body"]["items"]["item"][0]
    item["firstimage"] = ""
    item["firstimage2"] = "not-a-url"
    monkeypatch.setenv("TOUR_API_SERVICE_KEY", "shared-key")
    monkeypatch.setenv("TOUR_API_ENDPOINT", "https://example.test/tour")
    monkeypatch.setattr(
        "services.tourapi.httpx.Client",
        lambda timeout=10.0: _Client(payload, {}),
    )

    result = fetch_nearby_attractions(34.68, 126.66)

    assert result["attractions"][0]["image_url"] == ""
    assert result["attractions"][0]["distance_m"] is None


def test_returns_unavailable_when_call_fails(monkeypatch):
    monkeypatch.setenv("TOUR_API_SERVICE_KEY", "shared-key")
    monkeypatch.setenv("TOUR_API_ENDPOINT", "https://example.test/tour")

    class _Broken:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, params=None):
            raise TimeoutError("timeout")

    monkeypatch.setattr("services.tourapi.httpx.Client", lambda timeout=10.0: _Broken())

    result = fetch_nearby_attractions(34.68, 126.66)
    assert result["status"] == "unavailable"
    assert result["attractions"] == []
    assert result["restaurants"] == []
