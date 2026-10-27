"""
extract_ddos.py — Módulo ETL para el Dataset Científico DDOS (CVPRW 2024)
==========================================================================
Paper: "DDOS: The Drone Depth and Obstacle Segmentation Dataset"
Autores: Benedikt Kolbeinsson y Krystian Mikolajczyk (Imperial College London)

Procesa secuencias de vuelo frontal con:
  - Imagenes RGB (1280x720) -> Redimensionadas a 256x256 letterbox para MiDaS
  - Ground Truth Depth (16 bits) -> Redimensionadas y sincronizadas
  - Ground Truth Semantic Segmentation -> Extraccion de etiquetas exactas:
      * has_pole  : True si contiene la clase 'thin_structures' (valor 240)
      * has_tree  : True si contiene la clase 'trees' (valor 180)
      * has_cable : True si contiene la clase 'ultra_thin' (valor 255)
      * pole_pixels: Cantidad exacta de pixeles del poste en el frame
      * tree_pixels: Cantidad de pixeles del arbol en el frame

Permite evaluar formalmente la precision de profundidad (RMSE, MAE, AbsRel)
frente al Ground Truth en los Hitos 2 y 3.

Autor: Gustavo Bryan Lopez Cosme
Repositorio: https://github.com/Gus7Ghost/Tesis-Evasion-Air2S
"""

import os
import sys
import io
import time
import cv2
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Forzar UTF-8 en stdout para Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Clases semanticas oficiales del paper DDOS
LABEL_ULTRA_THIN = 255      # Cables y alambres
LABEL_THIN_STRUCTURES = 240 # Postes de luz, postes de concreto/madera, astas
LABEL_TREES = 180           # Arboles, ramas, troncos, arbustos
LABEL_BUILDINGS = 160       # Fachadas de edificios, casas


def _letterbox_image(img: np.ndarray, target_size: Tuple[int, int] = (256, 256)) -> np.ndarray:
    """Redimensiona una imagen con padding negro (letterbox) conservando aspecto."""
    tw, th = target_size
    h, w = img.shape[:2]
    scale = min(tw / w, th / h)
    nw, nh = int(w * scale), int(h * scale)
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    resized = cv2.resize(img, (nw, nh), interpolation=interp)

    if len(img.shape) == 3:
        canvas = np.zeros((th, tw, img.shape[2]), dtype=img.dtype)
        x_off = (tw - nw) // 2
        y_off = (th - nh) // 2
        canvas[y_off:y_off + nh, x_off:x_off + nw] = resized
    else:
        canvas = np.zeros((th, tw), dtype=img.dtype)
        x_off = (tw - nw) // 2
        y_off = (th - nh) // 2
        canvas[y_off:y_off + nh, x_off:x_off + nw] = resized
    return canvas


def _letterbox_nearest(img: np.ndarray, target_size: Tuple[int, int] = (256, 256)) -> np.ndarray:
    """Redimensiona mascaras categoricas usando interpolacion NEAREST para no alterar valores de clase."""
    tw, th = target_size
    h, w = img.shape[:2]
    scale = min(tw / w, th / h)
    nw, nh = int(w * scale), int(h * scale)
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_NEAREST)

    canvas = np.zeros((th, tw), dtype=img.dtype)
    x_off = (tw - nw) // 2
    y_off = (th - nh) // 2
    canvas[y_off:y_off + nh, x_off:x_off + nw] = resized
    return canvas


