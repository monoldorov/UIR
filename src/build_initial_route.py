import json
from pathlib import Path
from typing import Dict, Any, List

import pandas as pd

from config import OUTPUT_DIR, ROUTES_DIR
from valhalla_client import ValhallaClient


def load_trips() -> List[Dict[str, Any]]:
    trips_path = OUTPUT_DIR / "trips.json"
    if not trips_path.exists():
        raise FileNotFoundError(f"Не найден файл: {trips_path}")

    with open(trips_path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_trip(trips: List[Dict[str, Any]], vehicle_id: str, trip_id: int) -> Dict[str, Any]:
    for trip in trips:
        if trip["vehicle_id"] == vehicle_id and int(trip["trip_id"]) == int(trip_id):
            return trip
    raise ValueError(f"Не найден рейс: ТС={vehicle_id}, рейс={trip_id}")


def build_ordered_points(trip: Dict[str, Any]) -> List[Dict[str, Any]]:
    points = []

    points.append({
        "label": "START",
        "point_type": "START",
        "point_id": None,
        "stop_seq": None,
        "address": trip["start"]["address"],
        "lat": float(trip["start"]["lat"]),
        "lon": float(trip["start"]["lon"]),
    })

    for stop in trip["stops"]:
        points.append({
            "label": f"STOP_{int(stop['stop_seq'])}",
            "point_type": "STOP",
            "point_id": stop["point_id"],
            "stop_seq": int(stop["stop_seq"]),
            "address": stop["address"],
            "lat": float(stop["lat"]),
            "lon": float(stop["lon"]),
        })

    points.append({
        "label": "END",
        "point_type": "END",
        "point_id": None,
        "stop_seq": None,
        "address": trip["end"]["address"],
        "lat": float(trip["end"]["lat"]),
        "lon": float(trip["end"]["lon"]),
    })

    return points


def build_initial_route_for_trip(vehicle_id: str, trip_id: int, verbose: bool = True) -> dict:
    trips = load_trips()
    trip = find_trip(trips, vehicle_id, trip_id)
    points = build_ordered_points(trip)

    client = ValhallaClient()

    segment_rows = []
    segment_jsons = []

    total_distance_km = 0.0
    total_time_sec = 0

    if verbose:
        print(f"Построение исходного маршрута: ТС={vehicle_id}, рейс={trip_id}")
        print(f"Точек в маршруте: {len(points)}")
        print()

    for idx in range(len(points) - 1):
        from_point = points[idx]
        to_point = points[idx + 1]

        locations = [
            {"lat": from_point["lat"], "lon": from_point["lon"], "type": "break"},
            {"lat": to_point["lat"], "lon": to_point["lon"], "type": "break"},
        ]

        route_json = client.route(locations)
        summary = client.extract_summary(route_json)

        distance_km = float(summary["distance_km"])
        time_sec = int(summary["time_sec"])
        time_min = float(summary["time_min"])

        total_distance_km += distance_km
        total_time_sec += time_sec

        segment_rows.append({
            "segment_no": idx + 1,

            "from_label": from_point["label"],
            "from_point_type": from_point["point_type"],
            "from_point_id": from_point["point_id"],
            "from_stop_seq": from_point["stop_seq"],
            "from_address": from_point["address"],
            "from_lat": from_point["lat"],
            "from_lon": from_point["lon"],

            "to_label": to_point["label"],
            "to_point_type": to_point["point_type"],
            "to_point_id": to_point["point_id"],
            "to_stop_seq": to_point["stop_seq"],
            "to_address": to_point["address"],
            "to_lat": to_point["lat"],
            "to_lon": to_point["lon"],

            "distance_km": distance_km,
            "time_sec": time_sec,
            "time_min": time_min,
        })

        segment_jsons.append({
            "segment_no": idx + 1,
            "from": from_point,
            "to": to_point,
            "route": route_json,
        })

        if verbose:
            print(
                f"[{idx + 1}] {from_point['label']} -> {to_point['label']} | "
                f"{distance_km} км | {time_min} мин"
            )

    total_time_min = round(total_time_sec / 60, 1)

    segments_df = pd.DataFrame(segment_rows)

    segments_xlsx_path = ROUTES_DIR / f"initial_route_{vehicle_id}_trip_{trip_id}_segments.xlsx"
    segments_json_path = ROUTES_DIR / f"initial_route_{vehicle_id}_trip_{trip_id}_segments.json"
    summary_json_path = ROUTES_DIR / f"initial_route_{vehicle_id}_trip_{trip_id}_summary.json"

    segments_df.to_excel(segments_xlsx_path, index=False)

    with open(segments_json_path, "w", encoding="utf-8") as f:
        json.dump(segment_jsons, f, ensure_ascii=False, indent=2)

    summary = {
        "vehicle_id": vehicle_id,
        "trip_id": trip_id,
        "segments_count": len(segment_rows),
        "nodes_count": len(points),
        "total_distance_km": round(total_distance_km, 3),
        "total_time_sec": total_time_sec,
        "total_time_min": total_time_min,
        "method": "valhalla_segmented_original_order",
    }

    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    if verbose:
        print()
        print(f"Суммарная длина маршрута: {summary['total_distance_km']} км")
        print(f"Суммарное время маршрута: {summary['total_time_min']} мин")
        print()
        print("Файлы сохранены:")
        print(segments_xlsx_path)
        print(segments_json_path)
        print(summary_json_path)

    return {
        "vehicle_id": vehicle_id,
        "trip_id": trip_id,
        "status": "success",
        "summary": summary,
        "segments_xlsx_path": str(segments_xlsx_path),
        "segments_json_path": str(segments_json_path),
        "summary_json_path": str(summary_json_path),
    }


def main():
    VEHICLE_ID = "Е691ЕК550"
    TRIP_ID = 1
    build_initial_route_for_trip(VEHICLE_ID, TRIP_ID, verbose=True)


if __name__ == "__main__":
    main()