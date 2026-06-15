import argparse

from build_trips import main as build_trips_main
from run_all_trips import main as run_all_trips_main
from build_final_report_table import main as build_final_report_table_main


def run_full_pipeline() -> None:
    print("=== ШАГ 1. Формирование trips.json из входного XLSX ===")
    build_trips_main()
    print()

    print("=== ШАГ 2. Полный пакетный расчет по всем рейсам ===")
    run_all_trips_main()
    print()

    print("=== ШАГ 3. Построение финальной отчетной таблицы ===")
    build_final_report_table_main()
    print()

    print("=== ГОТОВО ===")
    print("Полный pipeline УИР завершен.")


def main():
    parser = argparse.ArgumentParser(
        description="Единый запуск проекта УИР: от входного XLSX до итоговой отчетной таблицы"
    )
    parser.parse_args()

    run_full_pipeline()


if __name__ == "__main__":
    main()