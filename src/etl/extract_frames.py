"""
extract_frames.py — Módulo ETL: Extracción de Frames a 10 FPS
=============================================================
Hito 1 — Semana 9 (27 de octubre de 2026)

Toma un video de vuelo urbano (o un directorio de videos) y extrae
fotogramas a una tasa configurable (por defecto 10 FPS). Calcula la
varianza del operador Laplaciano de cada frame como métrica de nitidez
y registra todos los metadatos en un diccionario listo para el siguiente
paso del pipeline (filter_blur.py).

Métricas expuestas:
    - frames_totales  : Número total de frames muestreados.
    - frames_validos  : Número de frames que superan el umbral de nitidez.
    - tasa_retencion  : Porcentaje frames_validos / frames_totales.
    - fps_procesados  : Velocidad real de procesamiento del pipeline.

Autor: Gustavo Bryan López Cosme
Repositorio: https://github.com/Gus7Ghost/Tesis-Evasion-Air2S
"""

import os
import sys
import io
import time
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional

# Forzar UTF-8 en stdout para compatibilidad con Windows (CP1252)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Constantes por defecto
# ---------------------------------------------------------------------------
DEFAULT_TARGET_FPS: float = 10.0       # Fotogramas por segundo a extraer
DEFAULT_BLUR_THRESHOLD: float = 80.0   # Varianza laplaciana mínima (nitidez)
DEFAULT_OUTPUT_SIZE: tuple = (256, 256) # Resolución requerida por MiDaS Small


def _laplacian_variance(frame_gray: np.ndarray) -> float:
    """
    Calcula la varianza del operador Laplaciano sobre un frame en escala
    de grises.  Un valor alto indica imagen nítida; uno bajo indica blur.

    Args:
        frame_gray: Frame en escala de grises (uint8, shape HxW).

    Returns:
        Varianza del Laplaciano (float >= 0).
    """
    return float(cv2.Laplacian(frame_gray, cv2.CV_64F).var())


def _letterbox_resize(frame: np.ndarray, target_size: tuple) -> np.ndarray:
    """
    Redimensiona un frame al tamaño objetivo conservando la relación de
    aspecto original (letterbox).  Los bordes se rellenan con negro.

    Args:
        frame      : Frame BGR original (HxWxC).
        target_size: Tupla (ancho, alto) del tamaño objetivo.

    Returns:
        Frame redimensionado con letterbox (target_size[1] x target_size[0] x 3).
    """
    target_w, target_h = target_size
    orig_h, orig_w = frame.shape[:2]

    # Escala uniforme (sin distorsión)
    scale = min(target_w / orig_w, target_h / orig_h)
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)

    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

    # Canvas negro del tamaño objetivo
    canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
    # Centrar la imagen redimensionada
    x_off = (target_w - new_w) // 2
    y_off = (target_h - new_h) // 2
    canvas[y_off:y_off + new_h, x_off:x_off + new_w] = resized

    return canvas


