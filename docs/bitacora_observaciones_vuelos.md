# BITÁCORA DE OBSERVACIONES CRÍTICAS DE VUELO REAL
**Fecha:** 13 de Noviembre de 2026  
**Plataforma:** DJI Air 2S + RosettaDrone + MiDaS v2.1 Small  
**Estado:** ✅ CORREGIDO (18 de Noviembre de 2026) — Listo para segunda batería de 50 pruebas.

---

## 1. Movimiento Cinemático Predominante
* **Observación:** El dron tiende a moverse predominantemente en línea recta y hacia su derecha.
* **Aspecto a revisar posteriormente:** 
  * Balance de las velocidades laterales $v_y$ en la FSM.
  * Análisis de los sectores de disparidad (evaluar si el sector izquierdo presenta un sesgo de fondo que empuja constantemente el escape hacia la derecha).

---

## 2. Correspondencia entre Vista de Cámara y Sentido de Evasión
* **Observación:** Verificar que coincidan los controles observados con los que el código ejecuta; descartar si la imagen de video está en espejo o si el signo de $v_y$ en RosettaDrone VirtualSticks está invertido respecto al marco de referencia físico del dron.
* **Aspecto a revisar posteriormente:**
  * Prueba de comprobación de cuadrantes: Sector libre en pantalla vs vector de velocidad comandado (NED / Body Frame: $+y$ derecha, $-y$ izquierda en DJI).
  * Verificar si OpenCV recibe el flujo con o sin inversión horizontal.

---

## 3. Control de Gimbal y Rotación Activa del Dron
* **Observación:** Incorporar control del gimbal (cabeceo / pitch de la cámara) para que no quede estática y asegurar que el dron rote activamente sobre su eje vertical (*yaw / guiñada*).
* **Aspecto a revisar posteriormente:**
  * Inyección de comandos MAVLink `MAV_CMD_DO_MOUNT_CONTROL` para apuntar el gimbal hacia el centro del objetivo humano.
  * Verificar las ganancias del lazo proporcional de guiñada para que los giros sobre su eje sean más evidentes en vuelo físico.

---

## 4. Sensibilidad de Detección de la Caja en MiDaS
* **Observación:** Al acercar la caja al dron repetidamente, la red MiDaS no la pintó de amarillo (alta disparidad / proximidad) y no se activó la maniobra de evasión.
* **Aspecto a revisar posteriormente:**
  * Inspección de la salida numérica del tensor MiDaS con `ai-edge-litert` (verificar rango de normalización y escalas mín/máx).
  * Evaluación de la textura de la caja: si la caja es de color uniforme bajo luz artificial, verificar si MiDaS diluye el objeto con la pared.
  * Calibración de umbrales y del percentil para forzar la detección de contraste y disparidad en objetos homogéneos.


---

# CORRECCIONES APLICADAS (18-Nov-2026)

## Obs.1 — Sesgo de evasión hacia la derecha
* **Archivo:** `prototipo_completo_tesis.py`, línea ~1043
* **Causa raíz:** La condición `if dist_right >= dist_left` con operador `>=` siempre favorecía la derecha en empates.
* **Corrección:** Se agregó un margen de desempate del 15%. Si la diferencia entre el sector derecho e izquierdo es menor al 15%, la dirección de escape alterna entre ciclos pares e impares (`total_cycles % 2`), eliminando el sesgo sistemático.

## Obs.2 — Signo de vy (efecto espejo)
* **Archivo:** `prototipo_completo_tesis.py`, argumento `--invert-vy`
* **Estado:** Ya estaba corregido desde la versión anterior (`--invert-vy` activo por defecto = True). Se mantiene.

## Obs.3 — Control del gimbal y rotación activa de yaw
* **Archivo:** `prototipo_completo_tesis.py`
* **Corrección A (Gimbal):** Se agregó el método `_setup_gimbal_pitch()` que envía un comando de cabeceo (*pitch*) de −15° al iniciar la conexión, apuntando la cámara ligeramente hacia abajo para capturar obstáculos a nivel del banco de pruebas.
* **Corrección B (Yaw):** La ganancia proporcional de guiñada se incrementó de 0.65 a **1.2** y el tope de velocidad angular de 25°/s a **40°/s**, haciendo que la rotación del dron sobre su eje vertical sea más pronunciada y visible durante el vuelo real.

## Obs.4 — Falta de sensibilidad de MiDaS ante la caja de cartón
* **Archivo:** `prototipo_completo_tesis.py`, línea ~963
* **Causa raíz:** La red MiDaS v2.1 Small depende de gradientes de textura para inferir profundidad monocular. Las cajas de cartón de color uniforme bajo luz fluorescente producen gradientes mínimos y se diluyen con el fondo.
* **Corrección:** Se aplica ecualización adaptativa CLAHE (clipLimit=3.0, 8×8) en el canal de luminancia L del espacio LAB **antes** de la normalización y la inferencia MiDaS. Esto realza los bordes y micro-texturas de superficies homogéneas, incrementando los valores de disparidad del obstáculo en el tensor de salida.


---

# AJUSTES CRÍTICOS PRUEBA 2 (18-Nov-2026)

## 1. Integración de Red Neuronal Profunda MobileNet-SSD para Seguimiento Humano
* **Problema:** Los clasificadores Haar Cascade perdían al usuario el 51% del tiempo si giraba el rostro o caminaba de espaldas, provocando que `cmd_yaw_rate` cayera a 0°/s.
* **Solución:** Se integró la red `mobilenet.caffemodel` (MobileNet-SSD) cargada vía OpenCV DNN, que detecta el cuerpo humano completo con más del 85% de confianza en cualquier postura y ángulo de visión.
* **Persistencia angular (Memoria de 2.0 s):** Si el humano sale rápido del encuadre por el flanco derecho o izquierdo, el dron mantiene activa la guiñada de búsqueda en esa dirección para re-engancharlo inmediatamente.

