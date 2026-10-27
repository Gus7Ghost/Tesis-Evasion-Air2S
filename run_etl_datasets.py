"""
run_etl_datasets.py — ETL Unificado para Múltiples Datasets Alternativos
=========================================================================
Hito 1 — Semana 9 (27 de octubre de 2026)

Orquesta el pipeline ETL completo sobre los tres datasets alternativos
(Semantic Drone Dataset, Utility Poles, UAVid) y genera un índice
maestro unificado (dataset_index_master.csv) listo para la inferencia
offline con MiDaS (Hito 2).

Uso:
    python run_etl_datasets.py --datasets_root datasets/raw

Flags opcionales:
    --datasets_root  Directorio raíz con los datasets descargados
    --output_root    Directorio de salida del dataset procesado
    --blur_threshold Umbral de varianza laplaciana (default: 80.0)
    --max_per_dataset Limite de imágenes por dataset (para pruebas rápidas)
    --auto_threshold  Calcula umbral automáticamente para >=80% retención

Autor: Gustavo Bryan López Cosme
Repositorio: https://github.com/Gus7Ghost/Tesis-Evasion-Air2S
"""

import sys
import io
import argparse
import time
from pathlib import Path

# Forzar UTF-8 en stdout para Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.etl.extract_images import extract_images_from_directory
from src.etl.extract_frames import extract_frames_from_directory
from src.etl.filter_blur import filter_records, print_report, suggest_threshold
from src.etl.dataset_manager import build_dataset
from src.etl.dataset_merger import merge_indexes, print_summary, export_master


