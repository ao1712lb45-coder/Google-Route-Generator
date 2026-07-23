import zipfile
from pathlib import Path

from google_route_generator.itinerary import (
    _clean_lodging,
    _split_heading_stops,
    extract_docx_text,
    parse_itinerary,
)


def create_docx(path: Path, paragraphs: list[str]) -> None:
    body = "".join(
        f'<w:p><w:r><w:t>{text}</w:t></w:r></w:p>' for text in paragraphs
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)


def create_table_docx(path: Path, rows: list[tuple[str, str]]) -> None:
    table_rows = "".join(
        "<w:tr>"
        f"<w:tc><w:p><w:r><w:t>{day}</w:t></w:r></w:p></w:tc>"
        f"<w:tc><w:p><w:r><w:t>{content}</w:t></w:r></w:p></w:tc>"
        "</w:tr>"
        for day, content in rows
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body><w:tbl>{table_rows}</w:tbl></w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)


def test_extract_docx_text(tmp_path: Path) -> None:
    path = tmp_path / "trip.docx"
    create_docx(path, ["第 2 天", "阿姆斯特丹－桑斯安斯風車村", "早餐：飯店"])

    assert extract_docx_text(path).splitlines() == [
        "第 2 天",
        "阿姆斯特丹－桑斯安斯風車村",
        "早餐：飯店",
    ]


def test_parse_docx_itinerary(tmp_path: Path) -> None:
    path = tmp_path / "trip.docx"
    create_docx(path, ["第 2 天", "阿姆斯特丹－桑斯安斯風車村", "早餐：飯店"])

    result = parse_itinerary(path)

    assert result["days"][0]["day"] == 2
    assert [stop["name"] for stop in result["days"][0]["stops"]] == [
        "阿姆斯特丹",
        "桑斯安斯風車村",
    ]


def test_split_travel_agency_heading_keeps_main_places_and_airports() -> None:
    heading = "免稅店-淺草觀音寺～雷門、仲見世商店街-成田國際空港✈桃園國際機場 NRT/TPE TR875"

    assert _split_heading_stops(heading) == [
        "免稅店",
        "淺草觀音寺",
        "成田國際空港",
        "桃園國際機場",
    ]


def test_clean_lodging_uses_first_hotel() -> None:
    assert _clean_lodging("住宿：品川王子大飯店 或太陽城王子同級") == "品川王子大飯店"


def test_table_itinerary_starts_next_day_from_previous_lodging(tmp_path: Path) -> None:
    path = tmp_path / "agency-trip.docx"
    create_table_docx(
        path,
        [
            ("第4天", "全日自由活動"),
            ("", "住宿：品川王子大飯店 或太陽城王子同級"),
            ("第5天", "免稅店-淺草觀音寺～雷門、仲見世商店街-成田國際空港✈桃園國際機場"),
            ("", "住宿：溫暖的家"),
        ],
    )

    result = parse_itinerary(path)

    assert [stop["name"] for stop in result["days"][1]["stops"]] == [
        "品川王子大飯店",
        "免稅店",
        "淺草觀音寺",
        "成田國際空港",
        "桃園國際機場",
    ]
