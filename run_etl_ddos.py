"""
run_etl_ddos.py — Ejecucion del Pipeline ETL sobre el Dataset DDOS (CVPRW 2024)
==============================================================================
Paper: "DDOS: The Drone Depth and Obstacle Segmentation Dataset"
Autores: Benedikt Kolbeinsson y Krystian Mikolajczyk (Imperial College London)

Ejecuta el procesamiento ETL sobre los vuelos descargados de DDOS:
  1. Extraccion y sincronizacion de RGB, Ground Truth Depth y Segmentacion
  2. Redimensionamiento a 256x256 letterbox para MiDaS
  3. Deteccion de postes, arboles y cables en la linea de vuelo frontal
  4. Particion anti-leakage por vuelo individual (train/val/test)
  5. Exportacion de metadatos enriquecidos (ddos_dataset_index.csv)

Autor: Gustavo Bryan Lopez Cosme
Repositorio: https://github.com/Gus7Ghost/Tesis-Evasion-Air2S
"""

import sys
import io
import time
import argparse
from pathlib import Path

# Forzar UTF-8 en stdout para Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.etl.extract_ddos import process_all_ddos_flights
from src.etl.dataset_manager import assign_splits, export_index


def main():
    parser = argparse.ArgumentParser(description="ETL para dataset frontal DDOS")
    parser.add_argument("--raw_dir", type=str, default="datasets/raw/ddos")
    parser.add_argument("--output_dir", type=str, default="datasets/dataset_final/ddos_processed")
    parser.add_argument("--blur_threshold", type=float, default=30.0)
    args = parser.parse_args()

    raw_path = Path(args.raw_dir)
    out_path = Path(args.output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 65)
    print("  PIPELINE ETL — DATASET CIENTIFICO DDOS (CVPRW 2024)")
    print("  Tesis: Evasion de Postes y Arboles en Drones de Persecucion")
    print("=" * 65)

    t0 = time.perf_counter()
    df = process_all_ddos_flights(
        ddos_raw_dir=raw_path,
        output_dir=out_path,
        blur_threshold=args.blur_threshold,
    )

    if df.empty:
        print("[ERROR] No se procesaron frames de DDOS.")
        return

    # Asignar particion anti-leakage a nivel de vuelo completo
    records = df.to_dict(orient="records")
    records_split = assign_splits(records, train_ratio=0.70, val_ratio=0.15, seed=42)

    # Exportar CSV final
    csv_final = export_index(records_split, str(out_path), "ddos_dataset_index_master.csv")
    elapsed = time.perf_counter() - t0

    print("=" * 65)
    print("  ETL DDOS COMPLETADO")
    print("=" * 65)
    print(f"  Frames frontales procesados : {len(records_split)}")
    print(f"  Frames con postes de frente : {sum(1 for r in records_split if r['has_pole'])}")
    print(f"  Frames con arboles de frente: {sum(1 for r in records_split if r['has_tree'])}")
    print(f"  Frames con cables aereos    : {sum(1 for r in records_split if r['has_cable'])}")
    print(f"  Throughput de procesamiento : {len(records_split)/elapsed:.1f} FPS")
    print(f"  Tiempo total                : {elapsed:.2f} s")
    print(f"  CSV maestro con Ground Truth: {csv_final}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
