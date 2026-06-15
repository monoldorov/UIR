import json
from pathlib import Path
from typing import Dict, Any, List, Tuple

import pandas as pd

from config import OUTPUT_DIR, MATRICES_DIR
from valhalla_client import ValhallaClient


def load_trips() -> List[Dict[str, Any]]:
    trips_path = OUTPUT_DIR / "trips.json"
    if not trips_path.exists():
        raise FileNotFoundError(
            f"Не найден файл {trips_path}. Сначала запусти main.py"
        )

    with open(trips_path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_trip(trips: List[Dict[str, Any]], vehicle_id: str, trip_id: int) -> Dict[str, Any]:
    for trip in trips:
        if trip["vehicle_id"] == vehicle_id and int(trip["trip_id"]) == int(trip_id):
            return trip
    raise ValueError(f"Не найден рейс: ТС={vehicle_id}, рейс={trip_id}")


def build_trip_nodes(trip: Dict[str, Any]) -> pd.DataFrame:
    rows = []

    rows.append({
        "node_seq": 1,
        "label": "START",
        "point_type": "START",
        "point_id": None,
        "stop_seq": None,
        "address": trip["start"]["address"],
        "lat": float(trip["start"]["lat"]),
        "lon": float(trip["start"]["lon"]),
    })

    seq = 2
    for stop in trip["stops"]:
        rows.append({
            "node_seq": seq,
            "label": f"STOP_{stop['stop_seq']}",
            "point_type": "STOP",
            "point_id": stop["point_id"],
            "stop_seq": int(stop["stop_seq"]),
            "address": stop["address"],
            "lat": float(stop["lat"]),
            "lon": float(stop["lon"]),
        })
        seq += 1

    rows.append({
        "node_seq": seq,
        "label": "END",
        "point_type": "END",
        "point_id": None,
        "stop_seq": None,
        "address": trip["end"]["address"],
        "lat": float(trip["end"]["lat"]),
        "lon": float(trip["end"]["lon"]),
    })

    df = pd.DataFrame(rows)

    df["coord_key"] = df.apply(lambda r: f"{r['lat']:.6f}|{r['lon']:.6f}", axis=1)

    counts = df["coord_key"].value_counts().to_dict()
    df["coord_count"] = df["coord_key"].map(counts)
    df["is_duplicate_coord"] = df["coord_count"] > 1

    return df


def build_unique_nodes(nodes_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    unique_rows = []
    mapping_rows = []

    grouped = nodes_df.groupby("coord_key", sort=False)

    unique_id = 1
    for coord_key, group in grouped:
        first = group.iloc[0]

        labels = group["label"].astype(str).tolist()
        point_ids = group["point_id"].dropna().astype(str).tolist()
        addresses = group["address"].dropna().astype(str).tolist()

        unique_node_code = f"U{unique_id}"

        unique_rows.append({
            "unique_node_id": unique_node_code,
            "coord_key": coord_key,
            "lat": float(first["lat"]),
            "lon": float(first["lon"]),
            "labels_joined": " | ".join(labels),
            "point_ids_joined": " | ".join(point_ids) if point_ids else None,
            "addresses_joined": " | ".join(addresses),
            "source_count": len(group),
        })

        for _, row in group.iterrows():
            mapping_rows.append({
                "node_seq": int(row["node_seq"]),
                "label": row["label"],
                "point_type": row["point_type"],
                "point_id": row["point_id"],
                "stop_seq": row["stop_seq"],
                "address": row["address"],
                "lat": row["lat"],
                "lon": row["lon"],
                "coord_key": row["coord_key"],
                "unique_node_id": unique_node_code,
            })

        unique_id += 1

    unique_nodes_df = pd.DataFrame(unique_rows)
    mapping_df = pd.DataFrame(mapping_rows)

    return unique_nodes_df, mapping_df


def build_distance_matrix(unique_nodes_df: pd.DataFrame, verbose: bool = True) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    client = ValhallaClient()

    matrix_rows = []
    matrix_json = []

    n = len(unique_nodes_df)

    for i in range(n):
        from_row = unique_nodes_df.iloc[i]
        for j in range(n):
            to_row = unique_nodes_df.iloc[j]

            if from_row["unique_node_id"] == to_row["unique_node_id"]:
                distance_km = 0.0
                time_sec = 0
                route_json = None
            else:
                locations = [
                    {"lat": float(from_row["lat"]), "lon": float(from_row["lon"]), "type": "break"},
                    {"lat": float(to_row["lat"]), "lon": float(to_row["lon"]), "type": "break"},
                ]
                route_json = client.route(locations)
                summary = client.extract_summary(route_json)
                distance_km = summary["distance_km"]
                time_sec = summary["time_sec"]

            matrix_rows.append({
                "from_node": from_row["unique_node_id"],
                "to_node": to_row["unique_node_id"],
                "from_lat": float(from_row["lat"]),
                "from_lon": float(from_row["lon"]),
                "to_lat": float(to_row["lat"]),
                "to_lon": float(to_row["lon"]),
                "distance_km": distance_km,
                "time_sec": time_sec,
                "time_min": round(time_sec / 60, 1),
            })

            matrix_json.append({
                "from_node": from_row["unique_node_id"],
                "to_node": to_row["unique_node_id"],
                "distance_km": distance_km,
                "time_sec": time_sec,
                "route": route_json,
            })

            if verbose:
                print(
                    f"{from_row['unique_node_id']} -> {to_row['unique_node_id']} | "
                    f"{distance_km} км | {round(time_sec / 60, 1)} мин"
                )

    matrix_df = pd.DataFrame(matrix_rows)
    return matrix_df, matrix_json


def save_json(data: Any, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_distance_matrix_for_trip(vehicle_id: str, trip_id: int, verbose: bool = True) -> dict:
    trips = load_trips()
    trip = find_trip(trips, vehicle_id, trip_id)

    if verbose:
        print(f"Построение матрицы: ТС={vehicle_id}, рейс={trip_id}")
        print()

    nodes_df = build_trip_nodes(trip)
    unique_nodes_df, mapping_df = build_unique_nodes(nodes_df)

    if verbose:
        print(f"Исходных узлов: {len(nodes_df)}")
        print(f"Уникальных геоточек: {len(unique_nodes_df)}")
        print()

    duplicates_df = nodes_df[nodes_df["is_duplicate_coord"]].copy()
    if verbose and not duplicates_df.empty:
        print("Найдены дубли координат:")
        print(duplicates_df[["node_seq", "label", "coord_key", "address"]].to_string(index=False))
        print()

    matrix_df, matrix_json = build_distance_matrix(unique_nodes_df, verbose=verbose)

    nodes_path = MATRICES_DIR / f"trip_nodes_{vehicle_id}_trip_{trip_id}.xlsx"
    unique_nodes_path = MATRICES_DIR / f"trip_unique_nodes_{vehicle_id}_trip_{trip_id}.xlsx"
    mapping_path = MATRICES_DIR / f"trip_node_mapping_{vehicle_id}_trip_{trip_id}.xlsx"
    matrix_path = MATRICES_DIR / f"trip_distance_matrix_{vehicle_id}_trip_{trip_id}.xlsx"
    matrix_json_path = MATRICES_DIR / f"trip_distance_matrix_{vehicle_id}_trip_{trip_id}.json"

    nodes_df.to_excel(nodes_path, index=False)
    unique_nodes_df.to_excel(unique_nodes_path, index=False)
    mapping_df.to_excel(mapping_path, index=False)
    matrix_df.to_excel(matrix_path, index=False)
    save_json(matrix_json, matrix_json_path)

    if verbose:
        print("Файлы сохранены:")
        print(nodes_path)
        print(unique_nodes_path)
        print(mapping_path)
        print(matrix_path)
        print(matrix_json_path)

    return {
        "vehicle_id": vehicle_id,
        "trip_id": trip_id,
        "status": "success",
        "nodes_count": int(len(nodes_df)),
        "unique_nodes_count": int(len(unique_nodes_df)),
        "nodes_path": str(nodes_path),
        "unique_nodes_path": str(unique_nodes_path),
        "mapping_path": str(mapping_path),
        "matrix_path": str(matrix_path),
        "matrix_json_path": str(matrix_json_path),
    }


def main():
    VEHICLE_ID = "Е691ЕК550"
    TRIP_ID = 1
    build_distance_matrix_for_trip(VEHICLE_ID, TRIP_ID, verbose=True)


if __name__ == "__main__":
    main()