import json
import subprocess
from pathlib import Path
from typing import List, Dict

import pandas as pd

from config import GLPK_DIR, MODELS_DIR, GLPSOL_EXE, OPT_INPUT_DIR
from file_naming import normalize_vehicle_id_for_filename

GLPK_TIMEOUT_SEC = 120


def parse_glpk_output(output_text: str) -> Dict:
    lines = output_text.splitlines()

    objective = None
    selected_arcs = []

    in_arc_block = False

    for line in lines:
        line = line.strip()

        if line.startswith("Objective_km="):
            objective = float(line.split("=")[1])

        elif line == "SelectedArcsBegin":
            in_arc_block = True
            continue
        elif line == "SelectedArcsEnd":
            in_arc_block = False
            continue

        elif in_arc_block and line:
            parts = line.split(",")
            if len(parts) == 3:
                selected_arcs.append({
                    "from_node": parts[0],
                    "to_node": parts[1],
                    "distance_km": float(parts[2]),
                })

    if objective is None:
        raise ValueError("Не удалось прочитать objective из вывода GLPK")

    return {
        "objective_km": objective,
        "selected_arcs": selected_arcs,
    }


def restore_path(selected_arcs: List[Dict], start_node: str, finish_node: str) -> List[str]:
    next_map = {}
    for arc in selected_arcs:
        next_map[arc["from_node"]] = arc["to_node"]

    path = [start_node]
    current = start_node
    visited = {start_node}

    while current != finish_node:
        if current not in next_map:
            raise ValueError(f"Не найден следующий узел из {current}")
        current = next_map[current]
        if current in visited and current != finish_node:
            raise ValueError(f"Обнаружен цикл при восстановлении пути: {current}")
        path.append(current)
        visited.add(current)

    return path


def load_arc_metrics(vehicle_id: str, trip_id: int) -> dict:
    arcs_path = OPT_INPUT_DIR / f"opt_arcs_{vehicle_id}_trip_{trip_id}.xlsx"
    if not arcs_path.exists():
        raise FileNotFoundError(f"Не найден файл дуг: {arcs_path}")

    arcs_df = pd.read_excel(arcs_path)

    lookup = {}
    for _, row in arcs_df.iterrows():
        key = (str(row["from_node"]), str(row["to_node"]))
        lookup[key] = {
            "distance_km": float(row["distance_km"]),
            "time_sec": int(row["time_sec"]),
            "time_min": float(row["time_min"]),
        }
    return lookup


def solve_glpk_for_trip(vehicle_id: str, trip_id: int, verbose: bool = True) -> dict:
    safe_vehicle_id = normalize_vehicle_id_for_filename(vehicle_id)

    model_path = MODELS_DIR / "tsp_path.mod"
    data_path = GLPK_DIR / f"trip_{safe_vehicle_id}_trip_{trip_id}.dat"
    raw_output_path = GLPK_DIR / f"glpk_raw_output_{safe_vehicle_id}_trip_{trip_id}.txt"
    result_json_path = GLPK_DIR / f"glpk_result_{safe_vehicle_id}_trip_{trip_id}.json"
    result_xlsx_path = GLPK_DIR / f"glpk_result_{safe_vehicle_id}_trip_{trip_id}.xlsx"

    if not GLPSOL_EXE.exists():
        raise FileNotFoundError(f"Не найден glpsol.exe: {GLPSOL_EXE}")
    if not model_path.exists():
        raise FileNotFoundError(f"Не найдена модель: {model_path}")
    if not data_path.exists():
        raise FileNotFoundError(f"Не найден .dat файл: {data_path}")

    if verbose:
        print(f"Запуск GLPK: ТС={vehicle_id}, рейс={trip_id}")
        print(f"Модель: {model_path}")
        print(f"Данные: {data_path}")
        print()

    cmd = [
        str(GLPSOL_EXE),
        "-m", str(model_path),
        "-d", str(data_path),
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GLPK_TIMEOUT_SEC
        )

    except subprocess.TimeoutExpired:
        raise TimeoutError(
            f"GLPK превысил лимит времени {GLPK_TIMEOUT_SEC} сек для ТС={vehicle_id}, рейс={trip_id}"
            )
    full_output = (proc.stdout or "") + "\n" + (proc.stderr or "")

    with open(raw_output_path, "w", encoding="utf-8") as f:
        f.write(full_output)

    if proc.returncode != 0:
        if verbose:
            print(full_output)
        raise RuntimeError(f"GLPK завершился с кодом {proc.returncode}")

    parsed = parse_glpk_output(full_output)

    arc_lookup = load_arc_metrics(vehicle_id, trip_id)

    total_time_sec = 0
    enriched_selected_arcs = []

    for arc in parsed["selected_arcs"]:
        key = (arc["from_node"], arc["to_node"])
        if key not in arc_lookup:
            raise ValueError(f"Не найдены метрики для дуги {key}")

        metrics = arc_lookup[key]

        enriched_arc = {
            "from_node": arc["from_node"],
            "to_node": arc["to_node"],
            "distance_km": metrics["distance_km"],
            "time_sec": metrics["time_sec"],
            "time_min": metrics["time_min"],
        }
        enriched_selected_arcs.append(enriched_arc)
        total_time_sec += metrics["time_sec"]

    total_time_min = round(total_time_sec / 60, 1)

    with open(data_path, "r", encoding="utf-8") as f:
        dat_text = f.read()

    start_node = None
    finish_node = None
    for line in dat_text.splitlines():
        line = line.strip()
        if line.startswith('param start :='):
            start_node = line.split('"')[1]
        if line.startswith('param finish :='):
            finish_node = line.split('"')[1]

    if not start_node or not finish_node:
        raise ValueError("Не удалось извлечь start/finish из .dat файла")

    path_nodes = restore_path(enriched_selected_arcs, start_node, finish_node)

    result = {
        "vehicle_id": vehicle_id,
        "trip_id": trip_id,
        "method": "glpk_mtz_path",
        "objective_km": round(parsed["objective_km"], 3),
        "total_time_sec": total_time_sec,
        "total_time_min": total_time_min,
        "selected_arcs_count": len(enriched_selected_arcs),
        "path_nodes": path_nodes,
        "start_node": start_node,
        "finish_node": finish_node,
        "selected_arcs": enriched_selected_arcs,
    }

    with open(result_json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    pd.DataFrame(enriched_selected_arcs).to_excel(result_xlsx_path, index=False)

    if verbose:
        print(f"Objective: {result['objective_km']} км")
        print(f"Время маршрута: {result['total_time_min']} мин")
        print("Путь:")
        print(" -> ".join(path_nodes))
        print()
        print("Файлы сохранены:")
        print(raw_output_path)
        print(result_json_path)
        print(result_xlsx_path)

    return {
        "vehicle_id": vehicle_id,
        "trip_id": trip_id,
        "status": "success",
        "summary": result,
        "raw_output_path": str(raw_output_path),
        "result_json_path": str(result_json_path),
        "result_xlsx_path": str(result_xlsx_path),
    }


def main():
    VEHICLE_ID = "М564НМ790"
    TRIP_ID = 2
    solve_glpk_for_trip(VEHICLE_ID, TRIP_ID, verbose=True)


if __name__ == "__main__":
    main()