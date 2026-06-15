from dataclasses import dataclass, asdict
from typing import List, Dict, Any
import pandas as pd


@dataclass
class Point:
    point_type: str   # START / STOP / END
    address: str
    lat: float
    lon: float
    point_id: str | None = None
    stop_seq: int | None = None
    district: str | None = None
    time_window: str | None = None


@dataclass
class Trip:
    vehicle_id: str
    trip_id: int
    start: Point
    stops: List[Point]
    end: Point


def _service_points_to_dict(service_df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    result = {}
    for _, row in service_df.iterrows():
        code = str(row["Код точки"]).strip()
        result[code] = {
            "point_type": str(row["Тип служебной точки"]).strip(),
            "address": str(row["Адрес площадки"]).strip(),
            "lat": float(row["Широта площадки"]),
            "lon": float(row["Долгота площадки"]),
            "comment": str(row["Комментарий"]).strip() if pd.notna(row["Комментарий"]) else None,
        }
    return result


def build_trips(routes_df: pd.DataFrame, service_df: pd.DataFrame, rules_df: pd.DataFrame) -> List[Trip]:
    service_points = _service_points_to_dict(service_df)

    trips: List[Trip] = []

    grouped = routes_df.groupby(["Номер ТС", "Номер рейса"], sort=True)

    for (vehicle_id, trip_id), trip_points_df in grouped:
        trip_points_df = trip_points_df.sort_values("Номер задания").copy()

        rule_match = rules_df[
            (rules_df["Номер ТС"] == vehicle_id) &
            (rules_df["Номер рейса"] == trip_id)
        ]

        if rule_match.empty:
            raise ValueError(f"Не найдено правило применения для ТС={vehicle_id}, рейс={trip_id}")

        start_code = str(rule_match.iloc[0]["START_код"]).strip()
        end_code = str(rule_match.iloc[0]["END_код"]).strip()

        if start_code not in service_points:
            raise ValueError(f"Не найдена служебная точка START: {start_code}")

        if end_code not in service_points:
            raise ValueError(f"Не найдена служебная точка END: {end_code}")

        start_point = Point(
            point_type="START",
            address=service_points[start_code]["address"],
            lat=service_points[start_code]["lat"],
            lon=service_points[start_code]["lon"],
        )

        end_point = Point(
            point_type="END",
            address=service_points[end_code]["address"],
            lat=service_points[end_code]["lat"],
            lon=service_points[end_code]["lon"],
        )

        stops: List[Point] = []
        for _, row in trip_points_df.iterrows():
            stops.append(
                Point(
                    point_type="STOP",
                    address=str(row["Адрес площадки"]).strip(),
                    lat=float(row["Широта площадки"]),
                    lon=float(row["Долгота площадки"]),
                    point_id=str(row["ID задания"]).strip(),
                    stop_seq=int(row["Номер задания"]),
                    district=str(row["Район"]).strip() if pd.notna(row["Район"]) else None,
                    time_window=str(row["Интервал вывоза"]).strip() if pd.notna(row["Интервал вывоза"]) else None,
                )
            )

        trips.append(
            Trip(
                vehicle_id=str(vehicle_id).strip(),
                trip_id=int(trip_id),
                start=start_point,
                stops=stops,
                end=end_point,
            )
        )

    return trips


def trips_to_json_serializable(trips: List[Trip]) -> List[Dict[str, Any]]:
    return [
        {
            "vehicle_id": trip.vehicle_id,
            "trip_id": trip.trip_id,
            "start": asdict(trip.start),
            "stops": [asdict(stop) for stop in trip.stops],
            "end": asdict(trip.end),
        }
        for trip in trips
    ]