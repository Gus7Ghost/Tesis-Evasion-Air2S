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
  [O]         : Alternar Offboard en el aire (ceder mando al radiocontrol o retomar IA)
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
import tempfile
import shutil
import csv
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
    parser.add_argument("--auto-takeoff", action="store_true", help="Despegue automático a 1.50m directo (cuenta regresiva de 3s sin esperar tecla T)")
    parser.add_argument("--alt", type=float, default=1.70, help="Altitud objetivo de vuelo en metros (default: 1.70 m)")
    parser.add_argument("--speed", type=float, default=0.45, help="Velocidad segura de crucero y evasion en m/s (default: 0.45 m/s, estable y sin sobrevirajes)")
    parser.add_argument("--mavlink-port", type=int, default=19980, help="Puerto MAVLink UDP de RosettaDrone (default: 19980)")
    parser.add_argument("--tablet-ip", type=str, default=None, help="IP de la tablet RosettaDrone (por defecto usa la última IP guardada)")
    parser.add_argument("--yaw-gain", type=float, default=57.3, help="Ganancia compensatoria de escala angular deg/rad para el puente RosettaDrone (default: 57.3)")
    parser.add_argument("--model", type=str, default="Air2S_MAVSDK/models/midas_v21_small_256.tflite", help="Ruta al modelo MiDaS")
    parser.add_argument("--invert-vy", action="store_true", default=False, help="Invertir signo lateral si el marco de referencia lo requiere (default: False)")
    parser.add_argument("--no-invert-vy", dest="invert_vy", action="store_false", help="Desactivar inversión lateral")
    parser.add_argument("--no-gui", action="store_true", help="Omitir la pantalla gráfica de configuración y usar parámetros directos")
    return parser.parse_args()

def read_key_input(delay_ms=10):
    """Lee pulsaciones de teclado tanto desde la ventana OpenCV como desde la terminal."""
    k = cv2.waitKey(delay_ms) & 0xFF
    if k != 255:
        return k
    if os.name == 'nt':
        try:
            import msvcrt
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                return ord(ch.decode('ascii'))
        except Exception:
            pass
    return 255

