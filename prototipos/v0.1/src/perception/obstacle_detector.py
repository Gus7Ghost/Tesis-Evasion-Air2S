import numpy as np

class ObstacleDetector:
    """
    Convierte mapas de profundidad geométricos en información espacial para VFH+.
    Su función principal es extraer el obstáculo más cercano en cada columna (ángulo visual).
    """
    def __init__(self, config: dict):
        self.max_depth_meters = config.get("max_depth_meters", 10.0)
        # FOV Horizontal del DJI Air 2S (aproximadamente 88 grados)
        self.fov_horizontal_deg = 88.0 
        
        self.last_min_distance = -1.0

    def to_polar_histogram(self, depth_map: np.ndarray):
        """
        Toma el mapa 2D y lo comprime en un Histograma Polar 1D.
        Asume que los obstáculos críticos (árboles, postes) son verticales.
        
        Retorna:
            angles (np.ndarray): Array de grados (ej. -44.0 a +44.0).
            histogram (np.ndarray): 'Densidad' de obstáculo en ese ángulo (0.0 a 1.0).
        """
        # 1. Normalizar el mapa de profundidad
        # MiDaS devuelve disparidad (valores más altos = más cerca).
        # Lo escalamos de 0 (infinito/libre) a 1.0 (colisión inminente).
        d_min = depth_map.min()
        d_max = depth_map.max()
        
        if d_max - d_min > 1e-6:
            depth_norm = (depth_map - d_min) / (d_max - d_min)
        else:
            depth_norm = np.zeros_like(depth_map)
            
        # 2. Compresión Columnar (Proyección al plano 1D)
        # Tomamos el valor máximo (el objeto más cercano) a lo largo del eje Y (vertical)
        # Esto reduce una imagen (256, 256) a un array 1D de (256,)
        polar_histogram = np.max(depth_norm, axis=0)
        
        # 3. Mapeo Angular
        width = depth_map.shape[1]
        half_fov = self.fov_horizontal_deg / 2.0
        # Generamos un array lineal de ángulos desde la izquierda (-) a la derecha (+)
        angles = np.linspace(-half_fov, half_fov, width)
        
        # Opcional: Calcular la distancia mínima cruda para las métricas de la Tesis
        # Si la disparidad máxima es 1.0, simulamos una distancia en metros
        max_disparity = np.max(polar_histogram)
        if max_disparity > 0:
            # Fórmula inversa simplificada (distancia ~ 1/disparidad)
            # Adaptada para evitar divisiones por cero y limitarla al máximo visible
            self.last_min_distance = self.max_depth_meters * (1.0 - max_disparity)
        else:
            self.last_min_distance = self.max_depth_meters
            
        return angles, polar_histogram

    def get_min_distance(self) -> float:
        """Devuelve la distancia más cercana detectada (en metros simulados) para el Logger."""
        return self.last_min_distance
