import json
from pathlib import Path

import pandas as pd

from config import ROUTES_DIR, OPT_RESULTS_DIR, GLPK_DIR
from file_naming import normalize_vehicle_id_for_filename


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Не найден файл: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def safe_pct(saved: float, base: float) -> float:
    if base == 0:
        return 0.0
    return round((saved / base) * 100, 2)


def compare_all_methods_for_trip(vehicle_id: str, trip_id: int, verbose: bool = True) -> dict:
    safe_vehicle_id = normalize_vehicle_id_for_filename(vehicle_id)

    initial_summary_path = ROUTES_DIR / f"initial_route_{vehicle_id}_trip_{trip_id}_summary.json"
    greedy_summary_path = OPT_RESULTS_DIR / f"greedy_summary_{vehicle_id}_trip_{trip_id}.json"
    glpk_summary_path = GLPK_DIR / f"glpk_result_{safe_vehicle_id}_trip_{trip_id}.json"

    initial_summary = load_json(initial_summary_path)
    greedy_summary = load_json(greedy_summary_path)
    glpk_summary = load_json(glpk_summary_path)

    initial_distance = float(initial_summary["total_distance_km"])
    initial_time_min = float(initial_summary["total_time_min"])

    greedy_distance = float(greedy_summary["total_distance_km"])
    greedy_time_min = float(greedy_summary["total_time_min"])

    glpk_distance = float(glpk_summary["objective_km"])
    glpk_time_min = float(glpk_summary["total_time_min"])

    greedy_saved_km = round(initial_distance - greedy_distance, 3)
    greedy_saved_pct = safe_pct(greedy_saved_km, initial_distance)

    greedy_saved_min = round(initial_time_min - greedy_time_min, 1)
    greedy_saved_time_pct = safe_pct(greedy_saved_min, initial_time_min)

    glpk_saved_km = round(initial_distance - glpk_distance, 3)
    glpk_saved_pct = safe_pct(glpk_saved_km, initial_distance)

    glpk_saved_min = round(initial_time_min - glpk_time_min, 1)
    glpk_saved_time_pct = safe_pct(glpk_saved_min, initial_time_min)

    glpk_vs_greedy_km = round(greedy_distance - glpk_distance, 3)
    glpk_vs_greedy_pct = safe_pct(glpk_vs_greedy_km, greedy_distance)

    glpk_vs_greedy_min = round(greedy_time_min - glpk_time_min, 1)
    glpk_vs_greedy_time_pct = safe_pct(glpk_vs_greedy_min, greedy_time_min)

    result = {
        "vehicle_id": vehicle_id,
        "trip_id": trip_id,

        "initial_distance_km": initial_distance,
        "initial_time_min": initial_time_min,

        "greedy_distance_km": greedy_distance,
        "greedy_time_min": greedy_time_min,
        "greedy_saved_vs_initial_km": greedy_saved_km,
        "greedy_saved_vs_initial_pct": greedy_saved_pct,
        "greedy_saved_vs_initial_min": greedy_saved_min,
        "greedy_saved_vs_initial_time_pct": greedy_saved_time_pct,

        "glpk_distance_km": glpk_distance,
        "glpk_time_min": glpk_time_min,
        "glpk_saved_vs_initial_km": glpk_saved_km,
        "glpk_saved_vs_initial_pct": glpk_saved_pct,
        "glpk_saved_vs_initial_min": glpk_saved_min,
        "glpk_saved_vs_initial_time_pct": glpk_saved_time_pct,

        "glpk_better_than_greedy_km": glpk_vs_greedy_km,
        "glpk_better_than_greedy_pct": glpk_vs_greedy_pct,
        "glpk_better_than_greedy_min": glpk_vs_greedy_min,
        "glpk_better_than_greedy_time_pct": glpk_vs_greedy_time_pct,

        "greedy_method": greedy_summary.get("method"),
        "glpk_method": glpk_summary.get("method"),
        "greedy_path_nodes": greedy_summary.get("path_nodes", []),
        "glpk_path_nodes": glpk_summary.get("path_nodes", []),
    }

    out_json = OPT_RESULTS_DIR / f"comparison_all_methods_{vehicle_id}_trip_{trip_id}.json"
    out_xlsx = OPT_RESULTS_DIR / f"comparison_all_methods_{vehicle_id}_trip_{trip_id}.xlsx"

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    pd.DataFrame([result]).to_excel(out_xlsx, index=False)

    if verbose:
        print(f"Сравнение всех методов: ТС={vehicle_id}, рейс={trip_id}")
        print()
        print(f"Исходный маршрут: {initial_distance} км, {initial_time_min} мин")
        print(f"Greedy:           {greedy_distance} км, {greedy_time_min} мин")
        print(f"GLPK:             {glpk_distance} км, {glpk_time_min} мин")
        print()
        print(f"Greedy vs initial: -{greedy_saved_km} км ({greedy_saved_pct}%)")
        print(f"Greedy vs initial: -{greedy_saved_min} мин ({greedy_saved_time_pct}%)")
        print()
        print(f"GLPK vs initial:   -{glpk_saved_km} км ({glpk_saved_pct}%)")
        print(f"GLPK vs initial:   -{glpk_saved_min} мин ({glpk_saved_time_pct}%)")
        print()
        print(f"GLPK vs greedy:    -{glpk_vs_greedy_km} км ({glpk_vs_greedy_pct}%)")
        print(f"GLPK vs greedy:    -{glpk_vs_greedy_min} мин ({glpk_vs_greedy_time_pct}%)")
        print()
        print("Файлы сохранены:")
        print(out_json)
        print(out_xlsx)

    return {
        "vehicle_id": vehicle_id,
        "trip_id": trip_id,
        "status": "success",
        "summary": result,
        "comparison_json_path": str(out_json),
        "comparison_xlsx_path": str(out_xlsx),
    }


def main():
    VEHICLE_ID = "Е691ЕК550"
    TRIP_ID = 1
    compare_all_methods_for_trip(VEHICLE_ID, TRIP_ID, verbose=True)


if __name__ == "__main__":
    main()