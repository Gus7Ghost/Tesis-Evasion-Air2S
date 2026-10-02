import cv2
import threading
import time
import os

class VideoStream:
    """
    Captura el stream RTSP de RosettaDrone.
    Usa un hilo en segundo plano para evitar la acumulación de buffer (latencia).
    """
    def __init__(self, uri: str):
        self.uri = uri
        
        # Opciones para forzar baja latencia en OpenCV/FFMPEG
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp|fflags;nobuffer|flags;low_delay"
        
        self.cap = cv2.VideoCapture(self.uri, cv2.CAP_FFMPEG)
        self.current_frame = None
        self.running = True
        
        # Iniciamos el hilo que leerá los frames constantemente
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()
        
        print(f"[VideoStream] Intentando conectar a {self.uri}...")

    def _update(self):
        """Bucle infinito en segundo plano para limpiar el buffer."""
        while self.running:
            if self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    self.current_frame = frame
                else:
                    # Si perdemos conexión, intentamos reconectar
                    self.cap.release()
                    time.sleep(1)
                    self.cap = cv2.VideoCapture(self.uri, cv2.CAP_FFMPEG)
            else:
                time.sleep(0.1)

    def read_frame(self):
        """Devuelve el frame más reciente capturado."""
        return self.current_frame

    def stop(self):
        """Detiene el hilo y libera los recursos."""
        self.running = False
        if self.thread.is_alive():
            self.thread.join()
        self.cap.release()
