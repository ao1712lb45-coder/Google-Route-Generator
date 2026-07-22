"""End-to-end route generation pipeline."""

from pathlib import Path

from .geocoding import default_geocoder, geocode_stops
from .map_renderer import render_map
from .pdf_parser import parse_pdf


def generate_route_map(pdf_path: Path, output_path: Path, title: str = "Travel Route") -> Path:
    stops = parse_pdf(pdf_path)
    if not stops:
        raise ValueError("No dated itinerary stops were found in the PDF.")
    return render_map(geocode_stops(stops, default_geocoder()), output_path, title)

