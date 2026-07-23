import pytest

from google_route_generator.web_itinerary import (
    parse_besttour_schedule,
    parse_web_itinerary_html,
    validate_itinerary_url,
)


def test_validate_itinerary_url_accepts_supported_sites() -> None:
    assert validate_itinerary_url("https://orient-2.ittms.com.tw/web/trip.asp?id=1")
    assert validate_itinerary_url("https://www.besttour.com.tw/itinerary/ABC123")


def test_validate_itinerary_url_rejects_other_hosts() -> None:
    with pytest.raises(ValueError):
        validate_itinerary_url("http://127.0.0.1/internal")


def test_parse_web_itinerary_uses_previous_lodging() -> None:
    html = """
    <html><head><title>東京五日遊</title></head><body>
      <h4>第 4 天 全日自由活動</h4>
      <div>住宿：品川王子大飯店 或 太陽城王子同級</div>
      <h4>第 5 天 免稅店-淺草觀音寺～雷門、仲見世商店街-成田國際空港✈桃園國際機場</h4>
      <div>住宿：溫暖的家</div>
    </body></html>
    """

    result = parse_web_itinerary_html(html)

    assert [stop["name"] for stop in result["days"][1]["stops"]] == [
        "品川王子大飯店",
        "免稅店",
        "淺草觀音寺",
        "成田國際空港",
        "桃園國際機場",
    ]


def test_parse_besttour_schedule_uses_api_heading_and_hotel() -> None:
    payload = {
        "status": "0",
        "data": [
            {
                "day": "1",
                "abstract_1": "桃園／吉隆坡→布城→飯店",
                "hotel": {"data": [{"name": "吉隆坡艾美酒店"}]},
            },
            {
                "day": "2",
                "abstract_1": "吉隆坡→雙子星塔",
                "hotel": {"data": [{"name": "大紅花海上渡假村"}]},
            },
        ],
    }

    result = parse_besttour_schedule(payload)

    assert [stop["name"] for stop in result["days"][1]["stops"]] == [
        "吉隆坡艾美酒店",
        "吉隆坡",
        "雙子星塔",
    ]
