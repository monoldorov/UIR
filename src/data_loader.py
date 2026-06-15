import pandas as pd
from config import INPUT_XLSX, SHEET_ROUTES, SHEET_SERVICE, SHEET_RULES


def load_excel_data():
    routes_df = pd.read_excel(INPUT_XLSX, sheet_name=SHEET_ROUTES)
    service_df = pd.read_excel(INPUT_XLSX, sheet_name=SHEET_SERVICE)
    rules_df = pd.read_excel(INPUT_XLSX, sheet_name=SHEET_RULES)

    return routes_df, service_df, rules_df