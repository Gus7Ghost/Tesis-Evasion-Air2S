# Matriz de Gestión de Riesgos y Estrategias de Mitigación
**Taller de Investigación - Docente: Glen Rodríguez (Semana 07)**

En cumplimiento de los lineamientos de las Diapositivas 5 a 8 de la asignatura, se documenta la matriz formal de riesgos identificados en el desarrollo de la tesis y las estrategias de ingeniería aplicadas para su mitigación.

---

## 1. Riesgos Técnicos (Slide 5)

| Tipo de Riesgo | Ejemplo Específico en el Proyecto | Estrategia de Mitigación Implementada |
| :--- | :--- | :--- |
| **Falta de datos balanceados o representativos** | Ausencia de datasets locales para postes de concreto caóticos y marañas de cables aéreos peruanos. | Empleo de *Transfer Learning* y selección de datasets análogos de alta densidad urbana como **India Driving Dataset (IDD)** y Roboflow Utility Poles. |
| **Alta demanda computacional** | El dron no posee computadora a bordo (Onboard Computer); procesamiento pesado en GPU no disponible en campo. | Descarga y cuantización a **TensorFlow Lite (TFLite)** de MiDaS v2.1 Small con multihilo optimizado en CPU (4 núcleos). |
| **Errores de integración en interfaces** | RosettaDrone no retorna mensaje de confirmación ACK tras el comando de despegue (`takeoff`), deteniendo el script. | Implementación de bloques `try-except` tolerantes a fallos en MAVSDK para permitir la continuidad del lazo de control. |
| **Fallas de versión o compatibilidad** | Rupturas de código por actualización de MAVSDK v4, bugs en OpenCV 5.0 alpha y bloqueos de seguridad por WDAC en PyTorch. | **Congelamiento de dependencias en `requirements.txt`**: fijación de `mavsdk==3.17.4`, `opencv-python==4.10.0.84` y detector nativo HOG. |
| **Falta de reproducibilidad** | Variabilidad de resultados entre distintas corridas de vuelo o pérdida de telemetría. | Fijación de parámetros deterministas en `config.yaml` y registro sincrónico de telemetría y decisiones en archivo `metrics_log.csv`. |

---

## 2. Riesgos Metodológicos (Validación y Medición) (Slide 6)

| Tipo de Riesgo | Ejemplo Específico en el Proyecto | Estrategia de Mitigación Implementada |
| :--- | :--- | :--- |
| **Métricas mal elegidas** | Evaluar la evasión únicamente con una tasa booleana simple (chocó / no chocó). | Incorporación de métricas multidimensionales: Distancia mínima real al obstáculo ($m$), Latencia por etapa ($ms$), FPS sostenidos y estabilidad angular. |
| **Muestra o pruebas no representativas** | Probar únicamente en un laboratorio cerrado o con un único obstáculo artificial. | Diseño de experimentos en dos fases: Fase 1 (Laboratorio con freno de mano) y Fase 2 (Entorno urbano real con postes y árboles). |
| **Comparaciones injustas** | Comparar la latencia de la laptop con la de drones de laboratorio con hardware embebido dedicado. | Definir formalmente la arquitectura como *Offboard Edge Computing* midiendo la latencia neta del canal inalámbrico de forma independiente. |

---

## 3. Riesgos de Gestión del Proyecto (Slide 7)

| Tipo de Riesgo | Ejemplo Específico en el Proyecto | Estrategia de Mitigación Implementada |
| :--- | :--- | :--- |
| **Mal manejo del control de versiones** | Pérdida de código o sobrescritura accidental durante pruebas en campo. | Uso riguroso de Git y GitHub (`Gus7Ghost/Tesis-Evasion-Air2S`), versionado semántico con Git Tags (`v0.1`, `v0.2`, `v0.3`) y commits descriptivos. |
| **Falta de documentación de experimentos** | No registrar los parámetros con los que se voló una misión específica. | Mantenimiento de bitácoras por versión en `docs/prototipos/` y exportación automática de métricas fechadas en la carpeta `logs/`. |
| **Cambios de alcance no controlados** | Intentar desarrollar simultáneamente un piloto automático completo desde cero. | Acotar el alcance a **Navegación Reactiva y Evasión Local de Obstáculos Frontales**, aprovechando la estabilización inercial nativa del DJI Air 2S. |

---

## 4. Riesgos Cognitivos y de Complejidad (Slide 8)

| Tipo de Riesgo | Ejemplo Específico en el Proyecto | Estrategia de Mitigación Implementada |
| :--- | :--- | :--- |
| **Modelo excesivamente complejo** | Intentar entrenar redes neuronales de segmentación 3D punto a punto en tiempo real. | Adopción de una arquitectura híbrida probada: Percepción con Deep Learning ligero (MiDaS TFLite) acoplada a navegación matemática determinista (VFH+). |
| **Sobredependencia de herramientas automáticas** | Usar bibliotecas opacas sin entender la respuesta cinemática del dron. | Desacoplamiento explícito de cada etapa del pipeline, documentando las ecuaciones de costo y las transiciones de la Máquina de Estados Finitos (FSM). |