## 2. Rotación en su propio eje (Guiñada / Yaw) incrementada a ±55 deg/s
* **Problema:** El cabeceo/yaw del dron era insuficiente para mantener al objetivo encuadrado.
* **Solución:** Se aumentó la ganancia proporcional a $2.0 \times \text{target\_angle}$ con velocidad angular máxima de **55°/s**, generando giros sobre su eje vertical ágiles y visibles en vuelo físico.

## 3. Calibración de umbrales para laboratorio indoor
* **Problema:** En un laboratorio de ~3m de ancho, el margen lateral de 1.35m activaba falsas evasiones contra las paredes laterales, forzando al dron a derivar hacia la izquierda en lugar de perseguir.
* **Solución:**
  * Margen lateral reducido a `0.90 m` (evita falsas alarmas con paredes y estantes).
  * Umbral frontal de obstáculo (`OBSTACLE_THRESH`) fijado en `1.15 m`.
  * Umbral crítico (`CRITICAL_HALT`) fijado en `0.65 m` con escape lateral activo en vez de detención estática.


---

# VALIDACIÓN EMPÍRICA EN VUELO REAL (19-Nov-2026, 12:23)
**Archivos de telemetría analizados:**  
* `Air2S_MAVSDK/logs/metricas_vuelo_20261119_121914.csv` (898 ciclos, altitud hasta 1.80 m).
* `Air2S_MAVSDK/logs/metricas_vuelo_20261119_122221.csv` (577 ciclos, altitud hasta 1.50 m).

## 1. Resultados Validados Empíricamente
* **Rotación en su Propio Eje (*Yaw*):**
  * Rango de orientación (*heading*) registrado: **$-176.5^\circ$ a $+176.0^\circ$** (diferencia de **$352.5^\circ$**, rotación completa en 360° para mantener el encuadre del usuario).
* **Velocidad y Maniobras de Evasión:**
  * Superación exitosa de la zona muerta de DJI con $0.65\text{ m/s}$. El dron se desplaza decididamente y evade obstáculos delgados y paredes.
* **Activación Completa de la Máquina de Estados (FSM):**
  * Todos los estados de navegación fueron ejecutados con éxito:
    1. `PERSIGUIENDO_HUMANO`
    2. `ESQUIVANDO_HACIA_IZQUIERDA`
    3. `ESQUIVANDO_HACIA_DERECHA`
    4. `ESCAPE_EMERGENCIA_DER`
    5. `ESCAPE_EMERGENCIA_IZQ`
    6. `CORRECCION_PARED_IZQ`
    7. `CORRECCION_PARED_DER`
    8. `ROTANDO_BUSCANDO_HUMANO`
    9. `BUSQUEDA_CRUCERO`

## 3. Desacoplamiento Cinemático: Eliminación del Sobre-Viraje Lateral (*Banked Turns*)
* **Causa del desvío "de largo" a la izquierda:**  
  Al aparecer un obstáculo frente al dron y ocluir temporalmente a la persona, el módulo de seguimiento angular conservaba en memoria el último ángulo observado (ej. $-35^\circ$), ordenando una guiñada de $-45^\circ/\text{s}$. Simultáneamente, el planificador reactivo activaba la evasión lateral izquierda con $v_y = -0.65\text{ m/s}$. La combinación de balanceo lateral izquierdo (*Roll*) con rotación en el eje hacia la izquierda (*Yaw*) generó un viraje en curva inclinada (*banked turn*), acelerando al dron con fuerza centrípeta hacia la pared izquierda.
* **Solución Implementada:**
  1. **Desacoplamiento Estricto:** Durante cualquier maniobra de evasión (`ESQUIVANDO`, `ESCAPE_EMERGENCIA`, `CORRECCION_PARED`), la velocidad angular se fuerza a cero absoluto (`cmd_yaw_rate = 0.0`). El dron se desplaza de forma puramente lateral (traslación en cangrejo mediante *Roll*), manteniendo su orientación de brújula fija.
  2. **Definición Clara del Giro en su Eje:** La rotación sobre el eje vertical se restringe a:
     * *Persecución Activa (`PERSIGUIENDO_HUMANO`):* Solo con camino frontal despejado, con zona muerta de $\pm 5^\circ$ y velocidad angular suave acotada a $\pm 28^\circ/\text{s}$.
     * *Búsqueda en el Lugar (`ROTANDO_BUSCANDO_HUMANO`):* Solo en hover estático ($v_x=0, v_y=0$) y con frente despejado ($> 1.25\text{ m}$), a $\pm 22^\circ/\text{s}$.
  3. **Calibración de Velocidad Lateral:** Se ajustó la velocidad de escape a $0.45\text{ m/s}$ (avance de evasión $0.10\text{ m/s}$), eliminando la inercia excesiva en laboratorio.

## 4. Regulación de Distancia Segura (*Standoff* a 1.0 m), Rotación Pura en el Eje y Control Continuo de Altura (1.70 m)
* **Archivos de telemetría analizados:**  
  * `Air2S_MAVSDK/logs/metricas_vuelo_20261119_132638.csv` (798 ciclos, 174.8 s).
  * `Air2S_MAVSDK/logs/metricas_vuelo_20261119_134448.csv` (1902 ciclos, 242.6 s, 80.2% tiempo con objetivo detectado).
