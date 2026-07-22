"""PDF text extraction and conservative itinerary parsing."""

import re
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader

from .models import ItineraryStop

DATE_LINE = re.compile(
    r"^(?P<date>\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})"
    r"\s*(?:[-–—:|]\s*)?(?P<place>.+)$"
)


def extract_text(pdf_path: Path) -> str:
    """Extract text from every page of a PDF."""
    reader = PdfReader(pdf_path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def parse_stops(text: str) -> list[ItineraryStop]:
    """Parse stops written as `YYYY-MM-DD - Place` or `DD/MM/YYYY - Place`."""
    stops: list[ItineraryStop] = []
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        match = DATE_LINE.match(line)
        if not match:
            continue
        day = _parse_date(match.group("date"))
        place = match.group("place").strip(" -–—:|")
        if day and place:
            stops.append(ItineraryStop(name=place, day=day))
    return stops


def parse_pdf(pdf_path: Path) -> list[ItineraryStop]:
    return parse_stops(extract_text(pdf_path))


def _parse_date(value: str):
    normalized = value.replace("/", "-")
    for pattern in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(normalized, pattern).date()
        except ValueError:
            pass
    return None

