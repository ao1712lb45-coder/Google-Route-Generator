import zipfile
from pathlib import Path

from google_route_generator.itinerary import extract_docx_text, parse_itinerary


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
