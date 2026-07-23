"""Geocoding and road-routing services with free-provider fallbacks."""

from __future__ import annotations

import json
import os
import time
from math import isfinite
from pathlib import Path
from threading import Lock

import requests


class MapServices:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Google-Route-Generator/0.2"})
        self.geoapify_key = os.getenv("GEOAPIFY_API_KEY", "").strip()
        self.openrouteservice_key = os.getenv("OPENROUTESERVICE_API_KEY", "").strip()
        self.cache_path = Path(os.getenv("ROUTE_CACHE_PATH", ".cache/locations.json"))
        self.cache: dict[str, dict | None] = self._load_cache()
        self.lock = Lock()
        self.last_nominatim_request = 0.0

    def geocode(self, query: str) -> dict | None:
        if self.geoapify_key:
            try:
                result = self._cached_geocode("geoapify", query, self._geoapify_geocode)
                if result:
                    return result
            except requests.RequestException:
                pass
        return self._cached_geocode("nominatim", query, self._nominatim_geocode)

    def route(self, stops: list[dict]) -> dict | None:
        points = [
            stop
            for stop in stops
            if _valid_coordinate(stop.get("latitude"), stop.get("longitude"))
        ]
        if len(points) < 2:
            return None
        if self.openrouteservice_key:
            try:
                result = self._openrouteservice_route(points)
                if result:
                    return result
            except requests.RequestException:
                pass
        return self._osrm_route(points)

    def provider_status(self) -> dict:
        return {
            "geocoding": "Geoapify（免費額度）"
            if self.geoapify_key
            else "OpenStreetMap Nominatim（備援）",
            "routing": "openrouteservice（免費額度）"
            if self.openrouteservice_key
            else "OSRM（備援）",
            "geoapify_configured": bool(self.geoapify_key),
            "openrouteservice_configured": bool(self.openrouteservice_key),
        }

    def _cached_geocode(self, provider: str, query: str, lookup) -> dict | None:
        key = f"{provider}:{query.strip().casefold()}"
        with self.lock:
            if key in self.cache:
                return self.cache[key]
        result = lookup(query)
        with self.lock:
            self.cache[key] = result
            self._save_cache()
        return result

    def _geoapify_geocode(self, query: str) -> dict | None:
        response = self.session.get(
            "https://api.geoapify.com/v1/geocode/search",
            params={
                "text": query,
                "format": "json",
                "limit": 1,
                "lang": "zh",
                "apiKey": self.geoapify_key,
            },
            timeout=20,
        )
        response.raise_for_status()
        rows = response.json().get("results", [])
        if not rows:
            return None
        return {
            "latitude": float(rows[0]["lat"]),
            "longitude": float(rows[0]["lon"]),
            "display_name": rows[0].get("formatted", query),
            "provider": "Geoapify",
        }

    def _nominatim_geocode(self, query: str) -> dict | None:
        with self.lock:
            delay = 1.05 - (time.monotonic() - self.last_nominatim_request)
            if delay > 0:
                time.sleep(delay)
            self.last_nominatim_request = time.monotonic()
        response = self.session.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "jsonv2", "limit": 1, "accept-language": "zh-TW"},
            timeout=20,
        )
        response.raise_for_status()
        rows = response.json()
        if not rows:
            return None
        return {
            "latitude": float(rows[0]["lat"]),
            "longitude": float(rows[0]["lon"]),
            "display_name": rows[0].get("display_name", query),
            "provider": "OpenStreetMap Nominatim",
        }

    def _openrouteservice_route(self, points: list[dict]) -> dict | None:
        response = self.session.post(
            "https://api.openrouteservice.org/v2/directions/driving-car/geojson",
            headers={"Authorization": self.openrouteservice_key, "Content-Type": "application/json"},
            json={
                "coordinates": [[point["longitude"], point["latitude"]] for point in points],
                "instructions": False,
            },
            timeout=35,
        )
        response.raise_for_status()
        features = response.json().get("features", [])
        if not features:
            return None
        feature = features[0]
        summary = feature.get("properties", {}).get("summary", {})
        return {
            "distance_km": round(float(summary["distance"]) / 1000, 1),
            "duration_minutes": round(float(summary["duration"]) / 60),
            "geometry": feature["geometry"],
            "provider": "openrouteservice",
        }

    def _osrm_route(self, points: list[dict]) -> dict | None:
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
            "provider": "OSRM",
        }

    def _load_cache(self) -> dict:
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_cache(self) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(
                json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:
            pass


def _valid_coordinate(latitude, longitude) -> bool:
    return (
        isinstance(latitude, (int, float))
        and isinstance(longitude, (int, float))
        and isfinite(latitude)
        and isfinite(longitude)
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
    )
