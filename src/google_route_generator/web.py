"""FastAPI web application for uploading PDFs and generating road routes."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .itinerary import parse_itinerary
from .services import MapServices


STATIC_DIR = Path(__file__).parent / "static"
MAX_PDF_BYTES = 20 * 1024 * 1024
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
    stops: list[StopRequest]


class RouteRequest(BaseModel):
    days: list[DayRequest]


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/parse")
def parse_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "請上傳 PDF 行程檔。")
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
        temp_path = Path(handle.name)
        shutil.copyfileobj(file.file, handle)
    try:
        if temp_path.stat().st_size > MAX_PDF_BYTES:
            raise HTTPException(413, "PDF 超過 20 MB。")
        result = parse_itinerary(temp_path)
        if not result["days"]:
            raise HTTPException(422, "無法辨識每日行程，請確認 PDF 內含可選取文字。")
        return result
    finally:
        temp_path.unlink(missing_ok=True)


@app.post("/api/routes")
def build_routes(request: RouteRequest):
    output_days = []
    for day in request.days:
        stops = []
        for stop in day.stops:
            item = stop.model_dump()
            if item["latitude"] is None or item["longitude"] is None:
                try:
                    location = services.geocode(item["query"])
                except Exception as error:
                    item.update(status="error", note=f"座標服務失敗：{error.__class__.__name__}")
                else:
                    if location:
                        item.update(location, status="located", note="")
                    else:
                        item.update(status="unresolved", note="找不到座標，請修改搜尋名稱。")
            else:
                item.update(status="located", note="使用已確認座標")
            stops.append(item)
        try:
            route = services.route(stops)
        except Exception as error:
            route = {"error": f"道路服務失敗：{error.__class__.__name__}"}
        output_days.append({"day": day.day, "title": day.title, "stops": stops, "route": route})
    return {"days": output_days}


def run() -> None:
    import uvicorn

    uvicorn.run("google_route_generator.web:app", host="127.0.0.1", port=4173, reload=False)
