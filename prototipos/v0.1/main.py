"""
PROTOTIPO v0.1: Pipeline Modular de Navegación Reactiva Sense-Plan-Act
Proyecto de Tesis: Evasión Autónoma de Postes y Árboles
"""
import asyncio
import time
import yaml
import cv2
import numpy as np

from mavsdk import System
from src.capture.video_stream import VideoStream
from src.capture.telemetry import Telemetry
from src.perception.depth_estimator import DepthEstimator
from src.perception.obstacle_detector import ObstacleDetector
from src.planning.vfh_plus import VFH_Plus
from src.execution.drone_controller import DroneController
from src.metrics.profiler import Profiler
from src.metrics.logger import MetricsLogger

async def main():
    print("=" * 60)
    print("  INICIANDO PROTOTIPO v0.1: Pipeline Modular Sense-Plan-Act")
    print("=" * 60)

    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    # 1. Conexión con el Dron
    drone = System()
    print(f"Esperando conexión MAVLink en {config['network']['mavsdk_connection']}...")
    await drone.connect(system_address=config["network"]["mavsdk_connection"])

    async for state in drone.core.connection_state():
        if state.is_connected:
            print("[v0.1] ¡Conectado al sistema de vuelo!")
            break

    # 2. Inicializar Módulos
    video = VideoStream(config["network"]["video_stream_uri"])
    telemetry = Telemetry(drone)
    depth_estimator = DepthEstimator(config["perception"])
    obstacle_detector = ObstacleDetector(config["vfh_plus"])
    planner = VFH_Plus(config["vfh_plus"])
    controller = DroneController(drone, config["vfh_plus"])
    profiler = Profiler()
    logger = MetricsLogger(config["logging"])

    print("[v0.1] Iniciando Bucle de Control Reactivo...")
    try:
        await controller.start_offboard()

        while True:
            profiler.start_frame()

            # --- SENSE: Captura ---
            profiler.start_step("capture")
            frame = video.read_frame()
            drone_state = telemetry.get_state()

            if frame is None:
                await asyncio.sleep(0.01)
                continue

            # --- PERCEIVE: Estimación de Profundidad ---
            profiler.start_step("depth")
            depth_map = depth_estimator.estimate(frame)
            angles, polar_histogram = obstacle_detector.to_polar_histogram(depth_map)

            # --- PLAN: Algoritmo VFH+ ---
            profiler.start_step("planning")
            escape_angle, escape_speed = planner.calculate_escape(
                angles, 
                polar_histogram, 
                drone_state, 
                target_angle=0.0 # En v0.1 se asumía avance frontal directo
            )

            # --- ACT: Ejecución Cinemática ---
            profiler.start_step("execution")
            await controller.send_velocity(escape_angle, escape_speed)

            # --- METRICS: Registro de Desempeño ---
            profiler.end_frame()
            logger.log(
                timestamp=time.time(),
                estado_fsm="VFH_REACTIVO",
                latency_ms=profiler.get_total_latency(),
                fps=profiler.get_fps(),
                min_distance=obstacle_detector.get_min_distance(),
                target_angle=0.0,
                evasion_angle=escape_angle,
                telemetry=drone_state
            )

            # Visualización básica v0.1
            cv2.imshow("Prototipo v0.1 - Camara", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

            await asyncio.sleep(0.01)

    except Exception as e:
        print(f"[v0.1 Error] {e}")
    finally:
        print("[v0.1] Finalizando ejecución y liberando recursos...")
        await controller.stop_offboard()
        video.release()
        logger.close()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    asyncio.run(main())
