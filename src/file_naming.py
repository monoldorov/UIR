def normalize_vehicle_id_for_filename(vehicle_id: str) -> str:
    """
    Приводит номер ТС к безопасному имени файла.
    Заменяет похожие кириллические буквы на латиницу.
    """
    mapping = {
        "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M",
        "Н": "H", "О": "O", "Р": "P", "С": "C", "Т": "T",
        "У": "Y", "Х": "X",
        "а": "a", "в": "b", "е": "e", "к": "k", "м": "m",
        "н": "h", "о": "o", "р": "p", "с": "c", "т": "t",
        "у": "y", "х": "x",
    }

    result = []
    for ch in str(vehicle_id):
        result.append(mapping.get(ch, ch))

    safe_name = "".join(result)
    safe_name = safe_name.replace(" ", "_")
    return safe_name