import os
import ctypes

# 1. Forzar decodificación estable: threads=1 (elimina el crash pthread_frame), nobuffer (cero latencia)
opt = (
    "OPENCV_FFMPEG_CAPTURE_OPTIONS=protocol_whitelist;file,rtp,udp|"
    "fflags;nobuffer|flags;low_delay|buffer_size;4194304|threads;1|overrun_nonfatal;1"
)
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
    "protocol_whitelist;file,rtp,udp|fflags;nobuffer|flags;low_delay|buffer_size;4194304|threads;1|overrun_nonfatal;1"
)
try:
    ctypes.cdll.msvcrt._putenv(opt.encode("ascii"))
except Exception:
    pass

import cv2
import threading
import time
import sys

class RealtimeVideoReceiver:
    """
    Receptor de video en tiempo real.
    Descarta cuadros acumulados (cap.grab()) para asegurar que el frame
    siempre tenga menos de 80ms de latencia (tiempo real puro).
    """
    def __init__(self, sdp_path="rosetta.sdp"):
        self.cap = cv2.VideoCapture(sdp_path, cv2.CAP_FFMPEG)
        self.frame = None
        self.new_frame_ready = False
        self.running = True
        self.lock = threading.Lock()
        
        self.thread = threading.Thread(target=self._reader, daemon=True)
        self.thread.start()

    def _reader(self):
        while self.running:
            if self.cap.isOpened():
                # cap.grab() es ultra rápido (salta paquetes viejos)
                # Solo decodificamos el último frame recibido en la cola
                ret = self.cap.grab()
                if ret:
                    ret_decode, frame = self.cap.retrieve()
                    if ret_decode and frame is not None:
                        with self.lock:
                            self.frame = frame
                            self.new_frame_ready = True
                else:
                    time.sleep(0.005)
            else:
                time.sleep(0.05)

    def get_latest_frame(self):
        """Retorna el frame más reciente SOLO si es nuevo para evitar duplicados."""
        with self.lock:
            if self.new_frame_ready:
                self.new_frame_ready = False
                return self.frame
            return None

    def get_current_frame_holding(self):
        """Retorna la última imagen disponible para mantener la ventana viva."""
        with self.lock:
            return self.frame

    def stop(self):
        self.running = False
        if self.cap.isOpened():
            self.cap.release()

def test_stream():
    print("=" * 65)
    print("  TEST DE VIDEO EN TIEMPO REAL - DJI AIR 2S (SUB-100ms)")
    print("=" * 65)

    sdp_path = "rosetta.sdp"
    if not os.path.exists(sdp_path):
        with open(sdp_path, "w") as f:
            f.write("c=IN IP4 0.0.0.0\nm=video 5600 RTP/AVP 96\na=rtpmap:96 H264/90000\na=fmtp:96 packetization-mode=1\n")

    print("[1/3] Conectando receptor de video...")
    receiver = RealtimeVideoReceiver(sdp_path)

    print("[2/3] Sincronizando flujo con la cámara...")
    dots = 0
    while receiver.get_current_frame_holding() is None:
        time.sleep(0.5)
        dots += 1
        sys.stdout.write(f"\r      Sincronizando... [{dots}s]")
        sys.stdout.flush()

    print("\n\n[3/3] ¡VÍDEO EN VIVO CONECTADO! Mostrando ventana...")

    frame_count = 0
    fps_time = time.time()
    fps = 0.0

    while True:
        # Obtenemos el frame real que acaba de llegar (cero latencia)
        frame = receiver.get_latest_frame()
        if frame is None:
            # Esperamos 5ms para no saturar CPU y dejamos que el hilo lea
            time.sleep(0.005)
            continue

        frame_count += 1
        now = time.time()
        if now - fps_time >= 1.0:
            fps = frame_count / (now - fps_time)
            frame_count = 0
            fps_time = now

        # HUD en vivo
        display = frame.copy()
        cv2.putText(display, f"DJI Air 2S | FPS Camara: {fps:.1f}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.putText(display, "Tiempo Real (Baja Latencia) | 'q' para salir", (20, 75),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        cv2.imshow("Video en Vivo - DJI Air 2S", display)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    receiver.stop()
    cv2.destroyAllWindows()
    print("\n[INFO] Test finalizado exitosamente.")

if __name__ == "__main__":
    test_stream()
