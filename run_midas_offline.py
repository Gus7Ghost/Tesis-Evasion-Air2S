"""
run_midas_offline.py — Inferencia Offline de Profundidad con MiDaS v2.1 Small
=============================================================================
Hito 2 — Semana 10 (03 de noviembre de 2026)

Procesa el dataframe estructurado por el pipeline ETL (dataset_index_master.csv)
a traves del modelo de estimacion de profundidad monocular MiDaS v2.1 Small
(TensorFlow Lite) de forma 100% offline (sin dron encendido ni camara en vivo).

Objetivos y Metricas:
  1. Validar la deteccion y contraste de profundidad en postes y arboles.
  2. Evaluar el consumo computacional: latencia por fotograma (ms) y throughput (FPS).
  3. Verificar el cumplimiento del umbral de exito: latencia <= 50 ms en CPU.
  4. Generar mapas de profundidad coloreados (COLORMAP_INFERNO) y registros CSV.

Uso:
    python run_midas_offline.py --csv_path datasets/dataset_final/dataset_index_master.csv

Flags:
    --sample N       Procesar solo N imagenes aleatorias (ej. para validacion rapida)
    --save_vis       Guardar imagenes combinadas RGB + Mapa de profundidad (PNG)
    --num_threads    Hilos para el interprete TFLite (default: 4)

Autor: Gustavo Bryan Lopez Cosme
Repositorio: https://github.com/Gus7Ghost/Tesis-Evasion-Air2S
"""

import sys
import io
import os
import time
import json
import argparse
import numpy as np
import pandas as pd
import cv2
from pathlib import Path

# Forzar UTF-8 en stdout para Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.perception.depth_estimator import DepthEstimator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inferencia Offline de Profundidad con MiDaS v2.1 Small (TFLite)"
    )
    parser.add_argument(
        "--csv_path",
        type=str,
        default="datasets/dataset_final/dataset_index_master.csv",
        help="Ruta al archivo CSV maestro generado por el pipeline ETL",
    )
    parser.add_argument(
        "--model_path",
        type=str,
        default="models/midas_v21_small_256.tflite",
        help="Ruta al modelo cuantizado MiDaS TFLite",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="datasets/dataset_final/depth_maps",
        help="Directorio de salida para los mapas de profundidad",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Numero de muestras a procesar (None = todo el dataset)",
    )
    parser.add_argument(
        "--save_vis",
        action="store_true",
        default=True,
        help="Guardar visualizaciones lado a lado RGB + Profundidad",
    )
    parser.add_argument(
        "--num_threads",
        type=int,
        default=4,
        help="Numero de hilos para inferencia en CPU (default: 4)",
    )
    return parser.parse_args()


def colorize_depth(depth_map: np.ndarray) -> np.ndarray:
    """Normaliza y colorea un mapa de disparidad (valores altos = mas cercano)."""
    d_min, d_max = np.min(depth_map), np.max(depth_map)
    if d_max - d_min > 1e-6:
        depth_norm = ((depth_map - d_min) / (d_max - d_min) * 255.0).astype(np.uint8)
    else:
        depth_norm = np.zeros_like(depth_map, dtype=np.uint8)
    return cv2.applyColorMap(depth_norm, cv2.COLORMAP_INFERNO)


