"""Professional interactive map rendering."""

from pathlib import Path

import folium

from .models import ItineraryStop


def render_map(stops: list[ItineraryStop], output_path: Path, title: str) -> Path:
    """Render numbered stops and their connecting route to an HTML map."""
    points = [stop for stop in stops if stop.is_geocoded]
    if not points:
        raise ValueError("No geocoded stops are available to render.")

    center = [
        sum(stop.latitude for stop in points if stop.latitude is not None) / len(points),
        sum(stop.longitude for stop in points if stop.longitude is not None) / len(points),
    ]
    route_map = folium.Map(location=center, zoom_start=6, tiles="CartoDB positron")
    route_map.get_root().html.add_child(
        folium.Element(f'<h3 style="position:fixed;top:10px;left:50px;z-index:9999">{title}</h3>')
    )

    coordinates = []
    for index, stop in enumerate(points, start=1):
        coordinate = [stop.latitude, stop.longitude]
        coordinates.append(coordinate)
        day = stop.day.isoformat() if stop.day else "Date not specified"
        folium.Marker(
            coordinate,
            tooltip=f"{index}. {stop.name}",
            popup=f"<strong>{stop.name}</strong><br>{day}<br>{stop.details}",
            icon=folium.DivIcon(
                html=f'<div style="background:#1769aa;color:white;border-radius:50%;'
                f'width:28px;height:28px;text-align:center;line-height:28px;font-weight:bold">{index}</div>'
            ),
        ).add_to(route_map)

    if len(coordinates) > 1:
        folium.PolyLine(coordinates, color="#1769aa", weight=4, opacity=0.8).add_to(route_map)
        route_map.fit_bounds(coordinates, padding=(30, 30))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    route_map.save(str(output_path))
    return output_path

