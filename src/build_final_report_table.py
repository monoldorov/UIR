import json
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd

from config import OPT_RESULTS_DIR


def load_batch_results() -> List[Dict[str, Any]]:
    path = OPT_RESULTS_DIR / "batch_all_trips_results.json"
    if not path.exists():
        raise FileNotFoundError(f"Не найден файл: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def safe_round(value, digits=3):
    if value is None:
        return None
    return round(float(value), digits)


def build_final_method_label(row: Dict[str, Any]) -> str:
    final_method = row.get("final_method")
    if final_method == "glpk":
        return "GLPK"
    if final_method == "greedy":
        return "Greedy (fallback)"
    return "Unknown"


def build_final_distance(row: Dict[str, Any]):
    final_method = row.get("final_method")
    if final_method == "glpk":
        return row.get("glpk_distance_km")
    if final_method == "greedy":
        return row.get("greedy_distance_km")
    return None


def build_final_time(row: Dict[str, Any]):
    final_method = row.get("final_method")
    if final_method == "glpk":
        return row.get("glpk_time_min")
    if final_method == "greedy":
        return row.get("greedy_time_min")
    return None


def build_final_saved_km(row: Dict[str, Any]):
    final_method = row.get("final_method")
    if final_method == "glpk":
        return row.get("glpk_saved_vs_initial_km")
    if final_method == "greedy":
        return row.get("greedy_saved_vs_initial_km")
    return None


def build_final_saved_pct(row: Dict[str, Any]):
    final_method = row.get("final_method")
    if final_method == "glpk":
        return row.get("glpk_saved_vs_initial_pct")
    if final_method == "greedy":
        return row.get("greedy_saved_vs_initial_pct")
    return None


def build_final_saved_min(row: Dict[str, Any]):
    final_method = row.get("final_method")
    if final_method == "glpk":
        return row.get("glpk_saved_vs_initial_min")
    if final_method == "greedy":
        return row.get("greedy_saved_vs_initial_min")
    return None


def build_final_saved_time_pct(row: Dict[str, Any]):
    final_method = row.get("final_method")
    if final_method == "glpk":
        return row.get("glpk_saved_vs_initial_time_pct")
    if final_method == "greedy":
        return row.get("greedy_saved_vs_initial_time_pct")
    return None


def build_note(row: Dict[str, Any]) -> str:
    if row.get("status") == "success":
        return "Точный метод GLPK"
    if row.get("status") == "success_with_fallback":
        reason = row.get("glpk_status") or "unknown"
        return f"Использован fallback на greedy, причина: {reason}"
    if row.get("status") == "error":
        return f"Ошибка: {row.get('error_message')}"
    return ""


def main():
    rows = load_batch_results()

    final_rows = []

    for row in rows:
        final_distance = build_final_distance(row)
        final_time = build_final_time(row)
        final_saved_km = build_final_saved_km(row)
        final_saved_pct = build_final_saved_pct(row)
        final_saved_min = build_final_saved_min(row)
        final_saved_time_pct = build_final_saved_time_pct(row)

        final_rows.append({
            "ТС": row.get("vehicle_id"),
            "Рейс": row.get("trip_id"),
            "Статус": row.get("status"),
            "Итоговый метод": build_final_method_label(row),
            "Статус GLPK": row.get("glpk_status"),

            "Число уникальных узлов": row.get("matrix_unique_nodes_count"),

            "Исходная длина, км": safe_round(row.get("initial_distance_km")),
            "Исходное время, мин": safe_round(row.get("initial_time_min"), 1),

            "Greedy длина, км": safe_round(row.get("greedy_distance_km")),
            "Greedy время, мин": safe_round(row.get("greedy_time_min"), 1),

            "GLPK длина, км": safe_round(row.get("glpk_distance_km")),
            "GLPK время, мин": safe_round(row.get("glpk_time_min"), 1),

            "Итоговая длина, км": safe_round(final_distance),
            "Итоговое время, мин": safe_round(final_time, 1),

            "Экономия итогового метода, км": safe_round(final_saved_km),
            "Экономия итогового метода, %": safe_round(final_saved_pct, 2),
            "Экономия итогового метода, мин": safe_round(final_saved_min, 1),
            "Экономия итогового метода по времени, %": safe_round(final_saved_time_pct, 2),

            "GLPK лучше Greedy, км": safe_round(row.get("glpk_better_than_greedy_km")),
            "GLPK лучше Greedy, мин": safe_round(row.get("glpk_better_than_greedy_min"), 1),

            "Примечание": build_note(row),
        })

    df = pd.DataFrame(final_rows)

    xlsx_path = OPT_RESULTS_DIR / "final_report_table.xlsx"
    json_path = OPT_RESULTS_DIR / "final_report_table.json"

    df.to_excel(xlsx_path, index=False)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(final_rows, f, ensure_ascii=False, indent=2)

    # Краткая текстовая сводка
    total = len(df)
    success_glpk = int((df["Итоговый метод"] == "GLPK").sum())
    success_fallback = int((df["Итоговый метод"] == "Greedy (fallback)").sum())

    avg_initial = round(df["Исходная длина, км"].dropna().mean(), 3)
    avg_final = round(df["Итоговая длина, км"].dropna().mean(), 3)
    avg_saved = round(df["Экономия итогового метода, км"].dropna().mean(), 3)

    print("Финальная отчетная таблица построена")
    print()
    print(f"Всего рейсов: {total}")
    print(f"Итоговый GLPK: {success_glpk}")
    print(f"Fallback на Greedy: {success_fallback}")
    print()
    print(f"Средняя исходная длина: {avg_initial} км")
    print(f"Средняя итоговая длина: {avg_final} км")
    print(f"Средняя экономия: {avg_saved} км")
    print()
    print("Файлы сохранены:")
    print(xlsx_path)
    print(json_path)


if __name__ == "__main__":
    main()