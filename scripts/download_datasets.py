"""
download_datasets.py — Descarga Automatizada de Datasets Alternativos
======================================================================
Hito 1 — Semana 9 (27 de octubre de 2026)

Descarga los tres datasets públicos necesarios para el pipeline ETL
cuando no se dispone de videos reales del dron:

  D1. Semantic Drone Dataset (TU Graz) → via Kaggle API
  D2. Utility Poles                    → via Roboflow Universe API
  D3. UAVid Urban Aerial               → via Kaggle API

Requisitos antes de ejecutar:
    1. Cuenta Kaggle + kaggle.json en ~/.kaggle/kaggle.json
       (descargable desde https://www.kaggle.com/settings → API)
    2. Cuenta Roboflow + API Key gratis
       (obtener en https://app.roboflow.com → Settings → API)

Uso:
    python scripts/download_datasets.py \
        --roboflow_key TU_API_KEY \
        --output_dir datasets/raw

Autor: Gustavo Bryan López Cosme
Repositorio: https://github.com/Gus7Ghost/Tesis-Evasion-Air2S
"""

import sys
import io
import argparse
import subprocess
from pathlib import Path

# Forzar UTF-8 en stdout para Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Configuración de datasets
# ---------------------------------------------------------------------------

# D1 — Semantic Drone Dataset (TU Graz) en Kaggle
KAGGLE_SEMANTIC_DRONE = "bulentsiyah/semantic-drone-dataset"

# D3 — UAVid Dataset en Kaggle
KAGGLE_UAVID = "dasmehdixtr/uavid-dataset"

# D2 — Utility Poles en Roboflow Universe
# Proyecto público: workspace=cap6779, project=utility-poles-yqm8t, version=1
ROBOFLOW_WORKSPACE = "cap6779"
ROBOFLOW_PROJECT   = "utility-poles-yqm8t"
ROBOFLOW_VERSION   = 1


def check_kaggle_credentials() -> bool:
    """Verifica que access_token o kaggle.json esté configurado."""
    import os
    kaggle_dir = Path.home() / ".kaggle"
    access_token_file = kaggle_dir / "access_token"
    kaggle_json = kaggle_dir / "kaggle.json"

    if access_token_file.exists():
        token = access_token_file.read_text().strip()
        os.environ["KAGGLE_API_TOKEN"] = token
        return True
    elif kaggle_json.exists():
        return True
    elif "KAGGLE_API_TOKEN" in os.environ:
        return True

    print("[DOWNLOAD] ERROR: No se encontró ~/.kaggle/access_token ni kaggle.json")
    print("[DOWNLOAD] Obtén tu API key en: https://www.kaggle.com/settings")
    return False


