# Google Route Generator

將旅行社行程 PDF 自動轉成可編輯、可計算車程的互動式路線網頁。

## 網頁功能

- 從網頁上傳行程 PDF
- 自動辨識每日景點與參訪順序
- 自動查詢景點座標
- 依實際道路計算路線、距離與預估車程
- 每天不同顏色顯示於互動地圖
- 可在計算前修改景點名稱與座標搜尋文字
- 無法確認的地址不會亂放，會保留供人工修正

## 最簡單的使用方式

Windows 使用者可直接雙擊 `START_WEB.bat`，網頁會在瀏覽器開啟：

`http://127.0.0.1:4173`

第一次使用前請先安裝 Python 3.11 以上版本，並依下方方式安裝專案。

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

啟動網頁版：

```powershell
route-map-web
```

網頁採用免費服務優先與自動備援：

- 設定 `GEOAPIFY_API_KEY` 時，優先使用 Geoapify 搜尋景點與座標。
- 設定 `OPENROUTESERVICE_API_KEY` 時，優先使用 openrouteservice 計算道路與車程。
- 未設定金鑰或服務暫時失敗時，自動改用 OpenStreetMap Nominatim 與 OSRM。
- 座標結果會儲存在 `.cache/locations.json`，避免重複使用免費額度。

將 `.env.example` 複製為 `.env`，再填入免費 API Key。請勿將 `.env` 上傳至 GitHub。

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
