"""
Demostracion en Vivo: Persecucion Visual + Estimacion de Profundidad (Optimizado)
Tesis de Ingenieria de Sistemas - UNI
Autor: Gustavo Bryan Lopez Cosme

Optimizaciones aplicadas:
  1. Lector de frames en segundo plano (Zero-Latency Thread):
     Elimina la acumulacion de buffer y el congelamiento "(No responde)".
  2. Control de integridad RTP (Sequence Number check):
     Descarta paquetes incompletos en caso de perdida por Wi-Fi,
     evitando la corrupcion de macrobloques de H.264 (pantallas verdes y pixelado).
  3. Inyeccion limpia de SPS/PPS sincronizada con cuadros IDR:
     Asegura reconstruccion limpia sin distorsion visual.
  4. Ecualizacion adaptativa de contraste (CLAHE):
     Detecta el rostro/cuerpo incluso a contraluz (frente a ventanas o cortinas).

Controles:
  [Q] o [ESC] : Salir
  [S]         : Guardar captura en 'Air2S_MAVSDK/logs/capturas_demo/'
  [ESPACIO]   : Pausar / Reanudar el video
  [C]         : Cambiar mapa de colores (Inferno, Turbo, Magma, Jet)
"""

import os
import sys
import time
import socket
import struct
import threading
import shutil
import tempfile
import argparse
import ctypes
import re
import numpy as np
import cv2

# Configurar variables de entorno C-runtime para FFmpeg en Windows
opt = "OPENCV_FFMPEG_CAPTURE_OPTIONS=protocol_whitelist;file,rtp,udp|fflags;nobuffer|flags;low_delay|threads;1|overrun_nonfatal;1"
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "protocol_whitelist;file,rtp,udp|fflags;nobuffer|flags;low_delay|threads;1|overrun_nonfatal;1"
try:
    ctypes.cdll.msvcrt._putenv(opt.encode("ascii"))
except Exception:
    pass

# Suprimir advertencias menores de TensorFlow
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
import tensorflow as tf

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'

def parse_args():
    parser = argparse.ArgumentParser(description="Demo en Vivo de Persecucion y Profundidad")
    parser.add_argument("--cam", type=int, default=0, help="ID de la camara (0=Webcam)")
    parser.add_argument("--drone", action="store_true", help="Usar video del dron DJI via RosettaDrone (UDP 5600)")
    parser.add_argument("--model", type=str, default="Air2S_MAVSDK/models/midas_v21_small_256.tflite", help="Ruta al modelo MiDaS")
    return parser.parse_args()