def main() -> None:
    args = parse_args()

    print("\n" + "=" * 65)
    print("  INFERENCIA OFFLINE DE PROFUNDIDAD — MiDaS v2.1 Small (TFLite)")
    print("  Hito 2 — Taller de Investigacion (03 de noviembre de 2026)")
    print("  Tesis: Evasion de Postes y Arboles en Drones Urbanos")
    print("=" * 65 + "\n")

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        print(f"[ERROR] No se encontro el archivo CSV: {csv_path}")
        sys.exit(1)

    df = pd.read_csv(csv_path)
    total_records = len(df)
    print(f"[DATA] Registros cargados desde el CSV: {total_records}")

    if args.sample and args.sample < total_records:
        df = df.sample(n=args.sample, random_state=42).reset_index(drop=True)
        print(f"[DATA] Subconjunto muestreado para evaluacion: {len(df)} frames")

    # Inicializar DepthEstimator
    config = {
        "model_path": args.model_path,
        "input_width": 256,
        "input_height": 256,
        "num_threads": args.num_threads,
    }
    estimator = DepthEstimator(config)

    # Preparar directorios de salida
    out_dir = Path(args.output_dir)
    vis_dir = out_dir / "visualizations"
    raw_dir = out_dir / "raw_depth"
    vis_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    latencies_ms = []
    contrast_ratios = []
    processed_records = []

    print(f"\n[INFERENCIA] Iniciando inferencia offline sobre {len(df)} frames...")
    t_start_total = time.perf_counter()

    for i, row in df.iterrows():
        rel_path = row["frame_path"]
        # Resolver ruta relativa respecto a la raiz del proyecto si es necesario
        full_path = Path(rel_path)
        if not full_path.exists():
            full_path = PROJECT_ROOT / rel_path
        if not full_path.exists():
            print(f"[WARN] No existe el frame: {rel_path}")
            continue

        frame = cv2.imread(str(full_path))
        if frame is None:
            continue

        # Inferencia cronometrada
        t0 = time.perf_counter()
        depth_map = estimator.estimate(frame)
        t1 = time.perf_counter()

        latency_ms = (t1 - t0) * 1000.0
        latencies_ms.append(latency_ms)

        # Metrica de contraste de profundidad:
        # Relacion entre el valor maximo (objeto en primer plano: poste/arbol)
        # y el percentil 25 (fondo lejano)
        p25 = np.percentile(depth_map, 25)
        p95 = np.percentile(depth_map, 95)
        contrast = float(p95 / (p25 + 1e-5))
        contrast_ratios.append(contrast)

        vid_id = row.get("video_id", "unknown")
        fname = Path(rel_path).stem
        save_name = f"{vid_id}_{fname}"

        # Guardar array crudo comprimido .npz
        npz_path = raw_dir / f"{save_name}.npz"
        np.savez_compressed(npz_path, depth=depth_map.astype(np.float32))

        # Guardar visualizacion combinada
        vis_path = ""
        if args.save_vis:
            color_depth = colorize_depth(depth_map)
            h, w = frame.shape[:2]
            color_depth_resized = cv2.resize(color_depth, (w, h))
            combined = np.hstack([frame, color_depth_resized])
            vis_path = str(vis_dir / f"{save_name}_depth.jpg")
            cv2.imwrite(vis_path, combined)

        rec = {**row.to_dict()}
        rec["latency_ms"] = round(latency_ms, 2)
        rec["depth_contrast"] = round(contrast, 2)
        rec["depth_npz_path"] = str(npz_path)
        rec["depth_vis_path"] = vis_path
        processed_records.append(rec)

        if (i + 1) % 50 == 0 or (i + 1) == len(df):
            curr_avg = np.mean(latencies_ms[-50:])
            curr_fps = 1000.0 / curr_avg if curr_avg > 0 else 0
            print(f"[PROGRESO] {i+1:>4}/{len(df)} frames | Latencia media: {curr_avg:.1f} ms ({curr_fps:.1f} FPS)")

    total_time = time.perf_counter() - t_start_total
    latencies = np.array(latencies_ms)
    contrasts = np.array(contrast_ratios)

    # Exportar DataFrame enriquecido con las salidas de profundidad
    out_csv = Path(args.output_dir) / "dataset_with_depth.csv"
    res_df = pd.DataFrame(processed_records)
    res_df.to_csv(out_csv, index=False, encoding="utf-8")

    # Resumen de metricas
    mean_lat = float(np.mean(latencies))
    med_lat  = float(np.median(latencies))
    p95_lat  = float(np.percentile(latencies, 95))
    fps_sost = float(len(latencies) / total_time)
    mean_ctr = float(np.mean(contrasts))

    summary = {
        "total_frames_processed": len(latencies),
        "total_time_seconds": round(total_time, 2),
        "latency_mean_ms": round(mean_lat, 2),
        "latency_median_ms": round(med_lat, 2),
        "latency_p95_ms": round(p95_lat, 2),
        "effective_fps": round(fps_sost, 1),
        "mean_depth_contrast": round(mean_ctr, 2),
        "meets_latency_threshold_50ms": bool(mean_lat <= 50.0),
    }

    report_path = Path(args.output_dir) / "depth_inference_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=4)

    # Impresion de resultados en consola
    line = "=" * 65
    print("\n" + line)
    print("  RESULTADOS DE INFERENCIA OFFLINE — HITO 2 (03/11/2026)")
    print(line)
    print(f"  Frames evaluados              : {len(latencies):>6}")
    print(f"  Tiempo total de ejecucion     : {total_time:>6.1f} s")
    print(f"  Latencia media por frame      : {mean_lat:>6.2f} ms")
    print(f"  Latencia mediana              : {med_lat:>6.2f} ms")
    print(f"  Latencia Percentil 95 (P95)   : {p95_lat:>6.2f} ms")
    print(f"  Throughput efectivo           : {fps_sost:>6.1f} FPS")
    print(f"  Contraste medio obstaculo/fondo: {mean_ctr:>6.2f}x")
    print(line)
    print("  EVALUACION DE UMBRALES TECNICOS (TESIS):")
    cumple = "CUMPLE (APROBADO)" if mean_lat <= 50.0 else "SUPERA UMBRAL"
    print(f"  * Latencia <= 50 ms en CPU    : {mean_lat:.2f} ms --> {cumple}")
    print(f"  * Throughput >= 20 FPS        : {fps_sost:.1f} FPS --> {'CUMPLE' if fps_sost >= 20.0 else 'REVISAR'}")
    print(line)
    print(f"  Reporte exportado en: {report_path}")
    print(f"  Dataset con profundidad: {out_csv}")
    print(f"  Visualizaciones guardadas en: {vis_dir}")
    print(line + "\n")


if __name__ == "__main__":
    main()
