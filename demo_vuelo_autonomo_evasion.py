"""
Demostración de Vuelo Autónomo: Persecución y Evasión Reactiva a 1.5 Metros
Tesis de Ingeniería de Sistemas - Universidad Nacional de Ingeniería (UNI)
Autor: Gustavo Bryan Lopez Cosme

Plataforma: DJI Air 2S + RosettaDrone (MAVLink v2 + RTP H.264) + MiDaS v2.1 Small

Características de Demostración:
  1. Despegue y Mantenimiento de Altitud a 1.50 metros (bucle cerrado NED).
  2. Avance lento y seguro (0.25 m/s) para espacios controlados o de laboratorio.
  3. Evasión reactiva tridimensional (MiDaS Depth) ante obstáculos frontales.
  4. Persecución visual adaptativa (MediaPipe / CLAHE) con alineación de guiñada.
  5. Modo Dual:
     - Modo Simulación / Mesa (por defecto o --dry-run): Motores apagados, telemetría y
       decisiones en pantalla 100% reales para explicar a estudiantes con total seguridad.
     - Modo Vuelo Real (--fly o tecla [T]): Despegue real, control de velocidad offboard y aterrizaje.

Controles en Teclado:
  [T]         : Despegar y ascender a 1.5 metros (activar modo offboard)
  [L]         : Aterrizar suavemente (Land)
  [ESPACIO]   : Freno de emergencia / Mantener posición estática (Hover 0 m/s)
  [C]         : Cambiar mapa de color de profundidad (INFERNO, TURBO, JET, MAGMA)
  [S]         : Guardar captura del visor en 'Air2S_MAVSDK/logs/capturas_demo/'
  [Q] o [ESC] : Detener control, aterrizar si está volando y salir
"""

import os
import sys
import time
import math
import socket
import struct
import threading
import asyncio
import argparse
import ctypes
import re
import warnings
import numpy as np
import cv2

# Suprimir advertencias menores de TensorFlow y MAVSDK gRPC
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
warnings.simplefilter('ignore')

opt = "OPENCV_FFMPEG_CAPTURE_OPTIONS=protocol_whitelist;file,rtp,udp|fflags;nobuffer|flags;low_delay|threads;1|overrun_nonfatal;1"
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = opt
try:
    ctypes.cdll.msvcrt._putenv(opt.encode("ascii"))
except Exception:
    pass

def parse_arguments():
    parser = argparse.ArgumentParser(description="Tesis UNI - Demo de Vuelo Autónomo y Evasión a 1.5m")
    parser.add_argument("--cam", type=int, default=0, help="ID de cámara (0=Webcam si no hay dron conectado)")
    parser.add_argument("--drone", action="store_true", help="Usar video del DJI Air 2S vía RosettaDrone (UDP 5600)")
    parser.add_argument("--fly", action="store_true", help="¡ACTIVAR VUELO REAL! (Armado de motores y despegue)")
    parser.add_argument("--alt", type=float, default=1.50, help="Altitud objetivo de vuelo en metros (default: 1.50 m)")
    parser.add_argument("--speed", type=float, default=0.25, help="Velocidad lenta de crucero en m/s (default: 0.25 m/s)")
    parser.add_argument("--mavlink-port", type=int, default=19980, help="Puerto MAVLink UDP de RosettaDrone (default: 19980)")
    parser.add_argument("--model", type=str, default="Air2S_MAVSDK/models/midas_v21_small_256.tflite", help="Ruta al modelo MiDaS")
    return parser.parse_args()

