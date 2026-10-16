import math
from mavsdk import System
from mavsdk.offboard import OffboardError, VelocityBodyYawspeed

class DroneController:
    """
    Traduce las decisiones del algoritmo de evasión en comandos de vuelo 
    físicos (Pitch/Roll) vía MAVSDK y RosettaDrone.
    """
    def __init__(self, drone: System):
        self.drone = drone
        self.offboard_active = False

    async def start_offboard(self):
        """
        Activa el modo Offboard (Control por Computadora).
        Por seguridad, MAVLink requiere que se envíe al menos un comando inerte
        antes de autorizar el cambio de modo.
        """
        print("[Controller] Intentando iniciar modo Offboard...")
        try:
            # Comando inerte: 0 m/s en todos los ejes
            initial_velocity = VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0)
            await self.drone.offboard.set_velocity_body(initial_velocity)
            
            await self.drone.offboard.start()
            self.offboard_active = True
            print("[Controller] ✅ Modo Offboard ACTIVADO. Control tomado por la Laptop.")
            
        except OffboardError as error:
            print(f"[Controller] ❌ Error iniciando Offboard: {error._result.result}")
            print("Asegúrate de que RosettaDrone esté listo y el dron en el aire.")
            self.offboard_active = False

    async def send_velocity(self, angle_deg: float, speed_ms: float):
        """
        Envía comandos de velocidad (Pitch y Roll) al dron.
        
        Args:
            angle_deg: Ángulo de evasión (- a la izquierda, + a la derecha).
            speed_ms: Velocidad de evasión en metros/segundo.
        """
        if not self.offboard_active:
            # Si el modo offboard se desactivó por seguridad, no intentamos volar.
            return

        if speed_ms <= 0.01:
            # Si VFH+ dice 0 m/s (Todo bloqueado), frenamos en seco.
            forward = 0.0
            right = 0.0
        else:
            # Transformación Polar a Cartesiana (Cuerpo del Dron)
            angle_rad = math.radians(angle_deg)
            
            # Eje X del dron (Adelante = Pitch hacia abajo) -> Coseno
            forward = speed_ms * math.cos(angle_rad)
            
            # Eje Y del dron (Derecha = Roll a la derecha) -> Seno
            right = speed_ms * math.sin(angle_rad)

        # Configuramos el comando:
        # down_m_s = 0.0 (Mantenemos la altitud estable, no subimos ni bajamos)
        # yawspeed_deg_s = 0.0 (La cámara/trompa del dron sigue mirando al frente)
        velocity_cmd = VelocityBodyYawspeed(
            forward_m_s=forward,
            right_m_s=right,
            down_m_s=0.0,
            yawspeed_deg_s=0.0
        )
        
        try:
            # RosettaDrone traducirá esto a comandos de Virtual Sticks (Mobile SDK) de DJI
            await self.drone.offboard.set_velocity_body(velocity_cmd)
        except Exception as e:
            print(f"[Controller] ⚠️ Error enviando telemetría de control: {e}")

    async def stop(self):
        """
        Freno de seguridad. Envía 0 m/s y devuelve el control al piloto manual.
        """
        if self.offboard_active:
            try:
                # Frenar
                await self.drone.offboard.set_velocity_body(VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0))
                # Apagar control por IA
                await self.drone.offboard.stop()
                print("[Controller] Dron frenado. Offboard DESACTIVADO.")
            except Exception as e:
                print(f"[Controller] Error al detener Offboard: {e}")
            finally:
                self.offboard_active = False
