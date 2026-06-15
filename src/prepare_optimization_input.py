import json
from pathlib import Path
from typing import Tuple

import pandas as pd

from config import MATRICES_DIR, OPT_INPUT_DIR


def load_matrix_files(vehicle_id: str, trip_id: int) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    unique_nodes_path = MATRICES_DIR / f"trip_unique_nodes_{vehicle_id}_trip_{trip_id}.xlsx"
    mapping_path = MATRICES_DIR / f"trip_node_mapping_{vehicle_id}_trip_{trip_id}.xlsx"
    matrix_path = MATRICES_DIR / f"trip_distance_matrix_{vehicle_id}_trip_{trip_id}.xlsx"

    if not unique_nodes_path.exists():
        raise FileNotFoundError(f"Не найден файл: {unique_nodes_path}")
    if not mapping_path.exists():
        raise FileNotFoundError(f"Не найден файл: {mapping_path}")
    if not matrix_path.exists():
        raise FileNotFoundError(f"Не найден файл: {matrix_path}")

    unique_nodes_df = pd.read_excel(unique_nodes_path)
    mapping_df = pd.read_excel(mapping_path)
    matrix_df = pd.read_excel(matrix_path)

    return unique_nodes_df, mapping_df, matrix_df


def detect_node_roles(mapping_df: pd.DataFrame) -> pd.DataFrame:
    grouped = mapping_df.groupby("unique_node_id", sort=False)

    role_rows = []

    for unique_node_id, group in grouped:
        point_types = set(group["point_type"].dropna().astype(str))

        if "START" in point_types and "END" in point_types:
            raise ValueError(f"Узел {unique_node_id} одновременно START и END")
        if "START" in point_types and "STOP" in point_types:
            raise ValueError(f"Узел {unique_node_id} одновременно START и STOP")
        if "END" in point_types and "STOP" in point_types:
            raise ValueError(f"Узел {unique_node_id} одновременно END и STOP")

        if "START" in point_types:
            node_role = "START"
        elif "END" in point_types:
            node_role = "END"
        else:
            node_role = "STOP"

        role_rows.append({
            "unique_node_id": unique_node_id,
            "node_role": node_role,
            "source_count": len(group),
            "source_labels": " | ".join(group["label"].astype(str).tolist()),
            "source_addresses": " | ".join(group["address"].astype(str).tolist()),
            "source_point_ids": " | ".join(group["point_id"].dropna().astype(str).tolist()) if group["point_id"].notna().any() else None,
        })

    return pd.DataFrame(role_rows)


def build_nodes_for_optimization(unique_nodes_df: pd.DataFrame, roles_df: pd.DataFrame) -> pd.DataFrame:
    nodes_df = unique_nodes_df.merge(
        roles_df,
        on="unique_node_id",
        how="left",
        suffixes=("_unique", "_role")
    )

    if "source_count_unique" in nodes_df.columns:
        nodes_df["source_count"] = nodes_df["source_count_unique"]
    elif "source_count_role" in nodes_df.columns:
        nodes_df["source_count"] = nodes_df["source_count_role"]

    cols = [
        "unique_node_id",
        "node_role",
        "lat",
        "lon",
        "coord_key",
        "source_count",
        "labels_joined",
        "addresses_joined",
        "point_ids_joined",
        "source_labels",
        "source_addresses",
        "source_point_ids",
    ]

    existing_cols = [c for c in cols if c in nodes_df.columns]
    nodes_df = nodes_df[existing_cols].copy()

    start_count = int((nodes_df["node_role"] == "START").sum())
    end_count = int((nodes_df["node_role"] == "END").sum())

    if start_count != 1:
        raise ValueError(f"Ожидался ровно 1 START, найдено: {start_count}")
    if end_count != 1:
        raise ValueError(f"Ожидался ровно 1 END, найдено: {end_count}")

    return nodes_df


