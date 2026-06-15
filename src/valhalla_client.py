import requests
from typing import List, Dict, Any
from config import VALHALLA_URL


class ValhallaClient:
    def __init__(self, base_url: str = VALHALLA_URL, timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def build_route_payload(self, locations: List[Dict[str, float]]) -> Dict[str, Any]:
        return {
            "locations": locations,
            "costing": "auto",
            "directions_options": {
                "units": "kilometers"
            }
        }

    def route(self, locations: List[Dict[str, float]]) -> Dict[str, Any]:
        if len(locations) < 2:
            raise ValueError("Для построения маршрута нужно минимум 2 точки")

        payload = self.build_route_payload(locations)
        url = f"{self.base_url}/route"

        response = requests.post(url, json=payload, timeout=self.timeout)

        if response.status_code != 200:
            raise RuntimeError(
                f"Valhalla вернула ошибку {response.status_code}: {response.text}"
            )

        return response.json()

    @staticmethod
    def extract_summary(route_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Достает сводную информацию из ответа Valhalla.
        """
        trip = route_json.get("trip", {})
        legs = trip.get("legs", [])

        total_length_km = 0.0
        total_time_sec = 0
        has_legs = False

        for leg in legs:
            summary = leg.get("summary", {})
            total_length_km += float(summary.get("length", 0.0))
            total_time_sec += int(summary.get("time", 0))
            has_legs = True

        return {
            "has_legs": has_legs,
            "distance_km": round(total_length_km, 3),
            "time_sec": total_time_sec,
            "time_min": round(total_time_sec / 60, 1),
            "legs_count": len(legs),
        }