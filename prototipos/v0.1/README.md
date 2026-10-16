# Bitácora de Prototipo: Versión 0.1 (v0.1)
**Hito:** Definición del Pipeline Modular Sense-Plan-Act y Modelado Teórico de Evasión

---

## 1. Lo que se hizo
* **Diseño Arquitectónico Modular:** Se estructuró la solución bajo el paradigma de robótica autónoma *Sense-Plan-Act* dividiendo el sistema en módulos independientes:
  - `src/capture/`: Abstracción de cámaras y flujos de red.
  - `src/perception/`: Estimación de mapas de disparidad y visión computacional.
  - `src/planning/`: Algoritmo matemático VFH+ (Vector Field Histogram Plus).
  - `src/execution/`: Controlador de actuadores y comandos cinemáticos.
  - `src/metrics/`: Perfilador de latencias y escritor de bitácora CSV.
* **Modelado Algorítmico VFH+:** Se implementó la compresión de mapas de disparidad a histogramas polares unidimensionales (1D), aplicando umbrales de densidad para calcular el ángulo de escape óptimo libre de colisiones.

---

## 2. Problemas, Fallos y Dificultades
* **Fallo en Inferencia con PyDNet:** Al alimentar frames con resoluciones arbitrarias de cámara, el grafo congelado de TensorFlow arrojaba un error de incompatibilidad dimensional (`Tensor shape mismatch`).
* **Lógica Invertida de Proximidad:** El algoritmo trataba las áreas oscuras como obstáculos y las áreas brillantes como espacios libres, generando comportamientos de navegación inversos a los esperados.

---

## 3. Diagnóstico Técnico
* **Dimensiones Fijas del Checkpoint:** El modelo PyDNet original fue exportado con una capa de entrada estricta de `(1, 512, 256, 3)`, provocando excepciones al recibir frames estándar de video (`640x480` o `1280x720`).
* **Disparidad vs. Profundidad Métrica:** Los modelos monoculares estiman *disparidad relativa* (donde mayor valor numérico representa objetos más cercanos a la lente). Al asumir erróneamente que valores bajos indicaban cercanía, la lógica de seguridad quedaba invertida.

---

## 4. Cómo lo Solucionamos
* **Normalización y Reshape:** Se agregó un preprocesador matricial con `cv2.resize` que adapta cualquier frame al tamaño esperado por el tensor antes de la inferencia.
* **Inversión de Umbrales de Seguridad:** Se reescribió la lógica en la función de costo del histograma polar: valores altos de disparidad ahora activan inmediatamente los sectores bloqueados (`threshold_high = 0.8`), garantizando la evasión de obstáculos reales.
* **Plan de Migración:** Se tomó la decisión de migrar hacia **MiDaS v2.1 Small en formato TensorFlow Lite (TFLite)** para optimizar la velocidad en CPU y obtener una generalización urbana superior.
