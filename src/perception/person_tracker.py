import cv2
import numpy as np

class PersonTracker:
    """
    Rastrea a una persona usando el detector HOG (Histogram of Oriented Gradients).
    Este método es 100% nativo de OpenCV, funciona en cualquier versión (incluyendo 5.0+)
    y no requiere descargar modelos externos ni librerías, evadiendo completamente 
    cualquier bloqueo de Windows Defender.
    """
    def __init__(self, config: dict):
        self.fov_horizontal_deg = config.get("fov_horizontal_deg", 88.0)
        
        print("[PersonTracker] Inicializando detector nativo HOG (OpenCV puro sin dependencias)...")
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def track(self, frame: np.ndarray):
        """
        Analiza el frame y busca a la persona dominante usando ventanas deslizantes.
        Retorna:
            target_angle (float): Ángulo en grados (- izquierda, + derecha) o None.
            bbox (tuple): Coordenadas (x1, y1, x2, y2) para dibujarla.
        """
        (h, w) = frame.shape[:2]
        
        # Detectar personas. winStride ajusta la velocidad vs precisión.
        # Devuelve las cajas (x, y, ancho, alto) y los pesos de confianza.
        boxes, weights = self.hog.detectMultiScale(frame, winStride=(8, 8), padding=(8, 8), scale=1.05)
        
        if len(boxes) == 0:
            return None, None
            
        max_area = 0
        best_box = None
        
        for (x, y, bw, bh) in boxes:
            area = bw * bh
            # Nos quedamos con la caja más grande (persona más cercana)
            if area > max_area:
                max_area = area
                # Convertir (x, y, w, h) a (x1, y1, x2, y2)
                best_box = (int(x), int(y), int(x + bw), int(y + bh))
                
        if best_box is None:
            return None, None
            
        # Calcular el centro horizontal de la detección
        startX, startY, endX, endY = best_box
        center_x = (startX + endX) / 2.0
        
        # Mapear ese pixel X a un ángulo real
        target_angle = (center_x / w - 0.5) * self.fov_horizontal_deg
        
        return target_angle, best_box