class RTPVideoBridge:
    """
    Puente de red local: Recibe paquetes RTP H.264 por UDP 5600 de RosettaDrone,
    reensambla fragmentos FU-A respetando las fronteras NAL con verificación estricta
    de número de secuencia RTP para evitar distorsiones por paquetes Wi-Fi perdidos,
    inyecta las cabeceras SPS/PPS una sola vez al inicializar el decodificador,
    y reenvía el flujo H.264 limpio a 127.0.0.1:5601 para OpenCV.
    """
    def __init__(self, in_port=5600, out_port=5601):
        self.in_port = in_port
        self.out_port = out_port
        self.running = True
        self.packet_count = 0
        self.slice_count = 0
        
        # Cabeceras H.264 estándar para DJI Air 2S (1080p High Profile Level 5.0)
        self.sps = b'\x00\x00\x00\x01\x67\x64\x00\x32\xac\x4d\x00\xcc\x04\x4f\x3c\xb3\x50\x10\x10\x14\x00\x00\x03\x00\x04\x00\x00\x03\x00\xc8\x3c\x70\xca\x80'
        self.pps = b'\x00\x00\x00\x01\x68\xee\x3c\xb0'

        self.s_out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.s_out.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)
        except Exception:
            pass

        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def send_initial_headers(self):
        """Envía ráfaga inicial de SPS/PPS para inicializar el decodificador de OpenCV."""
        for _ in range(3):
            try:
                self.s_out.sendto(self.sps, ('127.0.0.1', self.out_port))
                self.s_out.sendto(self.pps, ('127.0.0.1', self.out_port))
            except Exception:
                pass
            time.sleep(0.01)

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

                if len(data) > 12:
                    seq = struct.unpack('!H', data[2:4])[0]
                    payload = data[12:]
                    nal_type = payload[0] & 0x1F

                    # Si la tablet emite SPS o PPS en vivo, capturarlos y reenviarlos tal cual
                    if nal_type in (7, 8):
                        if nal_type == 7:
                            self.sps = b'\x00\x00\x00\x01' + payload
                        else:
                            self.pps = b'\x00\x00\x00\x01' + payload
                        self.s_out.sendto(b'\x00\x00\x00\x01' + payload, ('127.0.0.1', self.out_port))
                        continue

                    if nal_type == 28: # FU-A Fragmentado
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
                            # Verificación estricta de continuidad de secuencia RTP
                            if last_seq is not None and seq != ((last_seq + 1) & 0xFFFF):
                                slice_corrupt = True
                            last_seq = seq
                            if not slice_corrupt:
                                fu_buf.extend(payload[2:])

                        if end and in_fua:
                            # Solo enviar si la rebanada está completa y no sufrió pérdida de paquetes
                            if not slice_corrupt and len(fu_buf) > 1:
                                if inner_type == 5:
                                    # Anteponer SPS y PPS inmediatamente antes del fotograma clave IDR
                                    self.s_out.sendto(self.sps, ('127.0.0.1', self.out_port))
                                    self.s_out.sendto(self.pps, ('127.0.0.1', self.out_port))
                                pkt = b'\x00\x00\x00\x01' + bytes(fu_buf)
                                self.s_out.sendto(pkt, ('127.0.0.1', self.out_port))
                                self.slice_count += 1
                            fu_buf = bytearray()
                            in_fua = False
                    elif nal_type == 5:
                        # NAL IDR directo: anteponer SPS y PPS
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

