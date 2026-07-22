"""Geocoding and road-routing services used by the web application."""

from __future__ import annotations

from math import isfinite
from threading import Lock

import requests


class MapServices:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Google-Route-Generator/0.2"})
        self.cache: dict[str, dict | None] = {}
        self.lock = Lock()

    def geocode(self, query: str) -> dict | None:
        key = query.strip().casefold()
        with self.lock:
            if key in self.cache:
                return self.cache[key]
        response = self.session.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "jsonv2", "limit": 1, "accept-language": "zh-TW"},
            timeout=20,
        )
        response.raise_for_status()
        rows = response.json()
        result = None
        if rows:
            result = {
                "latitude": float(rows[0]["lat"]),
                "longitude": float(rows[0]["lon"]),
                "display_name": rows[0].get("display_name", query),
            }
        with self.lock:
            self.cache[key] = result
        return result

    def route(self, stops: list[dict]) -> dict | None:
        points = [
            stop
            for stop in stops
            if _valid_coordinate(stop.get("latitude"), stop.get("longitude"))
        ]
        if len(points) < 2:
            return None
        coordinates = ";".join(f'{point["longitude"]},{point["latitude"]}' for point in points)
        response = self.session.get(
            f"https://router.project-osrm.org/route/v1/driving/{coordinates}",
            params={"overview": "full", "geometries": "geojson", "steps": "false"},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != "Ok" or not payload.get("routes"):
            return None
        route = payload["routes"][0]
        return {
            "distance_km": round(route["distance"] / 1000, 1),
            "duration_minutes": round(route["duration"] / 60),
            "geometry": route["geometry"],
        }


def _valid_coordinate(latitude, longitude) -> bool:
    return (
        isinstance(latitude, (int, float))
        and isinstance(longitude, (int, float))
        and isfinite(latitude)
        and isfinite(longitude)
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
    )