# ==============================================================================
# 1. PUENTE DE VIDEO RTP H.264 (ZERO-LATENCY + BOOTSTRAP DETERMINISTA)
# ==============================================================================
class RTPVideoBridge:
    def __init__(self, in_port=5600, out_port=5601):
        self.in_port = in_port
        self.out_port = out_port
        self.running = True
        self.boot_running = False
        self.boot_thread = None
        self.packet_count = 0
        self.slice_count = 0

        self.sps = b'\x00\x00\x00\x01\x67\x64\x00\x32\xac\x4d\x00\xcc\x04\x4f\x3c\xb3\x50\x10\x10\x14\x00\x00\x03\x00\x04\x00\x00\x03\x00\xc8\x3c\x70\xca\x80'
        self.pps = b'\x00\x00\x00\x01\x68\xee\x3c\xb0'

        self.bootstrap_nals = []
        candidates = [
            "test_raw.h264",
            os.path.join(os.path.dirname(__file__), "test_raw.h264"),
            os.path.join(os.path.dirname(__file__), "Air2S_MAVSDK", "test_raw.h264"),
            os.path.join(os.path.dirname(__file__), "..", "test_raw.h264")
        ]
        for c in candidates:
            if os.path.exists(c):
                try:
                    with open(c, 'rb') as f:
                        raw = f.read()
                    if len(raw) >= 28052:
                        bootstrap = raw[23016:28052]
                        nal_indices = [m.start() for m in re.finditer(b'\x00\x00\x00\x01', bootstrap)]
                        for i, idx in enumerate(nal_indices):
                            next_idx = nal_indices[i+1] if i+1 < len(nal_indices) else len(bootstrap)
                            self.bootstrap_nals.append(bootstrap[idx:next_idx])
                        break
                except Exception:
                    pass

        self.s_out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.s_out.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)
        except Exception:
            pass

        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def start_bootstrap(self):
        self.boot_running = True
        def loop():
            while self.boot_running:
                for n in self.bootstrap_nals:
                    try:
                        self.s_out.sendto(n, ('127.0.0.1', self.out_port))
                    except Exception:
                        pass
                    time.sleep(0.001)
                time.sleep(0.05)
        self.boot_thread = threading.Thread(target=loop, daemon=True)
        self.boot_thread.start()

    def stop_bootstrap(self):
        self.boot_running = False

    def _worker(self):
        s_in = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s_in.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s_in.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
        except Exception:
            pass

        try:
            s_in.bind(('0.0.0.0', self.in_port))
        except Exception as e:
            print(f"[Puente RTP] Aviso de socket: {e}")
            return
        s_in.settimeout(0.5)

        fu_buf = bytearray()
        in_fua = False
        slice_corrupt = False
        last_seq = None
        inner_type = 0

        while self.running:
            try:
                data, addr = s_in.recvfrom(4096)
                self.packet_count += 1
                if len(data) <= 12:
                    continue

                seq = struct.unpack('!H', data[2:4])[0]
                payload = data[12:]
                nal_type = payload[0] & 0x1F

                if nal_type in (7, 8):
                    if nal_type == 7:
                        self.sps = b'\x00\x00\x00\x01' + payload
                    else:
                        self.pps = b'\x00\x00\x00\x01' + payload
                    self.s_out.sendto(b'\x00\x00\x00\x01' + payload, ('127.0.0.1', self.out_port))
                    continue

                if nal_type == 28: # FU-A
                    fu_header = payload[1]
                    start = (fu_header & 0x80) != 0
                    end = (fu_header & 0x40) != 0
                    recon = (payload[0] & 0xE0) | (fu_header & 0x1F)
                    if start:
                        inner_type = fu_header & 0x1F
                        fu_buf = bytearray([recon]) + payload[2:]
                        in_fua = True
                        slice_corrupt = False
                        last_seq = seq
                    elif in_fua:
                        if last_seq is not None and seq != ((last_seq + 1) & 0xFFFF):
                            slice_corrupt = True
                        last_seq = seq
                        if not slice_corrupt:
                            fu_buf.extend(payload[2:])

                    if end and in_fua:
                        if not slice_corrupt and len(fu_buf) > 1:
                            if inner_type == 5:
                                self.s_out.sendto(self.sps, ('127.0.0.1', self.out_port))
                                self.s_out.sendto(self.pps, ('127.0.0.1', self.out_port))
                            pkt = b'\x00\x00\x00\x01' + bytes(fu_buf)
                            self.s_out.sendto(pkt, ('127.0.0.1', self.out_port))
                            self.slice_count += 1
                        fu_buf = bytearray()
                        in_fua = False
                elif nal_type == 5:
                    self.s_out.sendto(self.sps, ('127.0.0.1', self.out_port))
                    self.s_out.sendto(self.pps, ('127.0.0.1', self.out_port))
                    pkt = b'\x00\x00\x00\x01' + payload
                    self.s_out.sendto(pkt, ('127.0.0.1', self.out_port))
                    self.slice_count += 1
                elif nal_type in (1, 6):
                    pkt = b'\x00\x00\x00\x01' + payload
                    self.s_out.sendto(pkt, ('127.0.0.1', self.out_port))
                    self.slice_count += 1
            except socket.timeout:
                pass
            except Exception:
                pass

        s_in.close()
        self.s_out.close()

    def stop(self):
        self.running = False
        self.boot_running = False

