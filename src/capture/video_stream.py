import os
import ctypes

# Inyectar buffer grande (4MB) y threads=1 en Windows msvcrt para eliminar cuelgues de pthread y buffer lag
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

class VideoStream:
    """
    Captura el stream de video de RosettaDrone (UDP 5600 via SDP).
    Usa desacoplamiento rápido grab() / retrieve() y un hilo de lectura continuo
    para garantizar que el bucle de IA siempre procese el frame más reciente (latencia < 80ms).
    """
    def __init__(self, uri: str = "rosetta.sdp"):
        self.uri = uri
        self.cap = cv2.VideoCapture(self.uri, cv2.CAP_FFMPEG)
        self.current_frame = None
        self.running = True
        self.lock = threading.Lock()
        
        # Iniciamos el hilo que leerá y vaciará los frames constantemente
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()
        
        print(f"[VideoStream] Vinculado a {self.uri} (UDP 5600 - Tiempo Real / Threads=1)...")

    def _update(self):
        """Bucle infinito en segundo plano para vaciar el buffer de la red."""
        while self.running:
            if self.cap.isOpened():
                ret = self.cap.grab()
                if ret:
                    ret_decode, frame = self.cap.retrieve()
                    if ret_decode and frame is not None:
                        with self.lock:
                            self.current_frame = frame
                else:
                    time.sleep(0.005)
            else:
                time.sleep(0.05)

    def read_frame(self):
        """Devuelve el frame más reciente capturado (tiempo real)."""
        with self.lock:
            return self.current_frame

    def release(self):
        """Libera la captura de video y detiene el hilo."""
        self.running = False
        if self.cap.isOpened():
            self.cap.release()
