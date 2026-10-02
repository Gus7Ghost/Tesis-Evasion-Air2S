import time
from collections import deque

class Profiler:
    """
    Mide el rendimiento del código (Latencia en milisegundos y FPS).
    Calcula cuánto tiempo tarda el procesador en ejecutar la IA vs las Matemáticas.
    """
    def __init__(self):
        # Para calcular los FPS suavizados
        self.frame_times = deque(maxlen=30)
        
        self.frame_start_time = 0.0
        self.step_start_time = 0.0
        
        self.latencies = {
            "capture": 0.0,
            "perception": 0.0,
            "planning": 0.0,
            "execution": 0.0,
            "total": 0.0
        }
        
    def start_frame(self):
        """Marca el inicio de un nuevo ciclo completo."""
        self.frame_start_time = time.perf_counter()
        
    def start_step(self, step_name: str):
        """Marca el inicio de un paso específico (ej. 'perception')."""
        # Si había un paso anterior midiéndose, lo cerramos
        if hasattr(self, 'current_step'):
            self.end_step()
            
        self.current_step = step_name
        self.step_start_time = time.perf_counter()
        
    def end_step(self):
        """Termina la medición del paso actual en milisegundos."""
        if hasattr(self, 'current_step'):
            elapsed_ms = (time.perf_counter() - self.step_start_time) * 1000.0
            self.latencies[self.current_step] = elapsed_ms
            delattr(self, 'current_step')
            
    def end_frame(self):
        """Termina el ciclo y guarda el tiempo total."""
        if hasattr(self, 'current_step'):
            self.end_step()
            
        end_time = time.perf_counter()
        total_elapsed_ms = (end_time - self.frame_start_time) * 1000.0
        self.latencies["total"] = total_elapsed_ms
        
        # Guardar tiempo absoluto para FPS
        self.frame_times.append(end_time)

    def get_fps(self) -> float:
        """Calcula los cuadros por segundo basados en los últimos 30 frames."""
        if len(self.frame_times) < 2:
            return 0.0
        
        time_diff = self.frame_times[-1] - self.frame_times[0]
        if time_diff <= 0:
            return 0.0
            
        return (len(self.frame_times) - 1) / time_diff

    def get_total_latency(self) -> float:
        """Devuelve la latencia total del último ciclo en milisegundos."""
        return self.latencies["total"]
        
    def print_report(self):
        """Imprime un desglose de tiempos en consola para depuración."""
        print(f"[Profiler] FPS: {self.get_fps():.1f} | Latencia Total: {self.latencies['total']:.1f}ms")
        print(f"  ├─ Captura: {self.latencies.get('capture', 0):.1f}ms")
        print(f"  ├─ Percepción (IA): {self.latencies.get('perception', 0):.1f}ms")
        print(f"  ├─ Planificación (VFH): {self.latencies.get('planning', 0):.1f}ms")
        print(f"  └─ Ejecución (MAVSDK): {self.latencies.get('execution', 0):.1f}ms")