# ---------------------------------------------------------------------------
# Configuración por dataset: tipo y subdirectorio de imágenes
# ---------------------------------------------------------------------------
DATASET_CONFIGS = {
    "drone_urban": {
        "type":        "images",
        "images_dir":  "drone_urban",
        "description": "Aerial Drone Urban Dataset — 1,791 imagenes aereas urbanas de dron",
    },
    "semantic_drone": {
        "type":        "images",
        "images_dir":  "semantic_drone",          # relativo a datasets_root
        "description": "Semantic Drone Dataset (TU Graz) — clases: tree, pole, obstacle",
    },
    "utility_poles": {
        "type":        "images",
        "images_dir":  "utility_poles",
        "description": "Utility Poles (Roboflow) — postes de concreto y madera",
    },
    "uavid": {
        "type":        "videos",
        "videos_dir":  "uavid",
        "description": "UAVid Urban Aerial — clases: tree, building, road",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ETL unificado sobre múltiples datasets alternativos"
    )
    parser.add_argument(
        "--datasets_root",
        type=str,
        default="datasets/raw",
        help="Directorio raíz donde están los datasets descargados",
    )
    parser.add_argument(
        "--output_root",
        type=str,
        default="datasets/dataset_final",
        help="Directorio raíz del dataset unificado de salida",
    )
    parser.add_argument(
        "--frames_root",
        type=str,
        default="datasets/frames",
        help="Directorio temporal para frames extraídos antes de la partición",
    )
    parser.add_argument(
        "--blur_threshold",
        type=float,
        default=80.0,
        help="Umbral mínimo de varianza laplaciana (default: 80.0)",
    )
    parser.add_argument(
        "--target_fps",
        type=float,
        default=10.0,
        help="FPS de extracción para datasets de video (default: 10)",
    )
    parser.add_argument(
        "--train_ratio",
        type=float,
        default=0.70,
    )
    parser.add_argument(
        "--val_ratio",
        type=float,
        default=0.15,
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )
    parser.add_argument(
        "--max_per_dataset",
        type=int,
        default=None,
        help="Limita el número de imágenes por dataset (útil para pruebas rápidas)",
    )
    parser.add_argument(
        "--auto_threshold",
        action="store_true",
        help="Calcula el umbral automáticamente para garantizar >=80% retención",
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Procesar solo este dataset (semantic_drone, utility_poles, uavid)",
    )
    return parser.parse_args()


def process_single_dataset(
    name: str,
    config: dict,
    datasets_root: Path,
    frames_root: Path,
    output_root: Path,
    blur_threshold: float,
    target_fps: float,
    train_ratio: float,
    val_ratio: float,
    seed: int,
    max_images: int,
    auto_threshold: bool,
) -> str:
    """
    Ejecuta el pipeline ETL completo para un dataset individual
    y retorna la ruta al dataset_index.csv generado.
    """
    print(f"\n{'='*60}")
    print(f"  PROCESANDO: {name.upper()}")
    print(f"  {config['description']}")
    print(f"{'='*60}")

    # --- Extracción ---
    if config["type"] == "images":
        src_dir = datasets_root / config["images_dir"]
        if not src_dir.exists():
            print(f"  [OMITIDO] No existe: {src_dir}")
            print(f"  Ejecuta: python scripts/download_datasets.py")
            return ""

        all_records = extract_images_from_directory(
            images_dir=str(src_dir),
            output_dir=str(frames_root),
            dataset_id=name,
            blur_threshold=blur_threshold,
            max_images=max_images,
            save_frames=True,
            verbose=True,
        )
    else:  # videos
        src_dir = datasets_root / config["videos_dir"]
        if not src_dir.exists():
            print(f"  [OMITIDO] No existe: {src_dir}")
            return ""

        all_records = extract_frames_from_directory(
            videos_dir=str(src_dir),
            output_dir=str(frames_root),
            target_fps=target_fps,
            blur_threshold=blur_threshold,
            save_frames=True,
            verbose=True,
        )

    if not all_records:
        print(f"  [OMITIDO] No se extrajeron registros de {name}")
        return ""

    # --- Filtrado ---
    threshold = blur_threshold
    if auto_threshold:
        threshold = suggest_threshold(all_records, target_retention=0.80)
        print(f"  Umbral automatico calculado: {threshold:.2f}")

    valid_records, blurry_records = filter_records(all_records, blur_threshold=threshold)
    print_report(all_records, valid_records, blurry_records, threshold)

    if not valid_records:
        print(f"  [OMITIDO] Ningun frame supero el umbral en {name}")
        return ""

    # --- Estructuración por dataset individual ---
    dataset_out = output_root / "per_dataset" / name
    csv_path, _ = build_dataset(
        records=valid_records,
        dataset_root=str(dataset_out),
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        seed=seed,
        copy_files=True,
        verbose=True,
    )

    return csv_path


def main() -> None:
    args = parse_args()

    datasets_root = Path(args.datasets_root)
    output_root   = Path(args.output_root)
    frames_root   = Path(args.frames_root)

    print("\n" + "=" * 60)
    print("  ETL UNIFICADO — DATASETS ALTERNATIVOS")
    print("  Tesis: Evasion de Obstaculos con MiDaS (DJI Air 2S)")
    print("  Semana 9 — 27 de octubre de 2026")
    print("=" * 60)

    t_global = time.perf_counter()
    configs = DATASET_CONFIGS

    if args.only:
        if args.only not in configs:
            print(f"Dataset desconocido: {args.only}")
            print(f"Opciones: {list(configs.keys())}")
            sys.exit(1)
        configs = {args.only: configs[args.only]}

    # Procesar cada dataset
    csv_paths = []
    for name, config in configs.items():
        csv = process_single_dataset(
            name=name,
            config=config,
            datasets_root=datasets_root,
            frames_root=frames_root,
            output_root=output_root,
            blur_threshold=args.blur_threshold,
            target_fps=args.target_fps,
            train_ratio=args.train_ratio,
            val_ratio=args.val_ratio,
            seed=args.seed,
            max_images=args.max_per_dataset,
            auto_threshold=args.auto_threshold,
        )
        if csv:
            csv_paths.append(csv)

    if not csv_paths:
        print("\n[ETL] Ningun dataset fue procesado.")
        print("[ETL] Descarga los datasets con: python scripts/download_datasets.py")
        sys.exit(0)

    # Fusionar en índice maestro
    print(f"\n{'='*60}")
    print("  FUSION EN DATASET MAESTRO")
    print(f"{'='*60}")

    merged_df = merge_indexes(csv_paths, only_valid=True)
    print_summary(merged_df)

    master_csv = export_master(
        merged_df,
        output_dir=str(output_root),
        filename="dataset_index_master.csv",
        verbose=True,
    )

    # Resumen final de métricas (Hito 1)
    elapsed = time.perf_counter() - t_global
    total = sum(1 for _ in csv_paths)

    print("=" * 60)
    print("  ETL COMPLETADO — METRICAS HITO 1")
    print("=" * 60)
    print(f"  Datasets procesados      : {total}")
    print(f"  Total frames en maestro  : {len(merged_df)}")
    print(f"  Tiempo total             : {elapsed:.1f}s")
    print(f"  Dataset index maestro    : {master_csv}")

    if not merged_df.empty and "split" in merged_df.columns:
        print(f"\n  Distribucion train/val/test:")
        for sp, cnt in merged_df["split"].value_counts().items():
            print(f"    {sp:<6}: {cnt}")

    print("\n  Siguiente paso (Hito 2):")
    print("  python run_midas_offline.py --csv_path", master_csv)
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
