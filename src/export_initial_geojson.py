import json
from pathlib import Path
from typing import List, Tuple, Dict, Any

from config import ROUTES_DIR


def load_json(path: Path) -> dict | list:
    if not path.exists():
        raise FileNotFoundError(f"Не найден файл: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def decode_polyline(encoded: str, precision: int = 6) -> List[Tuple[float, float]]:
    index = 0
    lat = 0
    lng = 0
    coordinates = []
    factor = 10 ** precision

    while index < len(encoded):
        shift = 0
        result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat

        shift = 0
        result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng

        coordinates.append((lng / factor, lat / factor))  # GeoJSON: lon, lat

    return coordinates


def main():
    VEHICLE_ID = "Е691ЕК550"
    TRIP_ID = 1

    segments_json_path = ROUTES_DIR / f"initial_route_{VEHICLE_ID}_trip_{TRIP_ID}_segments.json"
    route_summary_path = ROUTES_DIR / f"initial_route_{VEHICLE_ID}_trip_{TRIP_ID}_summary.json"

    segment_jsons = load_json(segments_json_path)
    route_summary = load_json(route_summary_path)

    print(f"Экспорт initial GeoJSON: ТС={VEHICLE_ID}, рейс={TRIP_ID}")
    print(f"Сегментов в JSON: {len(segment_jsons)}")
    print()

    features = []
    all_line_coords: List[List[float]] = []

    total_distance_km = 0.0
    total_time_sec = 0

    ordered_nodes: List[Dict[str, Any]] = []

    for idx, segment in enumerate(segment_jsons, start=1):
        from_node = segment["from"]
        to_node = segment["to"]
        route_json = segment["route"]

        leg = route_json["trip"]["legs"][0]
        summary = leg["summary"]
        encoded_shape = leg["shape"]

        coords = decode_polyline(encoded_shape, precision=6)

        distance_km = float(summary.get("length", 0.0))
        time_sec = int(summary.get("time", 0))

        total_distance_km += distance_km
        total_time_sec += time_sec

        if all_line_coords:
            all_line_coords.extend(coords[1:])
        else:
            all_line_coords.extend(coords)

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coords
            },
            "properties": {
                "feature_type": "segment",
                "segment_no": idx,
                "from_label": from_node["label"],
                "to_label": to_node["label"],
                "from_point_type": from_node["point_type"],
                "to_point_type": to_node["point_type"],
                "from_point_id": from_node["point_id"],
                "to_point_id": to_node["point_id"],
                "from_address": from_node["address"],
                "to_address": to_node["address"],
                "distance_km": round(distance_km, 3),
                "time_sec": time_sec,
                "time_min": round(time_sec / 60, 1),
                "method": "initial_original_order"
            }
        })

        if idx == 1:
            ordered_nodes.append(from_node)
        ordered_nodes.append(to_node)

        print(
            f"[{idx}] {from_node['label']} -> {to_node['label']} | "
            f"{round(distance_km, 3)} км | {round(time_sec / 60, 1)} мин"
        )

    total_time_min = round(total_time_sec / 60, 1)

    features.append({
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": all_line_coords
        },
        "properties": {
            "feature_type": "full_route",
            "vehicle_id": VEHICLE_ID,
            "trip_id": TRIP_ID,
            "method": "initial_original_order",
            "total_distance_km": round(total_distance_km, 3),
            "total_time_sec": total_time_sec,
            "total_time_min": total_time_min,
            "route_kind": "initial"
        }
    })

    for order_no, node in enumerate(ordered_nodes, start=1):
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(node["lon"]), float(node["lat"])]
            },
            "properties": {
                "feature_type": "route_node",
                "order_no": order_no,
                "label": node["label"],
                "point_type": node["point_type"],
                "point_id": node["point_id"],
                "stop_seq": node["stop_seq"],
                "address": node["address"],
                "vehicle_id": VEHICLE_ID,
                "trip_id": TRIP_ID,
                "method": "initial_original_order"
            }
        })

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    final_summary = {
        "vehicle_id": VEHICLE_ID,
        "trip_id": TRIP_ID,
        "method": "initial_original_order",
        "segments_count": len(segment_jsons),
        "nodes_count": len(ordered_nodes),
        "total_distance_km": round(total_distance_km, 3),
        "total_time_sec": total_time_sec,
        "total_time_min": total_time_min,
        "source_summary_distance_km": route_summary.get("total_distance_km"),
        "source_summary_time_min": route_summary.get("total_time_min"),
    }

    geojson_path = ROUTES_DIR / f"initial_route_{VEHICLE_ID}_trip_{TRIP_ID}.geojson"
    summary_path = ROUTES_DIR / f"initial_route_{VEHICLE_ID}_trip_{TRIP_ID}_geojson_summary.json"

    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(final_summary, f, ensure_ascii=False, indent=2)

    print()
    print(f"Итоговая длина маршрута: {round(total_distance_km, 3)} км")
    print(f"Итоговое время маршрута: {total_time_min} мин")
    print()
    print("Файлы сохранены:")
    print(geojson_path)
    print(summary_path)


if __name__ == "__main__":
    main()