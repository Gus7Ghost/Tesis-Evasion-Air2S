# Sistema de Seguimiento y Evasión Autónoma para DJI Air 2S 🚁

Este repositorio contiene el código fuente para un sistema de navegación autónoma desarrollado como proyecto de Tesis de Ingeniería de Sistemas. El sistema dota a un dron comercial (DJI Air 2S) de capacidades de Inteligencia Artificial para rastrear a una persona y esquivar obstáculos urbanos (postes, árboles) en tiempo real, procesándolo todo en una computadora de forma externa.

## 🏗️ Arquitectura del Hardware y Red

Debido a que el DJI Air 2S es un dron de ecosistema cerrado y no admite código interno nativo, se diseñó la siguiente arquitectura en puente:
1. **Dron:** DJI Air 2S.
2. **Puente (Android):** Aplicación de código abierto [RosettaDrone](https://github.com/RosettaDrone/rosettadrone) corriendo en una Tablet conectada por USB al control remoto. Traduce el video a RTSP y la telemetría al protocolo universal MAVLink vía UDP.
3. **Procesamiento (Laptop):** Computadora ejecutando este repositorio en Python, utilizando `MAVSDK` para enviar órdenes de vuelta al dron.

## 🧠 Pipeline de Inteligencia Artificial (Sense-Plan-Act)

1. **Captura:** Recepción de video vía RTSP con cero-buffer (Hilos de OpenCV) y telemetría asíncrona.
2. **Percepción (Visión Computacional):**
   - **Person Tracker:** Red neuronal MobileNet-SSD (OpenCV DNN Nativo) para identificar al piloto y calcular el ángulo base de seguimiento.
   - **Depth Estimator:** Modelo MiDaS v2.1 Small (TensorFlow Lite) para extraer la geometría espacial y predecir cercanía de colisión.
   - **Proyección Espacial:** Compresión del mapa 3D a un Histograma Polar 1D.
3. **Planificación:** Variante del algoritmo matemático **VFH+ (Vector Field Histogram Plus)** modificado para buscar el sector libre seguro que minimice la desviación del objetivo principal.
4. **Ejecución:** Envío de vectores de velocidad bidimensionales (Pitch/Roll) en modo *Offboard* que RosettaDrone traduce en comandos *Virtual Sticks*.

## 🚀 Instrucciones de Uso

### Requisitos Previos
- Python 3.8+
- Entorno virtual con: `mavsdk<4`, `opencv-python==4.10.0.84`, `tensorflow`, `numpy`, `pyyaml`.
- Descargar los modelos a la carpeta `models/`:
  - `midas_v21_small_256.tflite`
  - `mobilenet.caffemodel` y su `deploy.prototxt`

### Configuración
1. Conectar la Tablet y la Laptop a la misma red Wi-Fi local.
2. En el archivo `config.yaml`, ingresar la dirección IP de la Tablet en la variable `video_stream_uri`.
3. En RosettaDrone (Tablet), configurar la IP de la laptop en el campo **GCS IP** y habilitar **Video Streaming**.

### Ejecución
Activar el entorno virtual y lanzar el sistema de control:
```bash
python main.py
```
*Se abrirá una interfaz HUD (Head-Up Display) dibujando en tiempo real las detecciones y el mapa de profundidad.*

## 📊 Sistema de Evaluación para Tesis
El sistema incluye de forma nativa los módulos `Profiler` y `Logger`, los cuales generan un archivo `.csv` en la carpeta `logs/`. Este archivo registra a alta frecuencia (Hz):
- Tiempos de latencia (ms) de cada submódulo algorítmico.
- Eficiencia general en FPS.
- Distancia crítica al obstáculo (metros).
- Ángulo de decisión matemática (VFH+).
- Coordenadas y comportamiento inercial.
