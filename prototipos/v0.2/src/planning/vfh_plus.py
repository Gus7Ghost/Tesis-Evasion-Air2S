import numpy as np

class VFHPlus:
    """
    Implementación del algoritmo Vector Field Histogram Plus (VFH+)
    adaptado para evasión de obstáculos con drones en base a visión monocular.
    """
    def __init__(self, config: dict):
        # Umbrales de densidad para considerar un sector bloqueado o libre
        self.threshold_high = config.get("threshold_high", 0.8)
        self.threshold_low = config.get("threshold_low", 0.4)
        
        # Velocidad máxima de avance
        self.max_speed = config.get("max_speed_ms", 2.0)
        
        # Pesos de la Función de Costo Matemático (ajustables para afinamiento en la Tesis)
        self.weight_target = 5.0    # Castigo por desviarse de la meta (0 grados = frente)
        self.weight_smooth = 2.0    # Castigo por cambiar bruscamente respecto a la decisión anterior
        
        self.last_selected_angle = 0.0

    def calculate_escape(self, angles: np.ndarray, polar_histogram: np.ndarray, telemetry: dict, target_angle: float = 0.0):
        """
        Calcula el mejor ángulo de escape y la velocidad segura.
        
        Args:
            angles: Array 1D con los ángulos del campo de visión (ej. -44 a +44).
            polar_histogram: Array 1D con la densidad de obstáculo (0.0 a 1.0).
            telemetry: Diccionario con telemetría actual (altitud, heading).
            target_angle: Ángulo deseado para perseguir al objetivo (viene de YOLO).
            
        Returns:
            best_angle (float): Ángulo relativo óptimo hacia dónde volar (grados).
            escape_speed (float): Velocidad de avance segura (m/s).
        """
        # 1. Binarización del Histograma
        # Marcamos como bloqueados los sectores donde la densidad del obstáculo supera el umbral seguro
        blocked_sectors = polar_histogram > self.threshold_low

        # 2. Encontrar Valles (Sectores Libres)
        valleys = self._find_valleys(angles, blocked_sectors)
        
        if not valleys:
            # ¡EMERGENCIA! Todo el campo visual está bloqueado.
            # Retornar ángulo 0 y velocidad 0 para que el dron frene en seco.
            return 0.0, 0.0

        # 3. Generar Ángulos Candidatos
        candidates = []
        for (start_idx, end_idx) in valleys:
            width_indices = end_idx - start_idx
            
            angle_start = angles[start_idx]
            angle_end = angles[end_idx]
            angle_center = (angle_start + angle_end) / 2.0
            
            # El centro del valle siempre es un buen candidato
            candidates.append(angle_center)
            
            # Si el hueco (valle) es muy ancho, no hace falta ir por el centro exacto,
            # podemos ir por los bordes (más cerca de la ruta original) dejando un margen.
            if width_indices > (len(angles) * 0.2): # Si es más del 20% del FOV
                margin = 10.0 # Margen de seguridad de 10 grados
                candidates.append(angle_start + margin)
                candidates.append(angle_end - margin)

        # 4. Evaluación (Función de Costo)
        best_angle = 0.0
        min_cost = float('inf')
        
        # Iteramos los candidatos comparándolos con el target_angle (La persona detectada)
        for candidate in candidates:
            # Costo 1: Desviación de la meta
            cost_target = abs(candidate - target_angle) * self.weight_target
            
            # Costo 2: Penalización por giros erráticos (inestabilidad)
            cost_smooth = abs(candidate - self.last_selected_angle) * self.weight_smooth
            
            total_cost = cost_target + cost_smooth
            
            if total_cost < min_cost:
                min_cost = total_cost
                best_angle = candidate

        self.last_selected_angle = best_angle
        
        # 5. Cálculo de Velocidad Adaptativa
        # Si el dron tiene que dar un giro brusco (ej. 40 grados), debe reducir la velocidad.
        # cos(0) = 1 (vel máxima), cos(60) = 0.5 (mitad de vel)
        speed_factor = np.cos(np.radians(best_angle))
        
        # Clip para asegurar que no vaya hacia atrás y tenga una vel mínima si avanza
        speed_factor = np.clip(speed_factor, 0.2, 1.0) 
        
        escape_speed = self.max_speed * speed_factor
        
        return best_angle, escape_speed

    def _find_valleys(self, angles: np.ndarray, blocked_sectors: np.ndarray) -> list:
        """
        Escanea el array booleano de sectores buscando secuencias continuas de 'False' (libre).
        """
        valleys = []
        in_valley = False
        start_idx = 0
        
        for i, is_blocked in enumerate(blocked_sectors):
            if not is_blocked and not in_valley:
                # Comienza un valle libre
                in_valley = True
                start_idx = i
            elif is_blocked and in_valley:
                # El valle libre se cierra por un obstáculo
                in_valley = False
                valleys.append((start_idx, i - 1))
        
        # Si terminamos de escanear y el valle seguía abierto
        if in_valley:
            valleys.append((start_idx, len(blocked_sectors) - 1))
            
        # Filtrado de seguridad: Descartar valles muy estrechos donde el dron no cabe.
        # Definimos que el dron necesita al menos un 10% del FOV libre para pasar de forma segura.
        min_width = int(len(angles) * 0.1)
        valid_valleys = [v for v in valleys if (v[1] - v[0]) >= min_width]
        
        return valid_valleys
