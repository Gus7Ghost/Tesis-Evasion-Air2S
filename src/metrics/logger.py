import time
import os
import csv

class MetricsLogger:
    """
    Registra cada ciclo del bucle de control en un archivo CSV.
    Indispensable para generar los gráficos y análisis de la tesis.
    """
    def __init__(self, config: dict):
        self.filepath = config.get("csv_path", "logs/metrics_log.csv")
        
        # Crear directorio si no existe
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        
        # Inicializar el archivo y escribir encabezados si es nuevo
        file_exists = os.path.isfile(self.filepath)
        
        self.file = open(self.filepath, mode='a', newline='')
        self.writer = csv.writer(self.file)
        
        if not file_exists:
            # Cabeceras para el análisis en Excel
            self.writer.writerow([
                "Timestamp", 
                "Latencia_Total_ms", 
                "FPS",
                "Distancia_Obstaculo_m", 
                "Angulo_Evasion_deg",
                "Latitud",
                "Longitud",
                "Altitud_m"
            ])
            self.file.flush()
            
    def log(self, timestamp, latency_ms, fps, min_distance, evasion_angle, telemetry):
        """Escribe una fila de datos en el CSV."""
        self.writer.writerow([
            f"{timestamp:.3f}",
            f"{latency_ms:.1f}",
            f"{fps:.1f}",
            f"{min_distance:.2f}",
            f"{evasion_angle:.1f}",
            f"{telemetry.get('lat', 0.0):.6f}",
            f"{telemetry.get('lon', 0.0):.6f}",
            f"{telemetry.get('altitude_m', 0.0):.2f}"
        ])
        # Forzamos la escritura a disco por si el programa se interrumpe
        self.file.flush() 

    def close(self):
        """Cierra el archivo de log."""
        if self.file and not self.file.closed:
            self.file.close()
