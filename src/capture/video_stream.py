import os
import ctypes

# Inyectar variables en el C-Runtime de Windows (msvcrt) para la DLL de FFMPEG
opt = "OPENCV_FFMPEG_CAPTURE_OPTIONS=protocol_whitelist;file,rtp,udp|fflags;nobuffer|flags;low_delay|max_delay;500000"
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
    "protocol_whitelist;file,rtp,udp|fflags;nobuffer|flags;low_delay|max_delay;500000"
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
    Usa un hilo en segundo plano para evitar la acumulación de buffer (latencia cero).
    """
    def __init__(self, uri: str):
        self.uri = uri
        
        self.cap = cv2.VideoCapture(self.uri, cv2.CAP_FFMPEG)
        self.current_frame = None
        self.running = True
        
        # Iniciamos el hilo que leerá los frames constantemente
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()
        
        print(f"[VideoStream] Vinculado a {self.uri} (UDP 5600)...")

    def _update(self):
        """Bucle infinito en segundo plano para limpiar el buffer."""
        while self.running:
            if self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    self.current_frame = frame
                else:
                    time.sleep(0.01)
            else:
                time.sleep(0.1)

    def read_frame(self):
        """Devuelve el frame más reciente capturado."""
        return self.current_frame

    def release(self):
        """Libera la captura de video y detiene el hilo."""
        self.running = False
        if self.cap.isOpened():
            self.cap.release()