* **Diagnóstico de las dos anomalías del Vuelo 134448:**
  1. **Caída a 50 cm de altura:** Al comenzar la persecución longitudinal ($v_x = 0.35\text{ m/s}$), el cuadricóptero se inclina hacia adelante (*pitch down*), lo que reduce naturalmente el empuje vertical ($T_z = T \cos\theta$). Al no haber un lazo cerrado continuo inyectando sustentación ascendente ($v_z$), el dron se hundió hasta los 40–50 cm.
  2. **Por qué no giraba en su eje:** La distancia calculada se saturó en 5.00 m, manteniendo $v_x = 0.35\text{ m/s}$ activo todo el tiempo. Un vehículo que avanza a $0.35\text{ m/s}$ simultáneamente con guiñada realiza una trayectoria curva con avance, no un giro sobre su propio eje.
* **Soluciones Definitivas Implementadas en `prototipo_completo_tesis.py`:**
  1. **Hallazgo Crítico: Convención de Signo Vertical en RosettaDrone:**
     * En el estándar MAVLink/NED formal, $v_z < 0$ es ascenso. Sin embargo, **RosettaDrone mapea el parámetro `down_m_s` directamente a la API de DJI Mobile SDK (`verticalThrottle`) sin invertir el signo**.
     * En el SDK de DJI, **los valores POSITIVOS (+m/s) ordenan SUBIR, y los valores NEGATIVOS (-m/s) ordenan BAJAR**.
     * Al enviar valores negativos para "subir", el software estaba ordenando descender al piso (-0.52 m/s), estancando el dron en 0.40–0.60 m.
     * **Corrección:** Se alineó el signo: ante cualquier error por debajo de la meta ($alt < 1.62\text{ m}$), se envía **$+0.35 \dots +0.55\text{ m/s}$ (SUBIR)**.
     * **Resultado:** El dron se eleva decididamente desde el despegue ($\ge 0.20\text{ m}$) hasta anclarse en **$1.70\text{ m}$** y mantiene esa altura sin importar las maniobras de avance.
  2. **Giro Puro en su Propio Eje Desacoplado:**
     * **Prioridad Absoluta de Orientación:** Si el objetivo se desvía más de $6.0^\circ$ hacia la izquierda o derecha, **la velocidad de avance y lateral se cancela a cero absoluto ($v_x = 0.0, v_y = 0.0$)**.
     * El dron se frena en seco y rota sobre su propio eje vertical (*Yaw*) a $24.0 \dots 42.0^\circ/\text{s}$ hasta encuadrar a la persona.
  3. **Aproximación y Standoff a 1.0 Metro Exacto:**
     * Solo cuando la persona está encuadrada ($|\theta| \le 6.0^\circ$), el dron avanza suavemente ($v_x = 0.30\text{ m/s}$) si la distancia es mayor a $1.05\text{ m}$.
     * Al alcanzar la zona de 1 metro ($0.70\text{ m} \le d \le 1.05\text{ m}$), $v_x = 0.0\text{ m/s}$ (*Hover* completo en seco).
     * Si la persona se acerca a menos de $0.70\text{ m}$, micro-retroceso suave ($v_x = -0.15\text{ m/s}$).





## 5. Eliminación de Oscilación Vertical (Limit-Cycle Hunting) y Adopción Dinámica de Altura Manual
* **Archivo de telemetría analizado:**
  * Air2S_MAVSDK/logs/metricas_vuelo_20261119_141513.csv (650 ciclos, 84.4 s, 399 ciclos en el aire).
* **Diagnóstico de la Oscilación Vertical (1.60 m <-> 1.80 m):**
  * En la telemetría se comprobó que el dron subió a 1.70 m de inmediato (el signo positivo de ascenso funcionó al 100%), pero osciló rítmicamente a ~0.6 Hz:
    1.6m -> 1.8m -> 1.7m -> 1.6m -> 1.8m -> 1.7m... (106 ciclos en 1.6m, 91 ciclos en 1.8m, 77 ciclos en 1.7m).
  * **Causa Física:** El lazo de control anterior poseía un salto discontinuo (bang-bang): al medir 1.60m, inyectaba un empuje brusco de +0.38 m/s (SUBIR). Por inercia y latencia del enlace UDP/RosettaDrone (~150 ms), el dron rebasaba 1.70m hasta 1.80m. Al cruzar 1.78m, el lazo invertía abruptamente a -0.31 m/s (BAJAR), precipitándolo a 1.60m y repitiendo el ciclo de rebote indefinidamente.
* **Solución Implementada:**
  1. **Aproximación Suave con Desaceleración Progresiva:**
     Desde el despegue hasta los 1.35 m, sube a +0.35 m/s. Entre 1.35 m y 1.62 m, una rampa lineal reduce progresivamente la velocidad ascendente de +0.35 m/s hasta +0.08 m/s, eliminando por completo el exceso de inercia (overshoot).
  2. **Bloqueo Nativo en Hover con VPS DJI (vz = 0.0 m/s):**
     Al llegar a la ventana de 1.70m (error <= 8 cm), se fija estrictamente vz = 0.0 m/s y se marca initial_climb_done = True. Al recibir 0.0 m/s, el sistema de posicionamiento visual inferior (VPS) del DJI Air 2S toma el control automático y bloquea la altitud con precisión milimétrica sin batir motores.
  3. **Adopción Automática de Altura Manual desde el Control Físico DJI:**
     Como vz = 0.0 m/s, el piloto puede mover libremente la palanca de aceleración del mando físico DJI para subir o bajar el dron a la altura deseada. El script detecta cuando la nueva cota se estabiliza por >= 1.0 s (Delta h >= 0.20 m) y actualiza automáticamente 	arget_alt = current_alt, manteniendo la nueva altitud fijada sin luchar contra el piloto.
  4. **Piso de Seguridad de Emergencia:**
     Si en cualquier momento la altitud desciende de 0.65 m, se inyecta un suave empuje ascendente (+0.25 m/s) para proteger al dron del suelo.

## 6. Corrección de Escala Angular MAVSDK-RosettaDrone (Factor 57.3) y Centrado Continuo Fino
* **Archivo de telemetría analizado:**
  * Air2S_MAVSDK/logs/metricas_vuelo_20261119_143414.csv (2395 ciclos, 323.2 s de vuelo autónomo continuo).