def build_arcs_for_optimization(matrix_df: pd.DataFrame) -> pd.DataFrame:
    arcs_df = matrix_df.copy()
    arcs_df = arcs_df[arcs_df["from_node"] != arcs_df["to_node"]].copy()

    keep_cols = [
        "from_node",
        "to_node",
        "distance_km",
        "time_sec",
        "time_min",
    ]
    arcs_df = arcs_df[keep_cols].copy()
    arcs_df = arcs_df.sort_values(by=["from_node", "to_node"]).reset_index(drop=True)

    return arcs_df


def validate_arc_connectivity(nodes_df: pd.DataFrame, arcs_df: pd.DataFrame) -> None:
    all_nodes = set(nodes_df["unique_node_id"])
    from_nodes = set(arcs_df["from_node"])
    to_nodes = set(arcs_df["to_node"])

    if all_nodes - from_nodes:
        raise ValueError(f"Есть узлы без исходящих дуг: {all_nodes - from_nodes}")

    if all_nodes - to_nodes:
        raise ValueError(f"Есть узлы без входящих дуг: {all_nodes - to_nodes}")


def build_problem_summary(vehicle_id: str, trip_id: int, nodes_df: pd.DataFrame, arcs_df: pd.DataFrame) -> dict:
    start_node = nodes_df.loc[nodes_df["node_role"] == "START", "unique_node_id"].iloc[0]
    end_node = nodes_df.loc[nodes_df["node_role"] == "END", "unique_node_id"].iloc[0]
    stop_nodes = nodes_df.loc[nodes_df["node_role"] == "STOP", "unique_node_id"].tolist()

    return {
        "vehicle_id": vehicle_id,
        "trip_id": trip_id,
        "nodes_count_total": int(len(nodes_df)),
        "stop_nodes_count": int(len(stop_nodes)),
        "arcs_count": int(len(arcs_df)),
        "start_node": start_node,
        "end_node": end_node,
        "stop_nodes": stop_nodes,
    }


def save_json(data: dict, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def prepare_optimization_input_for_trip(vehicle_id: str, trip_id: int, verbose: bool = True) -> dict:
    unique_nodes_df, mapping_df, matrix_df = load_matrix_files(vehicle_id, trip_id)

    roles_df = detect_node_roles(mapping_df)
    nodes_df = build_nodes_for_optimization(unique_nodes_df, roles_df)
    arcs_df = build_arcs_for_optimization(matrix_df)
    validate_arc_connectivity(nodes_df, arcs_df)

    summary = build_problem_summary(vehicle_id, trip_id, nodes_df, arcs_df)

    nodes_path = OPT_INPUT_DIR / f"opt_nodes_{vehicle_id}_trip_{trip_id}.xlsx"
    arcs_path = OPT_INPUT_DIR / f"opt_arcs_{vehicle_id}_trip_{trip_id}.xlsx"
    summary_path = OPT_INPUT_DIR / f"opt_problem_summary_{vehicle_id}_trip_{trip_id}.json"

    nodes_df.to_excel(nodes_path, index=False)
    arcs_df.to_excel(arcs_path, index=False)
    save_json(summary, summary_path)

    if verbose:
        print(f"Подготовка входа для оптимизации: ТС={vehicle_id}, рейс={trip_id}")
        print()

        cols_to_show = [c for c in ["unique_node_id", "node_role", "source_count"] if c in nodes_df.columns]
        print("Роли узлов:")
        print(nodes_df[cols_to_show].to_string(index=False))
        print()

        print(f"START: {summary['start_node']}")
        print(f"END:   {summary['end_node']}")
        print(f"STOP узлов: {summary['stop_nodes_count']}")
        print(f"Всего дуг без диагонали: {summary['arcs_count']}")
        print()
        print("Файлы сохранены:")
        print(nodes_path)
        print(arcs_path)
        print(summary_path)

    return {
        "vehicle_id": vehicle_id,
        "trip_id": trip_id,
        "status": "success",
        "summary": summary,
        "nodes_path": str(nodes_path),
        "arcs_path": str(arcs_path),
        "summary_path": str(summary_path),
    }


def main():
    VEHICLE_ID = "Е691ЕК550"
    TRIP_ID = 1
    prepare_optimization_input_for_trip(VEHICLE_ID, TRIP_ID, verbose=True)


if __name__ == "__main__":
    main()