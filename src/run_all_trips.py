import json
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd

from config import OUTPUT_DIR, OPT_RESULTS_DIR
from build_initial_route import build_initial_route_for_trip
from matrix_builder import build_distance_matrix_for_trip
from prepare_optimization_input import prepare_optimization_input_for_trip
from build_glpk_input import build_glpk_input_for_trip
from solve_trip_greedy import solve_greedy_for_trip
from solve_trip_glpk import solve_glpk_for_trip
from compare_all_methods import compare_all_methods_for_trip


def load_trips() -> List[Dict[str, Any]]:
    trips_path = OUTPUT_DIR / "trips.json"
    if not trips_path.exists():
        raise FileNotFoundError(f"Не найден файл: {trips_path}")

    with open(trips_path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_trip_keys(trips: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = []
    for trip in trips:
        result.append({
            "vehicle_id": trip["vehicle_id"],
            "trip_id": int(trip["trip_id"]),
            "stops_count": len(trip.get("stops", [])),
        })
    return result


def build_empty_row(vehicle_id: str, trip_id: int) -> Dict[str, Any]:
    return {
        "vehicle_id": vehicle_id,
        "trip_id": trip_id,

        "status": "unknown",
        "error_message": None,

        "glpk_status": None,
        "final_method": None,

        "matrix_nodes_count": None,
        "matrix_unique_nodes_count": None,

        "initial_distance_km": None,
        "initial_time_min": None,

        "greedy_distance_km": None,
        "greedy_time_min": None,

        "glpk_distance_km": None,
        "glpk_time_min": None,

        "greedy_saved_vs_initial_km": None,
        "greedy_saved_vs_initial_pct": None,
        "greedy_saved_vs_initial_min": None,
        "greedy_saved_vs_initial_time_pct": None,

        "glpk_saved_vs_initial_km": None,
        "glpk_saved_vs_initial_pct": None,
        "glpk_saved_vs_initial_min": None,
        "glpk_saved_vs_initial_time_pct": None,

        "glpk_better_than_greedy_km": None,
        "glpk_better_than_greedy_pct": None,
        "glpk_better_than_greedy_min": None,
        "glpk_better_than_greedy_time_pct": None,
    }


def run_full_pipeline_for_trip(vehicle_id: str, trip_id: int) -> Dict[str, Any]:
    row = build_empty_row(vehicle_id, trip_id)

    try:
        initial_result = build_initial_route_for_trip(vehicle_id, trip_id, verbose=False)
        matrix_result = build_distance_matrix_for_trip(vehicle_id, trip_id, verbose=False)
        prepare_optimization_input_for_trip(vehicle_id, trip_id, verbose=False)
        build_glpk_input_for_trip(vehicle_id, trip_id, verbose=False)
        greedy_result = solve_greedy_for_trip(vehicle_id, trip_id, verbose=False)

        row["matrix_nodes_count"] = matrix_result.get("nodes_count")
        row["matrix_unique_nodes_count"] = matrix_result.get("unique_nodes_count")

        initial_summary = initial_result["summary"]
        greedy_summary = greedy_result["summary"]

        row["initial_distance_km"] = initial_summary.get("total_distance_km")
        row["initial_time_min"] = initial_summary.get("total_time_min")

        row["greedy_distance_km"] = greedy_summary.get("total_distance_km")
        row["greedy_time_min"] = greedy_summary.get("total_time_min")

        # Сначала считаем, что greedy уже есть как fallback
        row["final_method"] = "greedy"

        # Пытаемся посчитать GLPK
        try:
            solve_glpk_for_trip(vehicle_id, trip_id, verbose=False)
            comparison_result = compare_all_methods_for_trip(vehicle_id, trip_id, verbose=False)
            summary = comparison_result["summary"]

            row.update({
                "status": "success",
                "glpk_status": "success",
                "final_method": "glpk",

                "initial_distance_km": summary.get("initial_distance_km"),
                "initial_time_min": summary.get("initial_time_min"),

                "greedy_distance_km": summary.get("greedy_distance_km"),
                "greedy_time_min": summary.get("greedy_time_min"),

                "glpk_distance_km": summary.get("glpk_distance_km"),
                "glpk_time_min": summary.get("glpk_time_min"),

                "greedy_saved_vs_initial_km": summary.get("greedy_saved_vs_initial_km"),
                "greedy_saved_vs_initial_pct": summary.get("greedy_saved_vs_initial_pct"),
                "greedy_saved_vs_initial_min": summary.get("greedy_saved_vs_initial_min"),
                "greedy_saved_vs_initial_time_pct": summary.get("greedy_saved_vs_initial_time_pct"),

                "glpk_saved_vs_initial_km": summary.get("glpk_saved_vs_initial_km"),
                "glpk_saved_vs_initial_pct": summary.get("glpk_saved_vs_initial_pct"),
                "glpk_saved_vs_initial_min": summary.get("glpk_saved_vs_initial_min"),
                "glpk_saved_vs_initial_time_pct": summary.get("glpk_saved_vs_initial_time_pct"),

                "glpk_better_than_greedy_km": summary.get("glpk_better_than_greedy_km"),
                "glpk_better_than_greedy_pct": summary.get("glpk_better_than_greedy_pct"),
                "glpk_better_than_greedy_min": summary.get("glpk_better_than_greedy_min"),
                "glpk_better_than_greedy_time_pct": summary.get("glpk_better_than_greedy_time_pct"),
            })

        except TimeoutError as e:
            # GLPK не успел, но greedy и initial уже есть
            initial_distance = float(row["initial_distance_km"])
            initial_time = float(row["initial_time_min"])
            greedy_distance = float(row["greedy_distance_km"])
            greedy_time = float(row["greedy_time_min"])

            greedy_saved_km = round(initial_distance - greedy_distance, 3)
            greedy_saved_pct = round((greedy_saved_km / initial_distance) * 100, 2) if initial_distance else 0.0

            greedy_saved_min = round(initial_time - greedy_time, 1)
            greedy_saved_time_pct = round((greedy_saved_min / initial_time) * 100, 2) if initial_time else 0.0

            row.update({
                "status": "success_with_fallback",
                "glpk_status": "timeout",
                "error_message": str(e),
                "final_method": "greedy",

                "greedy_saved_vs_initial_km": greedy_saved_km,
                "greedy_saved_vs_initial_pct": greedy_saved_pct,
                "greedy_saved_vs_initial_min": greedy_saved_min,
                "greedy_saved_vs_initial_time_pct": greedy_saved_time_pct,
            })

        except Exception as e:
            # GLPK дал не timeout, а другую ошибку
            initial_distance = float(row["initial_distance_km"])
            initial_time = float(row["initial_time_min"])
            greedy_distance = float(row["greedy_distance_km"])
            greedy_time = float(row["greedy_time_min"])

            greedy_saved_km = round(initial_distance - greedy_distance, 3)
            greedy_saved_pct = round((greedy_saved_km / initial_distance) * 100, 2) if initial_distance else 0.0

            greedy_saved_min = round(initial_time - greedy_time, 1)
            greedy_saved_time_pct = round((greedy_saved_min / initial_time) * 100, 2) if initial_time else 0.0

            row.update({
                "status": "success_with_fallback",
                "glpk_status": "solver_error",
                "error_message": str(e),
                "final_method": "greedy",

                "greedy_saved_vs_initial_km": greedy_saved_km,
                "greedy_saved_vs_initial_pct": greedy_saved_pct,
                "greedy_saved_vs_initial_min": greedy_saved_min,
                "greedy_saved_vs_initial_time_pct": greedy_saved_time_pct,
            })

    except Exception as e:
        row["status"] = "error"
        row["error_message"] = str(e)

    return row


def main():
    print("Полный пакетный запуск по всем рейсам")
    print()

    trips = load_trips()
    trip_keys = extract_trip_keys(trips)

    print(f"Найдено рейсов: {len(trip_keys)}")
    print()

    result_rows = []

    for idx, item in enumerate(trip_keys, start=1):
        vehicle_id = item["vehicle_id"]
        trip_id = item["trip_id"]
        stops_count = item["stops_count"]

        print(f"[{idx}/{len(trip_keys)}] ТС={vehicle_id}, рейс={trip_id}, stops={stops_count}")

        row = run_full_pipeline_for_trip(vehicle_id, trip_id)
        result_rows.append(row)

        if row["status"] == "success":
            print(
                f"  OK | final=glpk | unique_nodes={row['matrix_unique_nodes_count']} | "
                f"initial={row['initial_distance_km']} км | "
                f"greedy={row['greedy_distance_km']} км | "
                f"glpk={row['glpk_distance_km']} км"
            )
        elif row["status"] == "success_with_fallback":
            print(
                f"  FALLBACK | final=greedy | unique_nodes={row['matrix_unique_nodes_count']} | "
                f"initial={row['initial_distance_km']} км | "
                f"greedy={row['greedy_distance_km']} км | "
                f"reason={row['glpk_status']}"
            )
        else:
            print(f"  ERROR | {row['error_message']}")

        print()

    results_df = pd.DataFrame(result_rows)

    out_xlsx = OPT_RESULTS_DIR / "batch_all_trips_results.xlsx"
    out_json = OPT_RESULTS_DIR / "batch_all_trips_results.json"

    results_df.to_excel(out_xlsx, index=False)

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result_rows, f, ensure_ascii=False, indent=2)

    success_count = int((results_df["status"] == "success").sum())
    fallback_count = int((results_df["status"] == "success_with_fallback").sum())
    error_count = int((results_df["status"] == "error").sum())

    print("Пакетный запуск завершен")
    print(f"Успешно (GLPK): {success_count}")
    print(f"Успешно с fallback: {fallback_count}")
    print(f"С ошибкой: {error_count}")
    print()
    print("Файлы сохранены:")
    print(out_xlsx)
    print(out_json)


if __name__ == "__main__":
    main()