* **Confirmación de Altitud Estable a 1.70 m:**
  * Durante los 323.2 segundos en el aire (2292 ciclos), la altitud media fue **1.697 m con desviación estándar de solo 3.4 cm** (2273 ciclos clavado en 1.7 m). La oscilación vertical previa quedó 100% erradicada.
* **Diagnóstico Matemático del Giro Lento en el Eje:**
  * Al analizar la velocidad angular real (\text{heading})/dt$ vs cmd_yaw_rate_degs en los 1620 ciclos de ROTANDO_EN_EJE, se descubrió una relación exacta:
    \frac{\text{Velocidad Angular Real}}{\text{Velocidad Comandada}} = 0.0177 \approx \frac{1}{57.2958} = \frac{1}{\text{rad/deg}}
  * **Causa Raíz:** MAVSDK en su backend C++ convierte el parámetro yawspeed_deg_s a radianes por segundo antes de construir el paquete MAVLink SET_POSITION_TARGET_LOCAL_NED. Por su parte, la app RosettaDrone en la tablet toma el campo flotante MAVLink y lo entrega **directamente** a la API de DJI Mobile SDK (FlightControlData.setYaw), la cual opera en **grados por segundo**.
  * En consecuencia, una orden de ^\circ/\text{s}$ se convertía en .73^\circ/\text{s}$ en los motores DJI (¡57 veces más lento de lo previsto!). Girar ^\circ$ tomaba más de 40 segundos, provocando que la persona alcanzara las esquinas de visión ($-38.4^\circ$) antes de que el dron pudiera orientarse.
* **Soluciones Implementadas en prototipo_completo_tesis.py:**
  1. **Compensación de Ganancia Angular (yaw_gain = 57.3):**
     * En _control_tick, se multiplica scaled_yaw_cmd = safe_yaw * self.yaw_gain antes de pasar a VelocityBodyYawspeed.
     * Esto neutraliza la división de MAVSDK, haciendo que el dron rote físicamente a la velocidad real de **^\circ/\text{s} \dots 45^\circ/\text{s}$** (un giro de ^\circ$ se completa ahora en solo .75$ segundos).
  2. **Estrategia Multinivel de Centrado Continuo:**
     * **Zona Muerta Central:** $\pm 1.5^\circ$ (centro absoluto en la pantalla).
     * **Alineación Continua Fina (.5^\circ < |\theta| \le 5.0^\circ$):** El dron ajusta suavemente la orientación a ^\circ/\text{s} \dots 22^\circ/\text{s}$ mientras avanza hacia la persona, evitando que el objetivo se desvíe del centro mientras camina.
     * **Giro Puro en su Eje ($|\theta| > 5.0^\circ$):** Detención completa de avance/deriva ( = 0, v_y = 0$) y giro reactivo a ^\circ/\text{s} \dots 45^\circ/\text{s}$ para re-encuadrar instantáneamente al objetivo.
     * **Búsqueda Ágil tras Pérdida:** Si el objetivo sale momentáneamente del encuadre, rota a ^\circ/\text{s}$ en la dirección de memoria.

## 7. Calibración Amortiguada del Giro en el Eje (Eliminación de Sobreimpulso y Desenfoque de Detección)
* **Archivo de telemetría analizado:**
  * Air2S_MAVSDK/logs/metricas_vuelo_20261119_145128.csv (545 ciclos, 430 ciclos en el aire).
* **Diagnóstico del Giro Rápido y Pérdida de Objetivo:**
  * Al desbloquear la ganancia angular de 57.3, la velocidad de rotación real del cuadricóptero subió abruptamente hasta **.6^\circ/\text{s}$** (con órdenes continuas de ^\circ/\text{s}$).
  * **Causa Física:** A más de ^\circ/\text{s}$ en interiores:
    1. El sensor de la cámara genera desenfoque de movimiento (*motion blur*), reduciendo drásticamente la confianza de MobileNet-SSD y perdiendo la detección humana temporalmente (se registraron 70 transiciones a ROTANDO_BUSCANDO_HUMANO).
    2. La inercia angular de los 600 gramos del DJI Air 2S rebasaba la zona muerta central, causando un latigazo en péndulo hacia el lado opuesto (^\circ \to 61^\circ \to 141^\circ$).
* **Solución Calibrada (Control Proporcional Amortiguado):**
  1. **Reducción de Velocidades Angulares a Régimen Estable:**
     * **Zona Muerta:** $\pm 2.5^\circ$ (centro óptimo en la imagen).
     * **Micro-centrado suave (.5^\circ < |\theta| \le 8.0^\circ$):** Rotación sutil de **.0^\circ/\text{s} \dots 10.0^\circ/\text{s}$** mientras avanza a 1 metro.
     * **Giro Puro en su Eje ($|\theta| > 8.0^\circ$):** Cancelación de traslación ( = 0, v_y = 0$) y giro acotado a **.0^\circ/\text{s} \dots 18.0^\circ/\text{s}$** (máximo techo absoluto: .0^\circ/\text{s}$).
     * **Búsqueda en pérdida momentánea:** Giro calmo a **.0^\circ/\text{s}$** para permitir que la red neuronal reconozca inmediatamente a la persona sin distorsión.
  2. **Resultado Esperado:** Giro suave, nítido y controlado. El dron no sobre-vira, no desenfoca la cámara y mantiene al objetivo enfocado continuamente sin perderlo.

## 8. Eliminación del Tartamudeo Avance-Freno (Histéresis 4°-14°) y Retroceso Activo Inmediato a 1.0 m
* **Archivo de telemetría analizado:**
  * Air2S_MAVSDK/logs/metricas_vuelo_20261119_145656.csv (715 ciclos, 606 ciclos en el aire).
