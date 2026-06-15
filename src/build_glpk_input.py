import json
from pathlib import Path
from typing import Tuple

import pandas as pd

from config import OPT_INPUT_DIR, GLPK_DIR
from file_naming import normalize_vehicle_id_for_filename


def load_optimization_input(vehicle_id: str, trip_id: int) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    nodes_path = OPT_INPUT_DIR / f"opt_nodes_{vehicle_id}_trip_{trip_id}.xlsx"
    arcs_path = OPT_INPUT_DIR / f"opt_arcs_{vehicle_id}_trip_{trip_id}.xlsx"
    summary_path = OPT_INPUT_DIR / f"opt_problem_summary_{vehicle_id}_trip_{trip_id}.json"

    if not nodes_path.exists():
        raise FileNotFoundError(f"Не найден файл: {nodes_path}")
    if not arcs_path.exists():
        raise FileNotFoundError(f"Не найден файл: {arcs_path}")
    if not summary_path.exists():
        raise FileNotFoundError(f"Не найден файл: {summary_path}")

    nodes_df = pd.read_excel(nodes_path)
    arcs_df = pd.read_excel(arcs_path)

    with open(summary_path, "r", encoding="utf-8") as f:
        summary = json.load(f)

    return nodes_df, arcs_df, summary


def build_dat_content(nodes_df: pd.DataFrame, arcs_df: pd.DataFrame, summary: dict) -> str:
    nodes = nodes_df["unique_node_id"].astype(str).tolist()
    start_node = summary["start_node"]
    finish_node = summary["end_node"]

    lines = []
    lines.append("data;")
    lines.append("")

    lines.append("set N :=")
    lines.append("  " + " ".join(nodes))
    lines.append(";")
    lines.append("")

    lines.append("set A :=")
    for _, row in arcs_df.iterrows():
        i = str(row["from_node"])
        j = str(row["to_node"])
        lines.append(f"  ({i},{j})")
    lines.append(";")
    lines.append("")

    lines.append(f'param start := "{start_node}";')
    lines.append(f'param finish := "{finish_node}";')
    lines.append("")

    lines.append("param c :=")
    for _, row in arcs_df.iterrows():
        i = str(row["from_node"])
        j = str(row["to_node"])
        c = float(row["distance_km"])
        lines.append(f"  [{i},{j}] {c}")
    lines.append(";")
    lines.append("")

    lines.append("end;")
    lines.append("")

    return "\n".join(lines)


def build_glpk_input_for_trip(vehicle_id: str, trip_id: int, verbose: bool = True) -> dict:
    safe_vehicle_id = normalize_vehicle_id_for_filename(vehicle_id)

    nodes_df, arcs_df, summary = load_optimization_input(vehicle_id, trip_id)
    dat_content = build_dat_content(nodes_df, arcs_df, summary)

    out_path = GLPK_DIR / f"trip_{safe_vehicle_id}_trip_{trip_id}.dat"

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(dat_content)

    if verbose:
        print(f"Подготовка .dat для GLPK: ТС={vehicle_id}, рейс={trip_id}")
        print(f".dat файл сохранен: {out_path}")

    return {
        "vehicle_id": vehicle_id,
        "trip_id": trip_id,
        "status": "success",
        "dat_path": str(out_path),
        "nodes_count": int(len(nodes_df)),
        "arcs_count": int(len(arcs_df)),
        "start_node": summary["start_node"],
        "end_node": summary["end_node"],
    }


def main():
    VEHICLE_ID = "Е691ЕК550"
    TRIP_ID = 1
    build_glpk_input_for_trip(VEHICLE_ID, TRIP_ID, verbose=True)


if __name__ == "__main__":
    main()