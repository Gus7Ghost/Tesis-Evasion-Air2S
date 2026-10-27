"""
dataset_manager.py — Módulo ETL: Estructuración y Partición del Dataset
=======================================================================
Hito 1 — Semana 9 (27 de octubre de 2026)

Toma la lista de registros válidos (filtrada por filter_blur.py),
organiza los frames en carpetas train/val/test y exporta el dataframe
de metadatos (dataset_index.csv) listo para la experimentación
offline con MiDaS (Hito 2).

ESTRATEGIA DE PARTICIÓN (anti-data-leakage):
    La separación se realiza a nivel de video/secuencia completa, NO
    frame a frame.  Esto garantiza que frames temporalmente contiguos
    de un mismo vuelo nunca se mezclen entre conjuntos, evitando que el
    modelo aprenda correlaciones temporales y fracase ante vuelos nuevos.

Estructura de salida:
    <dataset_root>/
    ├── train/
    │   └── <video_id>/
    │       └── frame_XXXXXX.png
    ├── val/
    │   └── <video_id>/
    │       └── frame_XXXXXX.png
    ├── test/
    │   └── <video_id>/
    │       └── frame_XXXXXX.png
    └── dataset_index.csv

Columnas de dataset_index.csv:
    video_id, frame_index, frame_number, timestamp_ms,
    laplacian_var, is_valid, frame_path, split

Autor: Gustavo Bryan López Cosme
Repositorio: https://github.com/Gus7Ghost/Tesis-Evasion-Air2S
"""

import os
import shutil
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Tuple
from collections import defaultdict


# ---------------------------------------------------------------------------
# Proporciones por defecto de la partición train / val / test
# ---------------------------------------------------------------------------
DEFAULT_TRAIN_RATIO: float = 0.70
DEFAULT_VAL_RATIO:   float = 0.15
DEFAULT_TEST_RATIO:  float = 0.15   # El resto se asigna a test


