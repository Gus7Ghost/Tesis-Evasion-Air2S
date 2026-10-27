"""
extract_images.py — Módulo ETL: Extracción desde Directorios de Imágenes
========================================================================
Hito 1 — Semana 9 (27 de octubre de 2026)

Complemento de extract_frames.py para datasets que entregan imágenes
estáticas (JPEG/PNG) en lugar de videos, como:
  - Semantic Drone Dataset (TU Graz / Kaggle)
  - Utility Poles (Roboflow Universe)

Calcula varianza laplaciana, redimensiona a 256x256 letterbox y
devuelve la misma estructura de registros que extract_frames.py
para que filter_blur.py y dataset_manager.py funcionen sin cambios.

Autor: Gustavo Bryan López Cosme
Repositorio: https://github.com/Gus7Ghost/Tesis-Evasion-Air2S
"""

import sys
import io
import time
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional

# Forzar UTF-8 en stdout para compatibilidad con Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Extensiones de imagen soportadas
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}

DEFAULT_BLUR_THRESHOLD: float = 80.0
DEFAULT_OUTPUT_SIZE: tuple = (256, 256)


def _laplacian_variance(frame_gray: np.ndarray) -> float:
    """Calcula la varianza del operador Laplaciano (métrica de nitidez)."""
    return float(cv2.Laplacian(frame_gray, cv2.CV_64F).var())


def _letterbox_resize(frame: np.ndarray, target_size: tuple) -> np.ndarray:
    """Redimensiona conservando relación de aspecto con relleno negro (letterbox)."""
    target_w, target_h = target_size
    orig_h, orig_w = frame.shape[:2]
    scale = min(target_w / orig_w, target_h / orig_h)
    new_w, new_h = int(orig_w * scale), int(orig_h * scale)
    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
    x_off = (target_w - new_w) // 2
    y_off = (target_h - new_h) // 2
    canvas[y_off:y_off + new_h, x_off:x_off + new_w] = resized
    return canvas


def extract_images_from_directory(
    images_dir: str,
    output_dir: str,
    dataset_id: str,
    blur_threshold: float = DEFAULT_BLUR_THRESHOLD,
    output_size: tuple = DEFAULT_OUTPUT_SIZE,
    max_images: Optional[int] = None,
    save_frames: bool = True,
    verbose: bool = True,
) -> List[Dict[str, Any]]:
    """
    Procesa un directorio de imágenes estáticas aplicando el mismo
    pipeline de calidad que extract_frames.py.

    Args:
        images_dir    : Directorio raíz con las imágenes (recursivo).
        output_dir    : Directorio de salida donde se guardarán los PNG 256x256.
        dataset_id    : Identificador del dataset (ej. 'semantic_drone').
        blur_threshold: Umbral mínimo de varianza laplaciana.
        output_size   : Resolución de salida (ancho, alto).
        max_images    : Límite de imágenes a procesar (None = todas).
        save_frames   : Si True, guarda los PNG redimensionados en disco.
        verbose       : Si True, imprime progreso en consola.

    Returns:
        Lista de dicts con los mismos campos que extract_frames.py:
        video_id, frame_index, frame_number, timestamp_ms,
        laplacian_var, is_valid, frame_path
    """
    images_dir = Path(images_dir)
    if not images_dir.exists():
        raise FileNotFoundError(f"[ETL] Directorio no encontrado: {images_dir}")

    # Recopilar todas las imágenes
    image_files = sorted([
        f for f in images_dir.rglob("*")
        if f.suffix.lower() in IMAGE_EXTENSIONS and f.is_file()
    ])

    if max_images:
        image_files = image_files[:max_images]

    if not image_files:
        print(f"[ETL] No se encontraron imágenes en: {images_dir}")
        return []

    if verbose:
        print(f"\n[ETL] Dataset       : {dataset_id}")
        print(f"[ETL] Imagenes      : {len(image_files)} archivos")
        print(f"[ETL] Umbral blur   : varianza Laplaciana >= {blur_threshold}")
        print(f"[ETL] Tamaño out    : {output_size[0]}x{output_size[1]} px (letterbox)\n")

    records: List[Dict[str, Any]] = []
    valid_count = 0
    t_start = time.perf_counter()

    for idx, img_path in enumerate(image_files):
        frame = cv2.imread(str(img_path))
        if frame is None:
            if verbose:
                print(f"[ETL] No se pudo leer: {img_path.name}")
            continue

        # Calcular nitidez
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        lap_var = _laplacian_variance(gray)
        is_valid = lap_var >= blur_threshold

        # Redimensionar
        frame_resized = _letterbox_resize(frame, output_size)

        # Guardar
        frame_filename = ""
        if save_frames:
            out_dir = Path(output_dir) / dataset_id / ("valid" if is_valid else "blurry")
            out_dir.mkdir(parents=True, exist_ok=True)
            frame_filename = str(out_dir / f"frame_{idx:06d}.png")
            cv2.imwrite(frame_filename, frame_resized)

        records.append({
            "video_id":     dataset_id,
            "frame_index":  idx,
            "frame_number": idx,
            "timestamp_ms": 0.0,          # No aplica para imágenes estáticas
            "laplacian_var": round(lap_var, 4),
            "is_valid":     is_valid,
            "frame_path":   frame_filename,
            "source_path":  str(img_path),  # Campo extra: ruta original
        })

        if is_valid:
            valid_count += 1

        # Progreso cada 100 imágenes
        if verbose and (idx + 1) % 100 == 0:
            elapsed = time.perf_counter() - t_start
            fps = (idx + 1) / elapsed
            pct = (idx + 1) / len(image_files) * 100
            print(f"[ETL] {idx+1}/{len(image_files)} ({pct:.0f}%) | {fps:.1f} FPS | validas: {valid_count}")

    elapsed = time.perf_counter() - t_start
    fps_processing = len(records) / elapsed if elapsed > 0 else 0.0
    retention = (valid_count / len(records) * 100) if records else 0.0

    if verbose:
        print(f"\n[ETL] Imagenes procesadas  : {len(records)}")
        print(f"[ETL] Imagenes validas     : {valid_count} ({retention:.1f}%)")
        print(f"[ETL] FPS procesados       : {fps_processing:.1f}")
        print(f"[ETL] Tiempo total         : {elapsed:.2f}s\n")

    return records
