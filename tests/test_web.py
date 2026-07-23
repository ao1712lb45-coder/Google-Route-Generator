import pytest
from pydantic import ValidationError

from google_route_generator import web
from google_route_generator.web import (
    DayRequest,
    RouteRequest,
    StopRequest,
    _infer_destination_country,
    _formalize_place_query,
    _needs_place_confirmation,
    health,
)


def make_stops(count: int) -> list[StopRequest]:
    return [StopRequest(name=f"Point {index}", query=f"Point {index}") for index in range(count)]


def test_day_request_accepts_twenty_stops() -> None:
    request = DayRequest(day=1, stops=make_stops(20))

    assert len(request.stops) == 20


def test_day_request_rejects_more_than_twenty_stops() -> None:
    with pytest.raises(ValidationError):
        DayRequest(day=1, stops=make_stops(21))


def test_route_request_accepts_fourteen_days() -> None:
    request = RouteRequest(days=[DayRequest(day=index + 1, stops=[]) for index in range(14)])

    assert len(request.days) == 14


def test_route_request_rejects_more_than_fourteen_days() -> None:
    with pytest.raises(ValidationError):
        RouteRequest(days=[DayRequest(day=index + 1, stops=[]) for index in range(15)])


def test_health_endpoint_payload() -> None:
    assert health() == {"status": "ok"}


def test_japan_itinerary_infers_destination_country() -> None:
    stops = ["桃園國際機場", "成田國際空港", "鎌倉古街散策", "江之島電鐵", "淺草觀音寺"]

    assert _infer_destination_country(stops) == "jp"


def test_fuzzy_kamakura_description_becomes_official_place_query() -> None:
    query, rewritten = _formalize_place_query("鎌倉古街散策")

    assert query == "小町通 鎌倉"
    assert rewritten is True
    assert _needs_place_confirmation("鎌倉古街散策", rewritten) is True


def test_fuzzy_stop_requires_candidate_confirmation(monkeypatch) -> None:
    candidate = {
        "latitude": 35.32,
        "longitude": 139.55,
        "display_name": "小町通, 鎌倉市, 日本",
        "country_code": "jp",
        "provider": "test",
    }
    monkeypatch.setattr(web.services, "geocode_candidates", lambda *args, **kwargs: [candidate])
    request = RouteRequest(
        days=[DayRequest(day=1, stops=[StopRequest(name="鎌倉古街散策", query="鎌倉古街散策")])]
    )

    result = web.build_routes(request)

    assert result["needs_confirmation"] is True
    assert result["days"][0]["stops"][0]["status"] == "needs_confirmation"
    assert result["days"][0]["stops"][0]["candidates"][0]["country_code"] == "jp"