def extract_ddos_flight(
    flight_dir: Path,
    output_dir: Path,
    env_name: str,
    flight_id: str,
    target_size: Tuple[int, int] = (256, 256),
    blur_threshold: float = 80.0,
) -> List[Dict[str, Any]]:
    """
    Procesa un vuelo completo de DDOS, sincronizando RGB, Depth y Segmentacion.
    """
    img_dir = flight_dir / "image"
    depth_dir = flight_dir / "depth"
    seg_dir = flight_dir / "segmentation"

    if not img_dir.exists():
        return []

    image_files = sorted(list(img_dir.glob("*.png")), key=lambda p: int(p.stem) if p.stem.isdigit() else p.stem)
    if not image_files:
        return []

    video_id = f"ddos_{env_name}_flight_{flight_id}"
    out_flight = output_dir / video_id
    out_img = out_flight / "rgb"
    out_depth = out_flight / "depth_gt"
    out_seg = out_flight / "seg_gt"
    out_img.mkdir(parents=True, exist_ok=True)
    out_depth.mkdir(parents=True, exist_ok=True)
    out_seg.mkdir(parents=True, exist_ok=True)

    records = []
    print(f"\n[ETL-DDOS] Procesando vuelo: {video_id} ({len(image_files)} frames)...")

    for idx, fpath in enumerate(image_files):
        fname = fpath.name
        rgb = cv2.imread(str(fpath))
        if rgb is None:
            continue

        # Nitidez
        gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY)
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        is_valid = lap_var >= blur_threshold

        # Redimensionar RGB letterbox 256x256
        rgb_256 = _letterbox_image(rgb, target_size)
        save_rgb_path = out_img / f"frame_{idx:04d}.png"
        cv2.imwrite(str(save_rgb_path), rgb_256)

        # Ground Truth Depth (16-bit)
        depth_file = depth_dir / fname
        save_depth_path = ""
        depth_min, depth_max = 0.0, 0.0
        if depth_file.exists():
            depth = cv2.imread(str(depth_file), cv2.IMREAD_UNCHANGED)
            if depth is not None:
                depth_256 = _letterbox_image(depth, target_size)
                save_depth_path = str(out_depth / f"depth_{idx:04d}.png")
                cv2.imwrite(save_depth_path, depth_256)
                depth_min = float(depth.min())
                depth_max = float(depth.max())

        # Ground Truth Segmentacion
        seg_file = seg_dir / fname
        save_seg_path = ""
        has_pole = False
        has_tree = False
        has_cable = False
        pole_pixels = 0
        tree_pixels = 0
        cable_pixels = 0

        if seg_file.exists():
            seg = cv2.imread(str(seg_file), cv2.IMREAD_UNCHANGED)
            if seg is not None:
                seg_256 = _letterbox_nearest(seg, target_size)
                save_seg_path = str(out_seg / f"seg_{idx:04d}.png")
                cv2.imwrite(save_seg_path, seg_256)

                # Conteo de pixeles para evaluar colisiones de frente
                pole_pixels = int(np.sum(seg_256 == LABEL_THIN_STRUCTURES))
                tree_pixels = int(np.sum(seg_256 == LABEL_TREES))
                cable_pixels = int(np.sum(seg_256 == LABEL_ULTRA_THIN))

                has_pole = pole_pixels > 20
                has_tree = tree_pixels > 50
                has_cable = cable_pixels > 10

        records.append({
            "video_id":       video_id,
            "frame_index":    idx,
            "frame_number":   idx,
            "timestamp_ms":   round(idx * 100.0, 2), # 10 FPS simulado
            "laplacian_var":  round(lap_var, 2),
            "is_valid":       is_valid,
            "frame_path":     str(save_rgb_path),
            "depth_gt_path":  save_depth_path,
            "seg_gt_path":    save_seg_path,
            "has_pole":       has_pole,
            "has_tree":       has_tree,
            "has_cable":      has_cable,
            "pole_pixels":    pole_pixels,
            "tree_pixels":    tree_pixels,
            "cable_pixels":   cable_pixels,
            "environment":    env_name,
            "depth_raw_min":  depth_min,
            "depth_raw_max":  depth_max,
        })

    return records


def process_all_ddos_flights(
    ddos_raw_dir: Path,
    output_dir: Path,
    blur_threshold: float = 40.0,
) -> pd.DataFrame:
    """
    Escanea todos los vuelos descargados de DDOS y genera el dataset estructurado.
    """
    all_records = []
    flight_dirs = []

    for env in ["neighbourhood", "park"]:
        env_dir = ddos_raw_dir / env
        if env_dir.exists():
            for fid_dir in sorted(env_dir.iterdir()):
                if fid_dir.is_dir():
                    flight_dirs.append((env, fid_dir.name, fid_dir))

    for env_name, fid, fpath in flight_dirs:
        recs = extract_ddos_flight(
            flight_dir=fpath,
            output_dir=output_dir,
            env_name=env_name,
            flight_id=fid,
            blur_threshold=blur_threshold,
        )
        all_records.extend(recs)

    df = pd.DataFrame(all_records)
    if not df.empty:
        csv_path = output_dir / "ddos_dataset_index.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8")
        print(f"\n[ETL-DDOS] Dataset DDOS estructurado guardado en: {csv_path}")
        print(f"[ETL-DDOS] Total frames: {len(df)}")
        print(f"[ETL-DDOS] Frames con postes de frente : {int(df['has_pole'].sum())}")
        print(f"[ETL-DDOS] Frames con arboles de frente: {int(df['has_tree'].sum())}")
        print(f"[ETL-DDOS] Frames con cables aereos    : {int(df['has_cable'].sum())}")
    return df
