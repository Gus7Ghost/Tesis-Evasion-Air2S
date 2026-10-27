"""
dataset_merger.py — Módulo ETL: Fusión de Datasets Múltiples
=============================================================
Hito 1 — Semana 9 (27 de octubre de 2026)

Combina los dataset_index.csv generados por cada fuente de datos
(semantic_drone, utility_poles, uavid, etc.) en un índice maestro
único, respetando la separación anti-leakage por origen.

Funciones:
    - merge_indexes()  : Fusiona varios CSV en un DataFrame maestro.
    - print_summary()  : Estadísticas por dataset y por split.
    - export_master()  : Guarda dataset_index_master.csv.

Autor: Gustavo Bryan López Cosme
Repositorio: https://github.com/Gus7Ghost/Tesis-Evasion-Air2S
"""

import pandas as pd
from pathlib import Path
from typing import List, Optional


def merge_indexes(
    csv_paths: List[str],
    only_valid: bool = True,
) -> pd.DataFrame:
    """
    Carga y concatena múltiples dataset_index.csv en un DataFrame unificado.

    Args:
        csv_paths  : Lista de rutas a archivos CSV individuales por dataset.
        only_valid : Si True, descarta filas donde is_valid == False.

    Returns:
        DataFrame consolidado con todos los frames de todos los datasets.
    """
    frames = []
    for csv_path in csv_paths:
        csv_path = Path(csv_path)
        if not csv_path.exists():
            print(f"[MERGER] Advertencia: no existe {csv_path}")
            continue
        df = pd.read_csv(csv_path)
        df["source_csv"] = csv_path.name  # Trazar origen
        frames.append(df)

    if not frames:
        print("[MERGER] No se encontraron CSVs para fusionar.")
        return pd.DataFrame()

    merged = pd.concat(frames, ignore_index=True)

    if only_valid and "is_valid" in merged.columns:
        before = len(merged)
        merged = merged[merged["is_valid"] == True].copy()
        print(f"[MERGER] Filtrado is_valid: {before} -> {len(merged)} registros")

    # Reset index global
    merged = merged.reset_index(drop=True)
    print(f"[MERGER] Total frames fusionados: {len(merged)}")
    return merged


def print_summary(df: pd.DataFrame) -> None:
    """
    Imprime un resumen del dataset maestro por fuente y por split.

    Args:
        df: DataFrame maestro generado por merge_indexes().
    """
    if df.empty:
        print("[MERGER] DataFrame vacío.")
        return

    line = "-" * 50
    print(f"\n{line}")
    print(f" RESUMEN DEL DATASET MAESTRO")
    print(f"{line}")
    print(f" Total frames  : {len(df)}")

    if "split" in df.columns:
        print(f"\n Por split:")
        for split, cnt in df["split"].value_counts().items():
            pct = cnt / len(df) * 100
            print(f"   {split:<8}: {cnt:>6} ({pct:.1f}%)")

    if "video_id" in df.columns:
        print(f"\n Por dataset (video_id):")
        for vid, cnt in df["video_id"].value_counts().items():
            pct = cnt / len(df) * 100
            print(f"   {vid:<25}: {cnt:>6} ({pct:.1f}%)")

    if "laplacian_var" in df.columns:
        print(f"\n Nitidez (varianza laplaciana):")
        print(f"   Media   : {df['laplacian_var'].mean():.2f}")
        print(f"   Mediana : {df['laplacian_var'].median():.2f}")
        print(f"   Min     : {df['laplacian_var'].min():.2f}")
        print(f"   Max     : {df['laplacian_var'].max():.2f}")

    print(f"{line}\n")


def export_master(
    df: pd.DataFrame,
    output_dir: str,
    filename: str = "dataset_index_master.csv",
    verbose: bool = True,
) -> str:
    """
    Guarda el DataFrame maestro como CSV.

    Args:
        df         : DataFrame consolidado.
        output_dir : Directorio de destino.
        filename   : Nombre del archivo CSV.
        verbose    : Si True, imprime la ruta del archivo.

    Returns:
        Ruta absoluta del archivo CSV exportado.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / filename
    df.to_csv(csv_path, index=False, encoding="utf-8")
    if verbose:
        print(f"[MERGER] Dataset maestro exportado: {csv_path} ({len(df)} registros)")
    return str(csv_path)
