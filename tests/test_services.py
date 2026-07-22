from google_route_generator.services import MapServices


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "code": "Ok",
            "routes": [
                {
                    "distance": 12500,
                    "duration": 1800,
                    "geometry": {"type": "LineString", "coordinates": [[4.8, 52.3], [4.9, 52.4]]},
                }
            ],
        }


def test_route_summary(monkeypatch) -> None:
    service = MapServices()
    monkeypatch.setattr(service.session, "get", lambda *args, **kwargs: FakeResponse())

    route = service.route(
        [
            {"latitude": 52.3, "longitude": 4.8},
            {"latitude": 52.4, "longitude": 4.9},
        ]
    )

    assert route["distance_km"] == 12.5
    assert route["duration_minutes"] == 30
