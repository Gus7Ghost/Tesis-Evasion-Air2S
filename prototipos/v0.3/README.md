# Bitácora de Prototipo: Versión 0.3 (v0.3)
**Hito:** Máquina de Estados Finitos (FSM), Reanudación Continua de Seguimiento y Diagnóstico de Telemetría/Video

---

## 1. Lo que se hizo
* **Implementación de la Máquina de Estados Finitos (FSM):** Se formalizó el ciclo de navegación reactiva bajo una arquitectura de 4 estados para cumplir estrictamente con los requerimientos metodológicos del asesor de tesis:
  1. `BUSQUEDA`: El dron mantiene posición al no haber una persona en el campo de visión (FOV).
  2. `SEGUIMIENTO`: Comportamiento nominal donde el vector de velocidad guía al dron hacia la persona centrada.
  3. `EVASION`: Interrupción de seguridad cuando un obstáculo se encuentra a menos del radio crítico ($r_{seg} \le 1.5\text{ m}$) o cuando el vector óptimo VFH+ diverge más de $8^\circ$ del objetivo.
  4. `REANUDANDO`: Estado de transición post-evasión donde el dron realinea su orientación hacia la persona una vez superado el obstáculo, garantizando la continuidad de la misión.
* **Interfaz HUD Dinámica:** Se integró un Head-Up Display en OpenCV que proyecta sobre la pantalla en tiempo real: Estado de la FSM (con códigos de color Verde, Rojo, Amarillo, Gris), FPS reales, Latencia global en milisegundos, Distancia mínima estimada al obstáculo, y Comparativa angular entre Objetivo y Evasión.
* **Logging Científico para Tesis:** Actualización de `logger.py` para registrar en `logs/metrics_log.csv` las columnas: `Timestamp`, `Estado_FSM`, `Latencia_Total_ms`, `FPS`, `Distancia_Obstaculo_m`, `Angulo_Objetivo_deg`, `Angulo_Evasion_deg`, `Latitud`, `Longitud` y `Altitud_m`.
* **Herramienta de Diagnóstico Aislado:** Creación de `test_video.py` para verificar la conectividad de la cámara RTSP sin necesidad de activar motores ni gastar batería del dron.

---

## 2. Problemas, Fallos y Dificultades
1. **Pérdida de Conexión de Video RTSP:**
   - *Error:* `[ WARN:0@30.083] global cap_ffmpeg_impl.hpp:453 _opencv_ffmpeg_interrupt_callback Stream timeout triggered after 30082.853000 ms`.
   - La laptop recibía la telemetría MAVLink, pero el flujo de video no abría la ventana gráfica.
2. **Observación Metodológica del Asesor:**
   - Necesidad de demostrar documental y empíricamente que tras esquivar un obstáculo el dron no se desorienta y retoma inmediatamente la persecución.
3. **Restricción de Datasets para Postes y Cables Urbanos:**
   - Dificultad para encontrar datasets representativos de la densidad desordenada de ciudades latinoamericanas (Perú) con cableado aéreo y postes de concreto.

---

## 3. Diagnóstico Técnico
1. **Bloqueo de Buffer en OpenCV VideoCapture:** OpenCV por defecto acumula frames en cola TCP/UDP; si la tasa de transmisión no está perfectamente sincronizada o el switch en RosettaDrone está inactivo, el hilo principal se congela por timeout.
2. **Acoplamiento Implícito:** Anteriormente, el algoritmo VFH+ fusionaba el ángulo objetivo dentro de la función de costo, pero no existía una variable de estado discreta que probara ante un jurado cuándo el sistema estaba esquivando y cuándo estaba persiguiendo.
3. **Brecha de Dominio:** Los datasets estándar como Cityscapes o KITTI representan ciudades europeas ordenadas con calles anchas y sin marañas de cables.

---

## 4. Cómo lo Solucionamos
* **Aislamiento y Flags FFMPEG de Baja Latencia:** En `test_video.py` y `video_stream.py` se inyectaron las variables de entorno `rtsp_transport;udp|fflags;nobuffer|flags;low_delay` para vaciar el búfer de cuadros y permitir pruebas rápidas de red.
* **Formalización de Transición con Histéresis:** En `main.py` se codificó la condición de salida: el estado `REANUDANDO` vuelve a `SEGUIMIENTO` en cuanto la discrepancia angular $|\theta_{evasion} - \theta_{objetivo}| \le 3^\circ$, garantizando suavidad cinemática.
* **Selección de Benchmarks Urbanos Análogos:** Se seleccionó el **India Driving Dataset (IDD)** y colecciones de **Roboflow (Utility Poles)** como base de entrenamiento idónea para entornos de alta densidad similares a Perú.
