import os
import ctypes

# 1. Configurar FFmpeg para lectura inmediata con baja latencia y buffer de 4MB
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
    Receptor de video en hilo secundario.
    Lee directamente con cap.read() y actualiza la última imagen disponible,
    eliminando el buffer y evitando el bloqueo de 2 minutos.
    """
    def __init__(self, sdp_path="rosetta.sdp"):
        self.cap = cv2.VideoCapture(sdp_path, cv2.CAP_FFMPEG)
        self.frame = None
        self.running = True
        self.lock = threading.Lock()
        
        self.thread = threading.Thread(target=self._reader, daemon=True)
        self.thread.start()

    def _reader(self):
        while self.running:
            if self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    with self.lock:
                        self.frame = frame
                else:
                    time.sleep(0.005)
            else:
                time.sleep(0.05)

    def get_latest_frame(self):
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
    print("[1/3] Conectando receptor de video...")
    receiver = RealtimeVideoReceiver(sdp_path)

    print("[2/3] Sincronizando flujo con la cámara...")
    dots = 0
    start_time = time.time()
    while receiver.get_latest_frame() is None:
        time.sleep(0.5)
        dots += 1
        elapsed = time.time() - start_time
        sys.stdout.write(f"\r      Sincronizando stream... [{elapsed:.1f}s]")
        sys.stdout.flush()

    print("\n\n[3/3] ¡VÍDEO EN VIVO CONECTADO! Mostrando ventana...")

    fps_time = time.time()
    frame_count = 0
    fps = 0.0

    while True:
        frame = receiver.get_latest_frame()
        if frame is None:
            time.sleep(0.01)
            continue

        frame_count += 1
        now = time.time()
        if now - fps_time >= 1.0:
            fps = frame_count / (now - fps_time)
            frame_count = 0
            fps_time = now

        display = frame.copy()
        cv2.putText(display, f"DJI Air 2S | FPS Camara: {fps:.1f}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.putText(display, "Tiempo Real | Presiona 'q' para salir", (20, 75),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        cv2.imshow("Video en Vivo - DJI Air 2S", display)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    receiver.stop()
    cv2.destroyAllWindows()
    print("\n[INFO] Test finalizado exitosamente.")

if __name__ == "__main__":
    test_stream()