def download_kaggle_dataset(dataset_slug: str, output_dir: str) -> bool:
    """
    Descarga un dataset de Kaggle usando la CLI de kaggle.

    Args:
        dataset_slug: Slug del dataset en formato 'owner/name'.
        output_dir  : Directorio destino de la descarga.

    Returns:
        True si la descarga fue exitosa.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"\n[DOWNLOAD] Descargando de Kaggle: {dataset_slug}")
    print(f"[DOWNLOAD] Destino: {output_path}")

    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "kaggle",
                "datasets", "download",
                "-d", dataset_slug,
                "-p", str(output_path),
                "--unzip",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            print(f"[DOWNLOAD] OK: {dataset_slug}")
            return True
        else:
            print(f"[DOWNLOAD] ERROR descargando {dataset_slug}:")
            print(result.stderr)
            return False
    except FileNotFoundError:
        print("[DOWNLOAD] ERROR: kaggle no está instalado. Ejecuta: pip install kaggle")
        return False


def download_roboflow_dataset(
    api_key: str,
    workspace: str,
    project: str,
    version: int,
    output_dir: str,
    fmt: str = "folder",
) -> bool:
    """
    Descarga un dataset público de Roboflow Universe.

    Args:
        api_key   : API Key de tu cuenta Roboflow (gratis).
        workspace : Slug del workspace del dataset.
        project   : Slug del proyecto.
        version   : Número de versión del dataset.
        output_dir: Directorio destino.
        fmt       : Formato de descarga (folder = solo imágenes sin anotaciones).

    Returns:
        True si la descarga fue exitosa.
    """
    try:
        from roboflow import Roboflow
    except ImportError:
        print("[DOWNLOAD] ERROR: roboflow no instalado. Ejecuta: pip install roboflow")
        return False

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"\n[DOWNLOAD] Descargando de Roboflow: {workspace}/{project} v{version}")
    print(f"[DOWNLOAD] Destino: {output_path}")

    try:
        rf = Roboflow(api_key=api_key)
        proj = rf.workspace(workspace).project(project)
        dataset = proj.version(version).download(fmt, location=str(output_path))
        print(f"[DOWNLOAD] OK: dataset guardado en {dataset.location}")
        return True
    except Exception as e:
        print(f"[DOWNLOAD] ERROR descargando desde Roboflow: {e}")
        return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Descarga automatizada de datasets alternativos para el ETL"
    )
    parser.add_argument(
        "--roboflow_key",
        type=str,
        default=None,
        help="API Key de Roboflow (obtener en app.roboflow.com → Settings → API)",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="datasets/raw",
        help="Directorio raíz de salida para los datasets (default: datasets/raw)",
    )
    parser.add_argument(
        "--skip_d1",
        action="store_true",
        help="Omitir descarga del Semantic Drone Dataset (D1)",
    )
    parser.add_argument(
        "--skip_d2",
        action="store_true",
        help="Omitir descarga de Utility Poles Roboflow (D2)",
    )
    parser.add_argument(
        "--skip_d3",
        action="store_true",
        help="Omitir descarga del UAVid Dataset (D3)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)

    print("\n" + "=" * 60)
    print("  DESCARGA DE DATASETS ALTERNATIVOS — HITO 1")
    print("  Tesis: Evasion de Obstaculos con MiDaS (DJI Air 2S)")
    print("=" * 60)

    results = {}

    # ------------------------------------------------------------------
    # D1 — Semantic Drone Dataset (TU Graz) via Kaggle
    # ------------------------------------------------------------------
    if not args.skip_d1:
        print("\n[D1] Semantic Drone Dataset (TU Graz / Kaggle)")
        print("     Clases utiles: tree, fence-pole, wall, obstacle")
        print("     Tamaño aprox: ~1.1 GB")
        if check_kaggle_credentials():
            ok = download_kaggle_dataset(
                KAGGLE_SEMANTIC_DRONE,
                str(output_dir / "semantic_drone"),
            )
            results["D1_semantic_drone"] = "OK" if ok else "ERROR"
        else:
            results["D1_semantic_drone"] = "OMITIDO (sin kaggle.json)"

    # ------------------------------------------------------------------
    # D2 — Utility Poles (Roboflow Universe)
    # ------------------------------------------------------------------
    if not args.skip_d2:
        print("\n[D2] Utility Poles (Roboflow Universe)")
        print("     Clases: utility-pole (postes de concreto y madera)")
        print("     Tamaño aprox: ~200 MB")
        if args.roboflow_key:
            ok = download_roboflow_dataset(
                api_key=args.roboflow_key,
                workspace=ROBOFLOW_WORKSPACE,
                project=ROBOFLOW_PROJECT,
                version=ROBOFLOW_VERSION,
                output_dir=str(output_dir / "utility_poles"),
            )
            results["D2_utility_poles"] = "OK" if ok else "ERROR"
        else:
            print("[D2] OMITIDO: necesitas --roboflow_key")
            print("     Obtén tu API Key en: https://app.roboflow.com/settings/api")
            results["D2_utility_poles"] = "OMITIDO (sin --roboflow_key)"

    # ------------------------------------------------------------------
    # D3 — UAVid Dataset via Kaggle
    # ------------------------------------------------------------------
    if not args.skip_d3:
        print("\n[D3] UAVid Urban Aerial Dataset (Kaggle)")
        print("     Clases: building, tree, clutter/background")
        print("     Tamaño aprox: ~3 GB")
        if check_kaggle_credentials():
            ok = download_kaggle_dataset(
                KAGGLE_UAVID,
                str(output_dir / "uavid"),
            )
            results["D3_uavid"] = "OK" if ok else "ERROR"
        else:
            results["D3_uavid"] = "OMITIDO (sin kaggle.json)"

    # ------------------------------------------------------------------
    # Resumen final
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("  RESULTADO DE DESCARGAS")
    print("=" * 60)
    for name, status in results.items():
        icon = "OK" if status == "OK" else "!!"
        print(f"  [{icon}] {name:<35} : {status}")
    print()

    if all(v == "OK" for v in results.values()):
        print("  Todos los datasets descargados.")
        print("  Siguiente paso:")
        print("  python run_etl_datasets.py --datasets_root datasets/raw")
    else:
        print("  Algunos datasets no se descargaron.")
        print("  Revisa las instrucciones de configuración en el plan_datasets.md")
    print()


if __name__ == "__main__":
    main()
