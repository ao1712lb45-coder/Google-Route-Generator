from datetime import date

from google_route_generator.pdf_parser import parse_stops


def test_parse_stops_preserves_order() -> None:
    stops = parse_stops("2026-08-01 - Taipei 101\n02/08/2026 | Sun Moon Lake")

    assert [stop.name for stop in stops] == ["Taipei 101", "Sun Moon Lake"]
    assert stops[0].day == date(2026, 8, 1)


def test_parse_stops_ignores_undated_lines() -> None:
    assert parse_stops("Packing list\nBring a passport") == []
