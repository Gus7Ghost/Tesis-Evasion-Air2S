import cv2
import numpy as np
import tensorflow as tf

class DepthEstimator:
    """
    Motor de inferencia de Profundidad Monocular utilizando MiDaS v2.1 Small (TFLite).
    Optimizado para CPU, entrega alta velocidad con precisión geométrica relativa.
    """
    def __init__(self, config: dict):
        self.model_path = config["model_path"]
        self.width = config["input_width"]
        self.height = config["input_height"]
        
        print(f"[DepthEstimator] Inicializando intérprete TFLite con {self.model_path}...")
        # Pasamos num_threads directamente en el constructor para compatibilidad con TF modernos
        self.interpreter = tf.lite.Interpreter(model_path=self.model_path, num_threads=4)
        
        self.interpreter.allocate_tensors()
        
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()

        # Constantes de normalización estándar de ImageNet (Requeridas por MiDaS)
        self.mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        self.std = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    def estimate(self, frame: np.ndarray) -> np.ndarray:
        """
        Recibe un frame BGR de OpenCV y retorna un mapa de profundidad (disparidad).
        """
        # 1. Preprocesamiento
        img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, (self.width, self.height))
        
        # Normalización a float32 y estandarización (Z-score)
        img_input = (img.astype(np.float32) / 255.0)
        img_input = (img_input - self.mean) / self.std
        
        # Añadir dimensión de Batch: (1, 256, 256, 3)
        img_input = np.expand_dims(img_input, axis=0)
        
        # 2. Inferencia
        self.interpreter.set_tensor(self.input_details[0]['index'], img_input)
        self.interpreter.invoke()
        
        # 3. Postprocesamiento
        depth_map = self.interpreter.get_tensor(self.output_details[0]['index'])
        depth_map = depth_map[0] # Eliminar batch dim
        
        # El resultado es Disparidad: Valores altos = Objetos cercanos.
        return depth_map
