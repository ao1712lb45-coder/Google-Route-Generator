"""FastAPI web application for uploading PDFs and generating road routes."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import requests
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from .itinerary import parse_itinerary
from .services import MapServices, select_coherent_locations
from .web_itinerary import fetch_web_itinerary


STATIC_DIR = Path(__file__).parent / "static"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
ALLOWED_UPLOAD_SUFFIXES = {".pdf", ".docx"}
load_dotenv()
app = FastAPI(title="Google Route Generator", version="0.2.0")
services = MapServices()


class StopRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    query: str = Field(min_length=1, max_length=240)
    latitude: float | None = None
    longitude: float | None = None


class DayRequest(BaseModel):
    day: int = Field(ge=1, le=60)
    title: str = ""
    stops: list[StopRequest] = Field(max_length=20)


class RouteRequest(BaseModel):
    days: list[DayRequest] = Field(max_length=14)


class UrlRequest(BaseModel):
    url: str = Field(min_length=10, max_length=2048)


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/providers")
def providers():
    return services.provider_status()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/parse")
def parse_document(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        raise HTTPException(400, "請上傳 PDF 或 Word .docx 行程檔。")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        temp_path = Path(handle.name)
        shutil.copyfileobj(file.file, handle)
    try:
        if temp_path.stat().st_size > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "檔案超過 20 MB。")
        try:
            result = parse_itinerary(temp_path)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        if not result["days"]:
            raise HTTPException(422, "無法辨識每日行程，請確認文件內含可讀取文字。")
        return result
    finally:
        temp_path.unlink(missing_ok=True)


@app.post("/api/parse-url")
def parse_url(request: UrlRequest):
    try:
        result = fetch_web_itinerary(request.url)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except requests.RequestException as error:
        raise HTTPException(502, "無法讀取行程網址，請確認網址公開且可正常開啟。") from error
    if not result["days"]:
        raise HTTPException(422, "找不到每日行程，請確認網址是公開的行程詳細頁。")
    return result


@app.post("/api/routes")
def build_routes(request: RouteRequest):
    output_days = []
    preferred_country = _infer_destination_country(
        [stop.name for day in request.days for stop in day.stops]
    )
    for day in request.days:
        stops = [stop.model_dump() for stop in day.stops]
        candidate_groups = []
        for item in stops:
            if item["latitude"] is not None and item["longitude"] is not None:
                candidate_groups.append([item.copy()])
                continue
            try:
                country = None if _is_airport(item["name"]) else preferred_country
                candidate_groups.append(
                    services.geocode_candidates(item["query"], preferred_country=country)
                )
            except Exception:
                candidate_groups.append([])
        selected = select_coherent_locations(
            candidate_groups, [item["name"] for item in stops]
        )
        for item, location in zip(stops, selected):
            if item["latitude"] is None or item["longitude"] is None:
                if location:
                    item.update(location, status="located", note="")
                else:
                    item.update(status="unresolved", note="找不到地點，請補充國家或城市。")
            else:
                item.update(status="located", note="使用已確認座標")
        try:
            route = services.route(stops)
        except Exception as error:
            route = {"error": f"道路服務失敗：{error.__class__.__name__}"}
        output_days.append({"day": day.day, "title": day.title, "stops": stops, "route": route})
    return {"days": output_days}


def _is_airport(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in ("機場", "空港", "airport"))


def _infer_destination_country(stop_names: list[str]) -> str | None:
    country_tokens = {
        "jp": (
            "日本", "東京", "成田", "羽田", "鎌倉", "江之島", "品川", "淺草",
            "雷門", "仲見世", "富士", "大阪", "京都", "沖繩", "那霸", "北海道",
        ),
        "tw": ("台灣", "台北", "桃園", "台中", "高雄", "花蓮"),
        "nl": ("荷蘭", "阿姆斯特丹", "鹿特丹", "海牙"),
    }
    scores = {country: 0 for country in country_tokens}
    for name in stop_names:
        if _is_airport(name):
            continue
        for country, tokens in country_tokens.items():
            scores[country] += sum(token in name for token in tokens)
    country, score = max(scores.items(), key=lambda item: item[1])
    return country if score else None


def run() -> None:
    import uvicorn

    uvicorn.run("google_route_generator.web:app", host="127.0.0.1", port=4173, reload=False)