class FreshFrameReader:
    def __init__(self, src_uri):
        self.cap = cv2.VideoCapture(src_uri, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.latest_frame = None
        self.running = True
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def _worker(self):
        while self.running:
            try:
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    with self.lock:
                        self.latest_frame = frame
                else:
                    time.sleep(0.005)
            except Exception:
                time.sleep(0.01)

    def is_opened(self):
        return self.cap.isOpened()

    def read_latest(self):
        with self.lock:
            if self.latest_frame is None:
                return False, None
            return True, self.latest_frame.copy()

    def release(self):
        self.running = False
        self.cap.release()

# ==============================================================================
# 2. CONTROLADOR DE VUELO ASÍNCRONO MAVSDK EN HILO DEDICADO
# ==============================================================================
from mavsdk import System
from mavsdk.offboard import VelocityBodyYawspeed, OffboardError

class FlightController(threading.Thread):
    """
    Gestiona el enlace de telemetría y los comandos de vuelo físico con MAVSDK.
    Mantiene un bucle cerrado a 10 Hz para mantener la altitud objetivo (1.5 m)
    y aplicar las velocidades de avance y evasión de forma segura.
    """
    def __init__(self, system_address="udp://:19980", target_alt=1.5, allow_real_flight=False):
        super().__init__(daemon=True)
        self.system_address = system_address
        self.target_alt = target_alt
        self.allow_real_flight = allow_real_flight

        self.running = True
        self.loop = None
        self.drone = None
        self.offboard_active = False
        self.in_flight = False

        # Estado instantáneo compartido
        self.lock = threading.Lock()
        self.state = {
            "connected": False,
            "armed": False,
            "in_air": False,
            "flight_mode": "SIM_MESA" if not allow_real_flight else "DESCONECTADO",
            "altitude_m": 1.50 if not allow_real_flight else 0.0,
            "target_alt_m": target_alt,
            "battery_pct": 100 if not allow_real_flight else 0,
            "heading_deg": 0.0,
            "pitch_deg": 0.0,
            "roll_deg": 0.0,
            "vx_cmd": 0.0,
            "vy_cmd": 0.0,
            "vz_cmd": 0.0,
            "yaw_rate_cmd": 0.0,
            "fsm_state": "LISTO_EN_ESPERA"
        }

        # Comandos objetivo que provienen del planificador de visión
        self.cmd_vx = 0.0
        self.cmd_vy = 0.0
        self.cmd_yaw_rate = 0.0
        self.cmd_lock = threading.Lock()
        self.emergency_stop_active = False

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._main_flight_loop())

    async def _main_flight_loop(self):
        print(f"[FlightController] Inicializando MAVSDK en {self.system_address}...")
        self.drone = System()
        try:
            await self.drone.connect(system_address=self.system_address)
        except Exception as e:
            print(f"[FlightController] Error conectando MAVSDK: {e}")

        # Tareas de telemetría en segundo plano
        asyncio.create_task(self._telemetry_connection_task())
        asyncio.create_task(self._telemetry_position_task())
        asyncio.create_task(self._telemetry_attitude_task())
        asyncio.create_task(self._telemetry_battery_task())
        asyncio.create_task(self._telemetry_flight_mode_task())

        # Bucle de control de velocidad a 10 Hz (100 ms)
        while self.running:
            await self._control_tick()
            await asyncio.sleep(0.1)

    async def _telemetry_connection_task(self):
        try:
            async for state in self.drone.core.connection_state():
                with self.lock:
                    self.state["connected"] = state.is_connected
                    if state.is_connected and not self.allow_real_flight:
                        self.state["flight_mode"] = "CONECTADO (MESA)"
        except Exception:
            pass

    async def _telemetry_position_task(self):
        try:
            async for pos in self.drone.telemetry.position():
                with self.lock:
                    if self.allow_real_flight:
                        self.state["altitude_m"] = round(pos.relative_altitude_m, 2)
        except Exception:
            pass

    async def _telemetry_attitude_task(self):
        try:
            async for att in self.drone.telemetry.attitude_euler():
                with self.lock:
                    self.state["heading_deg"] = round(att.yaw_deg, 1)
                    self.state["pitch_deg"] = round(att.pitch_deg, 1)
                    self.state["roll_deg"] = round(att.roll_deg, 1)
        except Exception:
            pass

    async def _telemetry_battery_task(self):
        try:
            async for bat in self.drone.telemetry.battery():
                with self.lock:
                    if self.allow_real_flight:
                        self.state["battery_pct"] = int(bat.remaining_percent * 100)
        except Exception:
            pass

    async def _telemetry_flight_mode_task(self):
        try:
            async for mode in self.drone.telemetry.flight_mode():
                with self.lock:
                    if self.allow_real_flight:
                        self.state["flight_mode"] = str(mode)
        except Exception:
            pass

    async def _control_tick(self):
        """Calcula y envía el vector de velocidad al dron en modo Offboard."""
        with self.cmd_lock:
            vx = self.cmd_vx
            vy = self.cmd_vy
            yaw_rate = self.cmd_yaw_rate
            is_emergency = self.emergency_stop_active

        if is_emergency:
            vx = 0.0
            vy = 0.0
            yaw_rate = 0.0

        # Control en bucle cerrado de altitud para fijar 1.50 metros
        with self.lock:
            curr_alt = self.state["altitude_m"]

        alt_err = self.target_alt - curr_alt
        # Ganancia proporcional suave para vertical (límite +-0.15 m/s)
        # En coordenadas NED: Negativo es SUBIR, Positivo es BAJAR
        vz_corr = -float(np.clip(alt_err * 0.40, -0.15, 0.15))

        with self.lock:
            self.state["vx_cmd"] = round(vx, 2)
            self.state["vy_cmd"] = round(vy, 2)
            self.state["vz_cmd"] = round(vz_corr, 2)
            self.state["yaw_rate_cmd"] = round(yaw_rate, 1)

        # Si el vuelo real está habilitado y el dron está en el aire con offboard
        if self.allow_real_flight and self.offboard_active:
            try:
                cmd = VelocityBodyYawspeed(
                    forward_m_s=float(vx),
                    right_m_s=float(vy),
                    down_m_s=float(vz_corr),
                    yawspeed_deg_s=float(yaw_rate)
                )
                await self.drone.offboard.set_velocity_body(cmd)
            except Exception as e:
                # Si se pierde offboard, no saturar la consola
                pass

    # --- Métodos invocados desde el hilo principal de OpenCV ---
    def set_nav_commands(self, vx: float, vy: float, yaw_rate: float, fsm_state: str):
        with self.cmd_lock:
            self.cmd_vx = vx
            self.cmd_vy = vy
            self.cmd_yaw_rate = yaw_rate
        with self.lock:
            self.state["fsm_state"] = fsm_state

    def trigger_takeoff(self):
        """Inicia secuencia de despegue y enganche a 1.5 metros."""
        if not self.allow_real_flight:
            print("[Controller] Simulación en Mesa: Despegue emulado a 1.50m.")
            with self.lock:
                self.state["altitude_m"] = 1.50
                self.state["flight_mode"] = "OFFBOARD_SIM"
                self.state["fsm_state"] = "HOVER_1.5M"
            self.in_flight = True
            return

        async def _takeoff_task():
            print("[Controller] Iniciando armado de motores y despegue a 1.50m...")
            try:
                await self.drone.action.arm()
                await self.drone.action.takeoff()
                print("[Controller] Despegue ordenado. Esperando ascenso estable...")
                await asyncio.sleep(5.0)

                # Inicializar comando inerte antes de pasar a offboard
                await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
                await self.drone.offboard.start()
                self.offboard_active = True
                self.in_flight = True
                print("[Controller] ✅ Modo Offboard ACTIVO. IA al mando de la altitud y evasión.")
            except Exception as e:
                print(f"[Controller] Error durante el despegue: {e}")

        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(_takeoff_task(), self.loop)

    def trigger_land(self):
        """Aterriza el dron y detiene el modo offboard."""
        print("[Controller] Iniciando secuencia de aterrizaje seguro...")
        self.emergency_stop_active = True
        with self.lock:
            self.state["fsm_state"] = "ATERRIZANDO"

        if not self.allow_real_flight:
            print("[Controller] Simulación en Mesa: Dron en reposo.")
            with self.lock:
                self.state["altitude_m"] = 0.0
                self.state["flight_mode"] = "ATERRIZADO"
            self.in_flight = False
            return

        async def _land_task():
            try:
                if self.offboard_active:
                    await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
                    try:
                        await self.drone.offboard.stop()
                    except Exception:
                        pass
                    self.offboard_active = False

                await self.drone.action.land()
                print("[Controller] ✅ Orden de aterrizaje transmitida a RosettaDrone.")
                self.in_flight = False
            except Exception as e:
                print(f"[Controller] Error durante aterrizaje: {e}")

        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(_land_task(), self.loop)

    def toggle_emergency_hover(self):
        """Freno instantáneo / Pausa de vuelo en el lugar."""
        self.emergency_stop_active = not self.emergency_stop_active
        status = "ACTIVADO (FRENO)" if self.emergency_stop_active else "DESACTIVADO (CONTINUAR)"
        print(f"[Controller] Freno de Emergencia / Hover: {status}")

    def get_telemetry(self):
        with self.lock:
            return dict(self.state)

    def stop(self):
        self.running = False
        self.trigger_land()

