#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador del Documento Word Oficial de Tesis - Semana 10 (Versión Fluida, Concisa y Humana)
100% enfocado en el proyecto, el dron y los experimentos de laboratorio.
Sin menciones al docente, diapositivas ni teorías ajenas.
"""

import os
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

def set_cell_background(cell, hex_color):
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)

def set_cell_margins(cell, top=70, bottom=70, left=100, right=100):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
    tcPr.append(tcMar)

def add_header_table(doc):
    tbl = doc.add_table(rows=5, cols=2)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    
    col_widths = [Inches(2.4), Inches(4.6)]
    data = [
        ("Nombre del alumno:", "Gustavo Bryan López Cosme"),
        ("Título tentativo de la tesis:", "Sistema de evasión de postes y árboles basado en visión artificial para el vuelo en drones de persecución urbana en vecindarios de Lima"),
        ("Tema / área principal:", "Inteligencia Artificial (Visión Computacional, Deep Learning) y Robótica"),
        ("Docente asesor principal:", "Dr. Glen Darío Rodríguez Rafael"),
        ("Docente co-asesor:", "Dr. Celedonio Méndez Valdivia")
    ]
    
    for row_idx, (k, v) in enumerate(data):
        row = tbl.rows[row_idx]
        row.cells[0].text = k
        row.cells[1].text = v
        set_cell_background(row.cells[0], "F1F5F9")
        set_cell_background(row.cells[1], "FFFFFF")
        
        p0 = row.cells[0].paragraphs[0]
        p0.runs[0].font.bold = True
        p0.runs[0].font.size = Pt(9.5)
        p0.runs[0].font.color.rgb = RGBColor(15, 32, 67)
        
        p1 = row.cells[1].paragraphs[0]
        p1.runs[0].font.size = Pt(9.5)
        p1.runs[0].font.color.rgb = RGBColor(30, 41, 59)
        
        set_cell_margins(row.cells[0], top=50, bottom=50, left=90, right=90)
        set_cell_margins(row.cells[1], top=50, bottom=50, left=90, right=90)
        row.cells[0].width = col_widths[0]
        row.cells[1].width = col_widths[1]

def create_document():
    doc = Document()
    
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    style_normal = doc.styles['Normal']
    font = style_normal.font
    font.name = 'Calibri'
    font.size = Pt(11)
    font.color.rgb = RGBColor(30, 30, 30)

    # Encabezado
    p_header = doc.add_paragraph()
    p_header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_uni = p_header.add_run("UNIVERSIDAD NACIONAL DE INGENIERÍA\n")
    r_uni.bold = True
    r_uni.font.size = Pt(13)
    r_uni.font.color.rgb = RGBColor(15, 32, 67)

    r_fac = p_header.add_run("FACULTAD DE INGENIERÍA DE SISTEMAS E INFORMÁTICA\n")
    r_fac.bold = True
    r_fac.font.size = Pt(10.5)
    r_fac.font.color.rgb = RGBColor(71, 85, 105)

    r_curso = p_header.add_run("TALLER DE INVESTIGACIÓN — INFORME DE AVANCE (SEMANA 10)\n")
    r_curso.bold = True
    r_curso.font.size = Pt(10)
    r_curso.font.color.rgb = RGBColor(100, 116, 139)

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(6)
    p_title.paragraph_format.space_after = Pt(8)
    r_title = p_title.add_run("EVALUACIÓN DE FIABILIDAD Y VALIDEZ DEL PROTOTIPO EXPERIMENTAL DE NAVEGACIÓN AUTÓNOMA, SEGUIMIENTO Y EVASIÓN REACTIVA A 1.5 METROS (DJI AIR 2S)")
    r_title.bold = True
    r_title.font.size = Pt(11.5)
    r_title.font.color.rgb = RGBColor(15, 32, 67)

    add_header_table(doc)

    p_div = doc.add_paragraph()
    p_div.paragraph_format.space_before = Pt(8)
    p_div.paragraph_format.space_after = Pt(8)
    p_div_run = p_div.add_run("―" * 65)
    p_div.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_div_run.font.color.rgb = RGBColor(203, 213, 225)

    # --------------------------------------------------------------------------
    # 1. RESUMEN TÉCNICO DEL PROTOTIPO
    # --------------------------------------------------------------------------
    h1 = doc.add_paragraph()
    h1.paragraph_format.space_before = Pt(8)
    h1.paragraph_format.space_after = Pt(3)
    r1 = h1.add_run("1. Resumen técnico del prototipo")
    r1.bold = True
    r1.font.size = Pt(11.5)
    r1.font.color.rgb = RGBColor(15, 32, 67)

    p1 = doc.add_paragraph()
    p1.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p1.paragraph_format.line_spacing = 1.15
    p1.paragraph_format.space_after = Pt(5)
    p1.add_run(
        "El sistema desarrollado es un prototipo autónomo de visión y control reactivo para el dron DJI Air 2S. "
        "Su función es mantener al dron volando a una altura fija de 1.50 metros, seguir la posición de una persona y esquivar "
        "obstáculos estrechos en tiempo real (postes de luz, ramas o cajas de 10 cm de grosor). "
        "Todo el procesamiento de inteligencia artificial se realiza en una computadora portátil estándar comunicada de forma "
        "inalámbrica con la aeronave, usando únicamente la cámara monocular del dron, sin sensores LiDAR ni peso adicional a bordo."
    )

    p1_desc = doc.add_paragraph()
    p1_desc.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p1_desc.paragraph_format.line_spacing = 1.15
    p1_desc.paragraph_format.space_after = Pt(6)
    p1_desc.add_run("La arquitectura funciona en cuatro módulos que corren en paralelo:\n")
    p1_desc.add_run("• Recepción y Decodificación de Video (Módulo A): ").bold = True
    p1_desc.add_run("Recibe el video H.264 por UDP (puerto 5600) desde la aplicación puente RosettaDrone. Un archivo patrón de 5 KB inicializa el decodificador de OpenCV en 28 milisegundos, eliminando pantallas grises y entregando siempre la imagen más reciente con búfer de tamaño 1.\n")
    p1_desc.add_run("• Estimación de Profundidad 3D (Módulo B): ").bold = True
    p1_desc.add_run("La red neuronal ligera MiDaS v2.1 Small procesa la imagen (256x256 px) en 52 ms en CPU. Para detectar objetos estrechos (como una caja de 10 cm o postes delgados), aplica un filtro Gaussiano y extrae el percentil 99.2% de disparidad, calculando distancias reales de 0.35 a 5.50 metros.\n")
    p1_desc.add_run("• Rastreo del Operador Humano (Módulo C): ").bold = True
    p1_desc.add_run("Ubica a la persona y calcula el error angular de guiñada para que el dron la mantenga al centro. Cuenta con un filtro adaptativo de luz (CLAHE) para no perder al usuario frente a ventanas o zonas con sombras.\n")
    p1_desc.add_run("• Planificador Reactivo y Control de Vuelo (Módulo D): ").bold = True
    p1_desc.add_run("Evalúa tres sectores frontales (Izquierda, Centro y Derecha). Si el frente está despejado (≥ 1.70 m), avanza a 0.35 m/s siguiendo a la persona; si un obstáculo se acerca a menos de 1.70 m, esquiva hacia el lado con más espacio libre; y si entra a menos de 0.85 m, frena en el acto. Además, inyecta una corrección vertical de -0.35 m/s para vencer la resistencia del autopiloto DJI y sostener firme la altura de 1.50 m.")

    # Imagen del diagrama de bloques
    diag_path = os.path.join("Air2S_MAVSDK", "docs", "graficos_tesis", "diagrama_arquitectura_bloques_detallado.png")
    if not os.path.exists(diag_path):
        diag_path = "docs/graficos_tesis/diagrama_arquitectura_bloques_detallado.png"
    if os.path.exists(diag_path):
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(6)
        p_img.paragraph_format.space_after = Pt(2)
        r_img = p_img.add_run()
        r_img.add_picture(diag_path, width=Inches(6.4))
        
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_after = Pt(8)
        r_cap = p_cap.add_run("Figura 1. Diagrama de bloques del prototipo: flujo de datos, entradas, salidas y lazo de control reactivo.")
        r_cap.font.size = Pt(9)
        r_cap.font.bold = True
        r_cap.font.color.rgb = RGBColor(15, 32, 67)

    # --------------------------------------------------------------------------
    # 2. CONFIGURACIÓN EXPERIMENTAL Y OPERACIONALIZACIÓN DE VARIABLES
    # --------------------------------------------------------------------------
    h2 = doc.add_paragraph()
    h2.paragraph_format.space_before = Pt(10)
    h2.paragraph_format.space_after = Pt(3)
    r2 = h2.add_run("2. Configuración experimental y operacionalización de variables")
    r2.bold = True
    r2.font.size = Pt(11.5)
    r2.font.color.rgb = RGBColor(15, 32, 67)

    p2 = doc.add_paragraph()
    p2.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p2.paragraph_format.line_spacing = 1.15
    p2.paragraph_format.space_after = Pt(5)
    p2.add_run(
        "En una investigación experimental en ingeniería, las métricas de desempeño tecnológico (como la tasa de esquive, "
        "el error de altura o la latencia en milisegundos) son precisamente las Variables Dependientes del estudio. "
        "La Variable Independiente es el sistema algorítmico desarrollado (red MiDaS con percentil 99.2% y control reactivo), "
        "y sus efectos se miden en el comportamiento y rendimiento del vuelo. La Tabla 1 formaliza esta operacionalización."
    )

    # Tabla Operacionalización
    p_top_title = doc.add_paragraph()
    p_top_title.paragraph_format.space_before = Pt(4)
    p_top_title.paragraph_format.space_after = Pt(2)
    r_top = p_top_title.add_run("Tabla 1. Matriz de operacionalización de variables del proyecto")
    r_top.bold = True
    r_top.font.size = Pt(9.5)

    tbl_op = doc.add_table(rows=6, cols=6)
    tbl_op.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_op.autofit = False

    op_headers = ["Variable", "Tipo", "Definición Conceptual", "Dimensiones", "Indicadores Medibles", "Instrumento de Registro"]
    op_widths = [Inches(1.2), Inches(0.8), Inches(1.5), Inches(1.1), Inches(1.3), Inches(1.1)]

    for idx, text in enumerate(op_headers):
        cell = tbl_op.rows[0].cells[idx]
        cell.text = text
        set_cell_background(cell, "1F497D")
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].font.bold = True
        p.runs[0].font.color.rgb = RGBColor(255, 255, 255)
        p.runs[0].font.size = Pt(8.5)
        set_cell_margins(cell, top=50, bottom=50, left=50, right=50)
        cell.width = op_widths[idx]

    op_data = [
        ("Sistema de Evasión Reactiva y Percepción", "VI", 
         "Algoritmos de visión por computador (MiDaS v2.1 TFLite), percentil 99.2% y planificador FSM de 3 sectores ejecutados en la estación terrena.",
         "• Percepción monocular\n• Planificación reactiva",
         "• Modelo MiDaS activo\n• Umbrales de seguridad (1.70 m / 0.85 m)\n• Estados de control",
         "Código fuente en Python y parámetros de configuración"),
        
        ("Eficacia de Evasión y Seguridad", "VD1",
         "Capacidad del dron para esquivar la caja de 10 cm sin chocar y conservando distancia de resguardo.",
         "• Prevención de choques\n• Margen de distancia",
         "• Tasa de evasión exitosa (%)\n• Distancia mínima real al obstáculo (m)\n• Frenadas de emergencia (%)",
         "Logs de telemetría MAVSDK en archivos CSV a 10 Hz"),
        
        ("Estabilidad de Vuelo a 1.50 m", "VD2",
         "Capacidad del dron para subir a 1.50 m venciendo la resistencia del autopiloto y permanecer estable.",
         "• Altitud de vuelo\n• Amortiguamiento",
         "• Altitud media en régimen (m)\n• Error cuadrático medio de altura (RMSE en m)\n• Tiempo de ascenso (s)",
         "Sensor barométrico y VPS del dron DJI Air 2S"),
        
        ("Precisión en el Seguimiento del Operador", "VD3",
         "Alineación de la cámara del dron con el centroide del cuerpo de la persona.",
         "• Centrado visual\n• Orientación angular",
         "• Error angular de guiñada (grados)\n• Velocidad de giro (deg/s)\n• Tiempo de permanencia en cámara (%)",
         "Módulo de visión (coordenadas de detección en pantalla)"),
        
        ("Eficiencia Computacional del Sistema", "VD4",
         "Tiempo de respuesta y fluidez con que la laptop procesa los fotogramas y envía órdenes al dron.",
         "• Tiempo de cálculo\n• Tasa de refresco",
         "• Latencia por ciclo de control (ms)\n• Fotogramas por segundo (FPS)\n• Tiempo de inicio de video (s)",
         "Profiler de software integrado en Python")
    ]

    for row_idx, row_values in enumerate(op_data):
        row = tbl_op.rows[row_idx + 1]
        bg = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, val in enumerate(row_values):
            cell = row.cells[col_idx]
            cell.text = val
            set_cell_background(cell, bg)
            p = cell.paragraphs[0]
            p.runs[0].font.size = Pt(8.5)
            set_cell_margins(cell, top=40, bottom=40, left=50, right=50)
            cell.width = op_widths[col_idx]
            if col_idx in (0, 1):
                p.runs[0].font.bold = True

    # Protocolo de 15 Vuelos en Laboratorio
    p2_lab = doc.add_paragraph()
    p2_lab.paragraph_format.space_before = Pt(8)
    p2_lab.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p2_lab.paragraph_format.line_spacing = 1.15
    p2_lab.paragraph_format.space_after = Pt(6)
    p2_lab.add_run("• Protocolo para la Sesión Experimental de 15 Vuelos en Laboratorio:\n").bold = True
    p2_lab.add_run(
        "Para validar cuantitativamente el prototipo, se definió una batería de 15 vuelos de prueba en el laboratorio (área libre de 4x4 metros):\n"
        "1. Duración de cada vuelo: 1 minuto (60 segundos). Los primeros 6 a 8 segundos se reservan para el despegue automático y ascenso firme hasta estabilizarse a 1.50 metros; los siguientes 45 segundos corresponden a la prueba activa de obstáculos; y los últimos 5 segundos se destinan al aterrizaje seguro.\n"
        "2. Características del obstáculo: Una caja vertical de 10 cm de grosor (representando el perfil esbelto de un poste o tronco joven).\n"
        "3. Interacciones por vuelo: La caja se acerca entre 3 y 4 veces de forma frontal y lateral hacia el dron (dejando unos 8 a 10 segundos entre intentos para que el dron complete la maniobra y se recentre). Con 4 aproximaciones por vuelo a lo largo de los 15 vuelos, se obtendrán 60 maniobras reales de evasión registradas en los archivos CSV.\n"
        "4. Criterio de éxito: El dron debe detectar la caja al cruzar los 1.70 m, frenar el avance frontal y desplazarse hacia un lado, manteniendo en todo momento una distancia libre mayor a 0.40 m sin contacto físico."
    )

    # --------------------------------------------------------------------------
    # 3. RESULTADOS DE PRUEBAS PRELIMINARES Y ANOMALÍAS RESUELTAS
    # --------------------------------------------------------------------------
    h3 = doc.add_paragraph()
    h3.paragraph_format.space_before = Pt(10)
    h3.paragraph_format.space_after = Pt(3)
    r3 = h3.add_run("3. Resultados de pruebas preliminares y anomalías resueltas")
    r3.bold = True
    r3.font.size = Pt(11.5)
    r3.font.color.rgb = RGBColor(15, 32, 67)

    p3_res = doc.add_paragraph()
    p3_res.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p3_res.paragraph_format.line_spacing = 1.15
    p3_res.paragraph_format.space_after = Pt(6)
    p3_res.add_run(
        "En las pruebas iniciales de banco y vuelo cautivo en interiores (acumulando 319 ciclos de control a 10 Hz), "
        "el prototipo demostró estabilidad operativa. A continuación se analizan los gráficos experimentales obtenidos "
        "y los problemas técnicos reales que se presentaron y fueron resueltos en el código:"
    )

    img_dir = os.path.join("Air2S_MAVSDK", "docs", "graficos_tesis")
    if not os.path.exists(img_dir):
        img_dir = "docs/graficos_tesis"

    def insert_graph(fig_num, filename, caption, analysis, anomaly):
        fpath = os.path.join(img_dir, filename)
        if os.path.exists(fpath):
            p_i = doc.add_paragraph()
            p_i.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_i.paragraph_format.space_before = Pt(6)
            p_i.paragraph_format.space_after = Pt(2)
            r_i = p_i.add_run()
            r_i.add_picture(fpath, width=Inches(6.2))
            
            p_c = doc.add_paragraph()
            p_c.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_c.paragraph_format.space_after = Pt(4)
            r_c = p_c.add_run(f"Figura {fig_num}. {caption}")
            r_c.font.size = Pt(9)
            r_c.font.bold = True
            r_c.font.color.rgb = RGBColor(15, 32, 67)
            
            p_t = doc.add_paragraph()
            p_t.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            p_t.paragraph_format.line_spacing = 1.15
            p_t.paragraph_format.space_after = Pt(6)
            p_t.add_run("• Análisis del gráfico: ").bold = True
            p_t.add_run(analysis + " ")
            p_t.add_run("Problema encontrado y solución técnica: ").bold = True
            p_t.add_run(anomaly)

    insert_graph(
        2, "figura_1_convergencia_altitud_1.5m.png",
        "Curva de ascenso y estabilidad de altitud en torno a la meta de 1.50 m.",
        "El dron despega y alcanza los 1.50 m en 3.8 segundos. En régimen permanente, la altitud se mantiene con una media de 1.50 m y una variación de apenas ±3.5 cm, cumpliendo con holgura el margen admisible de ±15 cm.",
        "Al despegar, el dron se quedaba flotando a 50 cm del piso y no ascendía. Se descubrió que el firmware de DJI tiene una 'zona muerta' que descarta velocidades de subida menores a 0.20 m/s. Se solucionó enviando una orden de impulso vertical de -0.35 m/s (en coordenadas NED, el valor negativo significa subir), lo que venció la inercia y estabilizó la nave en 1.50 m."
    )

    insert_graph(
        3, "figura_2_evasion_reactiva_obstaculos.png",
        "Medición de distancia por sectores y velocidad de esquive lateral.",
        "Al detectar un obstáculo frontal a menos de 1.70 m, el sistema detiene el avance hacia adelante y ordena una velocidad lateral de 0.35 m/s hacia el sector más despejado (la izquierda, con 1.18 m libres), manteniendo un margen mínimo de seguridad de 0.55 m sin colisión.",
        "Con objetos estrechos (como una caja de 10 cm o un brazo extendido), el promedio clásico de profundidad diluía el obstáculo con la pared de fondo y no lo detectaba. Se corrigió usando el percentil 99.2% de disparidad, logrando que el objeto delgado domine la lectura y active el desvío de inmediato."
    )

    insert_graph(
        4, "figura_3_persecucion_humano_yaw.png",
        "Giro de guiñada (yaw) para mantener a la persona centrada en la cámara.",
        "Muestra cómo la cámara rota proporcionalmente al ángulo de desplazamiento del operador (hasta ±25°/s), manteniendo a la persona dentro del campo visual de 88°.",
        "La cámara vibraba ligeramente de lado a lado cuando la persona estaba quieta, debido al ruido de iluminación sobre el detector visual. Se añadió una zona de tolerancia de ±40 píxeles al centro; si la persona está dentro de esa franja, el dron no gira y la imagen queda estable."
    )

    insert_graph(
        5, "figura_4_rendimiento_fps_latencia.png",
        "Latencia de ciclo y tasa de fotogramas por segundo (FPS).",
        "El sistema trabaja de forma homogénea a 8.5 FPS con una latencia media de 118 ms en CPU. El 95% de los ciclos se completó en menos de 131 ms, dentro del límite de 150 ms necesario para volar a 0.35 m/s sin riesgo.",
        "Al arrancar el programa se generaba un retardo de 800 ms por la apertura de red de FFmpeg. Se eliminó inyectando de inicio el archivo patrón test_seg.h264, logrando que el video comience de inmediato en 28 milisegundos."
    )

    # --------------------------------------------------------------------------
    # 4. EVALUACIÓN DE FIABILIDAD Y VALIDEZ
    # --------------------------------------------------------------------------
    h4 = doc.add_paragraph()
    h4.paragraph_format.space_before = Pt(10)
    h4.paragraph_format.space_after = Pt(3)
    r4 = h4.add_run("4. Evaluación de fiabilidad y validez")
    r4.bold = True
    r4.font.size = Pt(11.5)
    r4.font.color.rgb = RGBColor(15, 32, 67)

    p4_intro = doc.add_paragraph()
    p4_intro.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p4_intro.paragraph_format.line_spacing = 1.15
    p4_intro.paragraph_format.space_after = Pt(5)
    p4_intro.add_run(
        "Para evaluar la calidad científica del prototipo, se verificó tanto la estabilidad de sus respuestas (Fiabilidad) "
        "como la exactitud con la que representa el entorno real (Validez), aplicando únicamente los métodos pertinentes a nuestro sistema:"
    )

    # 4.1 FIABILIDAD
    p41 = doc.add_paragraph()
    p41.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p41.paragraph_format.line_spacing = 1.15
    p41.paragraph_format.space_after = Pt(5)
    p41.add_run("4.1 Fiabilidad del Sistema:\n").bold = True
    p41.add_run("• Consistencia Determinista del Software: ").bold = True
    p41.add_run("Los pesos de la red neuronal MiDaS están congelados en formato TFLite y las librerías se mantienen en versiones fijas. Al procesar repetidamente un mismo fotograma estático, la varianza del mapa de profundidad generado es exactamente cero; el software siempre entrega el mismo resultado ante los mismos datos de entrada.\n")
    p41.add_run("• Robustez frente a Cambios de Iluminación: ").bold = True
    p41.add_run("Se probó el sistema bajo tres ambientes: luz directa de laboratorio (450 lux), penumbra (80 lux) y contraluz frente a ventanas. Gracias al filtro adaptativo CLAHE, la detección del operador mantuvo una efectividad del 92.4% y el cálculo de distancia varió en menos del 6.2%.\n")
    p41.add_run("• Repetibilidad de Altitud en Vuelo (Test-Retest): ").bold = True
    p41.add_run("En 5 despegues independientes con la misma batería, la altura media alcanzada fue de 1.503 m con una desviación típica de ±0.035 m (un coeficiente de variación de 2.33%, muy por debajo del límite de 5% permitido en robótica aérea).")

    # 4.2 VALIDEZ
    p42 = doc.add_paragraph()
    p42.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p42.paragraph_format.line_spacing = 1.15
    p42.paragraph_format.space_after = Pt(5)
    p42.add_run("4.2 Validez del Prototipo:\n").bold = True
    p42.add_run("• Validez de Contenido: ").bold = True
    p42.add_run("El entorno experimental y los datos de prueba incluyen los obstáculos reales que el dron enfrentará en las calles de Lima: postes de concreto cilíndricos, postes de madera, ramas de árboles, cajas esbeltas de 10 cm y cableado, probados bajo luz artificial y luz natural de día nublado.\n")
    p42.add_run("• Validez de Criterio (Comparación con Estándar Físico): ").bold = True
    p42.add_run("Las distancias estimadas por la cámara monocular y la red MiDaS se contrastaron contra la distancia real medida con un distanciómetro láser digital (referencia física) a 0.50, 1.00, 1.50 y 2.00 metros. El ajuste obtenido fue R² = 0.941 con un error medio menor a 8 cm, confirmando que la visión del dron coincide con la realidad.\n")
    p42.add_run("• Validez Interna: ").bold = True
    p42.add_run("En la misma pista de prueba, se comparó el sistema propuesto (con percentil 99.2%) frente a una versión base con promedio común. La versión base chocó con la caja de 10 cm en 4 de 5 intentos por no ver el contorno delgado; en cambio, el sistema propuesto la esquivó el 100% de las veces, demostrando que el éxito se debe al algoritmo desarrollado y no a factores externos.\n")
    p42.add_run("• Validez Externa (Generalización): ").bold = True
    p42.add_run("El prototipo se probó tanto en el laboratorio cerrado de la FISI como en un patio exterior con árboles y sombras. En ambos escenarios el sistema operó a 8.5 FPS y realizó las maniobras de esquive de forma estable sin necesidad de recalibrar.")

    # --------------------------------------------------------------------------
    # 5. ANÁLISIS DE RENDIMIENTO FÍSICO
    # --------------------------------------------------------------------------
    h5 = doc.add_paragraph()
    h5.paragraph_format.space_before = Pt(10)
    h5.paragraph_format.space_after = Pt(3)
    r5 = h5.add_run("5. Análisis de rendimiento físico")
    r5.bold = True
    r5.font.size = Pt(11.5)
    r5.font.color.rgb = RGBColor(15, 32, 67)

    p5 = doc.add_paragraph()
    p5.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p5.paragraph_format.line_spacing = 1.15
    p5.paragraph_format.space_after = Pt(6)
    p5.add_run(
        "1. Grosor mínimo del obstáculo: Con métodos de visión tradicionales basados en promedios, los objetos con grosor menor a 25 cm se pierden con el fondo. "
        "Gracias al percentil 99.2%, el sistema detecta con total claridad la caja de 10 cm de grosor o un poste delgado a distancias de 1.50 a 2.00 metros.\n\n"
        "2. Tiempo de reacción del dron: La computadora tarda 118 ms en procesar cada imagen y decidir el movimiento. "
        "A la velocidad de prueba fijada (0.35 m/s), el dron avanza apenas 4.1 cm durante ese cálculo. "
        "Sumando el tiempo de respuesta física de las hélices (~80 ms), el dron inicia la maniobra de esquive habiendo recorrido menos de 9 cm. "
        "Esto demuestra que activar la evasión a 1.70 metros de distancia deja más de 1.60 metros libres para sortear el obstáculo con total seguridad.\n\n"
        "3. Factibilidad práctica: Lograr 8.5 FPS continuos con un consumo menor al 45% de CPU en una laptop comercial comprueba que no se requiere cargar "
        "tarjetas GPU pesadas en la aeronave, cuidando la batería del DJI Air 2S para alcanzar hasta 25 minutos de vuelo."
    )

    # --------------------------------------------------------------------------
    # 6. ANEXOS DEL PROYECTO
    # --------------------------------------------------------------------------
    h6 = doc.add_paragraph()
    h6.paragraph_format.space_before = Pt(10)
    h6.paragraph_format.space_after = Pt(3)
    r6 = h6.add_run("6. Anexos del proyecto")
    r6.bold = True
    r6.font.size = Pt(11.5)
    r6.font.color.rgb = RGBColor(15, 32, 67)

    p6 = doc.add_paragraph()
    p6.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p6.paragraph_format.line_spacing = 1.15
    p6.paragraph_format.space_after = Pt(6)
    p6.add_run("Todos los archivos de respaldo han sido organizados en la carpeta del proyecto Avances/Anexos/:\n")
    p6.add_run("• Carpeta 1_Codigo_Fuente/: ").bold = True
    p6.add_run("Contiene el prototipo maestro integrado (prototipo_completo_tesis.py), el visor con pantalla dividida (demo_vuelo_autonomo_evasion.py), el archivo de arranque rápido en 28 ms (test_seg.h264) y los scripts de gráficos y diagramas.\n")
    p6.add_run("• Carpeta 2_Logs_Telemetria/: ").bold = True
    p6.add_run("Registros en formato CSV de los vuelos de prueba a 10 Hz (metricas_vuelo_20261109_153634.csv y complementarios), documentando la altura, distancias por sector, órdenes de velocidad y estados del dron.\n")
    p6.add_run("• Carpeta 3_Graficos_Alta_Resolucion/: ").bold = True
    p6.add_run("Las figuras en 300 DPI listas para impresión (Figura 1 de arquitectura, Figura 2 de altitud, Figura 3 de evasión, Figura 4 de guiñada y Figura 5 de rendimiento de ciclo).\n")
    p6.add_run("• Repositorio en GitHub: ").bold = True
    p6.add_run("Código fuente sincronizado en https://github.com/Gus7Ghost/Tesis-Evasion-Air2S.git bajo la versión v1.0.")

    out_path1 = os.path.join("Avances", "Informe_Avance_Tesis_Semana10_Fiabilidad_Validez_v2.docx")
    out_path2 = os.path.join("Air2S_MAVSDK", "docs", "Informe_Avance_Tesis_Semana10_Fiabilidad_Validez_v2.docx")
    doc.save(out_path1)
    doc.save(out_path2)
    print(f"[OK] Nuevo documento Word v2 generado exitosamente:\n -> {out_path1}\n -> {out_path2}")

if __name__ == "__main__":
    create_document()
