import json
from pathlib import Path

import pandas as pd

from config import ROUTES_DIR, OPT_RESULTS_DIR


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Не найден файл: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    VEHICLE_ID = "Е691ЕК550"
    TRIP_ID = 1

    initial_summary_path = ROUTES_DIR / f"initial_route_{VEHICLE_ID}_trip_{TRIP_ID}_summary.json"
    greedy_summary_path = OPT_RESULTS_DIR / f"greedy_summary_{VEHICLE_ID}_trip_{TRIP_ID}.json"

    initial_summary = load_json(initial_summary_path)
    greedy_summary = load_json(greedy_summary_path)

    initial_distance = float(initial_summary["total_distance_km"])
    greedy_distance = float(greedy_summary["total_distance_km"])

    initial_time_min = float(initial_summary["total_time_min"])
    greedy_time_min = float(greedy_summary["total_time_min"])

    distance_saved = round(initial_distance - greedy_distance, 3)
    time_saved_min = round(initial_time_min - greedy_time_min, 1)

    distance_saved_pct = round((distance_saved / initial_distance) * 100, 2) if initial_distance else 0.0
    time_saved_pct = round((time_saved_min / initial_time_min) * 100, 2) if initial_time_min else 0.0

    comparison = {
        "vehicle_id": VEHICLE_ID,
        "trip_id": TRIP_ID,
        "initial_distance_km": initial_distance,
        "greedy_distance_km": greedy_distance,
        "distance_saved_km": distance_saved,
        "distance_saved_pct": distance_saved_pct,
        "initial_time_min": initial_time_min,
        "greedy_time_min": greedy_time_min,
        "time_saved_min": time_saved_min,
        "time_saved_pct": time_saved_pct,
        "initial_method": "valhalla_segmented_original_order",
        "optimized_method": greedy_summary.get("method", "greedy"),
        "greedy_path_nodes": greedy_summary.get("path_nodes", []),
    }

    print(f"Сравнение маршрутов: ТС={VEHICLE_ID}, рейс={TRIP_ID}")
    print()
    print(f"Исходная длина:        {initial_distance} км")
    print(f"Жадная длина:          {greedy_distance} км")
    print(f"Экономия по длине:     {distance_saved} км ({distance_saved_pct}%)")
    print()
    print(f"Исходное время:        {initial_time_min} мин")
    print(f"Жадное время:          {greedy_time_min} мин")
    print(f"Экономия по времени:   {time_saved_min} мин ({time_saved_pct}%)")
    print()

    out_json = OPT_RESULTS_DIR / f"comparison_{VEHICLE_ID}_trip_{TRIP_ID}.json"
    out_xlsx = OPT_RESULTS_DIR / f"comparison_{VEHICLE_ID}_trip_{TRIP_ID}.xlsx"

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(comparison, f, ensure_ascii=False, indent=2)

    pd.DataFrame([comparison]).to_excel(out_xlsx, index=False)

    print("Файлы сохранены:")
    print(out_json)
    print(out_xlsx)


if __name__ == "__main__":
    main()