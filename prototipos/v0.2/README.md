# Bitácora de Prototipo: Versión 0.2 (v0.2)
**Hito:** Integración Hardware-Software (DJI Air 2S + RosettaDrone + MAVSDK) y Estabilización del Entorno

---

## 1. Lo que se hizo
* **Acoplamiento de Hardware Físico:** Se integró el dron cerrado comercial **DJI Air 2S** mediante un puente de red Wi-Fi:
  - **Mando DJI -> Cable USB -> Tablet Android (Redmi 13):** Ejecutando **RosettaDrone** para convertir la telemetría del SDK cerrado de DJI a paquetes estándar **MAVLink (UDP puerto 19980)** y el video a flujo **RTSP (puerto 8554)**.
  - **Laptop Windows:** Ejecutando Python con la librería **MAVSDK** para control de vuelo en modo *Offboard*.
* **Inferencia MiDaS en TFLite:** Implementación de `depth_estimator.py` utilizando el modelo cuantizado `midas_v21_small_256.tflite` con aceleración multihilo en CPU.
* **Control Cinemático Offboard:** Creación de `drone_controller.py` mapeando los vectores polares de evasión a comandos tridimensionales `VelocityBodyYawspeed` (Pitch / Roll / Yaw).
* **Secuencia de Despegue Automático:** Rutina de armado (`arm`) y despegue (`takeoff`) programada en el bucle principal.

---

## 2. Problemas, Fallos y Dificultades
1. **Bloqueo de Seguridad en Windows Defender (WDAC):**
   - *Error:* `OSError: [WinError 4551] Una directiva de Control de aplicaciones bloqueó este archivo. Error loading torch\lib\c10.dll`.
   - El sistema de seguridad institucional impidió la ejecución de PyTorch / YOLOv8.
2. **Incompatibilidad de Versión Mayor en MAVSDK v4:**
   - *Error:* `mavsdk._legacy.LegacyModuleError: No module named 'mavsdk.offboard'`.
   - MAVSDK actualizó automáticamente a la versión 4.0.2 con cambios incompatibles en su API.
3. **OpenCV 5.0 Experimental con Módulos Rotos:**
   - *Errores:* `cv2.error: Caffe importer has been removed` y posteriormente `AttributeError: module 'cv2' has no attribute 'HOGDescriptor'`.
   - Se había instalado una versión de desarrollo inestable (5.0.0.93) que eliminó clases fundamentales de visión.
4. **Deprecación de Métodos en TensorFlow Lite:**
   - *Error:* `AttributeError: 'Interpreter' object has no attribute 'set_num_threads'`.
5. **Timeout Crítico en Despegue Físico:**
   - *Error:* `mavsdk.action.ActionError: TIMEOUT: 'Timeout'; origin: takeoff()`.
   - El dron despegaba físicamente, pero el programa de Python abortaba la ejecución de inmediato.
6. **Riesgo de Vuelo en Interiores:**
   - En el laboratorio (techo de 2.5 metros), las paredes activaban el VFH+ de forma agresiva arriesgando una colisión física.

---

## 3. Diagnóstico Técnico
1. **Políticas WDAC:** Windows Defender Application Control restringe DLLs no firmadas o de gran volumen en la carpeta de usuario.
2. **Breaking Changes de MAVSDK:** La versión 4.x abandonó la arquitectura gRPC anterior y reestructuró la API de Offboard.
3. **Inestabilidad de OpenCV Alpha:** La rama 5.0 eliminó el backend Caffe e introdujo bugs en los descriptores clásicos.
4. **Actualización de API TFLite:** En TensorFlow >= 2.16, la configuración de hilos ya no se invoca como método de instancia, sino como parámetro del constructor.
5. **Ausencia de ACK en RosettaDrone:** La aplicación móvil transmite el comando al dron correctamente, pero no devuelve el mensaje de confirmación (`MAV_RESULT_ACCEPTED`) a la laptop dentro del tiempo límite de MAVSDK.

---

## 4. Cómo lo Solucionamos
* **Rastreador Nativo sin Dependencias Externas:** Se reprogramó `person_tracker.py` empleando el descriptor nativo **HOG (Histogram of Oriented Gradients)** con detector SVM preentrenado de OpenCV. Al estar compilado dentro del núcleo de OpenCV, no requiere DLLs de terceros y elude el bloqueo de Windows Defender.
* **Congelamiento de Dependencias Estables:**
  - Se forzó el downgrade a `mavsdk<4` (`mavsdk==3.17.4`).
  - Se desinstaló la versión alpha de OpenCV y se fijó `opencv-python==4.10.0.84`.
* **Refactorización de TFLite:** Se instanció el intérprete pasando `num_threads=4` directamente en el constructor: `tf.lite.Interpreter(model_path=..., num_threads=4)`.
* **Tolerancia a Fallos en Despegue:** Se envolvieron `arm()` y `takeoff()` en bloques `try-except` para capturar la excepción de timeout y permitir que el bucle de control continúe volando normalmente.
* **Freno de Mano de Seguridad para Pruebas Estacionarias:** Se forzó `controller.send_velocity(0.0, 0.0)` en `main.py`. El dron se mantiene en vuelo estacionario fijo (*hover*), permitiendo validar algoritmos, visión y métricas de forma segura dentro del laboratorio.
