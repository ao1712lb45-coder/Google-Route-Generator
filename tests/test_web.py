import pytest
from pydantic import ValidationError

from google_route_generator.web import DayRequest, StopRequest


def make_stops(count: int) -> list[StopRequest]:
    return [StopRequest(name=f"Point {index}", query=f"Point {index}") for index in range(count)]


def test_day_request_accepts_twenty_stops() -> None:
    request = DayRequest(day=1, stops=make_stops(20))

    assert len(request.stops) == 20


def test_day_request_rejects_more_than_twenty_stops() -> None:
    with pytest.raises(ValidationError):
        DayRequest(day=1, stops=make_stops(21))
