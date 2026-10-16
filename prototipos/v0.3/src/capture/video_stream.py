import os
import ctypes

# Inyectar variables de ultra baja latencia en el C-Runtime de Windows (msvcrt) para FFMPEG
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

class VideoStream:
    """
    Captura el stream de video de RosettaDrone (UDP 5600 via SDP).
    Usa un hilo en segundo plano con mutex para garantizar cero latencia y descartar cuadros viejos.
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
        
        print(f"[VideoStream] Vinculado a {self.uri} (UDP 5600 - Ultra Baja Latencia)...")

    def _update(self):
        """Bucle infinito en segundo plano para limpiar el buffer."""
        while self.running:
            if self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret and frame is not None:
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