def _get_video_groups(
    records: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Agrupa los registros por video_id.

    Args:
        records: Lista de dicts de metadatos de frames.

    Returns:
        Diccionario {video_id: [records...]}.
    """
    groups: Dict[str, List] = defaultdict(list)
    for r in records:
        groups[r["video_id"]].append(r)
    return dict(groups)


def assign_splits(
    records: List[Dict[str, Any]],
    train_ratio: float = DEFAULT_TRAIN_RATIO,
    val_ratio: float = DEFAULT_VAL_RATIO,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """
    Asigna la etiqueta 'split' (train / val / test) a cada registro
    agrupando por video completo para evitar data leakage temporal.

    Con un solo video, se aplica una partición por segmentos temporales
    (primero N% es train, siguiente M% es val, resto es test).

    Con múltiples videos, se asignan videos completos a cada split.

    Args:
        records     : Lista de dicts de metadatos (solo frames válidos).
        train_ratio : Proporción del conjunto de entrenamiento.
        val_ratio   : Proporción del conjunto de validación.
        seed        : Semilla de aleatoriedad para reproducibilidad.

    Returns:
        Lista de dicts actualizada con la clave 'split'.
    """
    import random
    random.seed(seed)

    groups = _get_video_groups(records)
    video_ids = sorted(groups.keys())  # Orden determinístico

    n_videos = len(video_ids)

    # --- Caso: un solo video → partición temporal por segmentos ---
    if n_videos == 1:
        vid = video_ids[0]
        vid_records = sorted(groups[vid], key=lambda r: r["frame_index"])
        n = len(vid_records)
        i_train = int(n * train_ratio)
        i_val   = i_train + int(n * val_ratio)

        updated = []
        for i, r in enumerate(vid_records):
            if i < i_train:
                split = "train"
            elif i < i_val:
                split = "val"
            else:
                split = "test"
            updated.append({**r, "split": split})
        return updated

    # --- Caso: múltiples videos → asignar videos completos a cada split ---
    shuffled = video_ids.copy()
    random.shuffle(shuffled)

    n_train = max(1, round(n_videos * train_ratio))
    n_val   = max(1, round(n_videos * val_ratio))
    # El resto va a test (mínimo 1 si hay suficientes videos)

    train_vids = set(shuffled[:n_train])
    val_vids   = set(shuffled[n_train:n_train + n_val])
    test_vids  = set(shuffled[n_train + n_val:])

    # Si solo hay 2 videos, forzar al menos train y test
    if not test_vids and len(val_vids) > 0:
        test_vids.add(val_vids.pop())
    if not val_vids and len(train_vids) > 1:
        val_vids.add(train_vids.pop())

    updated = []
    for vid in video_ids:
        if vid in train_vids:
            split = "train"
        elif vid in val_vids:
            split = "val"
        else:
            split = "test"

        for r in groups[vid]:
            updated.append({**r, "split": split})

    return updated


def copy_frames_to_splits(
    records: List[Dict[str, Any]],
    dataset_root: str,
    verbose: bool = True,
) -> List[Dict[str, Any]]:
    """
    Copia los archivos PNG de cada frame a la carpeta de split
    correspondiente dentro de dataset_root.

    Actualiza la clave 'frame_path' de cada registro con la ruta final.

    Args:
        records      : Lista de dicts con 'split' y 'frame_path' asignados.
        dataset_root : Directorio raíz del dataset de salida.
        verbose      : Si True, imprime el conteo por split.

    Returns:
        Lista de dicts con 'frame_path' actualizado a la ruta del split.
    """
    dataset_root = Path(dataset_root)
    counts = {"train": 0, "val": 0, "test": 0}
    updated = []

    for r in records:
        split = r.get("split", "train")
        src_path = r.get("frame_path", "")
        video_id = r["video_id"]

        if not src_path or not Path(src_path).exists():
            updated.append({**r})
            continue

        # Directorio destino: <dataset_root>/<split>/<video_id>/
        dest_dir = dataset_root / split / video_id
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_path = dest_dir / Path(src_path).name
        shutil.copy2(src_path, dest_path)

        counts[split] += 1
        updated.append({**r, "frame_path": str(dest_path)})

    if verbose:
        total = sum(counts.values())
        print(f"\n[ETL] ══ PARTICIÓN DEL DATASET (anti-leakage) ══")
        print(f"[ETL] Total frames copiados : {total}")
        for split_name, count in counts.items():
            pct = (count / total * 100) if total > 0 else 0
            print(f"[ETL]   {split_name:<6} : {count:>5} frames ({pct:.1f}%)")
        print()

    return updated


def export_index(
    records: List[Dict[str, Any]],
    dataset_root: str,
    filename: str = "dataset_index.csv",
    verbose: bool = True,
) -> str:
    """
    Exporta todos los registros de metadatos a un archivo CSV.

    Columnas exportadas:
        video_id, frame_index, frame_number, timestamp_ms,
        laplacian_var, is_valid, split, frame_path

    Args:
        records      : Lista de dicts de metadatos (con 'split' asignado).
        dataset_root : Directorio raíz donde se guardará el CSV.
        filename     : Nombre del archivo CSV.
        verbose      : Si True, imprime la ruta del CSV en consola.

    Returns:
        Ruta absoluta del archivo CSV generado.
    """
    dataset_root = Path(dataset_root)
    dataset_root.mkdir(parents=True, exist_ok=True)

    # Columnas en el orden lógico del pipeline
    columns = [
        "video_id",
        "frame_index",
        "frame_number",
        "timestamp_ms",
        "laplacian_var",
        "is_valid",
        "split",
        "frame_path",
    ]

    df = pd.DataFrame(records)

    # Asegurar que todas las columnas existen (añadir NaN si faltan)
    for col in columns:
        if col not in df.columns:
            df[col] = None

    df = df[columns]
    df = df.sort_values(["video_id", "frame_index"]).reset_index(drop=True)

    csv_path = dataset_root / filename
    df.to_csv(csv_path, index=False, encoding="utf-8")

    if verbose:
        print(f"[ETL] ✓ Dataset index exportado : {csv_path}")
        print(f"[ETL] ✓ Total de registros      : {len(df)}")
        # Resumen por split
        if "split" in df.columns:
            split_counts = df["split"].value_counts()
            for split_name, cnt in split_counts.items():
                print(f"[ETL]   {split_name:<6} : {cnt} frames")
        print()

    return str(csv_path)


def build_dataset(
    records: List[Dict[str, Any]],
    dataset_root: str,
    train_ratio: float = DEFAULT_TRAIN_RATIO,
    val_ratio: float = DEFAULT_VAL_RATIO,
    seed: int = 42,
    copy_files: bool = True,
    verbose: bool = True,
) -> Tuple[str, pd.DataFrame]:
    """
    Función principal: ejecuta el flujo completo de estructuración.

        1. Asigna splits (train/val/test) a nivel de video.
        2. Copia los frames al directorio de destino organizado.
        3. Exporta el dataset_index.csv.

    Args:
        records      : Lista de dicts de frames VÁLIDOS (is_valid == True).
        dataset_root : Directorio raíz del dataset de salida.
        train_ratio  : Proporción de entrenamiento.
        val_ratio    : Proporción de validación.
        seed         : Semilla de reproducibilidad.
        copy_files   : Si True, copia los PNGs al árbol de directorios del dataset.
        verbose      : Si True, imprime el progreso en consola.

    Returns:
        Tupla (csv_path: str, dataframe: pd.DataFrame).
    """
    if not records:
        print("[ETL] ⚠ No hay registros válidos para estructurar el dataset.")
        return "", pd.DataFrame()

    # 1. Asignación de splits anti-leakage
    if verbose:
        print("[ETL] Asignando splits (anti-leakage por video)...")
    records_with_splits = assign_splits(records, train_ratio, val_ratio, seed)

    # 2. Copiar frames a las carpetas de split
    if copy_files:
        records_with_splits = copy_frames_to_splits(
            records_with_splits, dataset_root, verbose=verbose
        )

    # 3. Exportar índice CSV
    csv_path = export_index(records_with_splits, dataset_root, verbose=verbose)

    df = pd.read_csv(csv_path)
    return csv_path, df
