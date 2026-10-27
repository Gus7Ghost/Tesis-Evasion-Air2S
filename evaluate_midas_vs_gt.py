"""
evaluate_midas_vs_gt.py — Evaluacion Cuantitativa MiDaS vs Ground Truth (DDOS)
==============================================================================
Paper: "DDOS: The Drone Depth and Obstacle Segmentation Dataset" (CVPRW 2024)

Calcula las metricas formales estandar de la literatura de Vision Computacional:
  1. AbsRel  : Error Relativo Absoluto (menor es mejor)
  2. SqRel   : Error Relativo Cuadratico (menor es mejor)
  3. RMSE    : Raiz del Error Cuadratico Medio (menor es mejor)
  4. delta < 1.25 : Precision con umbral 1.25 (mayor es mejor, estandar KITTI/NYU)
  5. delta < 1.25^2: Precision con umbral 1.56
  6. delta < 1.25^3: Precision con umbral 1.95

Ademas, calcula las metricas desglosadas especificamente sobre:
  - Pixeles de Postes (thin_structures, clase 240)
  - Pixeles de Arboles (trees, clase 180)

Autor: Gustavo Bryan Lopez Cosme
Repositorio: https://github.com/Gus7Ghost/Tesis-Evasion-Air2S
"""

import sys
import io
import json
import numpy as np
import pandas as pd
import cv2
from pathlib import Path

# Forzar UTF-8 en stdout para Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

LABEL_POLE = 240
LABEL_TREE = 180


def compute_depth_metrics(pred_disp: np.ndarray, gt_depth: np.ndarray, mask: np.ndarray = None):
    """
    Calcula metricas entre la disparidad predicha (MiDaS) y la profundidad GT.
    MiDaS predice disparidad relativa inversa: pred_depth = 1.0 / (pred_disp + eps).
    Se alinea la escala y traslacion (least squares median scaling) estandar en MiDaS.
    """
    valid = (gt_depth > 0) & (gt_depth < 65000) & (pred_disp > 0)
    if mask is not None:
        valid = valid & mask

    if np.sum(valid) < 10:
        return None

    # MiDaS predice disparidad -> convertir a profundidad relativa
    # Profundidad relativa ~ 1 / disparidad
    pred_d = 1.0 / (pred_disp[valid].astype(np.float64) + 1e-6)
    gt_d = gt_depth[valid].astype(np.float64)

    # Median scaling estandar para modelos de disparidad relativa (MegaDepth / MiDaS)
    scale = np.median(gt_d) / np.median(pred_d)
    pred_d_scaled = pred_d * scale

    # 1. AbsRel
    abs_rel = float(np.mean(np.abs(gt_d - pred_d_scaled) / gt_d))

    # 2. SqRel
    sq_rel = float(np.mean(((gt_d - pred_d_scaled) ** 2) / gt_d))

    # 3. RMSE
    rmse = float(np.sqrt(np.mean((gt_d - pred_d_scaled) ** 2)))

    # 4. Deltas (precisión con umbrales)
    ratio = np.maximum(gt_d / (pred_d_scaled + 1e-6), pred_d_scaled / (gt_d + 1e-6))
    d1 = float(np.mean(ratio < 1.25))
    d2 = float(np.mean(ratio < (1.25 ** 2)))
    d3 = float(np.mean(ratio < (1.25 ** 3)))

    return {
        "abs_rel": round(abs_rel, 4),
        "sq_rel": round(sq_rel, 4),
        "rmse": round(rmse, 2),
        "delta_1": round(d1 * 100.0, 2),
        "delta_2": round(d2 * 100.0, 2),
        "delta_3": round(d3 * 100.0, 2),
        "pixels": int(np.sum(valid)),
    }