def extract_frames_from_video(
    video_path: str,
    output_dir: str,
    target_fps: float = DEFAULT_TARGET_FPS,
    blur_threshold: float = DEFAULT_BLUR_THRESHOLD,
    output_size: tuple = DEFAULT_OUTPUT_SIZE,
    video_id: Optional[str] = None,
    save_frames: bool = True,
    verbose: bool = True,
) -> List[Dict[str, Any]]:
    """
    Extrae frames de un único video a la tasa indicada y registra
    los metadatos de cada frame en una lista de diccionarios.

    Args:
        video_path      : Ruta al archivo de video (.mp4, .mkv, .avi, etc.).
        output_dir      : Directorio donde se guardarán los frames extraídos.
        target_fps      : FPS objetivo para la extracción (default 10).
        blur_threshold  : Umbral mínimo de varianza laplaciana (default 80.0).
        output_size     : Resolución de salida en píxeles (ancho, alto).
        video_id        : Identificador del video (default: nombre del archivo).
        save_frames     : Si True, guarda los frames en disco como PNG.
        verbose         : Si True, imprime resumen en consola.

    Returns:
        Lista de diccionarios con los metadatos de cada frame extraído.
        Cada dict tiene las claves:
            - video_id       : str
            - frame_index    : int   (índice global del frame en el video)
            - frame_number   : int   (número correlativo extraído, ej. 0..N-1)
            - timestamp_ms   : float (posición en milisegundos del frame en el video)
            - laplacian_var  : float (varianza del operador Laplaciano)
            - is_valid       : bool  (True si supera el umbral de nitidez)
            - frame_path     : str   (ruta al PNG guardado o cadena vacía)
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"[ETL] Video no encontrado: {video_path}")

    if video_id is None:
        video_id = video_path.stem

    output_dir = Path(output_dir) / video_id
    if save_frames:
        output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise IOError(f"[ETL] No se pudo abrir el video: {video_path}")

    # -------------------------------------------------------------------
    # Calcular el intervalo de muestreo en fotogramas del video original
    # -------------------------------------------------------------------
    source_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames_video = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_s = total_frames_video / source_fps if source_fps > 0 else 0

    # Cada cuántos frames nativos hay que saltar para obtener `target_fps`
    frame_interval = max(1, round(source_fps / target_fps))

    if verbose:
        print(f"\n[ETL] Video      : {video_path.name}")
        print(f"[ETL] FPS fuente : {source_fps:.2f} | Duración: {duration_s:.1f}s")
        print(f"[ETL] Intervalo  : cada {frame_interval} frames ({target_fps:.1f} FPS extraídos)")
        print(f"[ETL] Umbral blur: varianza Laplaciana >= {blur_threshold}")
        print(f"[ETL] Tamaño out : {output_size[0]}x{output_size[1]} px (letterbox)\n")

    records: List[Dict[str, Any]] = []
    frame_idx = 0       # Índice del frame nativo en el video
    extracted = 0       # Número de frames que pasaron el filtro de intervalo
    valid_count = 0     # Número de frames que superan el umbral de nitidez

    t_start = time.perf_counter()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Solo procesamos frames en el intervalo definido
        if frame_idx % frame_interval == 0:
            timestamp_ms = cap.get(cv2.CAP_PROP_POS_MSEC)

            # --- Cálculo de nitidez ---
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            lap_var = _laplacian_variance(gray)
            is_valid = lap_var >= blur_threshold

            # --- Redimensionado letterbox para MiDaS ---
            frame_resized = _letterbox_resize(frame, output_size)

            # --- Guardar frame en disco ---
            frame_filename = ""
            if save_frames:
                # Guardar TODOS los frames (válidos e inválidos) para análisis
                # La separación final la hace dataset_manager.py
                subfolder = "valid" if is_valid else "blurry"
                save_path = output_dir / subfolder
                save_path.mkdir(parents=True, exist_ok=True)
                frame_filename = str(save_path / f"frame_{extracted:06d}.png")
                cv2.imwrite(frame_filename, frame_resized)

            records.append({
                "video_id":      video_id,
                "frame_index":   frame_idx,
                "frame_number":  extracted,
                "timestamp_ms":  round(timestamp_ms, 3),
                "laplacian_var": round(lap_var, 4),
                "is_valid":      is_valid,
                "frame_path":    frame_filename,
            })

            if is_valid:
                valid_count += 1
            extracted += 1

        frame_idx += 1

    cap.release()
    elapsed = time.perf_counter() - t_start

    # -------------------------------------------------------------------
    # Métricas de salida
    # -------------------------------------------------------------------
    fps_processing = extracted / elapsed if elapsed > 0 else 0.0
    retention_rate = (valid_count / extracted * 100) if extracted > 0 else 0.0

    if verbose:
        print(f"[ETL] Frames muestreados : {extracted}")
        print(f"[ETL] Frames validos     : {valid_count} ({retention_rate:.1f}%)")
        print(f"[ETL] Frames borrosos    : {extracted - valid_count}")
        print(f"[ETL] FPS procesados     : {fps_processing:.1f} FPS")
        print(f"[ETL] Tiempo total       : {elapsed:.2f}s\n")

    return records


def extract_frames_from_directory(
    videos_dir: str,
    output_dir: str,
    extensions: List[str] = None,
    target_fps: float = DEFAULT_TARGET_FPS,
    blur_threshold: float = DEFAULT_BLUR_THRESHOLD,
    output_size: tuple = DEFAULT_OUTPUT_SIZE,
    save_frames: bool = True,
    verbose: bool = True,
) -> List[Dict[str, Any]]:
    """
    Procesa todos los videos de un directorio y consolida los metadatos
    en una única lista de registros.

    Args:
        videos_dir    : Directorio raíz con los videos de entrada.
        output_dir    : Directorio de salida para los frames extraídos.
        extensions    : Extensiones válidas (default: .mp4, .mkv, .avi, .mov).
        target_fps    : FPS objetivo para la extracción.
        blur_threshold: Umbral mínimo de varianza laplaciana.
        output_size   : Resolución de salida en píxeles.
        save_frames   : Si True, guarda frames PNG en disco.
        verbose       : Si True, imprime resumen en consola.

    Returns:
        Lista unificada de registros de metadatos de todos los videos.
    """
    if extensions is None:
        extensions = [".mp4", ".mkv", ".avi", ".mov", ".h264"]

    videos_dir = Path(videos_dir)
    video_files = sorted([
        f for f in videos_dir.rglob("*")
        if f.suffix.lower() in extensions and f.is_file()
    ])

    if not video_files:
        print(f"[ETL] No se encontraron videos en: {videos_dir}")
        return []

    print(f"[ETL] Encontrados {len(video_files)} video(s) en '{videos_dir}'")

    all_records: List[Dict[str, Any]] = []
    for video_file in video_files:
        records = extract_frames_from_video(
            video_path=str(video_file),
            output_dir=output_dir,
            target_fps=target_fps,
            blur_threshold=blur_threshold,
            output_size=output_size,
            save_frames=save_frames,
            verbose=verbose,
        )
        all_records.extend(records)

    # --- Resumen global ---
    total = len(all_records)
    valid = sum(1 for r in all_records if r["is_valid"])
    print(f"\n[ETL] ══ RESUMEN GLOBAL ══")
    print(f"[ETL] Videos procesados : {len(video_files)}")
    print(f"[ETL] Frames totales    : {total}")
    print(f"[ETL] Frames válidos    : {valid} ({(valid/total*100):.1f}%)\n" if total > 0 else "")

    return all_records