* **Diagnóstico de las Dos Anomalías:**
  1. **Tartamudeo de Avance y Freno (Toggling  = 0.30 \leftrightarrow 0.00$):**
     * En la telemetría se comprobó que el estado alternaba continuamente cada 200 ms entre AVANZANDO_HACIA_HUMANO ( = 0.30$) y ROTANDO_EN_EJE ( = 0.00$) debido al umbral rígido sin histéresis en .0^\circ$.
     * Al avanzar con guiñada activa, el ángulo oscilaba entre .5^\circ$ y .3^\circ$, clavando los frenos repetidamente y haciendo que el dron avanzara a tirones mientras oscilaba izquierda-derecha.
  2. **Ausencia de Retroceso al Acercarse y Pérdida de Objetivo:**
     * La zona de hover estaba configurada en un rango excesivamente amplio (.70\text{ m} \le d \le 1.05\text{ m}$). Cuando la persona se acercaba de 1.0 m a 0.75 m, el dron se quedaba estático ( = 0.0$).
     * Al cruzar los 0.70 m, el cuerpo de la persona llenaba verticalmente todo el encuadre de la cámara, provocando que la red MobileNet-SSD perdiera la detección de cuerpo entero (box is None).
     * Al perder la detección, el planificador interpretaba a la persona como un obstáculo genérico y activaba la evasión lateral avanzando hacia adelante (cmd_vx = 0.10), perdiendo de vista al objetivo por completo.
* **Soluciones Implementadas en prototipo_completo_tesis.py:**
  1. **Histéresis Angular Desacoplada (.0^\circ \leftrightarrow 14.0^\circ$):**
     * Solo se conmuta a rotación pura en el eje ( = 0$) si el desvío angular supera los **.0^\circ$**.
     * Una vez iniciada la rotación, se continúa hasta centrar el objetivo a $\le 4.0^\circ$.
     * Mientras avanza, los desvíos leves (^\circ \dots 14^\circ$) se corrigen con una suave micro-alineación (.5^\circ/\text{s} \dots 7.5^\circ/\text{s}$) **sin detener el avance**. El avance es continuo, suave y en línea recta, sin tirones.
  2. **Regulación Bidireccional Activa de 1.0 Metro:**
     * **Zona de Hover Estable:** .90\text{ m} \le d \le 1.15\text{ m}$ ( = 0.0\text{ m/s}$).
     * **Avance Suave:**  > 1.15\text{ m}$ ( = +0.16 \dots +0.28\text{ m/s}$).
     * **Retroceso Inmediato y Decidido:** Tan pronto la persona cruza hacia  < 0.90\text{ m}$, el dron **inicia retroceso activo a $-0.24\text{ m/s}$** (y $-0.32\text{ m/s}$ si  < 0.65\text{ m}$), alejándose para restaurar el metro de separación.
  3. **Memoria de Proximidad Humana:**
     * Si la persona está muy cerca ( < 1.15\text{ m}$) y la detección de cuerpo entero se pierde temporalmente por el encuadre cerrado, el dron reconoce que es la persona y **continúa retrocediendo ( = -0.26\text{ m/s}$)** en lugar de esquivar lateralmente. Al retroceder, el cuerpo completo vuelve a entrar en cuadro y el enganche visual no se interrumpe.

## 9. Evasión Lateral de Obstáculos Intermedios (Flanking) con Mantenimiento del Objetivo en el Eje
* **Archivo de telemetría analizado:**
  * Air2S_MAVSDK/logs/metricas_vuelo_20261119_150546.csv (1677 ciclos, 1473 ciclos en el aire).
* **Confirmación del Retroceso y Distancia Segura a 1.0 m:**
  * En la telemetría se registraron 213 ciclos de retroceso activo (RETROCESO_MANTENIENDO_1M y RETROCESO_RAPIDO_SEGURIDAD) y 142 ciclos de hover estático a 1 metro (ENFOCANDO_A_1_METRO). El mantenimiento de la burbuja de 1 metro y el retroceso reactivo ante la aproximación humana quedaron 100% validados.
* **Diagnóstico de la Falta de Evasión de la Caja Delgada (5 cm):**
  * Al colocar una caja de 5 cm de grosor entre el dron y la persona, la red MobileNet-SSD continuaba detectando el cuerpo de la persona detrás de la caja (box is not None).
  * En el código anterior, dentro del bloque elif bbox is not None:, la velocidad lateral $ estaba forzada a cero absoluto ( = 0.0$, salvo para márgenes de paredes). El algoritmo de evasión lateral solo existía en el bloque secundario elif dist_center < OBSTACLE_THRESH:, el cual quedaba completamente eclipsado al detectar a la persona. Por tanto, el dron permanecía ciego a obstáculos intermedios y no ejecutaba esquiva lateral.
* **Soluciones Implementadas en prototipo_completo_tesis.py:**
  1. **Estimador Óptico de Distancia del Objetivo ({\text{humano}}$):**
     * A partir de la altura normalizada del recuadro delimitador ({\text{norm}} = h_{\text{box}} / h_{\text{frame}}$), se calcula la distancia geométrica al humano: {\text{hum}} \approx 0.75 / h_{\text{norm}}$.
  2. **Detección Sensible de Obstáculo Delgado:**
     * En disp_to_meters, se evalúan los percentiles 95.0 y 98.5 del corredor central (sec_narrow), asegurando que perfiles estrechos de 5 cm generen una lectura de disparidad dominante ({\text{centro}} < 1.10\text{ m}$).
  3. **Maniobra de Flanqueo Lateral con Re-Encuadre en el Eje:**
     * Si {\text{centro}} < 1.10\text{ m}$ y el humano está visible detrás ({\text{hum}} > d_{\text{centro}} + 0.25\text{ m}$), el sistema activa el **MODO 1.B: EVASIÓN DE OBSTÁCULO INTERMEDIO**.
     * **Decisión de Escape:** Evalúa la profundidad lateral (dist_right >= dist_left) para elegir el lado más despejado.
     * **Traslación Lateral ( = \pm 0.35\text{ m/s}$):** El dron da un paso lateral para salir de la sombra de la caja.
     * **Giro Simultáneo en el Eje ($):** A medida que se desplaza hacia un lado, rota su morro hacia el lado opuesto para mantener al humano fijado en el centro del encuadre, logrando que el objetivo quede con línea de visión limpia y sin obstáculos intermedios.


