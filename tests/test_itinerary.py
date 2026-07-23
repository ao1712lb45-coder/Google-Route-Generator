from google_route_generator.itinerary import _extract_days, _query_for


def test_extract_days_and_stops() -> None:
    text = """
    第 2 天
    抵達阿姆斯特丹－桑斯安斯風車村(木鞋工廠、起司工廠)－沃倫丹漁村－阿姆斯特丹

    桑斯安斯風車村（Zaanse Schans）景點介紹
    早餐：機上
    第 3 天
    公司參訪（全天）(派車)

    早餐：飯店
    """
    days = _extract_days(text)

    assert len(days) == 2
    assert [stop.name for stop in days[0].stops] == [
        "阿姆斯特丹",
        "桑斯安斯風車村",
        "沃倫丹漁村",
        "阿姆斯特丹",
    ]
    assert days[1].stops == []


def test_known_location_uses_precise_query() -> None:
    assert _query_for("羊角村") == "Giethoorn, Netherlands"


def test_flight_day_does_not_create_false_stops() -> None:
    days = _extract_days("第 1 天\n桃園／阿姆斯特丹 TPE/AMS CI073 23:40~07:40+1\n\n早餐：機上")

    assert days[0].stops == []
