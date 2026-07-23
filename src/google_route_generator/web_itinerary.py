"""Fetch and parse public travel-agency itinerary pages."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urlparse

import requests

from .itinerary import DAY_PATTERN, MEAL_PATTERN, ParsedDay, ParsedStop, _clean_lodging
from .itinerary import _deduplicate, _extract_title, _split_heading_stops


ALLOWED_HOSTS = {"besttour.com.tw", "www.besttour.com.tw", "besttour.tw", "www.besttour.tw"}
MAX_WEB_BYTES = 3 * 1024 * 1024
BLOCK_TAGS = {
    "article",
    "br",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "p",
    "section",
    "td",
    "th",
    "tr",
}


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored_depth = 0
        self.title_parts: list[str] = []
        self.in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.ignored_depth += 1
        if tag == "title":
            self.in_title = True
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self.ignored_depth:
            self.ignored_depth -= 1
        if tag == "title":
            self.in_title = False
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.ignored_depth:
            return
        self.parts.append(data)
        if self.in_title:
            self.title_parts.append(data)

    def lines(self) -> list[str]:
        return [clean for part in "".join(self.parts).splitlines() if (clean := " ".join(part.split()))]

    def title(self) -> str:
        return " ".join("".join(self.title_parts).split())


def validate_itinerary_url(url: str) -> str:
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower().rstrip(".")
    is_ittms = host.endswith(".ittms.com.tw")
    if parsed.scheme not in {"http", "https"} or not host or not (is_ittms or host in ALLOWED_HOSTS):
        raise ValueError("目前支援 ITTMS 與 Besttour／喜鴻假期的公開行程網址。")
    return parsed.geturl()


def fetch_web_itinerary(url: str) -> dict:
    safe_url = validate_itinerary_url(url)
    if _provider_name(safe_url) == "Besttour":
        return _fetch_besttour_itinerary(safe_url)
    response = requests.get(
        safe_url,
        headers={"User-Agent": "GoogleRouteGenerator/0.2 (+travel itinerary parser)"},
        timeout=20,
        stream=True,
    )
    response.raise_for_status()
    final_url = validate_itinerary_url(response.url)
    content = bytearray()
    for chunk in response.iter_content(64 * 1024):
        content.extend(chunk)
        if len(content) > MAX_WEB_BYTES:
            raise ValueError("行程網頁內容超過 3 MB，無法安全解析。")
    html = _decode_html(bytes(content), response.encoding)
    result = parse_web_itinerary_html(html)
    result.update(source_url=final_url, provider=_provider_name(final_url))
    return result


def _fetch_besttour_itinerary(url: str) -> dict:
    code_match = re.search(r"/itinerary/([^/?#]+)", urlparse(url).path, re.I)
    if not code_match:
        raise ValueError("請貼上 Besttour 的行程詳細頁網址。")
    code = code_match.group(1)
    response = requests.get(
        "https://travelapi.besttour.com.tw/api/travel_detail_schedule.asp",
        params={"travel_no": code},
        headers={"User-Agent": "GoogleRouteGenerator/0.2 (+travel itinerary parser)"},
        timeout=20,
    )
    response.raise_for_status()
    response.encoding = "utf-8"
    payload = response.json()
    result = parse_besttour_schedule(payload, title=code)
    result.update(source_url=url, provider="Besttour")
    return result


def parse_besttour_schedule(payload: dict, title: str = "Besttour 行程") -> dict:
    schedule = payload.get("data") or []
    days: list[ParsedDay] = []
    for item in schedule:
        heading = " ".join(str(item.get("abstract_1") or "").split())
        if not heading:
            continue
        hotels = ((item.get("hotel") or {}).get("data") or [])
        lodging = " ".join(str(hotels[0].get("name") or "").split()) if hotels else ""
        days.append(
            ParsedDay(
                day=int(item.get("day") or len(days) + 1),
                title=heading,
                lodging=lodging,
            )
        )

    _populate_day_stops(days)
    return {"title": title, "days": [day.as_dict() for day in days]}


def parse_web_itinerary_html(html: str) -> dict:
    parser = VisibleTextParser()
    parser.feed(html)
    lines = parser.lines()
    days: dict[int, ParsedDay] = {}
    current_day: int | None = None
    awaiting_lodging = False

    for line in lines:
        day_match = DAY_PATTERN.search(line)
        if day_match:
            current_day = int(day_match.group(1))
            day = days.setdefault(current_day, ParsedDay(day=current_day, title=""))
            remainder = line[day_match.end() :].strip(" ：:-")
            if remainder and not day.title:
                day.title = remainder
            awaiting_lodging = False
            continue
        if current_day is None:
            continue
        day = days[current_day]
        if line in {"住宿", "住宿飯店", "飯店"}:
            awaiting_lodging = True
            continue
        lodging_match = re.match(r"^(?:住宿|住宿飯店)\s*[:：]\s*(.+)$", line)
        if lodging_match:
            day.lodging = _clean_lodging(f"住宿：{lodging_match.group(1)}")
            awaiting_lodging = False
            continue
        if awaiting_lodging and not MEAL_PATTERN.match(line):
            day.lodging = _clean_lodging(f"住宿：{line}")
            awaiting_lodging = False
            continue
        if not day.title and not MEAL_PATTERN.match(line) and not _is_page_chrome(line):
            day.title = line

    ordered = [days[number] for number in sorted(days) if days[number].title]
    for day in ordered:
        if not day.lodging:
            day.lodging = _lodging_from_heading(day.title)
    _populate_day_stops(ordered)

    title = parser.title() or _extract_title("\n".join(lines))
    return {"title": title, "days": [day.as_dict() for day in ordered]}


def _provider_name(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return "ITTMS" if host.endswith(".ittms.com.tw") else "Besttour"


def _populate_day_stops(days: list[ParsedDay]) -> None:
    for index, day in enumerate(days):
        names = _split_heading_stops(day.title)
        names = [day.lodging if name == "飯店" and day.lodging else name for name in names]
        if index and days[index - 1].lodging:
            names.insert(0, days[index - 1].lodging)
        names = _deduplicate(names)
        day.stops = [ParsedStop(name=name, query=name) for name in names]


def _lodging_from_heading(heading: str) -> str:
    match = re.search(r"入住(?:五星)?\s*([^→－—–-]+?(?:酒店|飯店|渡假村))", heading)
    return " ".join(match.group(1).split()) if match else ""


def _decode_html(content: bytes, header_encoding: str | None) -> str:
    prefix = content[:8192].decode("ascii", errors="ignore")
    charset_match = re.search(r"charset\s*=\s*[\"']?([\w-]+)", prefix, re.I)
    encoding = charset_match.group(1) if charset_match else header_encoding
    if not encoding or encoding.lower() in {"iso-8859-1", "latin-1"}:
        encoding = "utf-8"
    try:
        return content.decode(encoding, errors="replace")
    except LookupError:
        return content.decode("utf-8", errors="replace")


def _is_page_chrome(line: str) -> bool:
    return bool(re.search(r"^(?:行程特色|每日行程|餐食|注意事項|下載|分享|返回|報名)", line))