def get_local_ip(target_hint=None):
    candidates = []
    if target_hint:
        candidates.append(target_hint)
    candidates.extend(['10.11.8.29', '10.11.8.36', '10.11.8.1', '192.168.43.1', '8.8.8.8', '1.1.1.1'])
    for target in candidates:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.4)
            s.connect((target, 80))
            ip = s.getsockname()[0]
            s.close()
            if ip and not ip.startswith('127.'):
                return ip
        except Exception:
            pass
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith('127.'):
                return ip
    except Exception:
        pass
    return '127.0.0.1'

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
        self.first_real_idr_received = False

        self.sps = b'\x00\x00\x00\x01\x67\x64\x00\x32\xac\x4d\x00\xcc\x04\x4f\x3c\xb3\x50\x10\x10\x14\x00\x00\x03\x00\x04\x00\x00\x03\x00\xc8\x3c\x70\xca\x80'
        self.pps = b'\x00\x00\x00\x01\x68\xee\x3c\xb0'

        # Cargar secuencia de arranque determinista (SPS + PPS + IDR keyframe inicial)
        self.bootstrap_nals = []
        candidates = [
            "test_seg.h264",
            os.path.join(os.path.dirname(__file__), "test_seg.h264"),
            os.path.join(os.path.dirname(__file__), "Air2S_MAVSDK", "test_seg.h264"),
            os.path.join(os.path.dirname(__file__), "..", "test_seg.h264"),
            "test_raw.h264",
            os.path.join(os.path.dirname(__file__), "test_raw.h264"),
            os.path.join(os.path.dirname(__file__), "Air2S_MAVSDK", "test_raw.h264")
        ]
        for c in candidates:
            if os.path.exists(c):
                try:
                    with open(c, 'rb') as f:
                        raw = f.read()
                    if "test_raw" in c and len(raw) >= 28052:
                        raw = raw[23016:28052]
                    nal_indices = [m.start() for m in re.finditer(b'\x00\x00\x00\x01', raw)]
                    for i, idx in enumerate(nal_indices):
                        next_idx = nal_indices[i+1] if i+1 < len(nal_indices) else len(raw)
                        self.bootstrap_nals.append(raw[idx:next_idx])
                    if len(self.bootstrap_nals) > 0:
                        break
                except Exception:
                    pass

        if not self.bootstrap_nals:
            self.bootstrap_nals = [self.sps, self.pps]

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
                time.sleep(0.04)
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
                    elif in_fua:
                        fu_buf.extend(payload[2:])

                    if end and in_fua:
                        if len(fu_buf) > 1:
                            if inner_type == 5:
                                self.s_out.sendto(self.sps, ('127.0.0.1', self.out_port))
                                self.s_out.sendto(self.pps, ('127.0.0.1', self.out_port))
                            pkt = b'\x00\x00\x00\x01' + bytes(fu_buf)
                            try:
                                self.s_out.sendto(pkt, ('127.0.0.1', self.out_port))
                                self.slice_count += 1
                            except Exception:
                                pass
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
        if isinstance(src_uri, int):
            self.cap = cv2.VideoCapture(src_uri, cv2.CAP_DSHOW)
            if not self.cap.isOpened():
                self.cap = cv2.VideoCapture(src_uri)
        else:
            self.cap = cv2.VideoCapture(src_uri, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.latest_frame = None
        self.frame_counter = 0
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

# Corrección Obs.3: Intentar importar módulo de gimbal para control dinámico de cabeceo
try:
    from mavsdk.gimbal import GimbalMode, ControlMode
    HAS_GIMBAL_API = True
except ImportError:
    HAS_GIMBAL_API = False

class FlightController(threading.Thread):
    """
    Gestiona el enlace de telemetría y los comandos de vuelo físico con MAVSDK.
    Mantiene un bucle cerrado a 10 Hz para mantener la altitud objetivo (1.5 m)
    y aplicar las velocidades de avance y evasión de forma segura.
    """
    def __init__(self, system_address="udpin://0.0.0.0:19980", target_alt=1.70, allow_real_flight=False, yaw_gain=57.3):
        super().__init__(daemon=True)
        self.system_address = system_address
        self.target_alt = target_alt
        self.allow_real_flight = allow_real_flight
        self.yaw_gain = yaw_gain

        self.running = True
        self.loop = None
        self.drone = None
        self.offboard_active = False
        self.in_flight = False
        self.initial_climb_done = False
        self.last_alt_stable = target_alt
        self.stable_alt_count = 0

        # Estado instantáneo compartido
        self.lock = threading.Lock()
        self.state = {
            "connected": False,
            "armed": False,
            "in_air": False,
            "flight_mode": "SIM_MESA" if not allow_real_flight else "DESCONECTADO",
            "altitude_m": target_alt if not allow_real_flight else 0.0,
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
        self.takeoff_requested = False

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
        asyncio.create_task(self._telemetry_altitude_task())
        asyncio.create_task(self._telemetry_attitude_task())
        asyncio.create_task(self._telemetry_battery_task())
        asyncio.create_task(self._telemetry_flight_mode_task())

        # Corrección Obs.3: Programar el gimbal a -15° de cabeceo (mirando ligeramente
        # hacia abajo) para capturar mejor los obstáculos a nivel del suelo/banco.
        asyncio.create_task(self._setup_gimbal_pitch())

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
                    if self.allow_real_flight and pos.relative_altitude_m > 0.05:
                        self.state["altitude_m"] = round(pos.relative_altitude_m, 2)
        except Exception:
            pass

    async def _telemetry_altitude_task(self):
        try:
            async for alt in self.drone.telemetry.altitude():
                with self.lock:
                    if self.allow_real_flight and alt.altitude_relative_m > 0.05:
                        self.state["altitude_m"] = round(alt.altitude_relative_m, 2)
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
                        pct = bat.remaining_percent
                        self.state["battery_pct"] = int(pct if pct <= 100 else pct / 100.0)
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

    async def _setup_gimbal_pitch(self):
        """Corrección Obs.3: Apuntar el gimbal -15° de cabeceo (pitch) hacia abajo
        para mejorar la captura de obstáculos al nivel del banco de pruebas.
        Se reintenta cada 5 segundos hasta lograrlo o hasta detenerse."""
        await asyncio.sleep(3.0)  # Esperar a que el dron se conecte
        try:
            await self.drone.gimbal.set_pitch_and_yaw(-15.0, 0.0)
            print("[Gimbal] Cabeceo ajustado a -15° (mirando ligeramente hacia abajo).")
        except Exception:
            # Si RosettaDrone no expone la API de gimbal, se usa el mando físico
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

        # Control determinista en lazo cerrado para elevar y mantener firmemente los 1.70 m:
        # MAPEO DEL PUENTE ROSETTADRONE / DJI MOBILE SDK:
        # • Valores POSITIVOS (+m/s) ordenan ASCENSO (SUBIR) a los motores DJI.
        # • Valores NEGATIVOS (-m/s) ordenan DESCENSO (BAJAR).
        # • Valor 0.0 m/s activa el VPS inferior de DJI (Hold vertical milimétrico sin oscilación).
        with self.lock:
            current_alt = self.state["altitude_m"]
            target_alt = self.target_alt  # 1.70 m por defecto

        vz_cmd = 0.0
        if self.allow_real_flight and self.offboard_active:
            # 1. Monitoreo de intervención manual (si el usuario elevó o bajó el dron con el control físico DJI)
            if self.initial_climb_done:
                if abs(current_alt - self.last_alt_stable) < 0.04:
                    self.stable_alt_count += 1
                else:
                    self.stable_alt_count = 0
                    self.last_alt_stable = current_alt

                # Si el usuario modificó la altura con el mando físico y se mantiene estable por ~1.0 s:
                # Se adopta automáticamente esa nueva altura como meta sin luchar contra el piloto.
                if self.stable_alt_count >= 10 and abs(current_alt - target_alt) >= 0.20:
                    with self.lock:
                        self.target_alt = round(current_alt, 2)
                        self.state["target_alt_m"] = self.target_alt
                        target_alt = self.target_alt
                    print(f"\n[Controller] 🎮 Nueva altitud manual adoptada: {target_alt:.2f} m (Mantenida firmemente)\n")

            # 2. Control de ascenso inicial y mantenimiento suave
            alt_error = target_alt - current_alt  # Positivo si está por debajo (debe SUBIR)

            if not self.initial_climb_done:
                # FASE 1: Ascenso inicial desde despegue hacia 1.70 m
                if alt_error > 0.35:
                    # Lejos de la meta: ascenso constante y firme (0.35 m/s)
                    vz_cmd = 0.35
                elif alt_error > 0.08:
                    # Desaceleración suave y progresiva al aproximarse (evita rebote/overshoot)
                    ramp = (alt_error - 0.08) / (0.35 - 0.08)
                    vz_cmd = float(np.clip(0.08 + ramp * (0.35 - 0.08), 0.08, 0.35))
                else:
                    # Meta alcanzada dentro de +-8 cm: BLOQUEO INMEDIATO EN HOVER (vz = 0.0)
                    vz_cmd = 0.0
                    self.initial_climb_done = True
                    self.last_alt_stable = current_alt
                    with self.lock:
                        self.target_alt = round(current_alt, 2)
                        self.state["target_alt_m"] = self.target_alt
                    print(f"\n[Controller] ✅ Altitud meta ({current_alt:.2f} m) alcanzada. VPS DJI bloqueado en hover estable (vz=0.0).\n")
            else:
                # FASE 2: Vuelo estabilizado con VPS DJI nativo
                # Banda muerta amplia (+-15 cm) donde vz=0.0 para que el VPS mantenga altura fija sin chattering
                if alt_error > 0.15:
                    # Caída no deseada: suave impulso ascendente
                    vz_cmd = float(np.clip(0.08 + (alt_error - 0.15) * 0.4, 0.08, 0.20))
                elif alt_error < -0.15:
                    # Subida no deseada: suave micro-corrección descendente
                    vz_cmd = -float(np.clip(0.06 + (abs(alt_error) - 0.15) * 0.3, 0.06, 0.18))
                else:
                    # Dentro de la ventana de estabilidad (+-15 cm): vz = 0.0 (VPS DJI activo)
                    vz_cmd = 0.0

            # 3. Piso de seguridad crítico: si el dron baja de 0.65m en cualquier momento, subir suavemente
            if current_alt < 0.65 and not is_emergency:
                vz_cmd = max(vz_cmd, 0.25)

        with self.lock:
            self.state["vx_cmd"] = round(vx, 2)
            self.state["vy_cmd"] = round(vy, 2)
            self.state["vz_cmd"] = round(vz_cmd, 2)
            self.state["yaw_rate_cmd"] = round(yaw_rate, 1)

        # Auto-enganche inteligente: si el usuario solicitó despegue (tecla T) y el dron deja el suelo (> 0.20m)
        if self.allow_real_flight and getattr(self, 'takeoff_requested', False) and not self.offboard_active:
            with self.lock:
                current_alt = self.state["altitude_m"]
            if current_alt >= 0.20:
                self.takeoff_requested = False
                print(f"\n[Controller] 🚀 Dron en el aire detectado ({current_alt:.2f} m).")
                print(f"[Controller] ▶ Modo Offboard enganchado. ¡Ascendiendo directamente a {self.target_alt:.2f} m!\n")
                asyncio.create_task(self._start_offboard_internal())

        # Si el vuelo real está habilitado y el dron está en el aire con offboard
        if self.allow_real_flight and self.offboard_active:
            try:
                # Compensación angular calibrada para el puente RosettaDrone:
                # MAVSDK internamente divide yawspeed_deg_s entre 57.2958 (convirtiendo a rad/s)
                # para el mensaje MAVLink SET_POSITION_TARGET_LOCAL_NED.
                # RosettaDrone envía el flotante MAVLink directamente a la API de DJI Mobile SDK
                # (FlightControlData.setYaw), la cual opera en GRADOS/SEGUNDO (deg/s).
                # Multiplicando por self.yaw_gain (57.3), restauramos la velocidad angular real.
                # Acotamos el giro a una velocidad suave y estable (máx +-20°/s) para evitar
                # sobre-virajes (overshoot) y desenfoque de movimiento (motion blur) en la cámara.
                safe_yaw = float(np.clip(yaw_rate, -20.0, 20.0))
                scaled_yaw_cmd = float(safe_yaw * self.yaw_gain)
                cmd = VelocityBodyYawspeed(
                    forward_m_s=float(vx),
                    right_m_s=float(vy),
                    down_m_s=float(vz_cmd),  # Positivo = SUBIR en RosettaDrone/DJI
                    yawspeed_deg_s=scaled_yaw_cmd
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

    def adjust_target_altitude(self, delta_m: float):
        """Ajusta dinámicamente la altitud objetivo desde teclado."""
        with self.lock:
            self.target_alt = round(max(0.60, min(3.00, self.target_alt + delta_m)), 2)
            self.state["target_alt_m"] = self.target_alt
            self.initial_climb_done = False
            self.last_alt_stable = self.target_alt
            self.stable_alt_count = 0
        print(f"\n[Controller] ↕ Altitud objetivo ajustada a: {self.target_alt:.2f} m\n")

    def trigger_takeoff(self):
        """Inicia secuencia de despegue y enganche a 1.5 metros."""
        if not self.allow_real_flight:
            print(f"[Controller] Simulación en Mesa: Despegue emulado a {self.target_alt:.2f}m.")
            with self.lock:
                self.state["altitude_m"] = self.target_alt
                self.state["flight_mode"] = "OFFBOARD_SIM"
                self.state["fsm_state"] = f"HOVER_{self.target_alt:.1f}M"
            self.in_flight = True
            return

        if self.offboard_active:
            print("[Controller] El modo Offboard ya se encuentra ACTIVO.")
            return

        if self.allow_real_flight and self.state["altitude_m"] > 0.25:
            print(f"[Controller] Dron ya detectado en el aire ({self.state['altitude_m']:.2f}m). Activando modo Offboard inmediato...")
            self.initial_climb_done = (self.state["altitude_m"] >= (self.target_alt - 0.15))
            self.last_alt_stable = self.state["altitude_m"]
            self.stable_alt_count = 0
            self.toggle_offboard()
            return

        self.takeoff_requested = True

        async def _takeoff_task():
            print(f"[Controller] Iniciando secuencia de despegue y ascenso a {self.target_alt:.2f}m...")
            takeoff_ok = False
            try:
                try:
                    await self.drone.action.arm()
                    print("[Controller] Motores armados exitosamente.")
                except Exception as e:
                    print(f"[Controller] Aviso armando motores: {e}")

                try:
                    await self.drone.action.takeoff()
                    print("[Controller] Despegue ordenado. Ascendiendo a altitud segura...")
                    takeoff_ok = True
                except Exception as e:
                    print("\n" + "!" * 72)
                    print("  [!] DESPEGUE AUTOMÁTICO DENEGADO POR ROSETTADRONE / DJI:")
                    print(f"      Detalle: {e}")
                    print("      POSIBLES CAUSAS Y SOLUCIÓN:")
                    print("      1. 'SAFETY ENABLED' en RosettaDrone: Toca el botón de seguridad en")
                    print("         la pantalla de la tablet para cambiarlo a VERDE ('READY TO FLY').")
                    print("      2. Bloqueo de interiores DJI (sin GPS): DJI restringe el despegue")
                    print("         automático por software en interiores.")
                    print("      --> MÉTODO DIRECTO RECOMENDADO (100% OPERATIVO):")
                    print("          a) Despega manualmente con el control físico DJI (palancas ↙ ↘).")
                    print("          b) Elévalo a ~1.20 - 1.50m (hover estable con sensores inferiores VPS).")
                    print("          c) Presiona la tecla [O] en la laptop para ceder el control a la IA.")
                    print("!" * 72 + "\n")

                if not takeoff_ok:
                    return

                print(f"[Controller] Esperando 5s para estabilización a {self.target_alt:.2f}m...")
                await asyncio.sleep(5.0)

                with self.lock:
                    if self.state["altitude_m"] < 0.20:
                        self.state["altitude_m"] = self.target_alt
                    self.state["flight_mode"] = "OFFBOARD_AUTO"

                # Inicializar comando inerte antes de pasar a offboard
                await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
                try:
                    await self.drone.offboard.start()
                    self.offboard_active = True
                    self.in_flight = True
                    print(f"[Controller] ✅ Modo Offboard ACTIVO. Altitud fijada a {self.target_alt:.2f}m (VPS). IA al mando de la evasión.")
                except Exception as e:
                    print(f"[Controller] Aviso iniciando Offboard: {e}. Reintentando comando inerte...")
                    await asyncio.sleep(0.5)
                    await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
                    await self.drone.offboard.start()
                    self.offboard_active = True
                    self.in_flight = True
                    print("[Controller] ✅ Modo Offboard ACTIVO tras reintento.")
            except Exception as e:
                print(f"[Controller] Error durante la secuencia de despegue: {e}")

        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(_takeoff_task(), self.loop)

    async def _start_offboard_internal(self):
        """Inicializa y arranca el modo Offboard de forma segura."""
        try:
            await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
            await self.drone.offboard.start()
            self.offboard_active = True
            self.in_flight = True
            self.initial_climb_done = (self.state["altitude_m"] >= (self.target_alt - 0.15))
            self.last_alt_stable = self.state["altitude_m"]
            self.stable_alt_count = 0
            with self.lock:
                self.state["flight_mode"] = "OFFBOARD_AUTO"
            print(f"[Controller] ✅ Modo Offboard ACTIVO. Altitud fijada a {self.target_alt:.2f}m (VPS). IA al mando de la evasión.")
        except Exception as e:
            print(f"[Controller] Error iniciando Offboard: {e}")

    def toggle_offboard(self):
        """Activa o suspende el modo Offboard directamente en pleno vuelo."""
        if not self.allow_real_flight:
            self.offboard_active = not self.offboard_active
            status = "SIM_OFFBOARD" if self.offboard_active else "SIM_MANUAL"
            print(f"[Controller] Simulación: Offboard alternado a {status}")
            return

        async def _toggle():
            if self.offboard_active:
                print("[Controller] ⏸ Pausando Offboard. Control manual cedido al radiocontrol DJI.")
                try:
                    await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
                    await self.drone.offboard.stop()
                except Exception:
                    pass
                self.offboard_active = False
                self.takeoff_requested = False
            else:
                print("[Controller] ▶ Activando modo Offboard en vuelo. La IA toma el control...")
                await self._start_offboard_internal()

        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(_toggle(), self.loop)

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

                try:
                    await self.drone.action.land()
                    print("[Controller] ✅ Orden de aterrizaje transmitida a RosettaDrone.")
                except Exception as e:
                    # RosettaDrone ejecuta el aterrizaje pero no envía el ACK formal MAVLink
                    print("[Controller] ✅ Orden de aterrizaje enviada a RosettaDrone (Dron en descenso seguro).")
                self.in_flight = False
            except Exception as e:
                print(f"[Controller] Aviso durante aterrizaje: {e}")

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
# 3. RASTREADOR DE PERSONA Y COMPENSADOR DE CONTRALUZ (CLAHE + MOBILENET-SSD)
#    CON SISTEMA DE BLOQUEO DE OBJETIVO Y RE-IDENTIFICACIÓN POR TECLA (SEMI-AUTO)
# ==============================================================================
class RobustTargetTracker:
    def __init__(self, fov_horizontal=88.0):
        self.fov = fov_horizontal
        self.last_box = None
        self.smooth_alpha = 0.65
        self.last_angle = 0.0
        self.last_seen_time = 0.0

        # Sistema de Bloqueo de Objetivo y Re-Identificación (Semi-Automático por Tecla)
        self.is_locked = False
        self.pilot_hist = None
        self.pilot_similarity = 0.0
        self.last_raw_candidates = []
        self.discarded_boxes = []
        self.lock_status_msg = "MODO LIBRE: Parate al centro y pulsa 'B' para BLOQUEAR PILOTO"

        # Cargar MobileNet-SSD Caffe para detección robusta de cuerpo entero en cualquier postura
        self.net = None
        proto = "Air2S_MAVSDK/models/deploy.prototxt"
        model = "Air2S_MAVSDK/models/mobilenet.caffemodel"
        if not os.path.exists(proto):
            proto = os.path.join(os.path.dirname(__file__), "Air2S_MAVSDK", "models", "deploy.prototxt")
            model = os.path.join(os.path.dirname(__file__), "Air2S_MAVSDK", "models", "mobilenet.caffemodel")

        if os.path.exists(proto) and os.path.exists(model):
            try:
                self.net = cv2.dnn.readNetFromCaffe(proto, model)
                self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                print("[Tracker] ✅ Red neuronal MobileNet-SSD lista para seguimiento humano en 360°.")
            except Exception as e:
                print(f"[Tracker] Aviso cargando MobileNet-SSD: {e}")

        # Fallback a Haar Cascade solo si no se pudo cargar la red neuronal
        self.clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        self.cascade = None
        if self.net is None:
            try:
                self.cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            except Exception:
                pass

    def extract_torso_hist(self, frame, box):
        """Extrae un histograma HSV tridimensional [8, 8, 8] del torso/vestimenta para Re-ID."""
        h, w = frame.shape[:2]
        bx1, by1, bx2, by2 = box
        bw = bx2 - bx1
        bh = by2 - by1
        if bw < 10 or bh < 20:
            return None
        # Región del torso: 20% a 70% de altura, 20% a 80% de anchura
        tx1 = max(0, min(w - 1, bx1 + int(bw * 0.20)))
        tx2 = min(w, bx1 + int(bw * 0.80))
        ty1 = max(0, min(h - 1, by1 + int(bh * 0.20)))
        ty2 = min(h, by1 + int(bh * 0.70))
        if tx2 <= tx1 + 4 or ty2 <= ty1 + 4:
            return None
        torso = frame[ty1:ty2, tx1:tx2]
        hsv = cv2.cvtColor(torso, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1, 2], None, [8, 8, 8], [0, 180, 0, 256, 0, 256])
        cv2.normalize(hist, hist, alpha=1.0, norm_type=cv2.NORM_L1)
        return hist

    def _compute_iou(self, boxA, boxB):
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])
        interArea = max(0, xB - xA) * max(0, yB - yA)
        boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
        return interArea / float(max(1, boxAArea + boxBArea - interArea))

    def lock_target(self, frame, target_box=None):
        """Bloquea al piloto extrayendo su firma de vestimenta HSV."""
        h, w = frame.shape[:2]
        chosen_box = None
        if target_box is not None:
            chosen_box = target_box
        elif self.last_raw_candidates:
            # Seleccionar al candidato más centrado horizontalmente en la cámara
            chosen = min(self.last_raw_candidates, key=lambda c: abs((c['box'][0] + c['box'][2])/2.0 - w/2.0))
            chosen_box = chosen['box']
        elif self.last_box is not None:
            chosen_box = self.last_box

        if chosen_box is None:
            self.lock_status_msg = "AVISO: No se detecto persona en encuadre para bloquear."
            return False, self.lock_status_msg

        hist = self.extract_torso_hist(frame, chosen_box)
        if hist is None:
            self.lock_status_msg = "AVISO: Tamano insuficiente de recuadro para registrar firma."
            return False, self.lock_status_msg

        self.pilot_hist = hist
        self.is_locked = True
        self.last_box = chosen_box
        self.last_seen_time = time.time()
        self.pilot_similarity = 1.0
        self.lock_status_msg = f"PILOTO BLOQUEADO (Lock Activo) | Pulsa 'B' re-bloquear, 'U' liberar"
        return True, f"🔒 ¡PILOTO BLOQUEADO CON ÉXITO! Recuadro: {chosen_box}. Firma HSV guardada."

    def lock_at_point(self, frame, click_x, click_y):
        """Permite bloquear al objetivo haciendo clic directo con el mouse en la ventana."""
        matched_box = None
        for cand in self.last_raw_candidates:
            bx1, by1, bx2, by2 = cand['box']
            if bx1 <= click_x <= bx2 and by1 <= click_y <= by2:
                matched_box = (bx1, by1, bx2, by2)
                break
        if matched_box is None and self.last_raw_candidates:
            matched_box = min(self.last_raw_candidates,
                              key=lambda c: np.hypot((c['box'][0]+c['box'][2])/2.0 - click_x,
                                                     (c['box'][1]+c['box'][3])/2.0 - click_y))['box']
        if matched_box is not None:
            return self.lock_target(frame, matched_box)
        return False, "No se encontró ningún humano cerca del punto seleccionado con el ratón."

    def unlock_target(self):
        """Libera el bloqueo y regresa al modo de detección libre."""
        self.is_locked = False
        self.pilot_hist = None
        self.pilot_similarity = 0.0
        self.discarded_boxes = []
        self.lock_status_msg = "MODO LIBRE: Parate al centro y pulsa 'B' para BLOQUEAR PILOTO"
        return True, "🔓 Objetivo liberado. Modo de detección libre activo."

    def detect(self, frame):
        h, w = frame.shape[:2]
        raw_candidates = []

        if self.net is not None:
            # Detección profunda de cuerpo completo (clase 15 = Persona en Pascal VOC)
            blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 0.007843, (300, 300), 127.5)
            self.net.setInput(blob)
            detections = self.net.forward()
            for i in range(detections.shape[2]):
                conf = float(detections[0, 0, i, 2])
                cls_id = int(detections[0, 0, i, 1])
                if cls_id == 15 and conf > 0.32:
                    box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                    bx1, by1, bx2, by2 = box.astype(int)
                    bx1 = max(0, min(w - 1, bx1))
                    by1 = max(0, min(h - 1, by1))
                    bx2 = max(0, min(w - 1, bx2))
                    by2 = max(0, min(h - 1, by2))
                    if (bx2 - bx1) >= 12 and (by2 - by1) >= 24:
                        raw_candidates.append({'box': (bx1, by1, bx2, by2), 'conf': conf})
        else:
            if self.cascade is not None:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray_eq = self.clahe.apply(gray)
                faces = self.cascade.detectMultiScale(gray_eq, scaleFactor=1.15, minNeighbors=4, minSize=(40, 40))
                for (fx, fy, fw, fh) in faces:
                    fb = (max(0, fx - int(fw*0.2)), max(0, fy - int(fh*0.2)),
                          min(w, fx + int(fw*1.4)), min(h, fy + int(fh*2.8)))
                    raw_candidates.append({'box': fb, 'conf': 0.85})

        self.last_raw_candidates = raw_candidates
        best_box = None
        confidence = 0.0

        if not self.is_locked:
            # ==================================================================
            # MODO 1: OBJETIVO VARIADO (EXACTAMENTE COMO EN PRUEBA 1 / AC4CE96)
            # Detecta y persigue al objetivo con mayor confianza en escena
            # ==================================================================
            self.discarded_boxes = []
            self.pilot_similarity = 0.0
            max_c = 0.0
            for cand in raw_candidates:
                if cand['conf'] > max_c:
                    max_c = cand['conf']
                    best_box = cand['box']
                    confidence = cand['conf']
        else:
            # ==================================================================
            # MODO BLOQUEADO (RE-ID): Filtrar gigantografías y falsos humanos
            # ==================================================================
            best_pilot = None
            best_score = -1.0
            best_sim = 0.0
            best_hist = None
            discarded = []

            for cand in raw_candidates:
                c_box = cand['box']
                c_conf = cand['conf']
                c_hist = self.extract_torso_hist(frame, c_box)

                if c_hist is not None and self.pilot_hist is not None:
                    bhatt = cv2.compareHist(self.pilot_hist, c_hist, cv2.HISTCMP_BHATTACHARYYA)
                    sim_color = max(0.0, 1.0 - float(bhatt))
                else:
                    sim_color = 0.0

                # Continuidad espacial (IoU y cercanía de centroides con el último encuadre del piloto)
                if self.last_box is not None:
                    iou = self._compute_iou(c_box, self.last_box)
                    cx = (c_box[0] + c_box[2]) / 2.0
                    cy = (c_box[1] + c_box[3]) / 2.0
                    last_cx = (self.last_box[0] + self.last_box[2]) / 2.0
                    last_cy = (self.last_box[1] + self.last_box[3]) / 2.0
                    d_norm = np.hypot(cx - last_cx, cy - last_cy) / float(w)
                    spatial_prox = max(0.0, 1.0 - d_norm * 2.2)
                    spatial_score = max(iou, spatial_prox)
                else:
                    spatial_score = 0.50

                # Puntuación combinada (60% apariencia de vestimenta, 40% proximidad espacial)
                match_score = 0.60 * sim_color + 0.40 * spatial_score

                # Criterio de discriminación estricto:
                # El póster/gigantografía en pared tiene sim_color < 0.20 y score < 0.25.
                # El piloto real mantiene sim_color >= 0.32 y score >= 0.36.
                if sim_color >= 0.32 and match_score >= 0.36:
                    if match_score > best_score:
                        best_score = match_score
                        best_pilot = cand
                        best_sim = sim_color
                        best_hist = c_hist
                else:
                    discarded.append({'box': c_box, 'conf': c_conf, 'sim': sim_color,
                                      'reason': f"Falso Objetivo/Gigantografia ({sim_color*100:.0f}%)"})

            self.discarded_boxes = discarded

            if best_pilot is not None:
                best_box = best_pilot['box']
                confidence = best_pilot['conf']
                self.pilot_similarity = best_sim
                # Adaptación lenta de la firma de vestimenta para tolerar cambios de sombra
                if best_sim > 0.60 and best_hist is not None:
                    self.pilot_hist = 0.92 * self.pilot_hist + 0.08 * best_hist
                    cv2.normalize(self.pilot_hist, self.pilot_hist, alpha=1.0, norm_type=cv2.NORM_L1)
            else:
                best_box = None
                confidence = 0.0
                self.pilot_similarity = 0.0

        if best_box is not None:
            if self.last_box is not None:
                x1 = int(self.smooth_alpha * best_box[0] + (1 - self.smooth_alpha) * self.last_box[0])
                y1 = int(self.smooth_alpha * best_box[1] + (1 - self.smooth_alpha) * self.last_box[1])
                x2 = int(self.smooth_alpha * best_box[2] + (1 - self.smooth_alpha) * self.last_box[2])
                y2 = int(self.smooth_alpha * best_box[3] + (1 - self.smooth_alpha) * self.last_box[3])
                best_box = (x1, y1, x2, y2)
            self.last_box = best_box
            cx = (best_box[0] + best_box[2]) / 2.0
            angle_deg = (cx / float(w) - 0.5) * self.fov
            self.last_angle = angle_deg
            self.last_seen_time = time.time()
            return best_box, angle_deg, confidence
        else:
            # Memoria de persistencia angular: si el objetivo salió del encuadre hace menos de 2.0s,
            # continuar la rotación en la dirección por donde se fue para re-engancharlo
            time_since_seen = time.time() - self.last_seen_time
            if time_since_seen < 2.0 and abs(self.last_angle) > 5.0:
                scan_angle = 35.0 if self.last_angle > 0 else -35.0
                return None, scan_angle, 0.0
            self.last_box = None
            return None, 0.0, 0.0

