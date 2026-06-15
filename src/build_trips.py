import json
from config import OUTPUT_DIR
from data_loader import load_excel_data
from trip_builder import build_trips, trips_to_json_serializable


def main():
    routes_df, service_df, rules_df = load_excel_data()
    trips = build_trips(routes_df, service_df, rules_df)

    print(f"Собрано рейсов: {len(trips)}")
    print()

    for trip in trips:
        print(f"ТС: {trip.vehicle_id} | Рейс: {trip.trip_id}")
        print(f"  START: {trip.start.address} ({trip.start.lat}, {trip.start.lon})")
        print(f"  STOPS: {len(trip.stops)}")
        print(f"  END:   {trip.end.address} ({trip.end.lat}, {trip.end.lon})")
        print()

    trips_json = trips_to_json_serializable(trips)
    out_path = OUTPUT_DIR / "trips.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(trips_json, f, ensure_ascii=False, indent=2)

    print(f"JSON сохранен: {out_path}")


if __name__ == "__main__":
    main()