def main():
    ddos_csv = Path("datasets/dataset_final/ddos_processed/ddos_dataset_index.csv")
    depth_dir = Path("datasets/dataset_final/ddos_processed/midas_depth/raw_depth")

    if not ddos_csv.exists():
        print(f"[ERROR] No existe: {ddos_csv}")
        return

    df = pd.read_csv(ddos_csv)
    print("=" * 65)
    print("  EVALUACION DE PRECISION: MiDaS v2.1 Small vs GROUND TRUTH (DDOS)")
    print("=" * 65)
    print(f"  Total frames a evaluar: {len(df)}")

    global_metrics = []
    pole_metrics = []
    tree_metrics = []

    for i, row in df.iterrows():
        vid_id = row["video_id"]
        frame_idx = row["frame_index"]
        # El nombre guardado por run_midas_offline es: {vid_id}_{stem}.npz
        # frame_path: datasets\dataset_final\ddos_processed\ddos_neighbourhood_flight_0\rgb\frame_0000.png
        fstem = Path(row["frame_path"]).stem
        save_name = f"{vid_id}_{fstem}.npz"
        npz_p = depth_dir / save_name

        gt_p = Path(row["depth_gt_path"])
        seg_p = Path(row["seg_gt_path"]) if pd.notna(row.get("seg_gt_path")) else None

        if not npz_p.exists() or not gt_p.exists():
            continue

        pred = np.load(npz_p)["depth"]
        gt = cv2.imread(str(gt_p), cv2.IMREAD_UNCHANGED)
        seg = cv2.imread(str(seg_p), cv2.IMREAD_UNCHANGED) if seg_p and seg_p.exists() else None

        # Redimensionar pred al tamaño de GT si difieren (ambos son 256x256 tras letterbox)
        if pred.shape != gt.shape:
            pred = cv2.resize(pred, (gt.shape[1], gt.shape[0]))

        # Metricas globales de la escena
        m_glob = compute_depth_metrics(pred, gt)
        if m_glob:
            global_metrics.append(m_glob)

        if seg is not None:
            # Metricas especificas sobre POSTES
            mask_pole = (seg == LABEL_POLE)
            if np.sum(mask_pole) > 20:
                m_pole = compute_depth_metrics(pred, gt, mask=mask_pole)
                if m_pole:
                    pole_metrics.append(m_pole)

            # Metricas especificas sobre ARBOLES
            mask_tree = (seg == LABEL_TREE)
            if np.sum(mask_tree) > 50:
                m_tree = compute_depth_metrics(pred, gt, mask=mask_tree)
                if m_tree:
                    tree_metrics.append(m_tree)

    def avg_m(metric_list):
        if not metric_list:
            return {}
        keys = ["abs_rel", "sq_rel", "rmse", "delta_1", "delta_2", "delta_3"]
        return {k: round(float(np.mean([m[k] for m in metric_list])), 3) for k in keys}

    res_global = avg_m(global_metrics)
    res_pole = avg_m(pole_metrics)
    res_tree = avg_m(tree_metrics)

    summary = {
        "global_scene": res_global,
        "utility_poles": res_pole,
        "trees": res_tree,
        "frames_evaluated": len(global_metrics),
        "frames_with_poles": len(pole_metrics),
        "frames_with_trees": len(tree_metrics),
    }

    out_file = Path("datasets/dataset_final/ddos_processed/midas_vs_gt_benchmark.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=4)

    line = "-" * 65
    print("\n" + line)
    print(f"{'METRICA CIENTIFICA':<22}{'ESCENA GLOBAL':>14}{'POSTES':>14}{'ARBOLES':>14}")
    print(line)
    for k, label in [
        ("abs_rel", "AbsRel (Error Rel.)"),
        ("sq_rel", "SqRel"),
        ("rmse", "RMSE"),
        ("delta_1", "delta < 1.25 (%)"),
        ("delta_2", "delta < 1.25^2 (%)"),
        ("delta_3", "delta < 1.25^3 (%)"),
    ]:
        vg = f"{res_global.get(k, 0.0):.3f}"
        vp = f"{res_pole.get(k, 0.0):.3f}"
        vt = f"{res_tree.get(k, 0.0):.3f}"
        print(f"{label:<22}{vg:>14}{vp:>14}{vt:>14}")

    print(line)
    print(f"Frames con evaluacion de postes : {len(pole_metrics)} / {len(global_metrics)}")
    print(f"Frames con evaluacion de arboles: {len(tree_metrics)} / {len(global_metrics)}")
    print(f"Benchmark exportado en: {out_file}")
    print(line + "\n")


if __name__ == "__main__":
    main()
