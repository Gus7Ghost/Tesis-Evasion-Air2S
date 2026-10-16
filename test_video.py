import os
import ctypes

# 1. Configurar bajo nivel en Windows para lectura inmediata sin buffer ni análisis previo
opt = (
    "OPENCV_FFMPEG_CAPTURE_OPTIONS=protocol_whitelist;file,rtp,udp|"
    "fflags;nobuffer|flags;low_delay|probesize;32|analyzeduration;0|max_delay;0"
)
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
    "protocol_whitelist;file,rtp,udp|fflags;nobuffer|flags;low_delay|probesize;32|analyzeduration;0|max_delay;0"
)
try:
    ctypes.cdll.msvcrt._putenv(opt.encode("ascii"))
except Exception:
    pass

import cv2
import threading
import time

class FastVideoReceiver:
    """Hilo de lectura continua para eliminar el buffer y la latencia."""
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
    print("  TEST DE VIDEO DE ULTRA BAJA LATENCIA (DJI Air 2S)")
    print("=" * 65)

    sdp_path = "rosetta.sdp"
    if not os.path.exists(sdp_path):
        with open(sdp_path, "w") as f:
            f.write("c=IN IP4 0.0.0.0\nm=video 5600 RTP/AVP 96\na=rtpmap:96 H264/90000\n")

    print("[Info] Conectando hilo receptor...")
    receiver = FastVideoReceiver(sdp_path)

    print("Esperando primer fotograma maestro (I-Frame)...")
    frame_count = 0
    fps_time = time.time()
    fps = 0

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

        # HUD en vivo
        display = frame.copy()
        cv2.putText(display, f"Air 2S Live Stream | FPS: {fps:.1f}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.putText(display, "Presiona 'q' para salir", (20, 75),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        cv2.imshow("Video en Vivo - DJI Air 2S (Cero Latencia)", display)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    receiver.stop()
    cv2.destroyAllWindows()
    print("[INFO] Test finalizado exitosamente.")

if __name__ == "__main__":
    test_stream()
