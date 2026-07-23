import pytest
from pydantic import ValidationError

from google_route_generator.web import DayRequest, RouteRequest, StopRequest, health


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
