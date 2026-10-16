import os
import ctypes

# 1. Configurar socket UDP grande (2MB) y permitir tráfico fluido sin saturación
opt = (
    "OPENCV_FFMPEG_CAPTURE_OPTIONS=protocol_whitelist;file,rtp,udp|"
    "fflags;nobuffer|flags;low_delay|buffer_size;2097152|max_delay;500000"
)
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
    "protocol_whitelist;file,rtp,udp|fflags;nobuffer|flags;low_delay|buffer_size;2097152|max_delay;500000"
)
try:
    ctypes.cdll.msvcrt._putenv(opt.encode("ascii"))
except Exception:
    pass

import cv2
import threading
import time
import sys

class StableVideoReceiver:
    """Hilo receptor con ensamblador de fragmentos FU-A (packetization-mode=1)."""
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
    print("  TEST DE RECEPCIÓN DE VIDEO DJI AIR 2S (UDP Puerto 5600)")
    print("=" * 65)

    sdp_path = "rosetta.sdp"
    if not os.path.exists(sdp_path):
        with open(sdp_path, "w") as f:
            f.write("c=IN IP4 0.0.0.0\nm=video 5600 RTP/AVP 96\na=rtpmap:96 H264/90000\na=fmtp:96 packetization-mode=1\n")

    print("[1/3] Conectando receptor de video...")
    receiver = StableVideoReceiver(sdp_path)

    print("[2/3] Sincronizando con el stream H.264 del dron...")
    print("      (Esperando fotograma maestro inicial / Keyframe, por favor no presiones Ctrl+C)")
    
    start_time = time.time()
    dots = 0
    while True:
        frame = receiver.get_latest_frame()
        if frame is None:
            time.sleep(0.5)
            dots += 1
            sys.stdout.write(f"\r      Sincronizando... [{dots}s]")
            sys.stdout.flush()
            continue

        print("\n\n[3/3] ¡ÉXITO TOTAL! Fotograma decodificado. Abriendo ventana en vivo...")
        break

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

        display = frame.copy()
        cv2.putText(display, f"DJI Air 2S Live | FPS: {fps:.1f}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.putText(display, "Presiona 'q' para salir", (20, 75),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        cv2.imshow("Video en Vivo - DJI Air 2S", display)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    receiver.stop()
    cv2.destroyAllWindows()
    print("\n[INFO] Test finalizado exitosamente.")

if __name__ == "__main__":
    test_stream()