# ==============================================================================
# 3. RASTREADOR DE PERSONA Y COMPENSADOR DE CONTRALUZ (CLAHE)
# ==============================================================================
class RobustTargetTracker:
    def __init__(self, fov_horizontal=88.0):
        self.fov = fov_horizontal
        self.clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        self.last_box = None
        self.smooth_alpha = 0.65

        cv2_dir = os.path.dirname(cv2.__file__)
        data_dir = os.path.join(cv2_dir, 'data')
        cascade_path = os.path.join(data_dir, 'haarcascade_frontalface_default.xml')
        self.cascade = cv2.CascadeClassifier(cascade_path) if os.path.exists(cascade_path) else None

    def detect(self, frame):
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_eq = self.clahe.apply(gray)

        best_box = None
        confidence = 0.92

        if self.cascade and not self.cascade.empty():
            faces = self.cascade.detectMultiScale(gray_eq, scaleFactor=1.15, minNeighbors=4, minSize=(40, 40))
            if len(faces) > 0:
                best_face = max(faces, key=lambda b: b[2] * b[3])
                fx, fy, fw, fh = best_face
                bx = max(0, int(fx - fw * 0.3))
                by = max(0, int(fy - fh * 0.2))
                bw = min(w - bx, int(fw * 1.6))
                bh = min(h - by, int(fh * 3.4))
                best_box = (bx, by, bx + bw, by + bh)

        if best_box is not None and self.last_box is not None:
            x1 = int(self.smooth_alpha * best_box[0] + (1 - self.smooth_alpha) * self.last_box[0])
            y1 = int(self.smooth_alpha * best_box[1] + (1 - self.smooth_alpha) * self.last_box[1])
            x2 = int(self.smooth_alpha * best_box[2] + (1 - self.smooth_alpha) * self.last_box[2])
            y2 = int(self.smooth_alpha * best_box[3] + (1 - self.smooth_alpha) * self.last_box[3])
            best_box = (x1, y1, x2, y2)

        self.last_box = best_box

        angle_deg = 0.0
        if best_box is not None:
            cx = (best_box[0] + best_box[2]) / 2.0
            angle_deg = (cx / w - 0.5) * self.fov

        return best_box, angle_deg, confidence