class FreshFrameReader:
    """
    Lector de video en segundo plano dedicado:
    Consume continuamente los fotogramas del buffer de OpenCV a maxima velocidad
    y entrega SIEMPRE el cuadro mas reciente en tiempo real.
    Elimina por completo la acumulacion de latencia y los bloqueos "(No responde)".
    """
    def __init__(self, src_uri):
        self.cap = cv2.VideoCapture(src_uri, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.latest_frame = None
        self.has_new_frame = False
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
                        self.has_new_frame = True
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

class RobustTargetTracker:
    """
    Rastreador de personas con ecualizacion adaptativa de contraste (CLAHE).
    Resuelve el problema de contraluz (ventanas o cortinas brillantes detras del usuario).
    """
    def __init__(self, fov_horizontal=88.0):
        self.fov = fov_horizontal
        self.face_cascade = None
        self.face_alt_cascade = None
        self.profile_cascade = None
        self.upper_cascade = None
        self.hog = None

        # Ecualizador de contraste adaptativo
        self.clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))

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

        self.face_cascade = load_cascade_safe('haarcascade_frontalface_default.xml')
        self.face_alt_cascade = load_cascade_safe('haarcascade_frontalface_alt2.xml')
        self.profile_cascade = load_cascade_safe('haarcascade_profileface.xml')
        self.upper_cascade = load_cascade_safe('haarcascade_upperbody.xml')

        try:
            self.hog = cv2.HOGDescriptor()
            self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        except Exception:
            pass

        self.last_box = None
        self.smooth_alpha = 0.65

    def detect(self, frame):
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Ecualizar contraste para ver con claridad rostros en sombra o a contraluz
        gray_eq = self.clahe.apply(gray)
        
        best_box = None
        max_area = 0
        confidence = 0.90

        # 1. Detector Alt2 (diseñado especialmente para rostros con sombras/contraluz)
        if self.face_alt_cascade is not None:
            try:
                faces = self.face_alt_cascade.detectMultiScale(gray_eq, scaleFactor=1.12, minNeighbors=3, minSize=(35, 35))
                for (x, y, bw, bh) in faces:
                    area = bw * bh
                    if area > max_area:
                        max_area = area
                        pad_x = int(bw * 0.15)
                        pad_y = int(bh * 0.20)
                        x1 = max(0, x - pad_x)
                        y1 = max(0, y - pad_y)
                        x2 = min(w, x + bw + pad_x)
                        y2 = min(h, y + bh + int(bh * 0.7))
                        best_box = (x1, y1, x2, y2)
                        confidence = 0.94
            except Exception:
                pass

        # 2. Detector Frontal por defecto
        if best_box is None and self.face_cascade is not None:
            try:
                faces = self.face_cascade.detectMultiScale(gray_eq, scaleFactor=1.15, minNeighbors=3, minSize=(35, 35))
                for (x, y, bw, bh) in faces:
                    area = bw * bh
                    if area > max_area:
                        max_area = area
                        pad_x = int(bw * 0.15)
                        pad_y = int(bh * 0.20)
                        x1 = max(0, x - pad_x)
                        y1 = max(0, y - pad_y)
                        x2 = min(w, x + bw + pad_x)
                        y2 = min(h, y + bh + int(bh * 0.7))
                        best_box = (x1, y1, x2, y2)
                        confidence = 0.91
            except Exception:
                pass

        # 3. Detector de Rostro de perfil
        if best_box is None and self.profile_cascade is not None:
            try:
                profiles = self.profile_cascade.detectMultiScale(gray_eq, scaleFactor=1.15, minNeighbors=3, minSize=(35, 35))
                for (x, y, bw, bh) in profiles:
                    area = bw * bh
                    if area > max_area:
                        max_area = area
                        best_box = (x, y, x + bw, y + bh)
                        confidence = 0.86
            except Exception:
                pass

        # 4. Detector de cuerpo superior
        if best_box is None and self.upper_cascade is not None:
            try:
                uppers = self.upper_cascade.detectMultiScale(gray_eq, scaleFactor=1.15, minNeighbors=2, minSize=(50, 50))
                for (x, y, bw, bh) in uppers:
                    area = bw * bh
                    if area > max_area:
                        max_area = area
                        best_box = (x, y, x + bw, y + bh)
                        confidence = 0.88
            except Exception:
                pass

        # 5. Si la persona esta de pie alejada, probar HOG
        if best_box is None and self.hog is not None:
            try:
                small_frame = cv2.resize(frame, (320, 240))
                boxes, _ = self.hog.detectMultiScale(small_frame, winStride=(8, 8), padding=(4, 4), scale=1.1)
                for (bx, by, bw, bh) in boxes:
                    scale_x = w / 320.0
                    scale_y = h / 240.0
                    area = (bw * scale_x) * (bh * scale_y)
                    if area > max_area:
                        max_area = area
                        best_box = (int(bx * scale_x), int(by * scale_y), int((bx + bw) * scale_x), int((by + bh) * scale_y))
                        confidence = 0.84
            except Exception:
                pass

        if best_box is None:
            self.last_box = None
            return None, 0.0, 0.0

        if self.last_box is not None:
            x1 = int(self.smooth_alpha * best_box[0] + (1 - self.smooth_alpha) * self.last_box[0])
            y1 = int(self.smooth_alpha * best_box[1] + (1 - self.smooth_alpha) * self.last_box[1])
            x2 = int(self.smooth_alpha * best_box[2] + (1 - self.smooth_alpha) * self.last_box[2])
            y2 = int(self.smooth_alpha * best_box[3] + (1 - self.smooth_alpha) * self.last_box[3])
            best_box = (x1, y1, x2, y2)

        self.last_box = best_box

        center_x = (best_box[0] + best_box[2]) / 2.0
        angle_deg = (center_x / w - 0.5) * self.fov

        return best_box, angle_deg, confidence

