import asyncio
from mavsdk import System

class TelemetryTracker:
    """
    Escucha la telemetría del dron vía MAVSDK de forma asíncrona.
    Mantiene el estado actualizado para que el planificador pueda leerlo sin bloquearse.
    """
    def __init__(self, drone: System):
        self.drone = drone
        
        # Estado actual del dron
        self.altitude_m = 0.0
        self.heading_deg = 0.0
        self.pitch_deg = 0.0
        self.roll_deg = 0.0
        self.latitude = 0.0
        self.longitude = 0.0

    async def start_tasks(self):
        """Inicia las tareas asíncronas para escuchar los streams de MAVSDK."""
        print("[Telemetry] Iniciando subscripciones de telemetría...")
        asyncio.create_task(self._update_position())
        asyncio.create_task(self._update_attitude())

    async def _update_position(self):
        """Stream constante de altitud y GPS."""
        async for position in self.drone.telemetry.position():
            self.altitude_m = position.relative_altitude_m
            self.latitude = position.latitude_deg
            self.longitude = position.longitude_deg

    async def _update_attitude(self):
        """Stream constante de la orientación del dron."""
        async for attitude in self.drone.telemetry.attitude_euler():
            self.heading_deg = attitude.yaw_deg
            self.pitch_deg = attitude.pitch_deg
            self.roll_deg = attitude.roll_deg

    def get_state(self) -> dict:
        """Devuelve un diccionario con el estado instantáneo del dron."""
        return {
            "altitude_m": self.altitude_m,
            "heading_deg": self.heading_deg,
            "pitch_deg": self.pitch_deg,
            "roll_deg": self.roll_deg,
            "lat": self.latitude,
            "lon": self.longitude
        }