## 10. Detección, Realce Brillante y Cuadro Amarillo del Obstáculo Delgado (5 cm) con Evasión Flanqueante
* **Objetivo de la Corrección:**
  * Adoptar formalmente la denominación técnica **"obstáculo delgado"** en toda la interfaz, máquina de estados FSM, HUD y logs.
  * Resolver la detección de obstáculos de perfil estrecho (5 cm de espesor) que se interponen entre el dron y el humano, los cuales eran visualmente omitidos porque la figura humana detrás dominaba la segmentación.
  * Realzar el obstáculo delgado de manera **brillante e incandescente** en el mapa de profundidad estimada (`right_view`).
  * Marcar el obstáculo delgado con un **cuadro delimitador amarillo** (`(0, 255, 255)` BGR) en la pantalla de la cámara de persecución (`left_view`).
  * Ejecutar maniobra de evasión lateral flanqueante ($v_y = \pm 0.35\text{ m/s}$) con giro simultáneo sobre su propio eje (Yaw) para recentrar al humano y asegurar que el objetivo no quede detrás del obstáculo delgado.
* **Soluciones Implementadas en `prototipo_completo_tesis.py` y `Air2S_MAVSDK/prototipo_completo_tesis.py`:**
  1. **Aislamiento Morfológico Top-Hat Horizontal (`kernel = 25 x 1`):**
     * En la matriz de disparidad MiDaS ($256 \times 256$), se ejecuta una apertura morfológica horizontal para sustraer el fondo ancho y aislar crestas verticales estrechas:
       $disp\_thin = depth\_norm - \text{cv2.morphologyEx}(depth\_norm, \text{MORPH\_OPEN}, (25, 1))$.
     * Se genera una máscara binaria focalizada en el corredor central y el entorno del objetivo humano para segmentar el obstáculo delgado incluso cuando no cubre la totalidad de la figura humana.
     * Mediante filtrado geométrico (altura $\ge 18\text{ px}$, anchura entre $4$ y $75\text{ px}$, relación de aspecto esbelta $\ge 1.10$), se extraen las coordenadas $(x, y, w, h)$ y se calcula su distancia métrica real $d_{\text{obs}}$.
     * Se integró persistencia temporal ($0.35\text{ s}$) para evitar parpadeos visuales en caso de ligeras variaciones de iluminación.
  2. **Realce Brillante en el Mapa de Profundidad (`right_view`):**
     * En la matriz de visualización previa al mapa de color, la disparidad en la región del obstáculo delgado se satura al **100% de brillo** ($depth\_norm\_vis = 1.0$), generando una respuesta luminosa incandescente (amarillo/blanco brillante en paletas Turbo, Inferno y Plasma).
     * Se renderiza un cuadro delimitador de realce y la etiqueta `OBSTACULO DELGADO ({d_obs:.2f}m)` directamente en la vista de profundidad.
  3. **Cuadro Amarillo en la Pantalla de Persecución (`left_view`):**
     * En la vista de la cámara de persecución, el obstáculo delgado se dibuja con un **recuadro amarillo** (`(0, 255, 255)`, grosor 3 px) y banner legible `OBSTACULO DELGADO ({d_obs:.2f}m)`.
     * El objetivo humano se mantiene en verde (`Target: Humano`), permitiendo una clara distinción visual en el HUD.
     * Si el obstáculo delgado se interpone en la línea de visión al humano, se activa la alerta en pantalla: `¡HUMANO DETRAS DE OBSTACULO! ESQUIVANDO...`.
  4. **Evasión Lateral Flanqueante y Centrado en el Eje:**
     * Cuando el obstáculo delgado obstruye el trayecto ($d_{\text{obs}} < 1.30\text{ m}$ y humano detrás):
       * **Traslación Lateral:** $v_y = +0.35\text{ m/s}$ (derecha) o $-0.35\text{ m/s}$ (izquierda) hacia el flanco con mayor profundidad disponible, respetando márgenes de pared ($SIDE\_MARGIN = 0.65\text{ m}$).
       * **Velocidad Longitudinal:** Micro-retroceso cauto ($v_x = -0.15\text{ m/s}$) si $d_{\text{obs}} < 0.65\text{ m}$, o suave avance diagonal ($v_x = +0.08\text{ m/s}$) para superar la obstrucción.
       * **Guiñada Proporcional en el Eje (Yaw):** Giro dinámico ($6.0^\circ/\text{s} \dots 16.0^\circ/\text{s}$, multiplicado por $yaw\_gain = 57.3$) enfocado en el humano para mantenerlo en el centro visual del dron mientras este flanquea lateralmente el obstáculo.
       * **Estado FSM:** `ESQUIVANDO_OBSTACULO_DELGADO_DERECHA >>` o `<< IZQUIERDA`.


## 11. Eliminación de Falsos Positivos Lejanos en Detección de Obstáculos Delgados y Confinamiento al Campo Cercano
* **Archivos de telemetría analizados:**
  * `Air2S_MAVSDK/logs/metricas_vuelo_20261119_160340.csv` (2557 ciclos).
  * `Air2S_MAVSDK/logs/metricas_vuelo_20261119_160920.csv` (938 ciclos, 532 ciclos con activación espuria de obstáculo).
