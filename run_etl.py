"""
run_etl.py — Script Principal del Pipeline ETL de Preprocesamiento
==================================================================
Hito 1 — Semana 9 (27 de octubre de 2026)

Orquesta los tres módulos del pipeline ETL:
    1. extract_frames.py  → Extracción de frames a 10 FPS + cálculo de blur
    2. filter_blur.py     → Filtrado de frames nítidos + reporte estadístico
    3. dataset_manager.py → Partición anti-leakage + export de dataset_index.csv

Uso:
    python run_etl.py --videos_dir <ruta_a_videos> --dataset_root <ruta_salida>

Flags opcionales:
    --target_fps      FPS de extracción       (default: 10)
    --blur_threshold  Umbral de varianza lap. (default: 80.0)
    --train_ratio     Proporción train         (default: 0.70)
    --val_ratio       Proporción val           (default: 0.15)
    --seed            Semilla de reproducib.   (default: 42)
    --no_copy         Solo genera el CSV sin copiar los PNGs
    --auto_threshold  Sugiere el umbral automáticamente para ≥80% retención

Ejemplo con videos de muestra:
    python run_etl.py --videos_dir videos_raw --dataset_root dataset

Autor: Gustavo Bryan López Cosme
Repositorio: https://github.com/Gus7Ghost/Tesis-Evasion-Air2S
"""

import sys
import argparse
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Asegurar que el directorio raíz del proyecto esté en sys.path
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.etl.extract_frames import extract_frames_from_directory, extract_frames_from_video
from src.etl.filter_blur import filter_records, print_report, suggest_threshold
from src.etl.dataset_manager import build_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pipeline ETL — Preprocesamiento de videos para MiDaS"
    )
    parser.add_argument(
        "--videos_dir",
        type=str,
        default="videos_raw",
        help="Directorio con los videos de entrada (.mp4, .mkv, .avi, .mov)",
    )
    parser.add_argument(
        "--dataset_root",
        type=str,
        default="dataset",
        help="Directorio raíz de salida del dataset estructurado",
    )
    parser.add_argument(
        "--target_fps",
        type=float,
        default=10.0,
        help="FPS de extracción de frames (default: 10)",
    )
    parser.add_argument(
        "--blur_threshold",
        type=float,
        default=80.0,
        help="Varianza laplaciana mínima para considerar un frame nítido (default: 80.0)",
    )
    parser.add_argument(
        "--train_ratio",
        type=float,
        default=0.70,
        help="Proporción del conjunto de entrenamiento (default: 0.70)",
    )
    parser.add_argument(
        "--val_ratio",
        type=float,
        default=0.15,
        help="Proporción del conjunto de validación (default: 0.15)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Semilla de reproducibilidad para la partición (default: 42)",
    )
    parser.add_argument(
        "--no_copy",
        action="store_true",
        help="Solo genera el dataset_index.csv sin copiar los PNGs al árbol de splits",
    )
    parser.add_argument(
        "--auto_threshold",
        action="store_true",
        help="Calcula automáticamente el umbral de blur para garantizar ≥80%% de retención",
    )
    parser.add_argument(
        "--single_video",
        type=str,
        default=None,
        help="Ruta a un único video (alternativa a --videos_dir)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("\n" + "=" * 60)
    print("  PIPELINE ETL — PREPROCESAMIENTO DE DATOS DE VUELO")
    print("  Tesis: Evasión de Obstáculos con MiDaS (DJI Air 2S)")
    print("  Semana 9 — 27 de octubre de 2026")
    print("=" * 60 + "\n")

    t_global = time.perf_counter()

    # ------------------------------------------------------------------
    # PASO 1: Extracción de frames a 10 FPS
    # ------------------------------------------------------------------
    print("─" * 60)
    print("PASO 1/3 — Extracción de frames")
    print("─" * 60)

    # Directorio temporal de frames crudos (antes de la partición)
    frames_raw_dir = str(Path(args.dataset_root) / "_frames_raw")

    if args.single_video:
        all_records = extract_frames_from_video(
            video_path=args.single_video,
            output_dir=frames_raw_dir,
            target_fps=args.target_fps,
            blur_threshold=args.blur_threshold,
            save_frames=True,
            verbose=True,
        )
    else:
        all_records = extract_frames_from_directory(
            videos_dir=args.videos_dir,
            output_dir=frames_raw_dir,
            target_fps=args.target_fps,
            blur_threshold=args.blur_threshold,
            save_frames=True,
            verbose=True,
        )

    if not all_records:
        print("[ETL] ⚠ No se extrajeron frames. Verifica la ruta de videos.")
        sys.exit(1)

    # ------------------------------------------------------------------
    # PASO 2: Filtrado de calidad (blur) + reporte estadístico
    # ------------------------------------------------------------------
    print("─" * 60)
    print("PASO 2/3 — Filtrado de nitidez")
    print("─" * 60)

    threshold = args.blur_threshold

    # Ajuste automático del umbral si se solicitó
    if args.auto_threshold:
        threshold = suggest_threshold(all_records, target_retention=0.80)
        print(f"[ETL] Umbral automático calculado: {threshold:.2f}")

    valid_records, blurry_records = filter_records(all_records, blur_threshold=threshold)
    print_report(all_records, valid_records, blurry_records, threshold)

    if not valid_records:
        print("[ETL] ⚠ Ningún frame superó el umbral de nitidez.")
        print(f"[ETL]   Prueba con --auto_threshold o reduce --blur_threshold")
        sys.exit(1)

    # ------------------------------------------------------------------
    # PASO 3: Estructuración del dataset (anti-leakage) + export CSV
    # ------------------------------------------------------------------
    print("─" * 60)
    print("PASO 3/3 — Estructuración y exportación del dataset")
    print("─" * 60)

    csv_path, df = build_dataset(
        records=valid_records,
        dataset_root=args.dataset_root,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        seed=args.seed,
        copy_files=not args.no_copy,
        verbose=True,
    )

    # ------------------------------------------------------------------
    # Resumen final
    # ------------------------------------------------------------------
    elapsed_total = time.perf_counter() - t_global
    total_frames = len(all_records)
    valid_frames = len(valid_records)
    retention_pct = (valid_frames / total_frames * 100) if total_frames > 0 else 0.0
    fps_total = total_frames / elapsed_total if elapsed_total > 0 else 0.0

    print("=" * 60)
    print("  PIPELINE ETL COMPLETADO")
    print("=" * 60)
    print(f"  Frames totales extraídos : {total_frames}")
    print(f"  Frames válidos           : {valid_frames} ({retention_pct:.1f}%)")
    print(f"  Umbral de nitidez usado  : {threshold:.2f}")
    print(f"  Tiempo total             : {elapsed_total:.2f}s")
    print(f"  Velocidad media          : {fps_total:.1f} FPS")
    print(f"  Dataset index (CSV)      : {csv_path}")
    print("=" * 60 + "\n")

    # Validar métricas técnicas de la tesis
    print("  MÉTRICAS TÉCNICAS (Hito 1):")
    tasa_ok = retention_pct >= 80.0
    fps_ok  = fps_total >= 30.0
    print(f"  ✓ Tasa retención ≥80%   : {retention_pct:.1f}% → {'✅ CUMPLE' if tasa_ok else '⚠ REVISAR umbral'}")
    print(f"  ✓ FPS procesados ≥30    : {fps_total:.1f} FPS → {'✅ CUMPLE' if fps_ok else '⚠ Hardware lento'}")
    print()


if __name__ == "__main__":
    main()
