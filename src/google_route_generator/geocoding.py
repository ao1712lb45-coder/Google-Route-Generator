"""Geocoding abstraction and a rate-limited default implementation."""

from dataclasses import replace
from typing import Protocol

from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim

from .models import ItineraryStop


class Geocoder(Protocol):
    def geocode(self, query: str): ...


def default_geocoder() -> Geocoder:
    client = Nominatim(user_agent="google-route-generator/0.1")
    return RateLimiter(client.geocode, min_delay_seconds=1)


def geocode_stops(stops: list[ItineraryStop], geocoder: Geocoder) -> list[ItineraryStop]:
    """Return successfully geocoded stops while preserving itinerary order."""
    result: list[ItineraryStop] = []
    for stop in stops:
        location = geocoder.geocode(stop.name)
        if location is not None:
            result.append(replace(stop, latitude=location.latitude, longitude=location.longitude))
    return result

