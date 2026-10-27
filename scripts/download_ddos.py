"""
download_ddos.py — Descargador selectivo de vuelos del dataset DDOS (Hugging Face)
==================================================================================
Descarga vuelos individuales de:
    https://huggingface.co/datasets/benediktkol/DDOS
    Paper: "DDOS: The Drone Depth and Obstacle Segmentation Dataset" (CVPRW 2024)

Descarga en paralelo (8 hilos) para maxima velocidad:
    - RGB images (1280x720)
    - Ground Truth Depth (16-bit)
    - Segmentation masks (postes, arboles, cables, edificios)
    - Flight metadata (pose, telemetria)

Autor: Gustavo Bryan Lopez Cosme
Repositorio: https://github.com/Gus7Ghost/Tesis-Evasion-Air2S
"""

import os
import sys
import io
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Tuple

# Forzar UTF-8 en stdout para Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HF_BASE_URL = "https://huggingface.co/datasets/benediktkol/DDOS/resolve/main"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def download_file(url: str, dest_path: Path) -> bool:
    """Descarga un archivo si no existe ya localmente."""
    if dest_path.exists() and dest_path.stat().st_size > 0:
        return True
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
        with open(dest_path, "wb") as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"[ERROR] Fallo al descargar {url}: {e}")
        return False


def download_flight(
    split: str,
    environment: str,
    flight_id: str,
    output_root: Path,
    num_frames: int = 100,
    include_depth: bool = True,
    include_seg: bool = True,
    max_workers: int = 8,
) -> bool:
    """
    Descarga una secuencia completa de vuelo de DDOS.
    """
    flight_name = f"{environment}_{flight_id}"
    dest_dir = output_root / environment / flight_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[DDOS] Iniciando descarga de vuelo: {environment}/{flight_id} ({num_frames} frames)...")
    tasks: List[Tuple[str, Path]] = []

    # Metadata
    meta_url = f"{HF_BASE_URL}/data/{split}/{environment}/{flight_id}/metadata.csv"
    tasks.append((meta_url, dest_dir / "metadata.csv"))

    # Frames (image, depth, segmentation)
    for i in range(num_frames):
        img_url = f"{HF_BASE_URL}/data/{split}/{environment}/{flight_id}/image/{i}.png"
        tasks.append((img_url, dest_dir / "image" / f"{i}.png"))

        if include_depth:
            depth_url = f"{HF_BASE_URL}/data/{split}/{environment}/{flight_id}/depth/{i}.png"
            tasks.append((depth_url, dest_dir / "depth" / f"{i}.png"))

        if include_seg:
            seg_url = f"{HF_BASE_URL}/data/{split}/{environment}/{flight_id}/segmentation/{i}.png"
            tasks.append((seg_url, dest_dir / "segmentation" / f"{i}.png"))

    total = len(tasks)
    completed = 0
    t0 = time.perf_counter()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(download_file, url, path): (url, path) for url, path in tasks}
        for future in as_completed(futures):
            res = future.result()
            completed += 1
            if completed % 25 == 0 or completed == total:
                elapsed = time.perf_counter() - t0
                speed = completed / elapsed if elapsed > 0 else 0
                pct = completed / total * 100
                print(f"[DDOS] {completed:>3}/{total} archivos ({pct:.0f}%) | {speed:.1f} arch/s")

    elapsed = time.perf_counter() - t0
    print(f"[DDOS] Vuelo {flight_name} descargado en {elapsed:.1f}s en: {dest_dir}")
    return True


def main():
    dest_root = Path("datasets/raw/ddos")

    # Descargaremos 3 vuelos clave:
    # 1. neighbourhood / 0 -> vuelo urbano de frente a casas, calles y postes
    # 2. neighbourhood / 1 -> vuelo urbano secundario
    # 3. park / 0          -> vuelo entre arboles y follaje
    flights = [
        ("validation", "neighbourhood", "0"),
        ("validation", "neighbourhood", "1"),
        ("validation", "park", "0"),
    ]

    print("=" * 65)
    print("  DESCARGA DE VUELOS FRONTALES — DATASET DDOS (CVPRW 2024)")
    print("  Paper: Drone Depth and Obstacle Segmentation Dataset")
    print("=" * 65)

    t_all = time.perf_counter()
    for split, env, fid in flights:
        download_flight(
            split=split,
            environment=env,
            flight_id=fid,
            output_root=dest_root,
            num_frames=100,
            include_depth=True,
            include_seg=True,
            max_workers=8,
        )

    t_total = time.perf_counter() - t_all
    print("\n" + "=" * 65)
    print(f"  DESCARGA COMPLETADA: 3 VUELOS ({len(flights)*100} FRAMES CON GROUND TRUTH)")
    print(f"  Tiempo total: {t_total:.1f} s")
    print(f"  Ubicacion: {dest_root.resolve()}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
