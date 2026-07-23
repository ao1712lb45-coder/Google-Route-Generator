"""Geocoding and road-routing services with free-provider fallbacks."""

from __future__ import annotations

import json
import os
import time
from math import asin, cos, isfinite, radians, sin, sqrt
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
        candidates = self.geocode_candidates(query)
        return candidates[0] if candidates else None

    def geocode_candidates(
        self, query: str, limit: int = 5, preferred_country: str | None = None
    ) -> list[dict]:
        country = (preferred_country or "").strip().lower()
        scoped_query = f"{query}|{country}" if country else query
        if self.geoapify_key:
            try:
                result = self._cached_geocode(
                    "geoapify-candidates",
                    scoped_query,
                    lambda _: self._geoapify_candidates(query, country),
                )
                if result:
                    return result[:limit]
            except requests.RequestException:
                pass
        result = self._cached_geocode(
            "nominatim-candidates",
            scoped_query,
            lambda _: self._nominatim_candidates(query, country),
        )
        return (result or [])[:limit]

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

    def _geoapify_candidates(self, query: str, country: str = "") -> list[dict]:
        params = {
            "text": query,
            "format": "json",
            "limit": 5,
            "lang": "zh",
            "apiKey": self.geoapify_key,
        }
        if country:
            params["filter"] = f"countrycode:{country}"
        response = self.session.get(
            "https://api.geoapify.com/v1/geocode/search",
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        rows = response.json().get("results", [])
        return [
            {
                "latitude": float(row["lat"]),
                "longitude": float(row["lon"]),
                "display_name": row.get("formatted", query),
                "country_code": (row.get("country_code") or "").lower(),
                "provider": "Geoapify",
            }
            for row in rows
        ]

    def _nominatim_candidates(self, query: str, country: str = "") -> list[dict]:
        with self.lock:
            delay = 1.05 - (time.monotonic() - self.last_nominatim_request)
            if delay > 0:
                time.sleep(delay)
            self.last_nominatim_request = time.monotonic()
        params = {
            "q": query,
            "format": "jsonv2",
            "limit": 5,
            "addressdetails": 1,
            "accept-language": "zh-TW",
        }
        if country:
            params["countrycodes"] = country
        response = self.session.get(
            "https://nominatim.openstreetmap.org/search",
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        rows = response.json()
        return [
            {
                "latitude": float(row["lat"]),
                "longitude": float(row["lon"]),
                "display_name": row.get("display_name", query),
                "country_code": row.get("address", {}).get("country_code", "").lower(),
                "provider": "OpenStreetMap Nominatim",
            }
            for row in rows
        ]

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


def select_coherent_locations(
    candidate_groups: list[list[dict]], stop_names: list[str]
) -> list[dict | None]:
    """Choose a plausible candidate chain and avoid accidental border crossings."""
    if not candidate_groups:
        return []
    groups: list[list[dict | None]] = [group or [None] for group in candidate_groups]
    costs: list[list[float]] = []
    parents: list[list[int | None]] = []
    for index, candidates in enumerate(groups):
        if index == 0:
            costs.append([rank * 8.0 for rank in range(len(candidates))])
            parents.append([None] * len(candidates))
            continue
        row_costs, row_parents = [], []
        for rank, candidate in enumerate(candidates):
            options = [
                previous_cost
                + rank * 8.0
                + _transition_cost(previous, candidate, stop_names[index - 1], stop_names[index])
                for previous_cost, previous in zip(costs[-1], groups[index - 1])
            ]
            best_parent = min(range(len(options)), key=options.__getitem__)
            row_costs.append(options[best_parent])
            row_parents.append(best_parent)
        costs.append(row_costs)
        parents.append(row_parents)
    choice = min(range(len(costs[-1])), key=costs[-1].__getitem__)
    selected: list[dict | None] = []
    for index in range(len(groups) - 1, -1, -1):
        selected.append(groups[index][choice])
        if parents[index][choice] is not None:
            choice = parents[index][choice]  # type: ignore[assignment]
    return list(reversed(selected))


def _transition_cost(first, second, first_name: str, second_name: str) -> float:
    if first is None or second is None:
        return 100_000.0
    distance = _haversine_km(first, second)
    countries = (first.get("country_code"), second.get("country_code"))
    names = f"{first_name} {second_name}".lower()
    airport_segment = any(token in names for token in ("機場", "空港", "airport"))
    if all(countries) and countries[0] != countries[1] and not airport_segment:
        distance += 50_000.0
    return distance


def _haversine_km(first: dict, second: dict) -> float:
    lat1, lon1 = radians(first["latitude"]), radians(first["longitude"])
    lat2, lon2 = radians(second["latitude"]), radians(second["longitude"])
    delta_lat, delta_lon = lat2 - lat1, lon2 - lon1
    value = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(value))
