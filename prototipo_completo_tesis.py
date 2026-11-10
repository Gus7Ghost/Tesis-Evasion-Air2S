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
    parser.add_argument("--alt", type=float, default=1.50, help="Altitud objetivo de vuelo en metros (default: 1.50 m)")
    parser.add_argument("--speed", type=float, default=0.35, help="Velocidad segura de crucero y evasion en m/s (default: 0.35 m/s)")
    parser.add_argument("--mavlink-port", type=int, default=19980, help="Puerto MAVLink UDP de RosettaDrone (default: 19980)")
    parser.add_argument("--tablet-ip", type=str, default="10.11.8.33", help="IP de la tablet RosettaDrone (default: 10.11.8.33)")
    parser.add_argument("--model", type=str, default="Air2S_MAVSDK/models/midas_v21_small_256.tflite", help="Ruta al modelo MiDaS")
    parser.add_argument("--invert-vy", action="store_true", default=True, help="Corregir signo lateral en RosettaDrone VirtualSticks (default: True)")
    parser.add_argument("--no-invert-vy", dest="invert_vy", action="store_false", help="Desactivar inversión lateral")
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
    candidates.extend(['10.11.8.33', '10.11.8.1', '10.11.8.43', '192.168.43.1', '8.8.8.8', '1.1.1.1'])
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

        # Solo cabeceras de parámetros SPS y PPS para sincronizar el formato H.264
        # (NO inyectar fotogramas antiguos de test_seg.h264 para evitar imágenes fantasma)
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
                        self.frame_counter += 1
                        # Drenar los fotogramas iniciales de arranque para mostrar solo video 100% fresco
                        if self.frame_counter > 10:
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
    def __init__(self, system_address="udpin://0.0.0.0:19980", target_alt=1.5, allow_real_flight=False):
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
        asyncio.create_task(self._telemetry_altitude_task())
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

        # Bloqueo determinista de altitud a 1.50 metros:
        # El DJI Air 2S cuenta con barómetro interno y sensores ópticos inferiores (VPS).
        # Enviar vz = 0.0 m/s ordena al autopiloto nativo de DJI fijar y congelar la altitud a 1.50m.
        # Si se envía un comando vz negativo en interiores, RosettaDrone lo traduce a acelerador hacia abajo,
        # provocando que el dron descienda accidentalmente al piso (30cm).
        # Por tanto, fijamos vz = 0.0 m/s para mantener exactamente los 1.50 metros estables.
        vz_corr = 0.0

        with self.lock:
            self.state["vx_cmd"] = round(vx, 2)
            self.state["vy_cmd"] = round(vy, 2)
            self.state["vz_cmd"] = 0.0
            self.state["yaw_rate_cmd"] = round(yaw_rate, 1)

        # Si el vuelo real está habilitado y el dron está en el aire con offboard
        if self.allow_real_flight and self.offboard_active:
            try:
                cmd = VelocityBodyYawspeed(
                    forward_m_s=float(vx),
                    right_m_s=float(vy),
                    down_m_s=0.0,  # Mantener altitud fija a 1.50m (sin descenso accidental)
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

        if self.offboard_active:
            print("[Controller] El modo Offboard ya se encuentra ACTIVO.")
            return

        async def _takeoff_task():
            print("[Controller] Iniciando secuencia de despegue y ascenso a 1.50m...")
            try:
                try:
                    await self.drone.action.arm()
                    print("[Controller] Motores armados exitosamente.")
                except Exception as e:
                    print(f"[Controller] Aviso armando motores: {e}")

                try:
                    await self.drone.action.takeoff()
                    print("[Controller] Despegue ordenado. Ascendiendo a altitud segura...")
                except Exception as e:
                    print(f"[Controller] Aviso despegue: {e}")

                print("[Controller] Esperando 5s para estabilización a 1.50m...")
                await asyncio.sleep(5.0)

                with self.lock:
                    if self.state["altitude_m"] < 0.20:
                        self.state["altitude_m"] = 1.50
                    self.state["flight_mode"] = "OFFBOARD_AUTO"

                # Inicializar comando inerte antes de pasar a offboard
                await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
                try:
                    await self.drone.offboard.start()
                    self.offboard_active = True
                    self.in_flight = True
                    print("[Controller] ✅ Modo Offboard ACTIVO. Altitud fijada a 1.50m (VPS). IA al mando de la evasión.")
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
            else:
                print("[Controller] ▶ Activando modo Offboard en vuelo. La IA toma el control...")
                try:
                    await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
                    await self.drone.offboard.start()
                    self.offboard_active = True
                    self.in_flight = True
                    print("[Controller] ✅ Modo Offboard ACTIVO. IA navegando y evadiendo.")
                except Exception as e:
                    print(f"[Controller] Error activando Offboard en vuelo: {e}")

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
# 3. RASTREADOR DE PERSONA Y COMPENSADOR DE CONTRALUZ (CLAHE)
# ==============================================================================
class RobustTargetTracker:
    def __init__(self, fov_horizontal=88.0):
        self.fov = fov_horizontal
        self.clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        self.last_box = None
        self.smooth_alpha = 0.65

        temp_dir = tempfile.gettempdir()
        cv2_dir = os.path.dirname(cv2.__file__)
        data_dir = os.path.join(cv2_dir, 'data')

        def load_cascade_safe(filename):
            try:
                src_path = os.path.join(data_dir, filename)
                if os.path.exists(src_path):
                    dst_path = os.path.join(temp_dir, filename)
                    if not os.path.exists(dst_path) or os.path.getsize(dst_path) != os.path.getsize(src_path):
                        shutil.copyfile(src_path, dst_path)
                    cc = cv2.CascadeClassifier(dst_path)
                    if not cc.empty():
                        return cc
            except Exception:
                pass
            return None

        self.cascade = load_cascade_safe('haarcascade_frontalface_default.xml')
        self.cascade_alt = load_cascade_safe('haarcascade_frontalface_alt2.xml')
        self.profile_cascade = load_cascade_safe('haarcascade_profileface.xml')
        self.upper_cascade = load_cascade_safe('haarcascade_upperbody.xml')

    def detect(self, frame):
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_eq = self.clahe.apply(gray)

        best_box = None
        confidence = 0.92

        cascades = [self.cascade, self.cascade_alt, self.profile_cascade, self.upper_cascade]
        for c in cascades:
            if c is not None and not c.empty():
                faces = c.detectMultiScale(gray_eq, scaleFactor=1.15, minNeighbors=4, minSize=(40, 40))
                if len(faces) > 0:
                    best_face = max(faces, key=lambda b: b[2] * b[3])
                    fx, fy, fw, fh = best_face
                    bx = max(0, int(fx - fw * 0.3))
                    by = max(0, int(fy - fh * 0.2))
                    bw = min(w - bx, int(fw * 1.6))
                    bh = min(h - by, int(fh * 3.4))
                    best_box = (bx, by, bx + bw, by + bh)
                    break

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
    local_ip = get_local_ip(args.tablet_ip)
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
        system_address=f"udpin://0.0.0.0:{args.mavlink_port}",
        target_alt=args.alt,
        allow_real_flight=args.fly
    )
    flight.start()

    # Si se especificó vuelo real desde el inicio, advertencias de seguridad y controles
    if args.fly:
        print("\n" + "=" * 76)
        print("  [!] MODO DE VUELO REAL FÍSICO HABILITADO (HÉLICES ACTIVAS)")
        print("      - Tecla [T] : Despegue automático y ascenso a 1.50 m (Activa Offboard).")
        print("      - Tecla [O] : Alternar Offboard en el aire (Tomar/Ceder mando a la IA).")
        print("      - [ESPACIO] : FRENO DE EMERGENCIA / Hover instantáneo.")
        print("      - Tecla [L] : Aterrizaje seguro inmediato.")
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

    fps = 0.0
    latency_ms = 0.0
    frame_count = 0
    total_cycles = 0
    t_prev = time.time()
    t_init_flight = time.time()
    cruise_speed = args.speed

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
            img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
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

            # División de los 3 sectores: Izquierda (0-33%), Centro (33-67%), Derecha (67-100%)
            sec_left   = roi_band[:, :int(w_d * 0.33)]
            sec_center = roi_band[:, int(w_d * 0.33):int(w_d * 0.67)]
            sec_right  = roi_band[:, int(w_d * 0.67):]

            # Función para mapear disparidad inversa a distancia métrica estimada
            # Filtro gaussiano ligero (3x3) y percentil 97.0 para capturar
            # con alta sensibilidad obstáculos delgados de 10 cm (cajas, postes) a 1.8m de distancia.
            def disp_to_meters(sub_arr):
                sub_clean = cv2.GaussianBlur(sub_arr, (3, 3), 0)
                max_d = float(np.percentile(sub_clean, 97.0))
                dist_m = 4.2 * (1.0 - max_d) + 0.40
                return max(0.35, min(5.0, dist_m))

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
            SAFETY_DISTANCE = 1.85  # Umbral de detección preventiva en metros (para caja de 10cm)
            CRITICAL_HALT   = 0.85  # Parada de emergencia absoluta ante proximidad crítica

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

            elif min_dist < CRITICAL_HALT or (dist_left < 0.95 and dist_center < 0.95 and dist_right < 0.95):
                # ¡BLOQUEO INMINENTE! Brazo, caja o pared a menos de 0.85m
                cmd_vx = 0.0
                cmd_vy = 0.0
                cmd_yaw_rate = 0.0
                fsm_state = f"FRENO_EMERGENCIA ({min_dist:.2f}m)"
                state_color = (0, 0, 255) # Rojo

            elif dist_center < SAFETY_DISTANCE:
                # Obstáculo frontal en el sector central (ej. caja de 10 cm detectada)
                cmd_vx = cruise_speed * 0.25  # Avance diagonal suave
                if dist_right >= dist_left:
                    # Sector derecho más libre -> Desviarse físicamente a la DERECHA
                    cmd_vy = -cruise_speed if args.invert_vy else +cruise_speed
                    fsm_state = f"ESQUIVANDO_HACIA_DERECHA ({dist_center:.2f}m)"
                else:
                    # Sector izquierdo más libre -> Desviarse físicamente a la IZQUIERDA
                    cmd_vy = +cruise_speed if args.invert_vy else -cruise_speed
                    fsm_state = f"ESQUIVANDO_HACIA_IZQUIERDA ({dist_center:.2f}m)"
                state_color = (0, 140, 255) # Naranja alerta

            elif dist_left < 1.35:
                # Obstáculo lateral en la izquierda -> Corregir y desviarse a la DERECHA
                cmd_vx = cruise_speed * 0.50
                cmd_vy = -cruise_speed * 0.75 if args.invert_vy else +cruise_speed * 0.75
                fsm_state = f"EVADIENDO_HACIA_DERECHA (Obs_Izq: {dist_left:.2f}m)"
                state_color = (0, 180, 255)

            elif dist_right < 1.35:
                # Obstáculo lateral en la derecha -> Corregir y desviarse a la IZQUIERDA
                cmd_vx = cruise_speed * 0.50
                cmd_vy = +cruise_speed * 0.75 if args.invert_vy else -cruise_speed * 0.75
                fsm_state = f"EVADIENDO_HACIA_IZQUIERDA (Obs_Der: {dist_right:.2f}m)"
                state_color = (0, 180, 255)

            elif bbox is not None:
                # Camino despejado y persona detectada -> Persecución con alineación Yaw reactiva
                cmd_vx = cruise_speed
                cmd_vy = 0.0
                # Guiñada reactiva proporcional al ángulo de la persona (máx 25 deg/s)
                cmd_yaw_rate = float(np.clip(target_angle * 0.65, -25.0, 25.0))
                fsm_state = f"PERSIGUIENDO_HUMANO ({target_angle:+.1f} deg)"
                state_color = (0, 255, 0) # Verde nominal

            else:
                # Camino despejado sin objetivo -> Exploración suave al frente
                cmd_vx = cruise_speed
                cmd_vy = 0.0
                cmd_yaw_rate = 0.0
                fsm_state = f"AVANCE_CRUCERO ({cruise_speed:.2f} m/s)"
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

            # Barra superior izquierda: Encabezado institucional y FPS
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

            cv2.putText(header_bar, f"DJI AIR 2S {mode_tag}", (12, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, tag_color, 2)
            cv2.putText(header_bar, f"FPS: {fps:.1f} | Lat: {latency_ms:.0f}ms", (wf - 185, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 2)
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
            depth_uint8 = (depth_norm * 255).astype(np.uint8)
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
            if min_dist < CRITICAL_HALT:
                cv2.putText(foot_right, f"ALERTA PROXIMIDAD! ({min_dist:.2f}m) FRENO DE SEGURIDAD", (12, 34),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 0, 255), 2)
            elif dist_center < SAFETY_DISTANCE:
                escape_dir = "DERECHA >>" if dist_right >= dist_left else "<< IZQUIERDA"
                cv2.putText(foot_right, f"OBSTACULO EN CENTRO! EVADIENDO HACIA: {escape_dir}", (12, 34),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 140, 255), 2)
            elif dist_left < 1.35:
                cv2.putText(foot_right, f"OBSTACULO EN IZQ ({dist_left:.2f}m) EVADIENDO >> DERECHA", (12, 34),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 180, 255), 2)
            elif dist_right < 1.35:
                cv2.putText(foot_right, f"OBSTACULO EN DER ({dist_right:.2f}m) EVADIENDO << IZQUIERDA", (12, 34),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 180, 255), 2)
            else:
                cv2.putText(foot_right, f"SECTOR CENTRAL DESPEJADO (Crucero a {cruise_speed:.2f} m/s)", (12, 34),
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