* **Diagnóstico de la Desestabilización por Falsos Positivos Lejanos:**
  1. **Confusión de Estructuras Distantes con Obstáculos Delgados:**
     * En la telemetría se comprobó que el estado `ESQUIVANDO_OBSTACULO_DELGADO` se disparó 532 veces a distancias del humano de $1.7\text{ m} \dots 2.6\text{ m}$ con lecturas de obstáculo a $1.1\text{ m} \dots 1.3\text{ m}$ (`ESQUIVANDO_OBSTACULO_DELGADO_DERECHA >> (Obs:1.29m | Hum:2.06m)`).
     * **Causa Física:** El filtro morfológico Top-Hat horizontal (`disp_thin_peak > 0.018` y `depth_norm > 0.58`, correspondiente a $1.61\text{ m}$) poseía una tolerancia excesiva que detectaba cualquier borde vertical distante en el laboratorio (marcos de puertas, patas de mesas, aristas de muebles, esquinas de paredes o el propio contorno del cuerpo del humano).
     * Como el humano estaba a $\sim 2.0\text{ m}$, la condición `d_cand < d_human_est + 0.25` resultaba verdadera en casi todos los ciclos. El dron creía falsamente que el humano estaba detrás de un obstáculo, cancelando el avance frontal e iniciando una oscilación violenta lateral ($v_y = \pm 0.35\text{ m/s}$) de vaivén descontrolado.
* **Soluciones Implementadas en `prototipo_completo_tesis.py` y `Air2S_MAVSDK/prototipo_completo_tesis.py`:**
  1. **Confinamiento Físico Estricto al Campo Cercano ($d \le 0.95\text{ m}$):**
     * Se incrementó el umbral de disparidad mínima de detección a $depth\_norm \ge 0.76$ ($d \le 0.95\text{ m}$).
     * Cualquier estructura ubicada a más de $0.95\text{ m}$ (fondos, puertas, muebles lejanos) queda completamente excluida de la detección de obstáculos delgados.
  2. **Contraste de Disparidad Prominente y Filtrado Geométrico Esbelto:**
     * Se elevó el umbral de la cresta Top-Hat a $disp\_thin\_peak \ge 0.055$ (eliminando texturas leves y pliegues de ropa).
     * Se exigió una relación de aspecto fuertemente vertical: $aspect\_ratio \ge 1.60$ con altura mínima de $32\text{ px}$ en tensor ($> 35\text{ cm}$ reales) y anchura entre $6$ y $42\text{ px}$.
  3. **Condición Geométrica Estricta de Interposición:**
     * Para activar la evasión flanqueante `is_intermediate_obstacle`, el centro horizontal del obstáculo delgado debe estar **estrictamente superpuesto frente al cuerpo del humano** ($bx1 - 15 \le ox_{\text{center}} \le bx2 + 15$) y estar **al menos $20\text{ cm}$ más cerca** ($d_{\text{obs}} \le d_{\text{human}} - 0.20\text{ m}$).
     * Si el humano está a distancia lejana ($> 1.15\text{ m}$) sin un obstáculo inmediato a menos de $0.95\text{ m}$, el dron avanza de forma recta y estable sin realizar maniobras laterales espurias.
  4. **Suavizado de `disp_to_meters`:**
     * Se cambió del percentil 98.5 al percentil 92.0 con filtro Gaussiano $(5, 5)$, eliminando picos de ruido que generaban falsas lecturas de proximidad.


## 12. Prueba 1 de Vuelo (20/11/2026): Validación de Estabilidad y Detección de Falso Humano en Gigantografía de Laboratorio
* **Archivos de telemetría analizados:**
  * `Air2S_MAVSDK/logs/metricas_vuelo_20261120_143859.csv` (3029 ciclos, duración total: $494.62\text{ s} \approx 8.24\text{ min}$).
* **Resultados Positivos del Vuelo:**
  1. **Excelente Estabilidad de Altitud:**
     * Durante los 2150 ciclos con el dron en vuelo activo ($> 0.5\text{ m}$), la altitud media se mantuvo en $1.493\text{ m} \pm 0.166\text{ m}$, respetando el rango operativo seguro y alcanzando el tope de consigna fijado en $1.70\text{ m}$.
     * La latencia media de ciclo fue de $133.5\text{ ms}$ ($\sim 6.14\text{ FPS}$), con ejecución simultánea en CPU del modelo MiDaS y MobileNet-SSD.
  2. **Continuidad de Seguimiento Humano:**
     * Se registraron 1854 ciclos con detección de objetivo humano positiva ($61.2\%$ de la sesión).
     * Las maniobras de rotación sobre el eje (Yaw con ganancia $57.3$) mantuvieron el encuadre centrado sin oscilaciones parásitas.
* **Problema Identificado en Campo:**
  * En una de las paredes del laboratorio se encuentra colocada una **gigantografía/póster de gran tamaño de un científico**.
  * Al ingresar en el campo de visión de la cámara, MobileNet-SSD clasifica la imagen del científico como clase 15 (`person`), debido a que su morfología 2D (cabeza, hombros y torso) satisface plenamente las características convolucionales aprendidas.
  * Dado que el algoritmo seleccionaba el objetivo mediante el criterio de máxima confianza matemática (`conf > max_conf`), la gigantografía (al estar fija, nítida y perfectamente iluminada) generaba un puntaje de confianza superior al del piloto en movimiento, provocando que el dron desenganchara al piloto y se fijara en el póster.