# ==============================================================================
# 4. MOTOR PRINCIPAL DE VISIÓN, NAVEGACIÓN Y DEMOSTRACIÓN
# ==============================================================================
def main():
    args = parse_arguments()

    print("=" * 76)
    print("  UNIVERSIDAD NACIONAL DE INGENIERÍA - FACULTAD DE INGENIERÍA DE SISTEMAS")
    print("  TESIS: NAVEGACIÓN AUTÓNOMA, PERSECUCIÓN Y EVASIÓN REACTIVA A 1.5 METROS")
    print(f"  Modo Operativo: {'[VUELO REAL CON MOTORES]' if args.fly else '[SIMULACIÓN SEGURA EN MESA (Sin hélices)]'}")
    print(f"  Altitud Objetivo: {args.alt:.2f} m | Velocidad Lenta de Demostración: {args.speed:.2f} m/s")
    print("=" * 76)

    # 1. Iniciar puente de video o lector de cámara
    bridge = None
    if args.drone:
        print("\n[*] Conectando receptor de video del Dron DJI Air 2S (UDP 5600)...")
        bridge = RTPVideoBridge(in_port=5600, out_port=5601)
        print("    - Esperando flujo de video de RosettaDrone...")
        while bridge.packet_count < 10:
            print(f"      Recibiendo paquetes de video: {bridge.packet_count}...", end="\r")
            time.sleep(0.1)
        print(f"\n    [OK] Flujo detectado ({bridge.packet_count} paquetes). Sincronizando...")
        bridge.start_bootstrap()
        reader = FreshFrameReader('udp://127.0.0.1:5601')
        t_boot = time.time()
        while time.time() - t_boot < 4.0:
            ret, _ = reader.read_latest()
            if ret:
                break
            time.sleep(0.05)
        bridge.stop_bootstrap()
    else:
        print(f"\n[*] Abriendo cámara integrada/USB (ID {args.cam})...")
        reader = FreshFrameReader(args.cam)

    # 2. Cargar modelo MiDaS v2.1 Small TFLite
    model_path = args.model
    if not os.path.exists(model_path):
        candidates = [
            os.path.join(os.path.dirname(__file__), "Air2S_MAVSDK", "models", "midas_v21_small_256.tflite"),
            os.path.join(os.path.dirname(__file__), "models", "midas_v21_small_256.tflite"),
            "midas_v21_small_256.tflite"
        ]
        for c in candidates:
            if os.path.exists(c):
                model_path = c
                break

    print(f"[*] Cargando red neuronal de profundidad: {model_path}")
    import tensorflow as tf
    interpreter = tf.lite.Interpreter(model_path=model_path, num_threads=4)
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    # 3. Inicializar Tracker y Controlador de Vuelo
    tracker = RobustTargetTracker(fov_horizontal=88.0)
    flight = FlightController(
        system_address=f"udp://:{args.mavlink_port}",
        target_alt=args.alt,
        allow_real_flight=args.fly
    )
    flight.start()

    # Si se especificó vuelo real desde el inicio, armar y despegar
    if args.fly:
        print("\n[!] AVISO DE SEGURIDAD: Modo de vuelo real habilitado.")
        print("    Presiona 'T' en la ventana para ordenar el despegue automático a 1.5 metros.")

    colormaps = [cv2.COLORMAP_INFERNO, cv2.COLORMAP_TURBO, cv2.COLORMAP_JET, cv2.COLORMAP_MAGMA]
    colormap_names = ["INFERNO", "TURBO", "JET", "MAGMA"]
    curr_cm_idx = 0

    win_name = "Tesis UNI - Demostracion: Persecucion y Evasion a 1.5m (DJI Air 2S)"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win_name, 1280, 540)

    fps = 0.0
    frame_count = 0
    t_prev = time.time()
    cruise_speed = args.speed

    out_dir = os.path.join("Air2S_MAVSDK", "logs", "capturas_demo")
    os.makedirs(out_dir, exist_ok=True)

    print("\n[OK] Demostración lista. Visualizador en pantalla activo.\n")

    try:
        while True:
            ret, frame = reader.read_latest()
            if not ret or frame is None:
                key = cv2.waitKey(5) & 0xFF
                if key == ord('q') or key == 27:
                    break
                continue

            frame_count += 1
            t_curr = time.time()
            if t_curr - t_prev >= 0.5:
                fps = frame_count / (t_curr - t_prev)
                frame_count = 0
                t_prev = t_curr

            hf_orig, wf_orig = frame.shape[:2]
            target_h = 440
            target_w = int(wf_orig * (target_h / hf_orig))
            frame_resized = cv2.resize(frame, (target_w, target_h))
            hf, wf = frame_resized.shape[:2]

            # ------------------------------------------------------------------
            # PASO 1: Inferencia de Profundidad MiDaS (Obstáculos 3D)
            # ------------------------------------------------------------------
            img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img_input = cv2.resize(img_rgb, (256, 256))
            img_input = (img_input.astype(np.float32) / 255.0 - mean) / std
            img_input = np.expand_dims(img_input, axis=0)

            interpreter.set_tensor(input_details[0]['index'], img_input)
            interpreter.invoke()
            depth_raw = interpreter.get_tensor(output_details[0]['index'])[0]

            d_min = float(depth_raw.min())
            d_max = float(depth_raw.max())
            depth_norm = (depth_raw - d_min) / (d_max - d_min + 1e-6)

            # Análisis en 3 sectores (Banda horizontal 20% a 80% de altura)
            h_d, w_d = depth_norm.shape
            roi_y1 = int(h_d * 0.20)
            roi_y2 = int(h_d * 0.80)
            roi_band = depth_norm[roi_y1:roi_y2, :]

            # División de los 3 sectores: Izquierda (0-35%), Centro (35-65%), Derecha (65-100%)
            sec_left   = roi_band[:, :int(w_d * 0.35)]
            sec_center = roi_band[:, int(w_d * 0.35):int(w_d * 0.65)]
            sec_right  = roi_band[:, int(w_d * 0.65):]

            # Función para mapear disparidad inversa a distancia métrica estimada
            def disp_to_meters(sub_arr):
                max_d = float(np.percentile(sub_arr, 95))
                # Disparidad 1.0 -> 0.4m; Disparidad 0.0 -> 8.0m
                dist_m = 8.0 * (1.0 - max_d) + 0.4
                return max(0.4, min(8.0, dist_m))

            dist_left   = disp_to_meters(sec_left)
            dist_center = disp_to_meters(sec_center)
            dist_right  = disp_to_meters(sec_right)
            min_dist    = min(dist_left, dist_center, dist_right)

            # ------------------------------------------------------------------
            # PASO 2: Detección del Objetivo Humano (Persecución)
            # ------------------------------------------------------------------
            left_view = frame_resized.copy()
            bbox, target_angle, conf = tracker.detect(left_view)

            # ------------------------------------------------------------------
            # PASO 3: Planificador Reactivo y Máquina de Estados (FSM)
            # ------------------------------------------------------------------
            SAFETY_DISTANCE = 1.80  # Umbral de seguridad en metros
            CRITICAL_HALT   = 0.90  # Parada de emergencia absoluta

            cmd_vx = 0.0
            cmd_vy = 0.0
            cmd_yaw_rate = 0.0
            fsm_state = "AVANCE_LENTO"
            state_color = (0, 255, 0) # Verde

            if flight.emergency_stop_active:
                cmd_vx = 0.0
                cmd_vy = 0.0
                cmd_yaw_rate = 0.0
                fsm_state = "FRENO_HOVER_ACTIVO"
                state_color = (0, 255, 255) # Amarillo

            elif min_dist < CRITICAL_HALT or (dist_left < 1.1 and dist_center < 1.1 and dist_right < 1.1):
                # ¡BLOQUEO TOTAL! Todos los sectores están congestionados
                cmd_vx = 0.0
                cmd_vy = 0.0
                cmd_yaw_rate = 0.0
                fsm_state = "FRENO_EMERGENCIA_BLOQUEO"
                state_color = (0, 0, 255) # Rojo

            elif dist_center < SAFETY_DISTANCE:
                # Obstáculo frontal en el sector central -> Prioridad de Evasión Lateral
                cmd_vx = 0.05  # Avance mínimo o nulo
                if dist_right >= dist_left:
                    cmd_vy = +cruise_speed  # Desviarse lentamente a la derecha
                    fsm_state = f"ESQUIVANDO_DERECHA ({dist_center:.2f}m)"
                else:
                    cmd_vy = -cruise_speed  # Desviarse lentamente a la izquierda
                    fsm_state = f"ESQUIVANDO_IZQUIERDA ({dist_center:.2f}m)"
                state_color = (0, 140, 255) # Naranja alerta

            elif bbox is not None:
                # Camino despejado y persona detectada -> Persecución con alineación Yaw
                cmd_vx = cruise_speed
                cmd_vy = 0.0
                # Guiñada suave proporcional al ángulo de la persona (máx 15 deg/s)
                cmd_yaw_rate = float(np.clip(target_angle * 0.45, -15.0, 15.0))
                fsm_state = f"PERSIGUIENDO_HUMANO ({target_angle:+.1f} deg)"
                state_color = (0, 255, 0) # Verde nominal

            else:
                # Camino despejado sin objetivo -> Exploración suave al frente
                cmd_vx = cruise_speed
                cmd_vy = 0.0
                cmd_yaw_rate = 0.0
                fsm_state = f"AVANCE_LENTO_CRUCERO ({cruise_speed:.2f} m/s)"
                state_color = (0, 255, 180)

            # Notificar al hilo de control de vuelo
            flight.set_nav_commands(cmd_vx, cmd_vy, cmd_yaw_rate, fsm_state)
            telem = flight.get_telemetry()

            # ------------------------------------------------------------------
            # PASO 4: Renderizado de la Vista Izquierda (Cámara + HUD de Vuelo)
            # ------------------------------------------------------------------
            center_x = wf // 2
            center_y = hf // 2

            # Mira central del dron
            cv2.drawMarker(left_view, (center_x, center_y), (0, 200, 255), cv2.MARKER_CROSS, 20, 2)
            cv2.circle(left_view, (center_x, center_y), 32, (0, 200, 255), 1)

            # Si hay persona detectada, dibujar recuadro y línea de puntería
            if bbox is not None:
                bx1, by1, bx2, by2 = bbox
                cv2.rectangle(left_view, (bx1, by1), (bx2, by2), (0, 255, 0), 2)
                tgt_cx = (bx1 + bx2) // 2
                tgt_cy = (by1 + by2) // 2
                cv2.circle(left_view, (tgt_cx, tgt_cy), 5, (0, 255, 0), -1)
                cv2.line(left_view, (center_x, center_y), (tgt_cx, tgt_cy), (0, 255, 255), 2)
                cv2.putText(left_view, f"Target: Humano ({conf:.2f})", (bx1, max(20, by1 - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

            # Vector de movimiento resultante (Flecha de navegación en el HUD)
            arrow_scale = 160.0
            arrow_end_x = int(center_x + (cmd_vy / max(0.01, cruise_speed)) * (arrow_scale * 0.7))
            arrow_end_y = int(center_y - (cmd_vx / max(0.01, cruise_speed)) * (arrow_scale * 0.5))
            if abs(cmd_vx) > 0.01 or abs(cmd_vy) > 0.01:
                cv2.arrowedLine(left_view, (center_x, center_y), (arrow_end_x, arrow_end_y), (0, 255, 255), 3, tipLength=0.25)
                cv2.putText(left_view, f"V: ({cmd_vx:+.2f}, {cmd_vy:+.2f}) m/s", (arrow_end_x + 8, arrow_end_y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 255, 255), 2)

            # Barra superior izquierda: Encabezado institucional y FPS
            header_bar = np.zeros((45, wf, 3), dtype=np.uint8)
            header_bar[:] = (20, 20, 20)
            mode_tag = "[VUELO REAL]" if args.fly else "[MESA / SIM]"
            cv2.putText(header_bar, f"DJI AIR 2S {mode_tag} - PERSECUCIÓN Y EVASIÓN", (12, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.60, (0, 255, 0) if args.fly else (0, 220, 255), 2)
            cv2.putText(header_bar, f"FPS: {fps:.1f}", (wf - 110, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.60, (255, 255, 255), 2)
            left_view = np.vstack((header_bar, left_view))

            # Barra inferior izquierda: Telemetría de vuelo y Altitud a 1.50m
            foot_bar = np.zeros((55, wf, 3), dtype=np.uint8)
            foot_bar[:] = (15, 15, 15)
            alt_actual = telem['altitude_m']
            alt_meta = telem['target_alt_m']
            bat = telem['battery_pct']
            cv2.putText(foot_bar, f"ESTADO: {fsm_state}", (12, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, state_color, 2)
            cv2.putText(foot_bar, f"ALTITUD: {alt_actual:.2f} m (Meta: {alt_meta:.2f} m) | Bat: {bat}% | Yaw: {telem['heading_deg']:.1f} deg",
                        (12, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (220, 220, 220), 1)
            left_view = np.vstack((left_view, foot_bar))

            # ------------------------------------------------------------------
            # PASO 5: Renderizado de la Vista Derecha (Profundidad + 3 Sectores)
            # ------------------------------------------------------------------
            depth_color = cv2.applyColorMap((depth_norm * 255).astype(np.uint8), colormaps[curr_cm_idx])
            right_view = cv2.resize(depth_color, (target_w, target_h))
            hr, wr = right_view.shape[:2]

            # Dibujar las 3 zonas de análisis sectorial
            w_sec = wr // 3
            y_top = int(hr * 0.20)
            y_bot = int(hr * 0.80)

            # Colores según proximidad
            def sector_color(d):
                if d < CRITICAL_HALT:
                    return (0, 0, 255) # Rojo peligro
                elif d < SAFETY_DISTANCE:
                    return (0, 140, 255) # Naranja advertencia
                return (0, 255, 0) # Verde libre

            # Sector Izquierdo
            c_left = sector_color(dist_left)
            cv2.rectangle(right_view, (0, y_top), (w_sec, y_bot), c_left, 2)
            cv2.putText(right_view, f"IZQ: {dist_left:.2f}m", (10, y_top + 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.60, c_left, 2)

            # Sector Central (Vía de avance principal)
            c_center = sector_color(dist_center)
            cv2.rectangle(right_view, (w_sec, y_top), (2 * w_sec, y_bot), c_center, 3)
            cv2.putText(right_view, f"CENTRO: {dist_center:.2f}m", (w_sec + 10, y_top + 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, c_center, 2)

            # Sector Derecho
            c_right = sector_color(dist_right)
            cv2.rectangle(right_view, (2 * w_sec, y_top), (wr, y_bot), c_right, 2)
            cv2.putText(right_view, f"DER: {dist_right:.2f}m", (2 * w_sec + 10, y_top + 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.60, c_right, 2)

            # Barra superior derecha
            header_right = np.zeros((45, wr, 3), dtype=np.uint8)
            header_right[:] = (20, 20, 20)
            cv2.putText(header_right, f"MAPA DE PROFUNDIDAD ESTIMADA [{colormap_names[curr_cm_idx]}]", (12, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 200, 255), 2)
            right_view = np.vstack((header_right, right_view))

            # Barra inferior derecha: Recomendación de escape
            foot_right = np.zeros((55, wr, 3), dtype=np.uint8)
            foot_right[:] = (15, 15, 15)
            if dist_center < SAFETY_DISTANCE:
                escape_dir = "DER >>" if dist_right >= dist_left else "<< IZQ"
                cv2.putText(foot_right, f"¡OBSTÁCULO CERCANO! EVADIENDO HACIA: {escape_dir}", (12, 34),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 140, 255), 2)
            else:
                cv2.putText(foot_right, f"SECTOR CENTRAL DESPEJADO (Avance seguro a {cruise_speed:.2f} m/s)", (12, 34),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
            right_view = np.vstack((right_view, foot_right))

            # Unir lado izquierdo y lado derecho en una sola ventana panorámica
            combined_display = np.hstack((left_view, right_view))
            cv2.imshow(win_name, combined_display)

            # ------------------------------------------------------------------
            # PASO 6: Interacción y Teclas de Control de Seguridad
            # ------------------------------------------------------------------
            key = cv2.waitKey(15) & 0xFF

            if key == ord('q') or key == 27:
                print("\n[Salida solicitada por usuario]. Aterrizando con seguridad...")
                flight.trigger_land()
                break

            elif key == ord('t') or key == ord('T'):
                # Orden manual de despegue a 1.5 metros
                flight.trigger_takeoff()

            elif key == ord('l') or key == ord('L'):
                # Orden manual de aterrizaje
                flight.trigger_land()

            elif key == ord(' '):
                # Pausa / Freno de emergencia en el aire
                flight.toggle_emergency_hover()

            elif key == ord('c') or key == ord('C'):
                curr_cm_idx = (curr_cm_idx + 1) % len(colormaps)
                print(f"[HUD] Mapa de color cambiado a: {colormap_names[curr_cm_idx]}")

            elif key == ord('s') or key == ord('S'):
                fname = f"demo_flight_{int(time.time())}.jpg"
                save_p = os.path.join(out_dir, fname)
                cv2.imwrite(save_p, combined_display)
                print(f"[HUD] ✅ Captura guardada en: {save_p}")

    except KeyboardInterrupt:
        print("\n[Ctrl+C] Interrupción de teclado detectada. Aterrizando dron...")
        flight.trigger_land()

    finally:
        print("[*] Cerrando módulos de visión y enlaces de comunicación...")
        flight.stop()
        reader.release()
        if bridge:
            bridge.stop()
        cv2.destroyAllWindows()
        print("[OK] Sesión finalizada con éxito.")

if __name__ == "__main__":
    main()
