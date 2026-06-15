import json
from pathlib import Path
from typing import Dict, List, Tuple, Any

import pandas as pd

from config import GLPK_DIR, OPT_INPUT_DIR, OPT_RESULTS_DIR
from file_naming import normalize_vehicle_id_for_filename
from valhalla_client import ValhallaClient


def load_json(path: Path) -> dict:
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


def load_node_lookup(vehicle_id: str, trip_id: int) -> Dict[str, Dict[str, Any]]:
    nodes_path = OPT_INPUT_DIR / f"opt_nodes_{vehicle_id}_trip_{trip_id}.xlsx"
    if not nodes_path.exists():
        raise FileNotFoundError(f"Не найден файл: {nodes_path}")

    df = pd.read_excel(nodes_path)

    lookup = {}
    for _, row in df.iterrows():
        node_id = str(row["unique_node_id"])
        lookup[node_id] = {
            "node_role": str(row["node_role"]),
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "addresses_joined": str(row["addresses_joined"]) if pd.notna(row["addresses_joined"]) else None,
            "labels_joined": str(row["labels_joined"]) if pd.notna(row["labels_joined"]) else None,
        }
    return lookup


def build_segments_from_path(path_nodes: List[str]) -> List[Tuple[str, str]]:
    return list(zip(path_nodes[:-1], path_nodes[1:]))


def main():
    VEHICLE_ID = "Е691ЕК550"
    TRIP_ID = 1
    SAFE_VEHICLE_ID = normalize_vehicle_id_for_filename(VEHICLE_ID)

    glpk_result_path = GLPK_DIR / f"glpk_result_{SAFE_VEHICLE_ID}_trip_{TRIP_ID}.json"
    glpk_result = load_json(glpk_result_path)

    node_lookup = load_node_lookup(VEHICLE_ID, TRIP_ID)

    path_nodes = glpk_result["path_nodes"]
    segments = build_segments_from_path(path_nodes)

    print(f"Экспорт GLPK GeoJSON: ТС={VEHICLE_ID}, рейс={TRIP_ID}")
    print("Путь:")
    print(" -> ".join(path_nodes))
    print()

    client = ValhallaClient()

    features = []
    total_distance_km = 0.0
    total_time_sec = 0

    all_line_coords: List[List[float]] = []

    for idx, (from_node, to_node) in enumerate(segments, start=1):
        if from_node not in node_lookup:
            raise ValueError(f"Узел {from_node} не найден в lookup")
        if to_node not in node_lookup:
            raise ValueError(f"Узел {to_node} не найден в lookup")

        p_from = node_lookup[from_node]
        p_to = node_lookup[to_node]

        locations = [
            {"lat": p_from["lat"], "lon": p_from["lon"], "type": "break"},
            {"lat": p_to["lat"], "lon": p_to["lon"], "type": "break"},
        ]

        route_json = client.route(locations)
        summary = client.extract_summary(route_json)

        encoded_shape = route_json["trip"]["legs"][0]["shape"]
        coords = decode_polyline(encoded_shape, precision=6)

        total_distance_km += summary["distance_km"]
        total_time_sec += summary["time_sec"]

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
                "segment_no": idx,
                "from_node": from_node,
                "to_node": to_node,
                "from_role": p_from["node_role"],
                "to_role": p_to["node_role"],
                "from_address": p_from["addresses_joined"],
                "to_address": p_to["addresses_joined"],
                "distance_km": summary["distance_km"],
                "time_sec": summary["time_sec"],
                "time_min": summary["time_min"],
                "method": "glpk_mtz_path"
            }
        })

        print(
            f"[{idx}] {from_node} -> {to_node} | "
            f"{summary['distance_km']} км | {summary['time_min']} мин"
        )

    total_time_min = round(total_time_sec / 60, 1)

    # Общая линия всего маршрута
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
            "method": "glpk_mtz_path",
            "total_distance_km": round(total_distance_km, 3),
            "total_time_sec": total_time_sec,
            "total_time_min": total_time_min,
            "path_nodes": " -> ".join(path_nodes)
        }
    })

    # Точки узлов
    for order_no, node_id in enumerate(path_nodes, start=1):
        node = node_lookup[node_id]
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [node["lon"], node["lat"]]
            },
            "properties": {
                "feature_type": "route_node",
                "order_no": order_no,
                "node_id": node_id,
                "node_role": node["node_role"],
                "addresses_joined": node["addresses_joined"],
                "labels_joined": node["labels_joined"],
                "vehicle_id": VEHICLE_ID,
                "trip_id": TRIP_ID,
                "method": "glpk_mtz_path"
            }
        })

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    summary = {
        "vehicle_id": VEHICLE_ID,
        "trip_id": TRIP_ID,
        "method": "glpk_mtz_path",
        "path_nodes": path_nodes,
        "segments_count": len(segments),
        "total_distance_km": round(total_distance_km, 3),
        "total_time_sec": total_time_sec,
        "total_time_min": total_time_min
    }

    geojson_path = OPT_RESULTS_DIR / f"optimized_glpk_{VEHICLE_ID}_trip_{TRIP_ID}.geojson"
    summary_path = OPT_RESULTS_DIR / f"optimized_glpk_{VEHICLE_ID}_trip_{TRIP_ID}_summary.json"

    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print()
    print(f"Итоговая длина маршрута: {round(total_distance_km, 3)} км")
    print(f"Итоговое время маршрута: {total_time_min} мин")
    print()
    print("Файлы сохранены:")
    print(geojson_path)
    print(summary_path)


if __name__ == "__main__":
    main()