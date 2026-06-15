import json
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from config import OPT_INPUT_DIR, OPT_RESULTS_DIR


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


def build_arc_lookup(arcs_df: pd.DataFrame) -> Dict[Tuple[str, str], Dict]:
    lookup = {}
    for _, row in arcs_df.iterrows():
        key = (str(row["from_node"]), str(row["to_node"]))
        lookup[key] = {
            "distance_km": float(row["distance_km"]),
            "time_sec": int(row["time_sec"]),
            "time_min": float(row["time_min"]),
        }
    return lookup


def greedy_path(
    start_node: str,
    stop_nodes: List[str],
    end_node: str,
    arc_lookup: Dict[Tuple[str, str], Dict]
):
    unvisited = set(stop_nodes)
    current = start_node
    path = [start_node]
    chosen_arcs = []

    total_distance_km = 0.0
    total_time_sec = 0

    while unvisited:
        candidates = []
        for node in unvisited:
            key = (current, node)
            if key not in arc_lookup:
                raise ValueError(f"Нет дуги {current} -> {node}")
            candidates.append((node, arc_lookup[key]["distance_km"], arc_lookup[key]["time_sec"]))

        candidates.sort(key=lambda x: (x[1], x[2], x[0]))
        next_node, dist_km, time_sec = candidates[0]

        chosen_arcs.append({
            "step_no": len(chosen_arcs) + 1,
            "from_node": current,
            "to_node": next_node,
            "distance_km": dist_km,
            "time_sec": time_sec,
            "time_min": round(time_sec / 60, 1),
            "selection_reason": "nearest_unvisited",
        })

        total_distance_km += dist_km
        total_time_sec += time_sec

        current = next_node
        path.append(next_node)
        unvisited.remove(next_node)

    end_key = (current, end_node)
    if end_key not in arc_lookup:
        raise ValueError(f"Нет дуги {current} -> {end_node}")

    end_arc = arc_lookup[end_key]
    chosen_arcs.append({
        "step_no": len(chosen_arcs) + 1,
        "from_node": current,
        "to_node": end_node,
        "distance_km": end_arc["distance_km"],
        "time_sec": end_arc["time_sec"],
        "time_min": round(end_arc["time_sec"] / 60, 1),
        "selection_reason": "finish_to_end",
    })

    total_distance_km += end_arc["distance_km"]
    total_time_sec += end_arc["time_sec"]
    path.append(end_node)

    result_summary = {
        "start_node": start_node,
        "end_node": end_node,
        "visited_stop_nodes_count": len(stop_nodes),
        "path_nodes": path,
        "path_edges_count": len(chosen_arcs),
        "total_distance_km": round(total_distance_km, 3),
        "total_time_sec": total_time_sec,
        "total_time_min": round(total_time_sec / 60, 1),
        "method": "greedy_nearest_neighbor_path",
    }

    return chosen_arcs, result_summary


def enrich_route_with_node_info(chosen_arcs_df: pd.DataFrame, nodes_df: pd.DataFrame) -> pd.DataFrame:
    node_info = nodes_df[["unique_node_id", "node_role", "lat", "lon", "addresses_joined"]].copy()

    node_info_from = node_info.rename(columns={
        "unique_node_id": "from_node",
        "node_role": "from_role",
        "lat": "from_lat",
        "lon": "from_lon",
        "addresses_joined": "from_addresses",
    })

    node_info_to = node_info.rename(columns={
        "unique_node_id": "to_node",
        "node_role": "to_role",
        "lat": "to_lat",
        "lon": "to_lon",
        "addresses_joined": "to_addresses",
    })

    result = chosen_arcs_df.merge(node_info_from, on="from_node", how="left")
    result = result.merge(node_info_to, on="to_node", how="left")

    return result


def save_json(data: dict, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def solve_greedy_for_trip(vehicle_id: str, trip_id: int, verbose: bool = True) -> dict:
    nodes_df, arcs_df, problem_summary = load_optimization_input(vehicle_id, trip_id)

    start_node = problem_summary["start_node"]
    end_node = problem_summary["end_node"]
    stop_nodes = problem_summary["stop_nodes"]

    arc_lookup = build_arc_lookup(arcs_df)

    chosen_arcs, result_summary = greedy_path(
        start_node=start_node,
        stop_nodes=stop_nodes,
        end_node=end_node,
        arc_lookup=arc_lookup,
    )

    chosen_arcs_df = pd.DataFrame(chosen_arcs)
    chosen_arcs_df = enrich_route_with_node_info(chosen_arcs_df, nodes_df)

    route_path = OPT_RESULTS_DIR / f"greedy_route_{vehicle_id}_trip_{trip_id}.xlsx"
    summary_path = OPT_RESULTS_DIR / f"greedy_summary_{vehicle_id}_trip_{trip_id}.json"

    chosen_arcs_df.to_excel(route_path, index=False)
    save_json(result_summary, summary_path)

    if verbose:
        print(f"Жадная оптимизация: ТС={vehicle_id}, рейс={trip_id}")
        print()
        print(f"START: {start_node}")
        print(f"END:   {end_node}")
        print(f"STOP узлов: {len(stop_nodes)}")
        print()
        print("Полученный порядок узлов:")
        print(" -> ".join(result_summary["path_nodes"]))
        print()
        print(f"Суммарная длина: {result_summary['total_distance_km']} км")
        print(f"Суммарное время: {result_summary['total_time_min']} мин")
        print()
        print("Файлы сохранены:")
        print(route_path)
        print(summary_path)

    return {
        "vehicle_id": vehicle_id,
        "trip_id": trip_id,
        "status": "success",
        "summary": result_summary,
        "route_path": str(route_path),
        "summary_path": str(summary_path),
    }


def main():
    VEHICLE_ID = "Е691ЕК550"
    TRIP_ID = 1
    solve_greedy_for_trip(VEHICLE_ID, TRIP_ID, verbose=True)


if __name__ == "__main__":
    main()