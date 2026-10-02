import asyncio
import time
import yaml
import cv2
import numpy as np
from mavsdk import System

# Importaciones de los módulos (los crearemos en los siguientes pasos)
from src.capture.video_stream import VideoStream
from src.capture.telemetry import TelemetryTracker
from src.perception.depth_estimator import DepthEstimator
from src.perception.obstacle_detector import ObstacleDetector
from src.perception.person_tracker import PersonTracker
from src.planning.vfh_plus import VFHPlus
from src.execution.drone_controller import DroneController
from src.metrics.logger import MetricsLogger
from src.metrics.profiler import Profiler

async def main():
    # 1. Cargar Configuración
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    print("Iniciando Sistema Integrado: Seguimiento + Evasión (Air 2S)...")

    # 2. Conectar a MAVSDK
    drone = System()
    print(f"Esperando conexión MAVLink en {config['network']['mavsdk_connection']}...")
    await drone.connect(system_address=config["network"]["mavsdk_connection"])

    async for state in drone.core.connection_state():
        if state.is_connected:
            print("¡Conectado al dron vía MAVSDK!")
            break

    # 3. Inicializar Módulos 
    video = VideoStream(config["network"]["video_stream_uri"])
    telemetry = TelemetryTracker(drone)
    await telemetry.start_tasks() 
    
    depth_estimator = DepthEstimator(config["perception"])
    obstacle_detector = ObstacleDetector(config["perception"])
    person_tracker = PersonTracker(config.get("perception", {})) # Nuevo módulo YOLO
    planner = VFHPlus(config["vfh_plus"])
    
    controller = DroneController(drone)
    logger = MetricsLogger(config["logging"])
    profiler = Profiler()

    print("Iniciando Bucle de Control Principal...")
    
    try:
        print("--- Secuencia Automática Iniciada ---")
        print("Armando motores...")
        try:
            await drone.action.arm()
        except Exception as e:
            print(f"Aviso al armar: {e}")
            
        print("Despegando...")
        try:
            await drone.action.takeoff()
        except Exception as e:
            print(f"Aviso de despegue (Común en RosettaDrone): {e}")
            
        print("Esperando 5 segundos para que alcance altitud de seguridad...")
        await asyncio.sleep(5)
        
        await controller.start_offboard()

        while True:
            profiler.start_frame()

            # --- PASO 1: Captura ---
            profiler.start_step("capture")
            frame = video.read_frame()
            drone_state = telemetry.get_state()
            
            if frame is None:
                print("Esperando conexión de Video RTSP de la tablet...")
                await asyncio.sleep(1)
                continue
            
            # --- PASO 2.A: Percepción (Persona/Objetivo) ---
            profiler.start_step("tracking")
            person_angle, person_box = person_tracker.track(frame)
            
            # Si no hay persona, nos quedamos quietos o mantenemos el último ángulo
            if person_angle is None:
                person_angle = 0.0
                target_speed = 0.0
            else:
                target_speed = planner.max_speed

            # --- PASO 2.B: Percepción (Obstáculos 3D) ---
            profiler.start_step("depth")
            depth_map = depth_estimator.estimate(frame)
            angles, polar_histogram = obstacle_detector.to_polar_histogram(depth_map)

            # --- PASO 3: Planificación (Fusión Matemática) ---
            profiler.start_step("planning")
            # VFH+ intentará ir hacia person_angle. Si hay un obstáculo, lo rodeará.
            escape_angle, escape_speed = planner.calculate_escape(
                angles, 
                polar_histogram, 
                drone_state, 
                target_angle=person_angle
            )
            
            # Ajustar velocidad: Si perdimos a la persona, no avanzamos.
            if target_speed == 0.0:
                escape_speed = 0.0

            # --- PASO 4: Ejecución ---
            profiler.start_step("execution")
            
            # --- MODO SEGURO PARA LABORATORIO CERRADO ---
            # En lugar de enviar la velocidad calculada por la IA, enviamos (0.0, 0.0) 
            # para que el dron solo flote en el sitio. 
            # Podrás ver la decisión en la pantalla (HUD) sin riesgo de estrellarlo contra las paredes.
            
            # await controller.send_velocity(escape_angle, escape_speed) # <- Línea original de movimiento
            await controller.send_velocity(0.0, 0.0) # <- Freno de mano activado
            
            # --- PASO 5: Métricas y Logging ---
            profiler.end_frame()
            
            logger.log(
                timestamp=time.time(),
                latency_ms=profiler.get_total_latency(),
                fps=profiler.get_fps(),
                min_distance=obstacle_detector.get_min_distance(),
                evasion_angle=escape_angle,
                telemetry=drone_state
            )

            # --- PASO 6: VISUALIZACIÓN EN VIVO (Para Sustentación) ---
            # 1. Dibujar Bounding Box en la imagen original
            vis_frame = frame.copy()
            if person_box is not None:
                x1, y1, x2, y2 = map(int, person_box)
                cv2.rectangle(vis_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(vis_frame, "Target", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # 2. Colorear el Mapa de Profundidad (MiDaS)
            d_min = depth_map.min()
            d_max = depth_map.max()
            if d_max - d_min > 1e-6:
                depth_norm = (depth_map - d_min) / (d_max - d_min)
            else:
                depth_norm = depth_map
                
            # Aplicar mapa de color (Inferno o Jet resaltan bien la profundidad)
            depth_color = cv2.applyColorMap((depth_norm * 255).astype(np.uint8), cv2.COLORMAP_INFERNO)
            
            # Redimensionar el mapa de profundidad para ponerlo a la derecha del video
            h, w = vis_frame.shape[:2]
            depth_color_resized = cv2.resize(depth_color, (int(w/2), h))
            
            # Unir video RGB + Mapa de Profundidad en una sola ventana
            combined_view = np.hstack((vis_frame, depth_color_resized))
            
            # 3. Textos HUD (Head-Up Display)
            cv2.putText(combined_view, f"FPS: {profiler.get_fps():.1f}", (15, 35), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(combined_view, f"Target Angle: {person_angle:.1f}", (15, 75), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.putText(combined_view, f"Evasion Angle: {escape_angle:.1f}", (15, 115), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255) if abs(escape_angle - person_angle) > 5 else (255, 255, 0), 2)
            
            # Mostrar la ventana
            cv2.imshow("Sistema Integrado - Tesis Air 2S", combined_view)
            
            # Capturar tecla 'q' para salir de emergencia
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("Tecla 'q' presionada. Abortando misión...")
                break

            await asyncio.sleep(0.01) 
            
    except KeyboardInterrupt:
        print("\nDeteniendo sistema por KeyboardInterrupt...")
    finally:
        print("Limpiando recursos...")
        await controller.stop()
        video.stop()
        logger.close()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    # Iniciar el bucle de eventos asíncrono
    asyncio.run(main())
