from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_XLSX = BASE_DIR / "data" / "input" / "СЗАО данные.xlsx"

OUTPUT_DIR = BASE_DIR / "data" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ROUTES_DIR = OUTPUT_DIR / "routes"
ROUTES_DIR.mkdir(parents=True, exist_ok=True)

MATRICES_DIR = OUTPUT_DIR / "matrices"
MATRICES_DIR.mkdir(parents=True, exist_ok=True)

OPT_INPUT_DIR = OUTPUT_DIR / "optimization_input"
OPT_INPUT_DIR.mkdir(parents=True, exist_ok=True)

OPT_RESULTS_DIR = OUTPUT_DIR / "optimization_results"
OPT_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

GLPK_DIR = OUTPUT_DIR / "glpk"
GLPK_DIR.mkdir(parents=True, exist_ok=True)

MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

GLPSOL_EXE = Path(r"C:\Users\Welcome\Downloads\glpk\glpk-4.65\w64\glpsol.exe")

VALHALLA_URL = "http://localhost:8002"

SHEET_ROUTES = "Все_маршруты"
SHEET_SERVICE = "Служебные_точки"
SHEET_RULES = "Правила_применения"