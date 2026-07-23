from google_route_generator.services import select_coherent_locations


def place(lat, lon, country):
    return {"latitude": lat, "longitude": lon, "country_code": country}


def test_ambiguous_stop_prefers_same_country_as_neighbour() -> None:
    china_temple = place(30.6, 114.3, "cn")
    japan_temple = place(35.7, 139.8, "jp")
    mount_fuji = place(35.36, 138.73, "jp")
    selected = select_coherent_locations(
        [[china_temple, japan_temple], [mount_fuji]], ["觀音寺", "富士山"]
    )
    assert selected == [japan_temple, mount_fuji]


def test_airports_may_cross_countries() -> None:
    narita = place(35.77, 140.39, "jp")
    taoyuan = place(25.08, 121.23, "tw")
    selected = select_coherent_locations(
        [[narita], [taoyuan]], ["成田空港", "桃園機場"]
    )
    assert selected == [narita, taoyuan]
