"""
PROTOTIPO v0.2: Integración Hardware Air 2S + RosettaDrone + MAVSDK
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
from src.perception.person_tracker import PersonTracker
from src.planning.vfh_plus import VFH_Plus
from src.execution.drone_controller import DroneController
from src.metrics.profiler import Profiler
from src.metrics.logger import MetricsLogger

async def main():
    print("=" * 60)
    print("  INICIANDO PROTOTIPO v0.2: Integración Hardware y Vuelo Estacionario")
    print("=" * 60)

    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    drone = System()
    print(f"Esperando conexión MAVLink en {config['network']['mavsdk_connection']}...")
    await drone.connect(system_address=config["network"]["mavsdk_connection"])

    async for state in drone.core.connection_state():
        if state.is_connected:
            print("[v0.2] ¡Conectado al DJI Air 2S vía MAVSDK!")
            break

    video = VideoStream(config["network"]["video_stream_uri"])
    telemetry = Telemetry(drone)
    depth_estimator = DepthEstimator(config["perception"])
    obstacle_detector = ObstacleDetector(config["vfh_plus"])
    person_tracker = PersonTracker(config.get("perception", {}))
    planner = VFH_Plus(config["vfh_plus"])
    controller = DroneController(drone, config["vfh_plus"])
    profiler = Profiler()
    logger = MetricsLogger(config["logging"])

    try:
        print("[v0.2] --- Secuencia Automática Iniciada ---")
        print("[v0.2] Armando motores...")
        try:
            await drone.action.arm()
        except Exception as e:
            print(f"[v0.2 Aviso al armar]: {e}")

        print("[v0.2] Despegando...")
        try:
            await drone.action.takeoff()
        except Exception as e:
            print(f"[v0.2 Aviso despegue (Común en RosettaDrone)]: {e}")

        print("[v0.2] Esperando 5 segundos para estabilización de altitud...")
        await asyncio.sleep(5)

        await controller.start_offboard()

        while True:
            profiler.start_frame()

            # Captura
            profiler.start_step("capture")
            frame = video.read_frame()
            drone_state = telemetry.get_state()

            if frame is None:
                print("[v0.2] Esperando conexión de video RTSP de la tablet...")
                await asyncio.sleep(1)
                continue

            # Percepción
            profiler.start_step("tracking")
            person_angle, person_box = person_tracker.track(frame)
            if person_angle is None:
                person_angle = 0.0

            profiler.start_step("depth")
            depth_map = depth_estimator.estimate(frame)
            angles, polar_histogram = obstacle_detector.to_polar_histogram(depth_map)

            # Planificación VFH+
            profiler.start_step("planning")
            escape_angle, escape_speed = planner.calculate_escape(
                angles, polar_histogram, drone_state, target_angle=person_angle
            )

            # Ejecución con Freno de Mano para Seguridad en Laboratorio
            profiler.start_step("execution")
            await controller.send_velocity(0.0, 0.0) # Modo seguro estacionario

            profiler.end_frame()
            logger.log(
                timestamp=time.time(),
                estado_fsm="ESTACIONARIO_SEGURO",
                latency_ms=profiler.get_total_latency(),
                fps=profiler.get_fps(),
                min_distance=obstacle_detector.get_min_distance(),
                target_angle=person_angle,
                evasion_angle=escape_angle,
                telemetry=drone_state
            )

            # Visualización lado a lado (RGB + Mapa de Profundidad Inferno)
            vis_frame = frame.copy()
            if person_box is not None:
                x1, y1, x2, y2 = map(int, person_box)
                cv2.rectangle(vis_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(vis_frame, "Target", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            d_norm = cv2.normalize(depth_map, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
            depth_color = cv2.applyColorMap(d_norm, cv2.COLORMAP_INFERNO)
            h, w = vis_frame.shape[:2]
            combined = np.hstack((vis_frame, cv2.resize(depth_color, (int(w/2), h))))

            cv2.putText(combined, f"FPS: {profiler.get_fps():.1f}", (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(combined, f"Target Angle: {person_angle:.1f}", (15, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.putText(combined, f"Evasion Angle: {escape_angle:.1f}", (15, 115), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            cv2.imshow("Prototipo v0.2 - Integracion Hardware Air 2S", combined)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

            await asyncio.sleep(0.01)

    except Exception as e:
        print(f"[v0.2 Error] {e}")
    finally:
        print("[v0.2] Aterrizando y liberando recursos...")
        await controller.stop_offboard()
        video.release()
        logger.close()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    asyncio.run(main())