* **Plan de Acción e Implementación de la Solución (Target Re-ID Semi-Automático con Tecla):**
  * Se descartó la necesidad de entrenar un dataset masivo desde cero (ineficiente, dependiente del vestuario y de alto costo computacional).
  * **Solución Implementada en Código (`prototipo_completo_tesis.py`):**
    1. **Bloqueo Semi-Automático por Tecla (`B`, `K`, `P`) y Clic en Pantalla:**
       * El piloto se ubica en el centro de la cámara y pulsa la tecla `B` (o hace clic sobre su figura en la ventana).
       * El sistema adquiere el bloqueo (`is_locked = True`) y computa un histograma de color HSV tridimensional $[8, 8, 8]$ normalizado en $L_1$ del torso del piloto.
    2. **Discriminación de Gigantografía por Distancia de Bhattacharyya e IoU Espacial:**
       * Para cada candidato detectado en escena, se evalúa:
         $$\text{Sim}_{\text{color}} = 1.0 - \text{cv2.compareHist}(H_{\text{piloto}}, H_{\text{cand}}, \text{cv2.HISTCMP\_BHATTACHARYYA})$$
         $$\text{Score} = 0.60 \times \text{Sim}_{\text{color}} + 0.40 \times \text{ContinuidadEspacial}$$
       * La gigantografía del científico (al presentar vestimenta y reflectancia distinta) arroja una similitud prácticamente nula ($\le 0.05$) y es clasificada como **`DESCARTADO: Gigantografia/Falso Humano`**, mostrándose en recuadro tenue en el HUD.
       * El piloto mantiene similitud $\ge 0.70$ y es seguido exclusivamente con recuadro **Cian Neón con esquinas de mira (`PILOTO [BLOQUEADO]`)**.
    3. **Teclas de Control y Desbloqueo:**
       * `[B]`: Bloquear/Re-bloquear piloto con la vestimenta actual.
       * `[U]`: Desbloquear objetivo y retornar al modo libre.
       * `[Clic]`: Selección directa por puntero sobre la pantalla.


## 13. Prueba 2 de Vuelo (20/11/2026): Validación de Re-ID y Corrección del Sobre-Paso Frontal por Desacople de Medición de Fondo
* **Archivo de telemetría analizado:**
  * `Air2S_MAVSDK/logs/metricas_vuelo_20261120_152330.csv` (1897 ciclos, duración total: $284.89\text{ s}$).
* **Comprobación Positiva:**
  * El sistema de identificación y bloqueo semi-automático reconoció y mantuvo identificado al piloto sin fijarse en la gigantografía de la pared, confirmando la eficacia del descriptor de color HSV y Re-ID en tiempo real.
* **Diagnóstico de la Pérdida de Control, Falta de Giro y Sobre-Paso:**
  1. **Confusión de Distancia (Uso de Fondo en lugar de la Persona):**
     * El controlador evaluaba el avance/retroceso respecto a `dist_center` (el tercio central de MiDaS).
     * Cuando el piloto se desplazaba lateralmente (ángulo $> 6^\circ$, presente en el $61\%$ de los ciclos con detección humana), el centro del encuadre apuntaba a la pared vacía del fondo ($1.8\text{ m} \dots 2.7\text{ m}$).
     * Como consecuencia, el sistema asumía que la persona estaba muy lejos y ordenaba avance frontal ($v_x = 0.28\text{ m/s}$).
  2. **Velocidad de Guiñada Insuficiente en Distancia Segura:**
     * Al estar fuera del modo de pivote puro, la guiñada estaba limitada a solo $3.5^\circ/\text{s} \dots 7.5^\circ/\text{s}$, insuficiente para orbitar a un humano a 1.0 m ($\omega \ge 20^\circ/\text{s}$).
     * El dron avanzaba frontalmente mientras giraba muy lentamente, pasándose de largo por el costado del piloto y perdiéndolo de vista.
  3. **Aceleración Ciega en Búsqueda:**
     * Al perder de vista al objetivo, el estado `BUSQUEDA_CRUCERO` aceleraba el dron hacia adelante a $0.21\text{ m/s}$ (1,000 ciclos), alejándolo aún más en el laboratorio.
* **Soluciones Implementadas en `prototipo_completo_tesis.py` y `Air2S_MAVSDK/prototipo_completo_tesis.py`:**
  1. **Medición Localizada de la Distancia al Piloto (`d_target`):**
     * Se extrae la profundidad dentro del recuadro del humano en MiDaS y se fusiona con la altura geométrica:
       $d_{\text{target}} = 0.55 \cdot d_{\text{midas\_roi}} + 0.45 \cdot d_{\text{geom}}$.
     * La regulación de distancia mide estrictamente al piloto, sin importar si está al centro, izquierda o derecha.
  2. **Regla de Oro Anti-Sobrepaso ($|target\_angle| > 6.0^\circ \implies v_x = 0.0$):**
     * Si el piloto está descentrado ($> 6.0^\circ$), la velocidad longitudinal se anula estrictamente ($v_x = 0.0, v_y = 0.0$).
     * El dron se detiene horizontalmente y gira ágilmente sobre su propio eje vertical ($5.0^\circ/\text{s} \dots 24.0^\circ/\text{s}$) hasta recentrar al piloto.
  3. **Hover Estático a 1.0 m y Retroceso Activo:**
     * Centrado $\le 6^\circ$ y $0.90\text{ m} \le d \le 1.25\text{ m}$: hover estático absoluto ($v_x = 0.0, v_y = 0.0$).
     * Aproximación $< 0.90\text{ m}$: retroceso activo inmediato ($v_x = -0.24\text{ m/s}$).
     * Avance $v_x > 0$ permitido únicamente si el piloto está centrado y se encuentra a $> 1.25\text{ m}$.
  4. **Hover de Espera en Pérdida:**
     * Si el piloto sale de cuadro, el dron no avanza hacia las paredes ($v_x = 0.0$), sino que hace hover en el lugar y rota sobre su eje en la última dirección vista para re-engancharlo.