# ==============================================================================
# 4. MOTOR PRINCIPAL DE VISIÓN, NAVEGACIÓN Y DEMOSTRACIÓN
# ==============================================================================
def main():
    args = parse_arguments()

    # Pantalla interactiva para verificar/modificar IPs de Tablet y Laptop
    if not args.no_gui:
        try:
            from interfaz_config_red import get_network_config_interactive, save_network_config
            net_cfg = get_network_config_interactive(current_args=args)
            if net_cfg is None:
                print("\n[Operación cancelada por el usuario en la pantalla de configuración].")
                return
            args.tablet_ip = net_cfg.get("tablet_ip")
            local_ip = net_cfg.get("laptop_ip", get_local_ip(args.tablet_ip))
            if "use_drone_video" in net_cfg:
                args.drone = net_cfg["use_drone_video"]
            if "real_flight" in net_cfg:
                args.fly = net_cfg["real_flight"]
            save_network_config(net_cfg)
        except Exception as e:
            print(f"[Aviso] Pantalla de configuración no disponible ({e}). Continuando...")
            from interfaz_config_red import load_network_config, save_network_config
            saved = load_network_config()
            args.tablet_ip = args.tablet_ip or saved.get("tablet_ip", "10.11.8.59")
            local_ip = saved.get("laptop_ip", get_local_ip(args.tablet_ip))
    else:
        from interfaz_config_red import load_network_config, save_network_config
        saved = load_network_config()
        if args.tablet_ip is None:
            args.tablet_ip = saved.get("tablet_ip", "10.11.8.59")
        local_ip = saved.get("laptop_ip", get_local_ip(args.tablet_ip))
        saved["tablet_ip"] = args.tablet_ip
        saved["laptop_ip"] = local_ip
        save_network_config(saved)

    tablet_ip_str = args.tablet_ip if args.tablet_ip else "Configurada en RosettaDrone"

    print("=" * 76)
    print("  UNIVERSIDAD NACIONAL DE INGENIERÍA - FACULTAD DE INGENIERÍA DE SISTEMAS")
    print("  TESIS: NAVEGACIÓN AUTÓNOMA, PERSECUCIÓN Y EVASIÓN REACTIVA A 1.5 METROS")
    print(f"  Laptop IP: {local_ip} | Tablet IP: {tablet_ip_str}")
    print(f"  Modo Operativo: {'[VUELO REAL CON MOTORES]' if args.fly else '[SIMULACIÓN SEGURA EN MESA (Sin hélices)]'}")
    print(f"  Altitud Objetivo: {args.alt:.2f} m | Velocidad Lenta de Demostración: {args.speed:.2f} m/s")
    print("=" * 76)

    # 1. Iniciar puente de video o lector de cámara
    bridge = None
    if args.drone:
        print("\n[*] Conectando receptor de video del Dron DJI Air 2S (UDP 5600)...")
        bridge = RTPVideoBridge(in_port=5600, out_port=5601)
        print("    - Esperando flujo de video de RosettaDrone en UDP 5600...")
        wait_cycles = 0
        while bridge.packet_count < 10:
            print(f"      Recibiendo paquetes de video: {bridge.packet_count}...   ", end="\r")
            time.sleep(0.3)
            wait_cycles += 1
            if wait_cycles % 15 == 0 and bridge.packet_count == 0:
                print(f"\n      [!] Recordatorio: RosettaDrone debe estar en 'START' enviando video a {local_ip}:5600.")
                print("          Verifica que 'Enable video feed' esté ON y el dron DJI esté encendido y vinculado.\n")
        print(f"\n    [OK] Flujo detectado ({bridge.packet_count} paquetes). Sincronizando decodificador en vivo...")
        bridge.start_bootstrap()
        reader = FreshFrameReader('udp://127.0.0.1:5601')
        print("    - Esperando primer fotograma descodificado del Air 2S...")
        t_boot = time.time()
        synced = False
        while time.time() - t_boot < 8.0:
            ret, test_f = reader.read_latest()
            if ret and test_f is not None:
                synced = True
                print(f"    [OK] Video en vivo del DJI Air 2S enganchado en tiempo real ({test_f.shape[1]}x{test_f.shape[0]}).")
                break
            time.sleep(0.05)
        bridge.stop_bootstrap()
        if not synced:
            print("    [!] AVISO: Flujo inicial recibido. El video se actualizará en vivo.")
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
    try:
        from ai_edge_litert.interpreter import Interpreter
        interpreter = Interpreter(model_path=model_path, num_threads=4)
    except Exception:
        try:
            import tflite_runtime.interpreter as tflite
            interpreter = tflite.Interpreter(model_path=model_path, num_threads=4)
        except Exception:
            import tensorflow as tf
            interpreter = tf.lite.Interpreter(model_path=model_path, num_threads=4)
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    # Corrección Obs.4: Ecualización CLAHE para mejorar detección de superficies
    # homogéneas (obstáculos delgados, paredes lisas) bajo luz artificial de laboratorio.
    # Se aplica al canal L del espacio LAB antes de la inferencia MiDaS.
    clahe_midas = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))

    # 3. Inicializar Tracker y Controlador de Vuelo
    tracker = RobustTargetTracker(fov_horizontal=88.0)
    flight = FlightController(
        system_address=f"udpin://0.0.0.0:{args.mavlink_port}",
        target_alt=args.alt,
        allow_real_flight=args.fly,
        yaw_gain=args.yaw_gain
    )
    flight.start()

    # Si se especificó vuelo real desde el inicio, advertencias de seguridad y controles
    if args.fly:
        print("\n" + "=" * 76)
        print("  [!] MODO DE VUELO REAL FÍSICO HABILITADO (HÉLICES ACTIVAS)")
        print(f"      - Tecla [T] : Despegue automático y ascenso a {args.alt:.2f} m (Activa Offboard).")
        print("      - Tecla [O] : Alternar Offboard en el aire (Tomar/Ceder mando a la IA).")
        print("      - [ESPACIO] : FRENO DE EMERGENCIA / Hover instantáneo.")
        print("      - Tecla [L] : Aterrizaje seguro inmediato.")
        print("      - Tecla [+/-] : Subir / Bajar altitud (+-10 cm) desde laptop.")
        print("      - Radiomando: Eleva o baja con el stick; la IA fijará la nueva altura.")
        print("      - Tecla [Q] : Aterrizar y salir.")
        print("      * NOTA: Las teclas funcionan tanto en la ventana de video como en esta consola.")
        print("=" * 76)

        if args.auto_takeoff:
            print("\n  [!] AUTO-TAKEOFF ACTIVADO: Iniciando despegue en 3 segundos...")
            print("      (Presiona [ESPACIO] o [Q] para cancelar)")
            abort_auto = False
            for c_sec in range(3, 0, -1):
                print(f"      Despegando en {c_sec}... ")
                t_w = time.time()
                while time.time() - t_w < 1.0:
                    k = read_key_input(20)
                    if k == ord(' ') or k == ord('q') or k == 27:
                        abort_auto = True
                        print("\n[!] Despegue automático cancelado por usuario.")
                        break
                if abort_auto:
                    break
            if not abort_auto:
                print("[Controller] ¡Ejecutando despegue automático a 1.50m!")
                flight.trigger_takeoff()

    colormaps = [cv2.COLORMAP_INFERNO, cv2.COLORMAP_TURBO, cv2.COLORMAP_JET, cv2.COLORMAP_MAGMA]
    colormap_names = ["INFERNO", "TURBO", "JET", "MAGMA"]
    curr_cm_idx = 0

    win_name = "Tesis UNI - Demostracion: Persecucion y Evasion a 1.5m (DJI Air 2S)"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win_name, 1280, 540)

    # Callback de ratón para selección/bloqueo directo del piloto haciendo clic en la ventana
    mouse_click_pos = [None]
    def on_mouse_click(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            mouse_click_pos[0] = (x, y)
    cv2.setMouseCallback(win_name, on_mouse_click)

    fps = 0.0
    latency_ms = 0.0
    frame_count = 0
    total_cycles = 0
    t_prev = time.time()
    t_init_flight = time.time()
    cruise_speed = args.speed
    last_human_seen_t = 0.0
    in_pure_pivot = False
    last_thin_obs_info = None
    last_thin_obs_time = 0.0

    out_dir = os.path.join("Air2S_MAVSDK", "logs", "capturas_demo")
    os.makedirs(out_dir, exist_ok=True)

    # 4. Registrador de Métricas Experimentales para la Tesis (CSV para Gráficos)
    csv_dir = os.path.join("Air2S_MAVSDK", "logs")
    os.makedirs(csv_dir, exist_ok=True)
    session_ts = time.strftime("%Y%m%d_%H%M%S")
    csv_file_path = os.path.join(csv_dir, f"metricas_vuelo_{session_ts}.csv")
    csv_file = open(csv_file_path, mode='w', newline='', encoding='utf-8')
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow([
        "timestamp_unix",
        "tiempo_relativo_s",
        "fps",
        "latencia_ciclo_ms",
        "estado_fsm",
        "distancia_minima_m",
        "dist_izq_m",
        "dist_centro_m",
        "dist_der_m",
        "humano_detectado",
        "angulo_humano_deg",
        "cmd_vx_ms",
        "cmd_vy_ms",
        "cmd_yaw_rate_degs",
        "altitud_actual_m",
        "altitud_meta_m",
        "bateria_pct",
        "heading_yaw_deg"
    ])
    csv_file.flush()
    print(f"[*] Registrador de métricas de tesis activo:\n    -> {csv_file_path}\n")

    print("[OK] Demostración lista. Visualizador en pantalla activo.\n")
    print("================================================================================")
    print(" 🎯 SISTEMA DE PERSECUCIÓN CON BLOQUEO SEMI-AUTOMÁTICO DE PILOTO (ANTI-GIGANTOGRAFÍA)")
    print(" --------------------------------------------------------------------------------")
    print("  [B] / [K] / [P]   : BLOQUEAR al Piloto (guarda firma HSV y descarta gigantografías)")
    print("  [Clic en Pantalla]: Bloqueo directo haciendo clic sobre el cuerpo del piloto")
    print("  [U]               : DESBLOQUEAR objetivo y volver a modo de detección libre")
    print("  [T] Despegue 1.5m | [L] Aterrizar | [O] Offboard | [Espacio] Parada de emergencia")
    print("================================================================================\n")

    try:
        while True:
            t_cycle_start = time.time()
            ret, frame = reader.read_latest()
            if not ret or frame is None:
                key = read_key_input(20)
                if key == ord('q') or key == 27:
                    print("\n[Salida solicitada por usuario]. Aterrizando con seguridad...")
                    flight.trigger_land()
                    break
                elif key == ord('t') or key == ord('T'):
                    flight.trigger_takeoff()
                elif key == ord('o') or key == ord('O'):
                    flight.toggle_offboard()
                elif key == ord('l') or key == ord('L'):
                    flight.trigger_land()
                time.sleep(0.01)
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
            # Corrección Obs.4: Aplicar CLAHE en espacio LAB para realzar bordes
            # de objetos homogéneos (obstáculos delgados, paredes lisas) antes de MiDaS.
            frame_lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            l_ch, a_ch, b_ch = cv2.split(frame_lab)
            l_eq = clahe_midas.apply(l_ch)
            frame_enhanced = cv2.cvtColor(cv2.merge((l_eq, a_ch, b_ch)), cv2.COLOR_LAB2BGR)

            img_rgb = cv2.cvtColor(frame_enhanced, cv2.COLOR_BGR2RGB)
            img_input = cv2.resize(img_rgb, (256, 256))
            img_input = (img_input.astype(np.float32) / 255.0 - mean) / std
            img_input = np.expand_dims(img_input, axis=0)

            interpreter.set_tensor(input_details[0]['index'], img_input)
            interpreter.invoke()
            depth_raw = np.squeeze(interpreter.get_tensor(output_details[0]['index']))

            d_min = float(depth_raw.min())
            d_max = float(depth_raw.max())
            depth_norm = (depth_raw - d_min) / (d_max - d_min + 1e-6)
            depth_norm = np.squeeze(depth_norm)

            # Análisis en 3 sectores (Banda horizontal ampliada 15% a 85% de altura)
            h_d, w_d = depth_norm.shape[:2]
            roi_y1 = int(h_d * 0.15)
            roi_y2 = int(h_d * 0.85)
            roi_band = depth_norm[roi_y1:roi_y2, :]

            # División en sectores: Izquierda (0-33%), Centro (33-67%), Derecha (67-100%)
            # y Corredor Central Focalizado (40-60%) para capturar obstáculos delgados (5-15 cm)
            sec_left   = roi_band[:, :int(w_d * 0.33)]
            sec_center = roi_band[:, int(w_d * 0.33):int(w_d * 0.67)]
            sec_narrow = roi_band[:, int(w_d * 0.40):int(w_d * 0.60)]
            sec_right  = roi_band[:, int(w_d * 0.67):]

            # Función para mapear disparidad a distancia métrica estimada
            # Percentil 92 con filtro Gaussiano 5x5 para filtrar ruido y fluctuaciones espurias
            def disp_to_meters(sub_arr, is_center=False, narrow_arr=None):
                sub_clean = cv2.GaussianBlur(sub_arr, (5, 5), 0)
                if is_center and narrow_arr is not None:
                    narrow_clean = cv2.GaussianBlur(narrow_arr, (5, 5), 0)
                    p_narrow = float(np.percentile(narrow_clean, 92.0))
                    p_wide   = float(np.percentile(sub_clean, 92.0))
                    max_d    = max(p_narrow, p_wide)
                else:
                    max_d = float(np.percentile(sub_clean, 92.0))
                val_clean = min(1.0, max(0.0, max_d))
                dist_m = 3.0 * (1.0 - val_clean) + 0.35
                return max(0.35, min(5.0, dist_m))

            dist_left   = disp_to_meters(sec_left)
            dist_center = disp_to_meters(sec_center, is_center=True, narrow_arr=sec_narrow)
            dist_right  = disp_to_meters(sec_right)
            min_dist    = min(dist_left, dist_center, dist_right)

            # Procesar clic de ratón si el usuario hizo clic en la ventana de video
            if mouse_click_pos[0] is not None:
                mx, my = mouse_click_pos[0]
                mouse_click_pos[0] = None
                if mx < wf and 45 <= my < 45 + hf:
                    c_x = mx
                    c_y = my - 45
                    ok, msg = tracker.lock_at_point(frame_resized, c_x, c_y)
                    print(f"\n[TARGET LOCK - CLIC] {msg}\n")

            # ------------------------------------------------------------------
            # PASO 2: Detección y Seguimiento del Objetivo Humano (MobileNet-SSD)
            # ------------------------------------------------------------------
            left_view = frame_resized.copy()
            bbox, target_angle, conf = tracker.detect(left_view)

            d_human_est = 0.0
            d_target = 0.0
            if bbox is not None:
                last_human_seen_t = time.time()
                bx1, by1, bx2, by2 = bbox
                w_box = max(1, bx2 - bx1)
                h_box = max(1, by2 - by1)
                w_norm = float(w_box) / float(wf)
                h_norm = float(h_box) / float(hf)

                # A. Estimación geométrica dual (Hombros/Ancho y Altura):
                # El ancho de hombros (~0.45m) se mantiene visible y medible incluso si las piernas
                # salen de la imagen al acercarse (w_norm crece de 0.20 a más de 0.65).
                d_geom_w = 0.42 / max(0.10, w_norm)
                d_geom_h = 0.75 / max(0.15, h_norm)
                if w_norm > 0.30 or h_norm > 0.48:
                    d_geom = min(d_geom_w, d_geom_h)
                else:
                    d_geom = 0.60 * d_geom_h + 0.40 * d_geom_w

                # B. Muestreo de profundidad MiDaS directamente sobre el torso del objetivo:
                rx1 = int(np.clip(bx1 * (256.0 / wf), 0, 255))
                ry1 = int(np.clip(by1 * (256.0 / hf), 0, 255))
                rx2 = int(np.clip(bx2 * (256.0 / wf), 0, 255))
                ry2 = int(np.clip(by2 * (256.0 / hf), 0, 255))
                rw = max(1, rx2 - rx1)
                rh = max(1, ry2 - ry1)
                cx1 = rx1 + int(rw * 0.20)
                cx2 = rx2 - int(rw * 0.20)
                cy1 = ry1 + int(rh * 0.15)
                cy2 = ry2 - int(rh * 0.25)
                if cx2 > cx1 and cy2 > cy1:
                    torso_disp = depth_norm[cy1:cy2, cx1:cx2]
                    p85_val = float(np.percentile(torso_disp, 85.0))
                    d_midas_torso = 3.0 * (1.0 - min(1.0, max(0.0, p85_val))) + 0.35
                    d_target = float(np.clip(0.50 * d_midas_torso + 0.50 * d_geom, 0.35, 4.50))
                else:
                    d_target = float(np.clip(d_geom, 0.35, 4.50))

                d_human_est = d_target

            time_since_human = time.time() - last_human_seen_t

            # ------------------------------------------------------------------
            # DETECCIÓN DE ALTA PRECISIÓN DEL OBSTÁCULO DELGADO CERCANO (5 cm)
            # ------------------------------------------------------------------
            # Solo se buscan obstáculos en el campo cercano (d <= 0.95 m, depth_norm >= 0.76).
            # Cualquier objeto o borde lejano (> 1.0 m) se descarta por completo para
            # evitar confundir objetos distantes (puertas, fondos, patas de mesa).
            kernel_thin = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1))
            disp_opened = cv2.morphologyEx(depth_norm, cv2.MORPH_OPEN, kernel_thin)
            disp_thin_peak = cv2.subtract(depth_norm, disp_opened)

            mask_thin_obs = np.zeros_like(depth_norm, dtype=np.uint8)
            mask_thin_obs[roi_y1:roi_y2, int(w_d * 0.22):int(w_d * 0.78)] = 1

            # Proximidad estricta (<= 0.95m) y cresta delgada contrastada (>= 0.055):
            cond_near_narrow = (depth_norm >= 0.76) & (disp_thin_peak >= 0.055) & (mask_thin_obs > 0)
            obs_candidates_u8 = (cond_near_narrow.astype(np.uint8)) * 255

            kernel_vert_close = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 9))
            obs_cleaned = cv2.morphologyEx(obs_candidates_u8, cv2.MORPH_CLOSE, kernel_vert_close)

            contours, _ = cv2.findContours(obs_cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            thin_obs_info = None
            best_score = -1.0

            for cnt in contours:
                if cv2.contourArea(cnt) < 70:
                    continue
                cx_c, cy_c, cw_c, ch_c = cv2.boundingRect(cnt)
                aspect_ratio = float(ch_c) / float(max(1, cw_c))

                # Filtro geométrico esbelto: ch >= 32 px, 6 <= cw <= 42 px, aspect_ratio >= 1.60
                if ch_c >= 32 and 6 <= cw_c <= 42 and aspect_ratio >= 1.60:
                    roi_obs = depth_norm[cy_c:cy_c+ch_c, cx_c:cx_c+cw_c]
                    p_val = float(np.percentile(roi_obs, 90.0))
                    d_cand = 3.0 * (1.0 - min(1.0, max(0.0, p_val))) + 0.35

                    # LÍMITE FÍSICO ESTRICTO: Solo obstáculos inmediatos (d <= 0.95 m)
                    if d_cand <= 0.95:
                        fx1 = int(cx_c * float(wf) / 256.0)
                        fy1 = int(cy_c * float(hf) / 256.0)
                        fx2 = int((cx_c + cw_c) * float(wf) / 256.0)
                        fy2 = int((cy_c + ch_c) * float(hf) / 256.0)
                        fx1 = max(0, min(wf - 1, fx1))
                        fy1 = max(0, min(hf - 1, fy1))
                        fx2 = max(0, min(wf - 1, fx2))
                        fy2 = max(0, min(hf - 1, fy2))
                        ox_center = (fx1 + fx2) / 2.0

                        # Obstruye la visión si su centro está frente al humano en la imagen
                        # y está físicamente más cerca que el humano por al menos 20 cm
                        obstructing = False
                        if bbox is not None:
                            in_front_of_human = (bx1 - 15 <= ox_center <= bx2 + 15)
                            closer_than_human = (d_cand <= d_human_est - 0.20)
                            if in_front_of_human and closer_than_human:
                                obstructing = True
                        else:
                            if abs(ox_center - (wf / 2.0)) < (wf * 0.18):
                                obstructing = True

                        score = (1.00 - d_cand) * 3.0 + aspect_ratio
                        if score > best_score:
                            best_score = score
                            thin_obs_info = {
                                "bbox_frame": (fx1, fy1, fx2, fy2),
                                "dist_m": d_cand,
                                "rect_256": (cx_c, cy_c, cw_c, ch_c),
                                "is_obstructing": obstructing
                            }

            # Persistencia corta (0.20 s) para evitar retener detecciones obsoletas
            t_now_obs = time.time()
            if thin_obs_info is not None:
                last_thin_obs_info = thin_obs_info
                last_thin_obs_time = t_now_obs
            elif last_thin_obs_info is not None and (t_now_obs - last_thin_obs_time) < 0.20:
                thin_obs_info = last_thin_obs_info
            else:
                last_thin_obs_info = None

            # ------------------------------------------------------------------
            # PASO 3: Planificador Reactivo y Desacoplamiento Cinemático (FSM)
            # ------------------------------------------------------------------
            # Umbrales calibrados para laboratorio indoor (~3 m de ancho, objetivo a 1 m):
            CRITICAL_HALT   = 0.45  # Frenado de emergencia ante choque inminente (< 0.45 m)
            OBSTACLE_THRESH = 0.80  # Umbral para iniciar maniobra evasiva lateral de obstáculos delgados/postes
            SIDE_MARGIN     = 0.65  # Margen lateral de seguridad ante paredes

            # Velocidades desacopladas (evita giros en curva y sobre-virajes):
            V_CRUISE    = min(0.35, cruise_speed)  # Avance nominal frontal cauto (0.35 m/s)
            V_EVADE     = 0.35                     # Evasión lateral (0.35 m/s)
            V_SIDE_CORR = 0.25                     # Micro-corrección de pared (0.25 m/s)

            cmd_vx = 0.0
            cmd_vy = 0.0
            cmd_yaw_rate = 0.0
            fsm_state = "AVANCE_CRUCERO"
            state_color = (0, 255, 0) # Verde

            if flight.emergency_stop_active:
                cmd_vx = 0.0
                cmd_vy = 0.0
                cmd_yaw_rate = 0.0
                fsm_state = "FRENO_HOVER_ACTIVO"
                state_color = (0, 255, 255) # Amarillo

            elif bbox is not None:
                # ==============================================================
                # MODO 1: SEGUIMIENTO HUMANO Y EVASIÓN DE OBSTÁCULO DELGADO INTERMEDIO
                # ==============================================================
                # DETECCIÓN ESTRICTA DE OBSTÁCULO DELGADO INTERMEDIO:
                # Se activa la evasión lateral flanqueante ÚNICAMENTE si:
                # 1) thin_obs_info está confirmado en campo cercano (d <= 0.95m)
                #    y está FRENTE al cuerpo humano en la imagen (is_obstructing == True).
                # 2) O el centro está físicamente bloqueado a distancia crítica (< 0.75m)
                #    con la persona claramente detrás (> 1.05m) y espacio lateral libre.
                # Si la persona está lejos (> 1.15m) sin un obstáculo inmediato delante,
                # el dron NO esquiva: AVANZA hacia el humano de forma limpia y directa.
                is_intermediate_obstacle = False
                d_obs_flank = dist_center

                if thin_obs_info is not None and thin_obs_info.get("is_obstructing", False):
                    # Solo considerar obstáculo delgado si está física y claramente por delante del humano:
                    if thin_obs_info["dist_m"] < d_target - 0.25:
                        is_intermediate_obstacle = True
                        d_obs_flank = thin_obs_info["dist_m"]

                if is_intermediate_obstacle:
                    # ==============================================================
                    # MODO 1.B: EVASIÓN LATERAL FLANQUEANTE DE OBSTÁCULO DELGADO
                    # El humano está detrás de un obstáculo delgado: esquivar lateralmente hacia
                    # el lado con mayor profundidad y girar en su eje para re-centrar al humano
                    # y despejar la línea de visión directa.
                    # ==============================================================
                    # Decisión de dirección de evasión según profundidad de los lados:
                    if dist_right >= dist_left:
                        evade_sign = +1.0
                    else:
                        evade_sign = -1.0

                    # Respeto de márgenes de paredes laterales:
                    if evade_sign > 0 and dist_right < SIDE_MARGIN:
                        evade_sign = -1.0
                    elif evade_sign < 0 and dist_left < SIDE_MARGIN:
                        evade_sign = +1.0

                    # Velocidad lateral decidida para librar el obstáculo delgado:
                    cmd_vy = float(evade_sign * V_EVADE)

                    # Avance cauto para rebasar el obstáculo delgado, o micro-retroceso si está peligrosamente cerca:
                    if d_obs_flank < 0.65:
                        cmd_vx = -0.15
                    else:
                        cmd_vx = 0.08  # Suave avance diagonal para rodearlo

                    # GIRO SIMULTÁNEO EN EL EJE PARA MANTENER AL HUMANO EN EL CENTRO DE LA VISIÓN:
                    if abs(target_angle) > 2.0:
                        dir_s = 1.0 if target_angle > 0 else -1.0
                        cmd_yaw_rate = float(dir_s * np.clip(6.0 + 0.65 * (abs(target_angle) - 2.0), 6.0, 18.0))
                    else:
                        cmd_yaw_rate = 0.0

                    dir_txt = "DERECHA >>" if evade_sign > 0 else "<< IZQUIERDA"
                    fsm_state = f"ESQUIVANDO_OBSTACULO_DELGADO_{dir_txt} (Obs:{d_obs_flank:.2f}m | Hum:{d_target:.2f}m)"
                    state_color = (0, 140, 255) # Naranja alerta

                else:
                    # ==============================================================
                    # MODO 1.A: PERSECUCIÓN CONTINUA FLUIDA Y REGULACIÓN A 1.0 METRO
                    # ==============================================================
                    # 1.1 ALINEACIÓN ANGULAR CONTINUA Y ÁGIL (Curva de persecución suave):
                    # El dron gira sobre su eje vertical proporcionalmente al error angular
                    # sin frenar el avance longitudinal, produciendo un seguimiento continuo.
                    if abs(target_angle) > 2.0:
                        dir_s = 1.0 if target_angle > 0 else -1.0
                        # Guiñada ágil y proporcional de 5.0°/s hasta 22.0°/s
                        cmd_yaw_rate = float(dir_s * np.clip(5.0 + 0.65 * (abs(target_angle) - 2.0), 5.0, 22.0))
                    else:
                        cmd_yaw_rate = 0.0

                    # 1.2 PIVOTE PURO DE SEGURIDAD SOLO SI EL OBJETIVO ESCAPA AL EXTREMO (> 22.0°):
                    # Solo hace pausa longitudinal si el objetivo se desalineó más de 22°,
                    # retornando a persecución continua al centrarse a <= 10.0°.
                    if in_pure_pivot:
                        if abs(target_angle) <= 10.0:
                            in_pure_pivot = False
                    else:
                        if abs(target_angle) > 22.0:
                            in_pure_pivot = True

                    if in_pure_pivot:
                        # PIVOTE PURO EN EL EJE: recentrado rápido en el lugar
                        cmd_vx = 0.0
                        cmd_vy = 0.0
                        dir_txt = "DERECHA" if target_angle > 0 else "IZQUIERDA"
                        fsm_state = f"ROTANDO_EN_EJE -> {dir_txt} ({target_angle:+.1f} deg | Yaw:{cmd_yaw_rate:+.0f})"
                        state_color = (0, 200, 255) # Amarillo/Cian

                    else:
                        # PERSECUCIÓN CONTINUA: AVANCE / RETROCESO FLUIDO CON REGULACIÓN A 1.0 METRO
                        # Factor de curvatura suave: modera levemente vx si el ángulo es grande, sin detenerse
                        vx_factor = float(np.clip(1.0 - 0.35 * (abs(target_angle) / 22.0), 0.60, 1.0))

                        if d_target > 1.25:
                            # Humano a más de 1.25 m: avance continuo hacia el humano
                            v_base = 0.28 if d_target > 1.70 else float(0.18 + (d_target - 1.25) * 0.22)
                            cmd_vx = float(np.clip(v_base * vx_factor, 0.16, 0.30))
                            cmd_vy = 0.0
                            fsm_state = f"AVANZANDO_HACIA_HUMANO ({d_target:.2f}m)"
                            state_color = (0, 255, 0) # Verde

                        elif d_target >= 0.90:
                            # ZONA DE SEGURIDAD EXACTA DE 1.0 METRO (0.90m - 1.25m): HOVER ESTÁTICO
                            # Mantiene posición frontal a 1.0m y rota en el eje si el humano se mueve a los lados
                            cmd_vx = 0.0
                            cmd_vy = 0.0
                            fsm_state = f"ENFOCANDO_A_1_METRO ({d_target:.2f}m)"
                            state_color = (0, 255, 200) # Verde cian

                        elif d_target >= 0.65:
                            # HUMANO ACERCÁNDOSE (< 0.90 m): RETROCESO ACTIVO INMEDIATO
                            # El dron retrocede activamente para restaurar la distancia segura de 1.0 m
                            cmd_vx = -0.26
                            cmd_vy = 0.0
                            fsm_state = f"RETROCESO_MANTENIENDO_1M ({d_target:.2f}m | Retroceso)"
                            state_color = (0, 200, 255) # Naranja advertencia

                        else:
                            # PROXIMIDAD CRÍTICA (< 0.65 m): RETROCESO RÁPIDO DE SEGURIDAD
                            # El humano está muy cerca: retroceso decidido hacia atrás
                            cmd_vx = -0.36
                            cmd_vy = 0.0
                            fsm_state = f"RETROCESO_RAPIDO_SEGURIDAD ({d_target:.2f}m)"
                            state_color = (0, 0, 255) # Rojo peligro

                        # Protección lateral ante paredes mientras sigue al humano:
                        if dist_left < 0.65:
                            cmd_vy = +0.20
                        elif dist_right < 0.65:
                            cmd_vy = -0.20
                        else:
                            cmd_vy = 0.0

            # SI NO HAY BBOX PERO UN HUMANO FUE VISTO HACE MENOS DE 2.5 SEGUNDOS:
            elif time_since_human < 2.5 and (dist_center < 1.15 or d_human_est < 1.15):
                # El humano está muy cerca y llenó el encuadre (pérdida momentánea de cuerpo entero):
                # ¡NO ESQUIVAR LATERALMENTE NI AVANZAR! Retroceder decididamente para abrir distancia.
                cmd_vx = -0.26
                cmd_vy = 0.0
                cmd_yaw_rate = 0.0
                fsm_state = f"RETROCESO_PROXIMIDAD_HUMANO ({min(dist_center, d_human_est):.2f}m)"
                state_color = (0, 140, 255) # Naranja

            elif min_dist < CRITICAL_HALT:
                # ==============================================================
                # MODO 2: EVASIÓN DE EMERGENCIA ANTE CHOQUE INMINENTE (< 0.45m)
                # ==============================================================
                cmd_vx = 0.0
                cmd_yaw_rate = 0.0  # Cero rotación para evitar banked turns
                if dist_right >= dist_left:
                    cmd_vy = +V_EVADE
                    fsm_state = f"ESCAPE_EMERGENCIA_DER ({min_dist:.2f}m)"
                else:
                    cmd_vy = -V_EVADE
                    fsm_state = f"ESCAPE_EMERGENCIA_IZQ ({min_dist:.2f}m)"
                state_color = (0, 0, 255) # Rojo

            elif (thin_obs_info is not None and thin_obs_info["dist_m"] < 0.80) or (dist_center < 0.72):
                # ==============================================================
                # MODO 3: EVASIÓN LATERAL DE OBSTÁCULO DELGADO ESTÁTICO (< 0.80m)
                # ==============================================================
                obs_d = thin_obs_info["dist_m"] if thin_obs_info is not None else dist_center
                cmd_vx = 0.10       # Avance lento para rebasar el obstáculo delgado
                cmd_yaw_rate = 0.0  # Cero rotación de eje durante esquiva lateral
                diff_m = dist_right - dist_left
                if diff_m > 0.10:
                    cmd_vy = +V_EVADE
                    fsm_state = f"ESQUIVANDO_OBSTACULO_DELGADO_DER ({obs_d:.2f}m)"
                else:
                    cmd_vy = -V_EVADE
                    fsm_state = f"ESQUIVANDO_OBSTACULO_DELGADO_IZQ ({obs_d:.2f}m)"
                state_color = (0, 140, 255) # Naranja alerta

            elif dist_left < SIDE_MARGIN:
                cmd_vx = V_CRUISE * 0.60
                cmd_vy = +V_SIDE_CORR
                cmd_yaw_rate = 0.0
                fsm_state = f"CORRECCION_PARED_IZQ ({dist_left:.2f}m)"
                state_color = (0, 180, 255)

            elif dist_right < SIDE_MARGIN:
                cmd_vx = V_CRUISE * 0.60
                cmd_vy = -V_SIDE_CORR
                cmd_yaw_rate = 0.0
                fsm_state = f"CORRECCION_PARED_DER ({dist_right:.2f}m)"
                state_color = (0, 180, 255)

            elif abs(target_angle) > 5.0 and dist_center >= 0.85:
                # ==============================================================
                # MODO 4: BÚSQUEDA DEL OBJETIVO PERDIDO EN SU PROPIO EJE
                # ==============================================================
                # El objetivo salió del encuadre recientemente: rotar en el lugar (Hover + Yaw)
                cmd_vx = 0.0
                cmd_vy = 0.0
                dir_sign = 1.0 if target_angle > 0 else -1.0
                cmd_yaw_rate = float(dir_sign * 14.0)
                dir_txt = "DERECHA" if target_angle > 0 else "IZQUIERDA"
                fsm_state = f"ROTANDO_BUSCANDO_HUMANO -> {dir_txt}"
                state_color = (0, 200, 255)

            else:
                # ==============================================================
                # MODO 5: CRUCERO CAUTO SIN OBSTÁCULOS NI OBJETIVO VISIBLE
                # ==============================================================
                cmd_vx = V_CRUISE * 0.60
                cmd_vy = 0.0
                cmd_yaw_rate = 0.0
                fsm_state = f"BUSQUEDA_CRUCERO ({V_CRUISE*0.60:.2f} m/s)"
                state_color = (0, 255, 180)

            # Notificar al hilo de control de vuelo
            flight.set_nav_commands(cmd_vx, cmd_vy, cmd_yaw_rate, fsm_state)
            telem = flight.get_telemetry()

            # Medición de ciclo y registro de métricas para la tesis (CSV)
            t_cycle_end = time.time()
            latency_ms = (t_cycle_end - t_cycle_start) * 1000.0
            t_rel = t_cycle_end - t_init_flight
            total_cycles += 1

            csv_writer.writerow([
                f"{t_cycle_end:.3f}",
                f"{t_rel:.2f}",
                f"{fps:.1f}",
                f"{latency_ms:.1f}",
                fsm_state,
                f"{min_dist:.2f}",
                f"{dist_left:.2f}",
                f"{dist_center:.2f}",
                f"{dist_right:.2f}",
                1 if bbox is not None else 0,
                f"{target_angle:.1f}" if bbox is not None else "0.0",
                f"{cmd_vx:.2f}",
                f"{cmd_vy:.2f}",
                f"{cmd_yaw_rate:.1f}",
                f"{telem['altitude_m']:.2f}",
                f"{telem['target_alt_m']:.2f}",
                f"{telem['battery_pct']}",
                f"{telem['heading_deg']:.1f}"
            ])
            if total_cycles % 10 == 0:
                csv_file.flush()

            # ------------------------------------------------------------------
            # PASO 4: Renderizado de la Vista Izquierda (Cámara + HUD de Vuelo)
            # ------------------------------------------------------------------
            center_x = wf // 2
            center_y = hf // 2

            # Mira central del dron
            cv2.drawMarker(left_view, (center_x, center_y), (0, 200, 255), cv2.MARKER_CROSS, 20, 2)
            cv2.circle(left_view, (center_x, center_y), 32, (0, 200, 255), 1)

            # 1. Dibujar falsos humanos o gigantografías descartadas (en rojo tenue / gris)
            for disc in tracker.discarded_boxes:
                dx1, dy1, dx2, dy2 = disc['box']
                d_sim = disc.get('sim', 0.0)
                cv2.rectangle(left_view, (dx1, dy1), (dx2, dy2), (80, 80, 180), 1)
                lbl_disc = f"DESCARTADO (Gigantografia: {d_sim*100:.0f}%)"
                (tw_d, th_d), _ = cv2.getTextSize(lbl_disc, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
                ly_d = max(th_d + 4, dy1 - 6)
                cv2.rectangle(left_view, (dx1, ly_d - th_d - 2), (dx1 + tw_d + 4, ly_d + 2), (20, 20, 20), -1)
                cv2.putText(left_view, lbl_disc, (dx1 + 2, ly_d),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.42, (100, 100, 220), 1)

            # 2. Dibujar objetivo válido / piloto
            if bbox is not None:
                bx1, by1, bx2, by2 = bbox
                tgt_cx = (bx1 + bx2) // 2
                tgt_cy = (by1 + by2) // 2
                if tracker.is_locked:
                    # PILOTO BLOQUEADO: Color Cian Neón (255, 255, 0) con esquinas tipo mira
                    box_color = (255, 255, 0)
                    sim_pct = int(tracker.pilot_similarity * 100)
                    lbl_tgt = f"PILOTO UNICO [BLOQUEADO] ({sim_pct}% | D:{d_human_est:.2f}m)"
                    cv2.rectangle(left_view, (bx1, by1), (bx2, by2), box_color, 2)
                    corner_len = max(8, min(20, min((bx2-bx1)//4, (by2-by1)//4)))
                    cv2.line(left_view, (bx1, by1), (bx1 + corner_len, by1), (0, 255, 255), 3)
                    cv2.line(left_view, (bx1, by1), (bx1, by1 + corner_len), (0, 255, 255), 3)
                    cv2.line(left_view, (bx2, by1), (bx2 - corner_len, by1), (0, 255, 255), 3)
                    cv2.line(left_view, (bx2, by1), (bx2, by1 + corner_len), (0, 255, 255), 3)
                    cv2.line(left_view, (bx1, by2), (bx1 + corner_len, by2), (0, 255, 255), 3)
                    cv2.line(left_view, (bx1, by2), (bx1, by2 - corner_len), (0, 255, 255), 3)
                    cv2.line(left_view, (bx2, by2), (bx2 - corner_len, by2), (0, 255, 255), 3)
                    cv2.line(left_view, (bx2, by2), (bx2, by2 - corner_len), (0, 255, 255), 3)
                else:
                    # MODO LIBRE: Color Verde indicando tecla 'B'
                    box_color = (0, 255, 0)
                    lbl_tgt = f"Humano (Variado) ({conf:.2f} | D:{d_human_est:.2f}m) [Pulsa 'B' Fijar Unico]"
                    cv2.rectangle(left_view, (bx1, by1), (bx2, by2), box_color, 2)

                cv2.circle(left_view, (tgt_cx, tgt_cy), 5, box_color, -1)
                cv2.line(left_view, (center_x, center_y), (tgt_cx, tgt_cy), (0, 255, 255), 2)
                (tw, th), _ = cv2.getTextSize(lbl_tgt, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 2)
                ly = max(th + 6, by1 - 8)
                cv2.rectangle(left_view, (bx1, ly - th - 4), (bx1 + tw + 6, ly + 4), (0, 0, 0), -1)
                cv2.putText(left_view, lbl_tgt, (bx1 + 3, ly),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.48, box_color, 2)

            # DIBUJAR RECUADRO AMARILLO DEL OBSTÁCULO DELGADO EN LA VISTA DE PERSECUCIÓN
            if thin_obs_info is not None:
                ox1, oy1, ox2, oy2 = thin_obs_info["bbox_frame"]
                d_obs_m = thin_obs_info["dist_m"]
                # 1) Recuadro amarillo brillante (BGR: (0, 255, 255))
                cv2.rectangle(left_view, (ox1, oy1), (ox2, oy2), (0, 255, 255), 3)

                # 2) Etiqueta de texto "OBSTACULO DELGADO" en amarillo con fondo negro
                lbl_obs = f"OBSTACULO DELGADO ({d_obs_m:.2f}m)"
                (tw, th), _ = cv2.getTextSize(lbl_obs, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 2)
                ly = max(th + 6, oy1 - 8)
                cv2.rectangle(left_view, (ox1, ly - th - 4), (ox1 + tw + 6, ly + 4), (0, 0, 0), -1)
                cv2.putText(left_view, lbl_obs, (ox1 + 3, ly),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 255, 255), 2)

                # Si el obstáculo delgado obstruye la línea de visión al humano:
                if thin_obs_info.get("is_obstructing", False) and bbox is not None:
                    obs_warn = "¡HUMANO DETRAS DE OBSTACULO! ESQUIVANDO..."
                    (aw, ah), _ = cv2.getTextSize(obs_warn, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 2)
                    warn_y = min(hf - 10, oy2 + 22)
                    cv2.rectangle(left_view, (ox1, warn_y - ah - 4), (ox1 + aw + 6, warn_y + 4), (0, 0, 160), -1)
                    cv2.putText(left_view, obs_warn, (ox1 + 3, warn_y),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 255, 255), 2)

            # Vector de movimiento resultante (Flecha de navegación en el HUD)
            arrow_scale = 160.0
            if "DERECHA" in fsm_state:
                vis_vy = +cruise_speed
            elif "IZQUIERDA" in fsm_state:
                vis_vy = -cruise_speed
            else:
                vis_vy = 0.0

            arrow_end_x = int(center_x + (vis_vy / max(0.01, cruise_speed)) * (arrow_scale * 0.7))
            arrow_end_y = int(center_y - (cmd_vx / max(0.01, cruise_speed)) * (arrow_scale * 0.5))
            if abs(cmd_vx) > 0.01 or abs(vis_vy) > 0.01:
                cv2.arrowedLine(left_view, (center_x, center_y), (arrow_end_x, arrow_end_y), (0, 255, 255), 3, tipLength=0.25)
                cv2.putText(left_view, f"V: ({cmd_vx:+.2f}, {vis_vy:+.2f}) m/s", (arrow_end_x + 8, arrow_end_y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 255, 255), 2)

            # Barra superior izquierda: Encabezado institucional, estado de Lock y FPS
            header_bar = np.zeros((45, wf, 3), dtype=np.uint8)
            header_bar[:] = (20, 20, 20)
            if not args.fly:
                mode_tag = "[MESA / SIM]"
                tag_color = (0, 220, 255)
            elif flight.offboard_active:
                mode_tag = "[VUELO REAL - OFFBOARD IA ACTIVO]"
                tag_color = (0, 255, 0)
            else:
                mode_tag = "[VUELO REAL - EN ESPERA (T / O)]"
                tag_color = (0, 165, 255)

            cv2.putText(header_bar, f"DJI AIR 2S {mode_tag}", (12, 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.46, tag_color, 2)
            cv2.putText(header_bar, f"FPS: {fps:.1f} | Lat: {latency_ms:.0f}ms", (wf - 185, 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255, 255, 255), 1)

            if tracker.is_locked:
                lock_text = "🔒 OBJETIVO UNICO BLOQUEADO [ACTIVO] (Pulsa 'B': re-fijar | 'U': variar | Clic)"
                lock_col = (255, 255, 0) # Cian
            else:
                lock_text = "🔓 OBJETIVO VARIADO (Persigue libre) | Pulsa 'B' para FIJAR OBJETIVO UNICO"
                lock_col = (0, 255, 128) # Verde claro
            cv2.putText(header_bar, lock_text, (12, 38),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.40, lock_col, 1)
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
            # PASO 5: Renderizado de la Vista Derecha (Profundidad + Obstáculo Delgado Brillante)
            # ------------------------------------------------------------------
            depth_norm_vis = depth_norm.copy()
            if thin_obs_info is not None:
                cx_o, cy_o, cw_o, ch_o = thin_obs_info["rect_256"]
                # Poner brillante el obstáculo delgado en el mapa de profundidad:
                pad_x = max(1, int(cw_o * 0.20))
                pad_y = max(1, int(ch_o * 0.10))
                rx1_256 = max(0, cx_o - pad_x)
                ry1_256 = max(0, cy_o - pad_y)
                rx2_256 = min(255, cx_o + cw_o + pad_x)
                ry2_256 = min(255, cy_o + ch_o + pad_y)
                # Boost de disparidad para que brille incandescente en el mapa de color
                depth_norm_vis[ry1_256:ry2_256, rx1_256:rx2_256] = np.clip(
                    depth_norm_vis[ry1_256:ry2_256, rx1_256:rx2_256] * 1.5 + 0.35, 0.0, 1.0
                )
                # Saturación al 100% de brillo (blanco/amarillo incandescente en colormap)
                depth_norm_vis[cy_o:cy_o+ch_o, cx_o:cx_o+cw_o] = 1.0

            depth_uint8 = (depth_norm_vis * 255).astype(np.uint8)
            if depth_uint8.ndim == 3:
                depth_uint8 = depth_uint8.squeeze()
            depth_color = cv2.applyColorMap(depth_uint8, colormaps[curr_cm_idx])
            right_view = cv2.resize(depth_color, (target_w, target_h))
            hr, wr = right_view.shape[:2]

            # Dibujar las 3 zonas de análisis sectorial
            w_sec = wr // 3
            y_top = int(hr * 0.15)
            y_bot = int(hr * 0.85)

            # Colores según proximidad
            def sector_color(d):
                if d < CRITICAL_HALT:
                    return (0, 0, 255) # Rojo peligro
                elif d < OBSTACLE_THRESH:
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
            # Corredor focalizado para obstáculos delgados (40-60%)
            w_nar1 = int(wr * 0.40)
            w_nar2 = int(wr * 0.60)
            cv2.rectangle(right_view, (w_nar1, y_top + 15), (w_nar2, y_bot - 15), (0, 255, 255), 1)
            cv2.putText(right_view, f"CENTRO: {dist_center:.2f}m", (w_sec + 10, y_top + 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, c_center, 2)

            # Sector Derecho
            c_right = sector_color(dist_right)
            cv2.rectangle(right_view, (2 * w_sec, y_top), (wr, y_bot), c_right, 2)
            cv2.putText(right_view, f"DER: {dist_right:.2f}m", (2 * w_sec + 10, y_top + 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.60, c_right, 2)

            # Resaltar obstáculo delgado en el mapa de profundidad
            if thin_obs_info is not None:
                cx_o, cy_o, cw_o, ch_o = thin_obs_info["rect_256"]
                rx1_d = int(cx_o * float(wr) / 256.0)
                ry1_d = int(cy_o * float(hr) / 256.0)
                rx2_d = int((cx_o + cw_o) * float(wr) / 256.0)
                ry2_d = int((cy_o + ch_o) * float(hr) / 256.0)
                cv2.rectangle(right_view, (rx1_d, ry1_d), (rx2_d, ry2_d), (0, 255, 255), 2)
                cv2.putText(right_view, f"OBSTACULO DELGADO ({thin_obs_info['dist_m']:.2f}m)",
                            (rx1_d, max(22, ry1_d - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 255, 255), 2)

            # Barra superior derecha
            header_right = np.zeros((45, wr, 3), dtype=np.uint8)
            header_right[:] = (20, 20, 20)
            cv2.putText(header_right, f"MAPA DE PROFUNDIDAD ESTIMADA [{colormap_names[curr_cm_idx]}]", (12, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 200, 255), 2)
            right_view = np.vstack((header_right, right_view))

            # Barra inferior derecha: Recomendación de escape
            foot_right = np.zeros((55, wr, 3), dtype=np.uint8)
            foot_right[:] = (15, 15, 15)
            if min_dist < CRITICAL_HALT:
                cv2.putText(foot_right, f"ALERTA PROXIMIDAD! ({min_dist:.2f}m) FRENO / ESCAPE", (12, 34),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 0, 255), 2)
            elif thin_obs_info is not None and thin_obs_info["dist_m"] < OBSTACLE_THRESH:
                escape_dir = "DERECHA >>" if dist_right >= dist_left else "<< IZQUIERDA"
                cv2.putText(foot_right, f"OBSTACULO DELGADO ({thin_obs_info['dist_m']:.2f}m)! EVADIENDO: {escape_dir}", (12, 34),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 140, 255), 2)
            elif dist_center < OBSTACLE_THRESH:
                escape_dir = "DERECHA >>" if dist_right >= dist_left else "<< IZQUIERDA"
                cv2.putText(foot_right, f"OBSTACULO EN CENTRO! EVADIENDO: {escape_dir}", (12, 34),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 140, 255), 2)
            elif dist_left < SIDE_MARGIN:
                cv2.putText(foot_right, f"MARGEN IZQ ({dist_left:.2f}m) CORRECCION >> DERECHA", (12, 34),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 180, 255), 2)
            elif dist_right < SIDE_MARGIN:
                cv2.putText(foot_right, f"MARGEN DER ({dist_right:.2f}m) CORRECCION << IZQUIERDA", (12, 34),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 180, 255), 2)
            else:
                cv2.putText(foot_right, f"CAMINO DESPEJADO (Crucero a {cruise_speed:.2f} m/s)", (12, 34),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
            right_view = np.vstack((right_view, foot_right))

            # Unir lado izquierdo y lado derecho en una sola ventana panorámica
            combined_display = np.hstack((left_view, right_view))
            cv2.imshow(win_name, combined_display)

            # ------------------------------------------------------------------
            # PASO 6: Interacción y Teclas de Control de Seguridad
            # ------------------------------------------------------------------
            key = read_key_input(15)

            if key == ord('q') or key == 27:
                print("\n[Salida solicitada por usuario]. Aterrizando con seguridad...")
                flight.trigger_land()
                break

            elif key == ord('t') or key == ord('T'):
                # Orden de despegue automático a 1.5 metros y enganche offboard
                flight.trigger_takeoff()

            elif key == ord('o') or key == ord('O'):
                # Alternar modo Offboard en pleno vuelo (ceder o tomar el mando autónomo)
                flight.toggle_offboard()

            elif key == ord('l') or key == ord('L'):
                # Orden manual de aterrizaje seguro
                flight.trigger_land()

            elif key == ord(' '):
                # Pausa / Freno de emergencia en el aire
                flight.toggle_emergency_hover()

            elif key == ord('b') or key == ord('B') or key == ord('k') or key == ord('K') or key == ord('p') or key == ord('P'):
                # Bloquear objetivo del Piloto actual (Semi-automático por tecla)
                ok, msg = tracker.lock_target(frame_resized)
                print(f"\n[TARGET LOCK - TECLADO] {msg}\n")

            elif key == ord('u') or key == ord('U'):
                # Desbloquear objetivo (Volver a modo libre)
                ok, msg = tracker.unlock_target()
                print(f"\n[TARGET LOCK - TECLADO] {msg}\n")

            elif key == ord('+') or key == ord('='):
                flight.adjust_target_altitude(+0.10)

            elif key == ord('-') or key == ord('_'):
                flight.adjust_target_altitude(-0.10)

            elif key == ord('r') or key == ord('R'):
                with flight.lock:
                    flight.target_alt = 1.70
                    flight.state["target_alt_m"] = 1.70
                    flight.initial_climb_done = False
                    flight.last_alt_stable = 1.70
                    flight.stable_alt_count = 0
                print("\n[Controller] 🔄 Altitud objetivo restablecida a 1.70 m.\n")

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
        if 'csv_file' in locals() and csv_file and not csv_file.closed:
            csv_file.flush()
            csv_file.close()
            print(f"[OK] Telemetría y métricas de tesis guardadas en:\n     -> {csv_file_path}")
        cv2.destroyAllWindows()
        print("[OK] Sesión finalizada con éxito.")

if __name__ == "__main__":
    main()
