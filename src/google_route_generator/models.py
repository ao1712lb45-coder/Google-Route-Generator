"""Core domain models."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class ItineraryStop:
    """A stop extracted from an itinerary."""

    name: str
    day: date | None = None
    details: str = ""
    latitude: float | None = None
    longitude: float | None = None

    @property
    def is_geocoded(self) -> bool:
        return self.latitude is not None and self.longitude is not None

