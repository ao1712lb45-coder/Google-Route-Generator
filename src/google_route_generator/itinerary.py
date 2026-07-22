"""Parse itinerary PDFs into editable day-by-day route candidates."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader


DAY_PATTERN = re.compile(r"第\s*(\d{1,2})\s*天")
SEPARATOR_PATTERN = re.compile(r"\s*(?:－|—|–|→|～|~|-)\s*")
MEAL_PATTERN = re.compile(r"^(?:早餐|中餐|午餐|晚餐|住宿)[:：]")

ALIASES = {
    "阿姆斯特丹史基浦機場": "Amsterdam Airport Schiphol, Netherlands",
    "阿姆斯特丹機場": "Amsterdam Airport Schiphol, Netherlands",
    "桑斯安斯風車村": "Zaanse Schans, Netherlands",
    "沃倫丹漁村": "Volendam, Netherlands",
    "羊角村": "Giethoorn, Netherlands",
    "梵谷國家森林公園": "Hoge Veluwe National Park, Netherlands",
    "庫勒慕勒美術館": "Kroller-Muller Museum, Otterlo, Netherlands",
    "阿姆斯特丹王宮": "Royal Palace Amsterdam, Netherlands",
    "水壩廣場": "Dam Square, Amsterdam, Netherlands",
    "玻璃船遊運河": "Amsterdam Centraal, Netherlands",
    "阿姆斯特丹": "Amsterdam, Netherlands",
    "桃園": "Taiwan Taoyuan International Airport",
}


@dataclass(slots=True)
class ParsedStop:
    name: str
    query: str
    status: str = "pending"
    latitude: float | None = None
    longitude: float | None = None
    note: str = ""

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "query": self.query,
            "status": self.status,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "note": self.note,
        }


@dataclass(slots=True)
class ParsedDay:
    day: int
    title: str
    stops: list[ParsedStop] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"day": self.day, "title": self.title, "stops": [stop.as_dict() for stop in self.stops]}


def extract_pdf_text(path: Path) -> str:
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def parse_itinerary(path: Path) -> dict:
    text = extract_pdf_text(path)
    title = _extract_title(text)
    days = _extract_days(text)
    return {"title": title, "days": [day.as_dict() for day in days]}


def _extract_title(text: str) -> str:
    for line in text.splitlines():
        clean = " ".join(line.split())
        if ("【" in clean or "[" in clean) and re.search(r"\d+\s*[日天]", clean):
            return re.sub(r"^旅遊名稱\s*", "", clean).strip("【】[] ")
    return "旅遊路線地圖"


def _extract_days(text: str) -> list[ParsedDay]:
    matches = list(DAY_PATTERN.finditer(text))
    days: list[ParsedDay] = []
    for index, match in enumerate(matches):
        block = text[match.end() : matches[index + 1].start() if index + 1 < len(matches) else len(text)]
        route_line = _leading_route_line(block)
        if not route_line:
            continue
        stops = [] if _is_flight_day(route_line) else _split_stops(route_line)
        days.append(ParsedDay(day=int(match.group(1)), title=route_line, stops=stops))
    return days


def _leading_route_line(block: str) -> str:
    lines = block.replace("\r", "").split("\n")
    collected: list[str] = []
    started = False
    for raw in lines:
        clean = " ".join(raw.split())
        if not clean:
            if started:
                break
            continue
        if MEAL_PATTERN.match(clean):
            break
        started = True
        collected.append(clean)
        if len(" ".join(collected)) > 280 or len(collected) >= 4:
            break
    return " ".join(collected).strip()


def _split_stops(route_line: str) -> list[ParsedStop]:
    known = _known_stops(route_line)
    if known:
        return [ParsedStop(name=name, query=ALIASES[name]) for name in known]
    pieces = SEPARATOR_PATTERN.split(route_line)
    results: list[ParsedStop] = []
    for piece in pieces:
        name = _clean_stop(piece)
        if not name or _is_non_location(name):
            continue
        query = _query_for(name)
        if results and results[-1].query.casefold() == query.casefold():
            continue
        results.append(ParsedStop(name=name, query=query))
    return results


def _known_stops(route_line: str) -> list[str]:
    candidates: list[tuple[int, int, str]] = []
    for name in ALIASES:
        for match in re.finditer(re.escape(name), route_line):
            candidates.append((match.start(), match.end(), name))
    candidates.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    selected: list[tuple[int, int, str]] = []
    for candidate in candidates:
        start, end, _ = candidate
        if any(start < current_end and end > current_start for current_start, current_end, _ in selected):
            continue
        selected.append(candidate)
    selected.sort()
    return [name for _, _, name in selected]


def _is_flight_day(route_line: str) -> bool:
    return bool(
        re.search(r"\b(?:TPE|AMS)\s*/\s*(?:TPE|AMS)\b", route_line, re.I)
        or re.search(r"\bCI\d{3,4}\b", route_line, re.I)
        or "溫暖的家" in route_line
    )


def _clean_stop(value: str) -> str:
    value = re.sub(r"^(?:抵達|返回|前往|準備登機)\s*", "", value.strip())
    value = re.sub(r"\s+(?:TPE|AMS)(?:/[A-Z]{3})?.*$", "", value, flags=re.I)
    value = re.sub(r"\s+(?:Amsterdam|Giethoorn)\b", "", value, flags=re.I)
    value = re.sub(r"\([^)]*(?:含|派車|Audio|兩人|DIY|木鞋|起司)[^)]*\)", "", value, flags=re.I)
    return " ".join(value.strip(" -－—–~～|：:").split())


def _is_non_location(value: str) -> bool:
    return bool(
        re.search(r"公司參訪|全天|機上|溫暖的家|準備登機|早餐|中餐|午餐|晚餐", value)
        or re.fullmatch(r"[A-Z]{2}\d{2,4}.*", value)
        or len(value) < 2
    )


def _query_for(name: str) -> str:
    for key, query in ALIASES.items():
        if key in name:
            return query
    english = re.search(r"\b[A-Z][A-Za-z .'-]{2,}\b", name)
    return f"{english.group(0).strip()}, Netherlands" if english else f"{name}, Netherlands"
