"""
filter_blur.py — Módulo ETL: Filtrado y Estadísticas de Nitidez
===============================================================
Hito 1 — Semana 9 (27 de octubre de 2026)

Recibe la lista de registros producida por extract_frames.py, aplica
filtros adicionales de calidad y exporta estadísticas del proceso de
limpieza.  No vuelve a leer el video: opera sobre los metadatos
ya calculados (laplacian_var, is_valid).

Funciones clave:
    - filter_records()    : Filtra la lista de registros por umbral de nitidez.
    - compute_stats()     : Calcula estadísticas descriptivas del dataset.
    - print_report()      : Imprime el reporte en consola (estilo tabla).

Autor: Gustavo Bryan López Cosme
Repositorio: https://github.com/Gus7Ghost/Tesis-Evasion-Air2S
"""

import numpy as np
from typing import List, Dict, Any


def filter_records(
    records: List[Dict[str, Any]],
    blur_threshold: float = 80.0,
) -> tuple:
    """
    Separa los registros en válidos e inválidos según la varianza laplaciana.

    Args:
        records        : Lista de dicts generados por extract_frames.py.
        blur_threshold : Umbral mínimo de varianza laplaciana para considerar
                         un frame como nítido.

    Returns:
        Tupla (valid_records, blurry_records) con las listas separadas.
    """
    valid_records = []
    blurry_records = []

    for record in records:
        lap_var = record.get("laplacian_var", 0.0)
        is_valid = lap_var >= blur_threshold

        # Actualizar el flag por si el umbral cambió respecto a extract_frames
        updated = {**record, "is_valid": is_valid}

        if is_valid:
            valid_records.append(updated)
        else:
            blurry_records.append(updated)

    return valid_records, blurry_records


def compute_stats(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calcula estadísticas descriptivas de la varianza laplaciana para
    un conjunto de registros.

    Args:
        records: Lista de dicts (puede ser el total, solo válidos, etc.)

    Returns:
        Diccionario con métricas estadísticas.
    """
    if not records:
        return {
            "count": 0,
            "min": None,
            "max": None,
            "mean": None,
            "std": None,
            "median": None,
            "p25": None,
            "p75": None,
        }

    lap_values = np.array([r["laplacian_var"] for r in records], dtype=np.float64)

    return {
        "count":  int(len(lap_values)),
        "min":    float(np.min(lap_values)),
        "max":    float(np.max(lap_values)),
        "mean":   float(np.mean(lap_values)),
        "std":    float(np.std(lap_values)),
        "median": float(np.median(lap_values)),
        "p25":    float(np.percentile(lap_values, 25)),
        "p75":    float(np.percentile(lap_values, 75)),
    }


def compute_per_video_stats(
    records: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    Agrupa los registros por video y calcula estadísticas de nitidez
    por video individual.

    Args:
        records: Lista completa de dicts de metadatos.

    Returns:
        Dict con video_id como clave y estadísticas como valor.
    """
    from collections import defaultdict

    groups: Dict[str, List] = defaultdict(list)
    for r in records:
        groups[r["video_id"]].append(r)

    return {vid: compute_stats(recs) for vid, recs in groups.items()}


def suggest_threshold(
    records: List[Dict[str, Any]],
    target_retention: float = 0.80,
) -> float:
    """
    Sugiere automáticamente un umbral de varianza laplaciana tal que se
    retenga aproximadamente el porcentaje indicado de frames.

    Útil cuando el video tiene condiciones de luz muy diferentes y el
    umbral fijo (80) descarta demasiados frames válidos.

    Args:
        records          : Lista completa de dicts de metadatos.
        target_retention : Porcentaje de retención deseado (0.0 a 1.0).

    Returns:
        Umbral sugerido (float).
    """
    if not records:
        return 80.0

    lap_values = sorted([r["laplacian_var"] for r in records])
    # El percentil = (1 - target_retention) * 100
    idx = int((1.0 - target_retention) * len(lap_values))
    idx = max(0, min(idx, len(lap_values) - 1))
    suggested = lap_values[idx]

    return round(float(suggested), 2)


def print_report(
    all_records: List[Dict[str, Any]],
    valid_records: List[Dict[str, Any]],
    blurry_records: List[Dict[str, Any]],
    blur_threshold: float,
) -> None:
    """
    Imprime un reporte detallado de la limpieza de datos en consola.

    Args:
        all_records    : Todos los registros extraídos.
        valid_records  : Registros que superan el umbral de nitidez.
        blurry_records : Registros descartados por blur.
        blur_threshold : Umbral de varianza laplaciana utilizado.
    """
    total = len(all_records)
    valid = len(valid_records)
    blurry = len(blurry_records)
    retention = (valid / total * 100) if total > 0 else 0.0

    all_stats   = compute_stats(all_records)
    valid_stats = compute_stats(valid_records)

    line = "─" * 54
    print(f"\n╔{line}╗")
    print(f"║{'REPORTE ETL — FILTRADO DE NITIDEZ':^54}║")
    print(f"╠{line}╣")
    print(f"║  Umbral laplaciano        : {blur_threshold:<26.2f}║")
    print(f"║  Frames totales extraídos : {total:<26d}║")
    print(f"║  Frames válidos (nítidos) : {valid:<26d}║")
    print(f"║  Frames descartados (blur): {blurry:<26d}║")
    print(f"║  Tasa de retención        : {retention:<25.1f}%║")
    print(f"╠{line}╣")
    print(f"║{'Estadísticas de varianza laplaciana':^54}║")
    print(f"╠{line}╣")
    header = f"{'Métrica':<20}{'Total':>10}{'Solo Válidos':>15}"
    print(f"║  {header:<52}║")
    print(f"╠{line}╣")

    metrics = [
        ("Mínimo",   "min"),
        ("Máximo",   "max"),
        ("Media",    "mean"),
        ("Desv. Est.","std"),
        ("Mediana",  "median"),
        ("P25",      "p25"),
        ("P75",      "p75"),
    ]
    for label, key in metrics:
        a_val = all_stats[key]
        v_val = valid_stats[key]
        a_str = f"{a_val:.2f}" if a_val is not None else "N/A"
        v_str = f"{v_val:.2f}" if v_val is not None else "N/A"
        row = f"{label:<20}{a_str:>10}{v_str:>15}"
        print(f"║  {row:<52}║")

    # Umbral sugerido para retención ≥ 80%
    suggested = suggest_threshold(all_records, target_retention=0.80)
    print(f"╠{line}╣")
    print(f"║  Umbral sugerido (≥80% retención): {suggested:<18.2f}║")
    print(f"╚{line}╝\n")