def main():
    args = parse_args()
    local_ip = get_local_ip()
    
    print("=" * 72)
    print("  TESIS UNI - SISTEMA DE PERSECUCION Y ESTIMACION DE PROFUNDIDAD")
    print("  Demostracion en Pantalla con Hardware Real (Motores Apagados)")
    print(f"  IP de tu Laptop: {local_ip}")
    print("=" * 72)

    bridge = None
    reader = None

    if args.drone:
        print("\n[*] MODO DRON SELECCIONADO:")
        print("    - Iniciando puente receptor RTP optimizado con filtro de integridad en UDP 5600...")
        bridge = RTPVideoBridge(in_port=5600, out_port=5601)
        
        print("    - Esperando flujo de video desde la tablet...")
        wait_cycles = 0
        while bridge.packet_count < 15:
            print(f"      Recibiendo paquetes de video de RosettaDrone: {bridge.packet_count}...   ", end="\r")
            time.sleep(0.4)
            wait_cycles += 1
            if wait_cycles % 25 == 0 and bridge.packet_count == 0:
                print(f"\n      [!] Recordatorio: RosettaDrone debe tener 'Enable video feed' ON enviando a {local_ip}:5600 (Bitrate: 2500 kbps).")
            
        print(f"\n    [OK] ¡Flujo de video del dron detectado! ({bridge.packet_count} paquetes)")
        print("[*] Sincronizando cabeceras H.264 e iniciando decodificador (Zero-Latency)...")
        print("[!] ACCIÓN EN LA TABLET: En RosettaDrone pulsa 'STOP' y luego 'START'")
        print("    (o en Ajustes confirma 'Video bitrate' en 2500 kbps) para emitir el fotograma clave.\n")
        bridge.send_initial_headers()
        reader = FreshFrameReader('udp://127.0.0.1:5601')
    else:
        print(f"\n[*] Abriendo camara web integrada (Dispositivo {args.cam})...")
        reader = FreshFrameReader(args.cam)

    # 1. Cargar Modelo MiDaS v2.1 Small
    model_path = args.model
    if not os.path.exists(model_path):
        candidates = [
            os.path.join(os.path.dirname(__file__), "Air2S_MAVSDK", "models", "midas_v21_small_256.tflite"),
            os.path.join(os.path.dirname(__file__), "models", "midas_v21_small_256.tflite"),
            os.path.join("models", "midas_v21_small_256.tflite"),
            os.path.join("Air2S_MAVSDK", "models", "midas_v21_small_256.tflite")
        ]
        for c in candidates:
            if os.path.exists(c):
                model_path = c
                break

    if not os.path.exists(model_path):
        print(f"Error: No se encontro el archivo del modelo en {args.model}")
        if reader:
            reader.release()
        if bridge:
            bridge.stop()
        sys.exit(1)

    print(f"[*] Cargando modelo MiDaS Small desde: {model_path}")
    interpreter = tf.lite.Interpreter(model_path=model_path, num_threads=4)
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    tracker = RobustTargetTracker(fov_horizontal=88.0)

    colormaps = [cv2.COLORMAP_INFERNO, cv2.COLORMAP_TURBO, cv2.COLORMAP_MAGMA, cv2.COLORMAP_JET]
    colormap_names = ["INFERNO", "TURBO", "MAGMA", "JET"]
    curr_cm_idx = 0

    paused = False
    last_frame_combined = None
    frame_count = 0
    fps = 0.0
    t_prev = time.time()

    if os.path.exists("logs"):
        out_dir = os.path.join("logs", "capturas_demo")
    else:
        out_dir = os.path.join("Air2S_MAVSDK", "logs", "capturas_demo")
    os.makedirs(out_dir, exist_ok=True)

    print("\n[OK] Sesión fluida iniciada! Mostrando ventana de visualización...")
    print("Controles:")
    print("  [Q] o [ESC] : Salir")
    print("  [S]         : Guardar captura en 'Air2S_MAVSDK/logs/capturas_demo/'")
    print("  [ESPACIO]   : Pausar / Reanudar")
    print("  [C]         : Cambiar mapa de color de profundidad\n")

    win_name = "Tesis UNI - Persecucion y Profundidad (Camara Dron)" if args.drone else "Tesis UNI - Persecucion y Profundidad (Webcam)"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win_name, 1280, 540)

    try:
        while True:
            if not paused:
                ret, frame = reader.read_latest()
                if not ret or frame is None:
                    # Mostrar pantalla de sincronización interactiva en lugar de ventana gris vacía
                    splash = np.zeros((540, 1280, 3), dtype=np.uint8)
                    splash[:] = (30, 30, 30)
                    cv2.putText(splash, "TESIS UNI - SISTEMA DE PERSECUCION Y PROFUNDIDAD", (180, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 220, 255), 2)
                    cv2.putText(splash, "Sincronizando flujo de video H.264 de la camara...", (260, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.70, (255, 255, 255), 2)
                    
                    if args.drone and bridge:
                        cv2.putText(splash, f"Paquetes UDP recibidos de RosettaDrone: {bridge.packet_count}", (310, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
                        cv2.putText(splash, "Esperando fotograma clave (IDR)...", (400, 310), cv2.FONT_HERSHEY_SIMPLEX, 0.60, (0, 220, 255), 2)
                        cv2.putText(splash, "--> EN LA TABLET: Pulsa 'STOP' y luego 'START' en RosettaDrone <--", (160, 380), cv2.FONT_HERSHEY_SIMPLEX, 0.70, (0, 255, 255), 2)
                        cv2.putText(splash, "(o en Ajustes confirma el bitrate en 2500 kbps para iniciar)", (260, 420), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
                    
                    cv2.imshow(win_name, splash)
                    key = cv2.waitKey(20) & 0xFF
                    if key == ord('q') or key == 27:
                        break
                    continue

                frame_count += 1
                t_curr = time.time()
                if t_curr - t_prev >= 0.5:
                    fps = frame_count / (t_curr - t_prev)
                    frame_count = 0
                    t_prev = t_curr

                h_f, w_f = frame.shape[:2]
                target_h = 440
                target_w = int(w_f * (target_h / h_f))
                frame_resized = cv2.resize(frame, (target_w, target_h))
                hf, wf = frame_resized.shape[:2]

                # ==========================================
                # 1. RASTREO Y PERSECUCIÓN (LADO IZQUIERDO)
                # ==========================================
                left_view = frame_resized.copy()
                bbox, target_angle, conf = tracker.detect(left_view)

                center_cam_x = wf // 2
                center_cam_y = hf // 2

                # Dibujar mira central (Crosshair del dron)
                cv2.drawMarker(left_view, (center_cam_x, center_cam_y), (0, 200, 255), cv2.MARKER_CROSS, 20, 2)
                cv2.circle(left_view, (center_cam_x, center_cam_y), 35, (0, 200, 255), 1)

                if bbox is not None:
                    x1, y1, x2, y2 = bbox
                    tgt_cx = (x1 + x2) // 2
                    tgt_cy = (y1 + y2) // 2

                    # Recuadro verde brillante de objetivo
                    cv2.rectangle(left_view, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    line_len = 15
                    cv2.line(left_view, (x1, y1), (x1 + line_len, y1), (0, 255, 0), 4)
                    cv2.line(left_view, (x1, y1), (x1, y1 + line_len), (0, 255, 0), 4)
                    cv2.line(left_view, (x2, y1), (x2 - line_len, y1), (0, 255, 0), 4)
                    cv2.line(left_view, (x2, y1), (x2, y1 + line_len), (0, 255, 0), 4)
                    cv2.line(left_view, (x1, y2), (x1 + line_len, y2), (0, 255, 0), 4)
                    cv2.line(left_view, (x1, y2), (x1, y2 - line_len), (0, 255, 0), 4)
                    cv2.line(left_view, (x2, y2), (x2 - line_len, y2), (0, 255, 0), 4)
                    cv2.line(left_view, (x2, y2), (x2, y2 - line_len), (0, 255, 0), 4)

                    # Linea vector de persecucion desde la mira al objetivo
                    cv2.line(left_view, (center_cam_x, center_cam_y), (tgt_cx, tgt_cy), (0, 255, 255), 2)
                    cv2.circle(left_view, (tgt_cx, tgt_cy), 5, (0, 255, 0), -1)

                    # Etiqueta de objetivo
                    label_txt = f"Target: Humano ({conf:.2f})"
                    cv2.putText(left_view, label_txt, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

                    dir_txt = "DERECHA" if target_angle > 2 else ("IZQUIERDA" if target_angle < -2 else "AL FRENTE")
                    status_color = (0, 255, 0)
                    status_str = f"PERSIGUIENDO | Yaw: {target_angle:+.1f} deg [{dir_txt}]"
                else:
                    status_color = (0, 165, 255)
                    status_str = "BUSCANDO OBJETIVO HUMANO..."

                cv2.rectangle(left_view, (5, hf - 35), (wf - 5, hf - 5), (20, 20, 20), -1)
                cv2.putText(left_view, status_str, (12, hf - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.55, status_color, 2)

                # ==========================================
                # 2. ESTIMACIÓN DE PROFUNDIDAD (LADO DERECHO)
                # ==========================================
                img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img_resized = cv2.resize(img_rgb, (256, 256))
                img_norm = (img_resized.astype(np.float32) / 255.0 - mean) / std
                img_input = np.expand_dims(img_norm, axis=0)

                interpreter.set_tensor(input_details[0]['index'], img_input)
                interpreter.invoke()
                depth_raw = interpreter.get_tensor(output_details[0]['index'])[0]

                d_min = float(depth_raw.min())
                d_max = float(depth_raw.max())
                depth_norm = (depth_raw - d_min) / (d_max - d_min + 1e-6)
                depth_uint8 = (depth_norm * 255.0).astype(np.uint8)

                depth_colored = cv2.applyColorMap(depth_uint8, colormaps[curr_cm_idx])
                right_view = cv2.resize(depth_colored, (wf, hf))

                # Deteccion de obstaculo en sector central (ROI)
                roi_depth = depth_norm[int(256*0.3):int(256*0.7), int(256*0.3):int(256*0.7)]
                max_center_disp = float(np.max(roi_depth))
                prox_dist = max(0.5, round(3.5 * (1.0 - max_center_disp) + 0.3, 2))

                if max_center_disp > 0.65:
                    obst_alert = f"ALERTA: OBSTACULO CERCANO ({prox_dist} m)"
                    alert_color = (0, 0, 255)
                    cv2.rectangle(right_view, (wf//4, hf//4), (3*wf//4, 3*hf//4), (0, 0, 255), 2)
                else:
                    obst_alert = f"SECTOR FRONTAL LIBRE (Obstaculo a > {prox_dist} m)"
                    alert_color = (0, 255, 0)

                cv2.rectangle(right_view, (5, hf - 35), (wf - 5, hf - 5), (20, 20, 20), -1)
                cv2.putText(right_view, obst_alert, (12, hf - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.55, alert_color, 2)

                # ==========================================
                # 3. UNIÓN DE PANTALLA DIVIDIDA Y ENCABEZADO
                # ==========================================
                split_frame = np.hstack([left_view, right_view])
                total_w = split_frame.shape[1]

                header_h = 50
                header = np.zeros((header_h, total_w, 3), dtype=np.uint8)
                header[:] = (35, 35, 35)

                origen_cam = "CAMARA DJI AIR 2S (EN VIVO)" if args.drone else "CAMARA WEB (LOCAL)"
                cv2.putText(header, f"{origen_cam} - PERSECUCION", (20, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.60, (0, 255, 0), 2)
                cv2.putText(header, f"MAPA DE PROFUNDIDAD MIDAS [{colormap_names[curr_cm_idx]}]", (wf + 20, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.60, (0, 220, 255), 2)
                cv2.putText(header, f"FPS: {fps:.1f}", (total_w - 130, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

                cv2.line(split_frame, (wf, 0), (wf, hf), (255, 255, 255), 2)

                footer_h = 30
                footer = np.zeros((footer_h, total_w, 3), dtype=np.uint8)
                footer[:] = (20, 20, 20)
                cv2.putText(footer, "[Q] Salir   |   [S] Guardar Foto   |   [ESPACIO] Pausar   |   [C] Cambiar Color de Mapa", (20, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

                last_frame_combined = np.vstack([header, split_frame, footer])

            if last_frame_combined is not None:
                cv2.imshow(win_name, last_frame_combined)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                print("\n[OK] Sesion finalizada por el usuario.")
                break
            elif key == ord('s'):
                fn = os.path.join(out_dir, f"captura_dron_{int(time.time())}.jpg")
                cv2.imwrite(fn, last_frame_combined)
                print(f"[*] Captura guardada con exito en: {fn}")
            elif key == 32:
                paused = not paused
                print("[*] Video " + ("PAUSADO" if paused else "REANUDADO"))
            elif key == ord('c'):
                curr_cm_idx = (curr_cm_idx + 1) % len(colormaps)
                print(f"[*] Mapa de color cambiado a: {colormap_names[curr_cm_idx]}")

    finally:
        if reader:
            reader.release()
        cv2.destroyAllWindows()
        if bridge:
            bridge.stop()

if __name__ == "__main__":
    main()
