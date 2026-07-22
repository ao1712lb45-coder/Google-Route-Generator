# Google Route Generator

Generate polished, interactive travel route maps from itinerary PDFs.

## Features

- Extracts itinerary text from PDF files
- Detects dated stops and location-like lines
- Geocodes stops with OpenStreetMap Nominatim
- Produces a professional, numbered Folium route map
- Keeps parsing, geocoding, and rendering separate for easy extension

## Quick start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
route-map itinerary.pdf --output trip-map.html
```

Geocoding uses a public service by default. For production or higher-volume use,
provide a commercial geocoder by implementing the `Geocoder` protocol.

## Project layout

```text
src/google_route_generator/  application package
tests/                       automated tests
```

## Development

```powershell
pytest
ruff check .
```
