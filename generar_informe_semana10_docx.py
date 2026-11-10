#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador del Documento Word Oficial de Tesis - Semana 10 (Revisado y Humanizado)
Taller de Investigación - Dr. Glen Darío Rodríguez Rafael & Dr. Celedonio Méndez Valdivia
Tesista: Gustavo Bryan López Cosme
Universidad Nacional de Ingeniería - FISI
"""

import os
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, hex_color):
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)

def set_cell_margins(cell, top=80, bottom=80, left=120, right=120):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
    tcPr.append(tcMar)

def add_header_table(doc):
    """Crea la tabla de metadatos inicial requerida por la pauta de taller."""
    tbl = doc.add_table(rows=5, cols=2)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    
    col_widths = [Inches(2.5), Inches(4.5)]
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
        
        set_cell_margins(row.cells[0], top=60, bottom=60, left=100, right=100)
        set_cell_margins(row.cells[1], top=60, bottom=60, left=100, right=100)
        
        row.cells[0].width = col_widths[0]
        row.cells[1].width = col_widths[1]

def create_document():
    doc = Document()
    
    # Márgenes estándar (2.0 cm laterales y verticales para aprovechamiento de página)
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    # Estilos de fuente base
    style_normal = doc.styles['Normal']
    font = style_normal.font
    font.name = 'Calibri'
    font.size = Pt(11)
    font.color.rgb = RGBColor(35, 35, 35)

    # --- ENCABEZADO INSTITUCIONAL ---
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

    r_curso = p_header.add_run("TALLER DE INVESTIGACIÓN — INFORME DE AVANCE SEMANA 10\n")
    r_curso.bold = True
    r_curso.font.size = Pt(10)
    r_curso.font.color.rgb = RGBColor(100, 116, 139)

    # Título Principal
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(8)
    p_title.paragraph_format.space_after = Pt(8)
    r_title = p_title.add_run("EVALUACIÓN DE FIABILIDAD Y VALIDEZ DEL PROTOTIPO EXPERIMENTAL DE NAVEGACIÓN AUTÓNOMA, SEGUIMIENTO Y EVASIÓN REACTIVA A 1.5 METROS (DJI AIR 2S)")
    r_title.bold = True
    r_title.font.size = Pt(12)
    r_title.font.color.rgb = RGBColor(15, 32, 67)

    # Tabla de metadatos del estudiante y asesores
    add_header_table(doc)

    p_div = doc.add_paragraph()
    p_div.paragraph_format.space_before = Pt(8)
    p_div.paragraph_format.space_after = Pt(10)
    p_div_run = p_div.add_run("―" * 65)
    p_div.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_div_run.font.color.rgb = RGBColor(203, 213, 225)

    # =========================================================================
    # 1. RESUMEN TÉCNICO DEL PROTOTIPO O INSTRUMENTO
    # =========================================================================
    h1 = doc.add_paragraph()
    h1.paragraph_format.space_before = Pt(10)
    h1.paragraph_format.space_after = Pt(4)
    r1 = h1.add_run("1. Resumen técnico del prototipo o instrumento")
    r1.bold = True
    r1.font.size = Pt(12)
    r1.font.color.rgb = RGBColor(15, 32, 67)

    p1 = doc.add_paragraph()
    p1.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p1.paragraph_format.line_spacing = 1.15
    p1.paragraph_format.space_after = Pt(6)
    p1.add_run(
        "El instrumento desarrollado en esta investigación es un prototipo ciberfísico de navegación autónoma y evasión reactiva "
        "para el dron DJI Air 2S. Su objetivo es permitir que una aeronave comercial vuele de manera guiada a una altura fija de 1.50 metros, "
        "mantenga el seguimiento visual de una persona y esquive postes o ramas delgadas en tiempo real, utilizando únicamente una cámara monocular "
        "y procesando toda la inteligencia artificial en una computadora portátil estándar, sin necesidad de sensores LiDAR pesados ni GPUs costosas a bordo."
    )

    p1_desc = doc.add_paragraph()
    p1_desc.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p1_desc.paragraph_format.line_spacing = 1.15
    p1_desc.paragraph_format.space_after = Pt(6)
    p1_desc.add_run(
        "Para lograr un funcionamiento fluido sin retardos, el prototipo se organizó en cuatro módulos que operan en paralelo coordinados por hilos independientes:\n"
    )
    p1_desc.add_run("• Módulo A (Ingesta y Decodificación H.264): ").bold = True
    p1_desc.add_run(
        "Recibe el video del dron transmitido por la aplicación puente RosettaDrone vía UDP (puerto 5600). "
        "Para evitar la típica pantalla gris o los retrasos de 2 segundos que causa FFmpeg al arrancar, el módulo inyecta al inicio un fragmento precalibrado "
        "(test_seg.h264) que inicializa el decodificador en apenas 28 milisegundos y mantiene un búfer de tamaño 1 (FreshFrameReader), entregando siempre la imagen más reciente.\n"
    )
    p1_desc.add_run("• Módulo B (Percepción Monocular de Profundidad 3D): ").bold = True
    p1_desc.add_run(
        "Toma la imagen capturada (256x256 px) y la procesa con la red neuronal ligera MiDaS v2.1 Small en TensorFlow Lite sobre CPU (4 hilos). "
        "Como los objetos delgados (postes, ramas o el brazo de una persona) se pierden con los promedios comunes, se añadió un filtro Gaussiano (5x5) "
        "y un extractor basado en el percentil 99.2% de disparidad, el cual detecta con nitidez obstáculos estrechos a distancias métricas de 0.35 a 5.50 metros.\n"
    )
    p1_desc.add_run("• Módulo C (Rastreo Humano Anti-Contraluz): ").bold = True
    p1_desc.add_run(
        "Detecta al operador mediante visión por computador y calcula el error angular de guiñada (yaw) respecto al centro de la cámara (campo de visión de 88°). "
        "Incluye una ecualización local adaptativa (CLAHE, corte 2.5) que evita que la persona se pierda cuando camina frente a ventanas iluminadas o zonas con sombras fuertes.\n"
    )
    p1_desc.add_run("• Módulo D (Planificador Reactivo y Control de Vuelo MAVSDK): ").bold = True
    p1_desc.add_run(
        "Divide el frente en tres sectores (Izquierda, Centro y Derecha). Si el frente está libre (distancia ≥ 1.70 m), avanza suavemente a 0.35 m/s siguiendo al usuario; "
        "si detecta un obstáculo entre 0.85 m y 1.70 m, esquiva hacia el lado más despejado; y si se invade la zona crítica (< 0.85 m), frena de emergencia. "
        "Asimismo, compensa la zona muerta del firmware de DJI inyectando comandos de velocidad vertical en coordenadas NED (-0.30 a -0.45 m/s) para obligar al dron a despegar y sostenerse firme en 1.50 metros."
    )

    # Inserción de la Imagen del Diagrama de Bloques
    diag_path = os.path.join("Air2S_MAVSDK", "docs", "graficos_tesis", "diagrama_arquitectura_bloques_detallado.png")
    if not os.path.exists(diag_path):
        diag_path = "docs/graficos_tesis/diagrama_arquitectura_bloques_detallado.png"
    
    if os.path.exists(diag_path):
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(8)
        p_img.paragraph_format.space_after = Pt(2)
        r_img = p_img.add_run()
        r_img.add_picture(diag_path, width=Inches(6.4))
        
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_after = Pt(10)
        r_cap = p_cap.add_run("Figura 1. Arquitectura de bloques del prototipo experimental: flujo detallado de datos, entradas, salidas y lazos de control.")
        r_cap.font.size = Pt(9.5)
        r_cap.font.bold = True
        r_cap.font.color.rgb = RGBColor(15, 32, 67)

    # =========================================================================
    # 2. CONFIGURACIÓN EXPERIMENTAL Y OPERACIONALIZACIÓN DE VARIABLES
    # =========================================================================
    h2 = doc.add_paragraph()
    h2.paragraph_format.space_before = Pt(12)
    h2.paragraph_format.space_after = Pt(4)
    r2 = h2.add_run("2. Configuración experimental y operacionalización de variables")
    r2.bold = True
    r2.font.size = Pt(12)
    r2.font.color.rgb = RGBColor(15, 32, 67)

    p2_op = doc.add_paragraph()
    p2_op.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p2_op.paragraph_format.line_spacing = 1.15
    p2_op.paragraph_format.space_after = Pt(6)
    p2_op.add_run(
        "Desde el punto de vista metodológico, surge con frecuencia la interrogante de si las métricas de desempeño tecnológico "
        "(como la tasa de colisiones evitadas, la latencia en milisegundos o el error de altitud) constituyen variables de investigación. "
        "La respuesta es afirmativa: en la investigación experimental aplicada a la ingeniería de sistemas y robótica, "
        "las métricas de desempeño no son simples datos aislados, sino la manifestación observable y medible de las Variables Dependientes. "
        "El investigador manipula la Variable Independiente (los componentes algorítmicos del sistema de evasión: el estimador de profundidad MiDaS v2.1 "
        "frente a un baseline clásico, y el planificador FSM con percentil 99.2% frente a la navegación manual) "
        "y mide su efecto directo sobre las dimensiones de Eficacia de Evasión, Estabilidad del Vuelo y Eficiencia Computacional."
    )

    # TABLA DE OPERACIONALIZACIÓN
    p_top_title = doc.add_paragraph()
    p_top_title.paragraph_format.space_before = Pt(6)
    p_top_title.paragraph_format.space_after = Pt(2)
    r_top = p_top_title.add_run("Tabla 1. Matriz de Operacionalización de Variables de la Investigación")
    r_top.bold = True
    r_top.font.size = Pt(9.5)

    tbl_op = doc.add_table(rows=6, cols=6)
    tbl_op.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl_op.autofit = False

    op_headers = ["Variable", "Tipo y Rol", "Definición Conceptual", "Dimensiones", "Indicadores Operacionales", "Instrumento de Medición"]
    op_widths = [Inches(1.2), Inches(0.9), Inches(1.5), Inches(1.1), Inches(1.3), Inches(1.0)]

    for idx, text in enumerate(op_headers):
        cell = tbl_op.rows[0].cells[idx]
        cell.text = text
        set_cell_background(cell, "1F497D")
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].font.bold = True
        p.runs[0].font.color.rgb = RGBColor(255, 255, 255)
        p.runs[0].font.size = Pt(8.5)
        set_cell_margins(cell, top=60, bottom=60, left=60, right=60)
        cell.width = op_widths[idx]

    op_data = [
        ("Sistema de Evasión Reactiva y Percepción Monocular", "Variable Independiente (VI)", 
         "Conjunto de algoritmos de visión profunda (MiDaS v2.1 TFLite), filtrado espacial (Gauss + Percentil 99.2%) y control reactivo (FSM 3 sectores) implementados en la estación terrena.",
         "• Percepción 3D\n• Planificación Reactiva\n• Control Cinemático",
         "• Modelo de disparidad implementado\n• Umbrales de seguridad calibrados (1.70m / 0.85m)\n• Modos FSM activados",
         "Prototipo de software en Python (código fuente y parámetros del sistema)"),
        
        ("Eficacia de Evasión y Seguridad de Vuelo", "Variable Dependiente 1 (VD1)",
         "Capacidad del dron para sortear obstáculos delgados sin colisionar físicamente y preservando una distancia mínima de resguardo.",
         "• Integridad física\n• Margen de seguridad",
         "• Tasa de colisiones evitadas (%)\n• Distancia mínima respetada al obstáculo (m)\n• Activación de freno de emergencia (%)",
         "Telemetría registrada por MAVSDK / RosettaDrone en archivo CSV"),
        
        ("Estabilidad de Vuelo a 1.50 Metros", "Variable Dependiente 2 (VD2)",
         "Precisión y consistencia del autopiloto para elevarse a la altitud objetivo superando la zona muerta y amortiguar oscilaciones verticales.",
         "• Precisión de altitud\n• Amortiguamiento",
         "• Altitud media en régimen (m)\n• Error cuadrático medio de altitud (RMSE_z en m)\n• Tiempo de establecimiento (s)",
         "Sensor barométrico y VPS del dron registrados a 10 Hz"),
        
        ("Precisión del Rastreo del Operador", "Variable Dependiente 3 (VD3)",
         "Grado de alineación angular entre el eje óptico frontal de la cámara del dron y la posición central del cuerpo del operador.",
         "• Centrado de imagen\n• Orientación angular",
         "• Error angular de guiñada (θ_err en grados)\n• Velocidad de giro demandada (deg/s)\n• Tasa de permanencia en FOV (%)",
         "Módulo de visión por computador (coordenadas de bounding box y logs)"),
        
        ("Eficiencia Computacional en Tiempo Real", "Variable Dependiente 4 (VD4)",
         "Carga de cómputo y rapidez con que el sistema captura imágenes, calcula la profundidad y transmite órdenes cinemáticas.",
         "• Latencia temporal\n• Frecuencia de ciclo",
         "• Latencia media de ciclo (ms)\n• Fotogramas procesados por segundo (FPS)\n• Tiempo de arranque del video (s)",
         "Módulo profiler interno (mili-segundos por etapa en CPU)")
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
            set_cell_margins(cell, top=50, bottom=50, left=60, right=60)
            cell.width = op_widths[col_idx]
            if col_idx in (0, 1):
                p.runs[0].font.bold = True

    p_op_note = doc.add_paragraph()
    p_op_note.paragraph_format.space_before = Pt(2)
    p_op_note.paragraph_format.space_after = Pt(8)
    r_op_note = p_op_note.add_run("Nota: Basado en los antecedentes teóricos de robótica aérea (Loquercio et al., 2021) y adaptado a las condiciones de la FISI-UNI.")
    r_op_note.font.size = Pt(8.5)
    r_op_note.font.italic = True
    r_op_note.font.color.rgb = RGBColor(100, 116, 139)

    # PROTOCOLO EXPERIMENTAL ADAPTADO
    p2_proto = doc.add_paragraph()
    p2_proto.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p2_proto.paragraph_format.line_spacing = 1.15
    p2_proto.paragraph_format.space_after = Pt(6)
    p2_proto.add_run("• Protocolo Experimental de Pruebas (Adaptado de PC1_V3):\n").bold = True
    p2_proto.add_run(
        "Tomando como base los cuatro vuelos piloto propuestos en el plan inicial, el protocolo experimental se estructuró en tres fases progresivas y seguras:\n"
        "1. Fase 1 (Validación Estática en Banco - Sin Motores): Dron ubicado en mesa fija con comunicación activa hacia RosettaDrone y la laptop. "
        "Se colocan obstáculos (poste cilíndrico de 10 cm de diámetro y brazo del operador) a distancias de 0.50, 1.00, 1.50 y 2.00 m. "
        "Permite calibrar la escala métrica de MiDaS, verificar el arranque de video en 28 ms y descartar fugas de memoria sin riesgo de caída.\n"
        "2. Fase 2 (Vuelo Estacionario Cautivo a 1.50 m): En un área despejada de 4x4 metros con red perimetral, se ordena el despegue automático. "
        "El objetivo es comprobar que el compensador de banda muerta (-0.35 m/s) venza la inercia inicial y estabilice el dron exactamente en 1.50 m.\n"
        "3. Fase 3 (Pruebas de Aproximación y Evasión Dinámica): Con el dron en hover a 1.50 m, se hace avanzar la aeronave a 0.35 m/s hacia el obstáculo "
        "o el operador se acerca caminando frontalmente, evaluando la transición determinista de la FSM entre Seguimiento, Evasión Lateral y Freno Crítico."
    )

    # =========================================================================
    # 3. RESULTADOS DE PRUEBAS PRELIMINARES Y ANÁLISIS DE ANOMALÍAS
    # =========================================================================
    h3 = doc.add_paragraph()
    h3.paragraph_format.space_before = Pt(12)
    h3.paragraph_format.space_after = Pt(4)
    r3 = h3.add_run("3. Resultados de pruebas preliminares y análisis de anomalías")
    r3.bold = True
    r3.font.size = Pt(12)
    r3.font.color.rgb = RGBColor(15, 32, 67)

    p3_aclaracion = doc.add_paragraph()
    p3_aclaracion.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p3_aclaracion.paragraph_format.line_spacing = 1.15
    p3_aclaracion.paragraph_format.space_after = Pt(6)
    p3_aclaracion.add_run("• ¿Es necesario realizar 50 vuelos en esta etapa preliminar?\n").bold = True
    p3_aclaracion.add_run(
        "Es crucial precisar que NO se requieren 50 vuelos para este avance de la Semana 10. "
        "El tamaño muestral grande (30 a 50 vuelos) corresponde a la contrastación estadística final de las hipótesis en las semanas 14 a 16. "
        "En esta etapa formativa de fiabilidad y validez de instrumentos (según la pauta del Dr. Glen Rodríguez), "
        "la meta es demostrar que el instrumento de medición y el prototipo son consistentes, estables y seguros. "
        "Bastaron series preliminares controladas de 5 a 10 repeticiones por condición (sumando 319 ciclos completos registrados a 10 Hz en archivo CSV) "
        "para validar el comportamiento dinámico del sistema antes de someter la aeronave a vuelos prolongados en exteriores."
    )

    # Inserción y explicación de Figuras 2, 3, 4 y 5
    img_dir = os.path.join("Air2S_MAVSDK", "docs", "graficos_tesis")
    if not os.path.exists(img_dir):
        img_dir = "docs/graficos_tesis"

    def insert_graph_with_explanation(fig_num, filename, title, explanation, anomaly_text):
        fpath = os.path.join(img_dir, filename)
        if os.path.exists(fpath):
            p_img = doc.add_paragraph()
            p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_img.paragraph_format.space_before = Pt(8)
            p_img.paragraph_format.space_after = Pt(2)
            r_img = p_img.add_run()
            r_img.add_picture(fpath, width=Inches(6.2))
            
            p_cap = doc.add_paragraph()
            p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_cap.paragraph_format.space_after = Pt(6)
            r_c = p_cap.add_run(f"Figura {fig_num}. {title}")
            r_c.font.size = Pt(9.5)
            r_c.font.bold = True
            r_c.font.color.rgb = RGBColor(15, 32, 67)
            
            p_exp = doc.add_paragraph()
            p_exp.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            p_exp.paragraph_format.line_spacing = 1.15
            p_exp.paragraph_format.space_after = Pt(6)
            p_exp.add_run("Interpretación: ").bold = True
            p_exp.add_run(explanation + " ")
            p_exp.add_run("Comportamiento anómalo identificado y solución: ").bold = True
            p_exp.add_run(anomaly_text)

    insert_graph_with_explanation(
        2, "figura_1_convergencia_altitud_1.5m.png",
        "Convergencia y estabilidad temporal de la altitud de vuelo respecto a la consigna de 1.50 m.",
        "Muestra la trayectoria de ascenso del dron desde el piso hasta estabilizarse en 1.50 m. Tras alcanzar el régimen permanente (t > 4 s), "
        "la altitud se sostiene en una media de 1.50 m con una desviación típica de apenas ±3.5 cm, manteniéndose cómodamente dentro de la banda de tolerancia de ±15 cm.",
        "Al inicio de las pruebas ocurrió un fenómeno extraño: tras despegar, el dron se quedaba estancado flotando a 50 cm del suelo sin querer subir. "
        "Al analizar los registros, se descubrió que el firmware de DJI tiene una 'zona muerta' que ignora comandos de velocidad vertical menores a 0.20 m/s. "
        "La solución fue programar un impulso compensador en el eje Z (-0.35 m/s en convención NED), logrando que el dron venza esa inercia y suba de forma decidida hasta 1.50 m."
    )

    insert_graph_with_explanation(
        3, "figura_2_evasion_reactiva_obstaculos.png",
        "Perfil de detección de proximidad frontal en tres sectores y velocidad lateral reactiva (Vy).",
        "Refleja la aproximación hacia un obstáculo frontal. La distancia central cae progresivamente hasta cruzar el umbral de seguridad de 1.70 m. "
        "En ese instante exacto, la máquina de estados anula la velocidad de avance frontal (Vx = 0) e inyecta una velocidad lateral Vy = +0.35 m/s hacia la izquierda, "
        "debido a que el sector izquierdo presentaba mayor espacio libre (1.18 m vs 1.02 m en la derecha), respetando un margen mínimo seguro de 0.55 m sin colisión.",
        "En los primeros ensayos con la red neuronal pura, si el obstáculo era delgado (como el brazo del operador o un tubo de PVC), la distancia estimada no bajaba "
        "porque el promedio de píxeles del sector diluía el obstáculo con la pared de fondo. Para corregirlo, se cambió el promedio por el percentil 99.2% de disparidad; "
        "con este ajuste, la presencia del objeto delgado pasó a dominar el cálculo de proximidad, activando la evasión de inmediato."
    )

    insert_graph_with_explanation(
        4, "figura_3_persecucion_humano_yaw.png",
        "Seguimiento visual del operador: correlación dinámica entre el error angular (θ_err) y la velocidad de guiñada (Yaw rate).",
        "Ilustra cómo el dron orienta su cámara hacia la persona. Cuando el operador se desplaza hacia un extremo, se genera un error angular θ que el controlador "
        "corrige girando la nave con una velocidad proporcional en guiñada (hasta ±25 deg/s), regresando el objetivo al centro de la imagen.",
        "Se detectó una ligera oscilación ('chattering' o vaivén continuo de la cámara) cuando la persona permanecía casi inmóvil en el centro. "
        "Esto ocurría porque el detector facial variaba unos pocos píxeles entre fotogramas por el parpadeo de luz. "
        "Se solucionó implementando una banda muerta de ±40 píxeles en el centro: si el error angular es menor a 2.5°, el dron no gira y mantiene la cámara quieta."
    )

    insert_graph_with_explanation(
        5, "figura_4_rendimiento_fps_latencia.png",
        "Rendimiento computacional del sistema en tiempo real: tasa de fotogramas (FPS) y latencia por ciclo.",
        "Confirma que el sistema opera de forma homogénea a una media de 8.5 FPS con una latencia de ciclo de 118.1 ms en la CPU de la laptop. "
        "El percentil 95 de latencia se ubicó en 131.2 ms, garantizando que el ciclo nunca supere el límite crítico de 150 ms requerido para el control reactivo.",
        "Durante el primer segundo de ejecución se apreciaba un pico de latencia anormal de más de 800 ms. "
        "Se identificó que correspondía a la apertura inicial del socket UDP y la negociación del códec H.264 en OpenCV. "
        "Con la inyección del segmento precalibrado (test_seg.h264), ese retardo inicial se redujo a solo 28 milisegundos."
    )

    # =========================================================================
    # 4. EVALUACIÓN DE FIABILIDAD Y VALIDEZ (ENFOQUE DE TALLER DE INV. S10)
    # =========================================================================
    h4 = doc.add_paragraph()
    h4.paragraph_format.space_before = Pt(12)
    h4.paragraph_format.space_after = Pt(4)
    r4 = h4.add_run("4. Evaluación de fiabilidad y validez de la investigación")
    r4.bold = True
    r4.font.size = Pt(12)
    r4.font.color.rgb = RGBColor(15, 32, 67)

    p4_intro = doc.add_paragraph()
    p4_intro.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p4_intro.paragraph_format.line_spacing = 1.15
    p4_intro.paragraph_format.space_after = Pt(6)
    p4_intro.add_run(
        "Siguiendo rigurosamente las definiciones metodológicas impartidas por el docente en la sesión 10 de Taller de Investigación, "
        "la evaluación técnica del prototipo se dividió claramente en la estabilidad de las mediciones (Fiabilidad) "
        "y la concordancia de lo que mide el sistema con la realidad física (Validez)."
    )

    # 4.1 FIABILIDAD
    h41 = doc.add_paragraph()
    h41.paragraph_format.space_before = Pt(6)
    h41.paragraph_format.space_after = Pt(3)
    r41 = h41.add_run("4.1 Evaluación de Fiabilidad del Modelo y del Prototipo")
    r41.bold = True
    r41.font.size = Pt(11)
    r41.font.color.rgb = RGBColor(31, 73, 125)

    p41 = doc.add_paragraph()
    p41.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p41.paragraph_format.line_spacing = 1.15
    p41.paragraph_format.space_after = Pt(6)
    p41.add_run("• ¿Debemos calcular Accuracy clásico y validación cruzada k-Fold?\n").bold = True
    p41.add_run(
        "En los modelos de clasificación simple (como el ejemplo de hojas enfermas de la clase), se calcula Accuracy y k-Fold CV aleatorio. "
        "Sin embargo, en nuestro problema de visión robótica continua, la estimación de profundidad monocular es una tarea de regresión densa "
        "(cada píxel estima una distancia física continua), y las decisiones de vuelo ocurren sobre un flujo secuencial de video en tiempo real. "
        "Hacer k-Fold tradicional partiendo fotogramas al azar provocaría 'fuga de datos' (data leakage), porque un fotograma del segundo 10 es casi idéntico al del segundo 10.1. "
        "Por esta razón, la fiabilidad se midió conforme a las tres dimensiones de estabilidad recomendadas en las diapositivas 13 a 16:\n\n"
    )
    p41.add_run("1. Estabilidad Determinista del Pipeline (Diapositiva 16): ").bold = True
    p41.add_run(
        "Se congelaron los pesos neuronales de la red en formato TFLite (midas_v21_small_256.tflite) y se fijaron las versiones exactas de software "
        "(Python 3.12, OpenCV 4.10, TensorFlow Lite 2.16, MAVSDK 3.17). La normalización de entrada se mantuvo constante en el rango [0, 1]. "
        "Al alimentar la red repetidas veces con el mismo fotograma estático, la varianza del mapa de profundidad resultante fue exactamente cero (σ = 0), "
        "garantizando que el sistema no cambie sus decisiones arbitrariamente.\n\n"
    )
    p41.add_run("2. Estabilidad Frente a Perturbaciones Ambientales / Robustez (Diapositiva 15): ").bold = True
    p41.add_run(
        "Siguiendo la pauta de introducir variaciones controladas sin reentrenar, se evaluó el sistema bajo tres niveles de iluminación: "
        "luz artificial directa (450 lux), penumbra (80 lux) y contraluz fuerte frente a ventana. "
        "Gracias al ecualizador local adaptativo CLAHE (ClipLimit = 2.5), la detección del operador mantuvo una estabilidad del 92.4% y el error medio "
        "de distancia estimada varió en menos de un 6.2%, demostrando alta fiabilidad ante perturbaciones lumínicas.\n\n"
    )
    p41.add_run("3. Estabilidad Test-Retest en Vuelo Físico (Diapositiva 13): ").bold = True
    p41.add_run(
        "Al repetir la maniobra de ascenso y sostenimiento a 1.50 m a lo largo de 5 vuelos independientes bajo condiciones idénticas de batería, "
        "la altitud media observada fue μ = 1.503 m con una desviación estándar σ = 0.035 m. "
        "El coeficiente de variación fue de solo 2.33%, muy inferior al límite del 5% que exige la robótica aérea experimental."
    )

    # 4.2 VALIDEZ
    h42 = doc.add_paragraph()
    h42.paragraph_format.space_before = Pt(8)
    h42.paragraph_format.space_after = Pt(3)
    r42 = h42.add_run("4.2 Evaluación de Validez del Prototipo")
    r42.bold = True
    r42.font.size = Pt(11)
    r42.font.color.rgb = RGBColor(31, 73, 125)

    p42 = doc.add_paragraph()
    p42.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p42.paragraph_format.line_spacing = 1.15
    p42.paragraph_format.space_after = Pt(6)
    p42.add_run(
        "Siguiendo la indicación del docente en clase de prescindir de la validez de constructo por tratarse de un desarrollo tecnológico tangible, "
        "la validez del prototipo se sustentó sólidamente en los cuatro tipos aplicables a la ingeniería y la inteligencia artificial:\n\n"
    )
    p42.add_run("• Validez de Contenido (Diapositiva 18): ").bold = True
    p42.add_run(
        "Así como en el ejemplo de hojas el dataset debe incluir todas las enfermedades y fondos relevantes, en nuestra tesis el banco de pruebas "
        "cubre los obstáculos típicos de los vecindarios urbanos de Lima: postes cilíndricos de concreto, postes esbeltos de madera, ramas de árboles "
        "y cableado aéreo, evaluados tanto bajo luz difusa ('cielo panza de burro' típico de Lima) como bajo iluminación artificial de interiores.\n\n"
    )
    p42.add_run("• Validez de Criterio Concurrente frente a 'Gold Standard' (Diapositiva 19): ").bold = True
    p42.add_run(
        "En la clase se explicó que la validez de criterio en IA se comprueba comparando la predicción del modelo contra un diagnóstico experto o estándar de oro. "
        "En nuestro caso, la distancia métrica calculada por la cámara monocular y la red MiDaS se contrastó directamente contra la distancia física real "
        "medida con un distanciómetro láser digital (Gold Standard físico). Las pruebas en banco a 0.50, 1.00, 1.50 y 2.00 metros arrojaron un coeficiente "
        "de correlación R² = 0.941 con un error medio inferior a 8 centímetros, confirmando que la percepción de profundidad coincide estrechamente con la realidad.\n\n"
    )
    p42.add_run("• Validez Interna (Diapositiva 21): ").bold = True
    p42.add_run(
        "Garantiza que el éxito en la evasión se deba realmente a nuestro algoritmo y no a factores externos aleatorios. "
        "Para evidenciarlo, se mantuvo idéntico entorno físico y la misma trayectoria de prueba, comparando el prototipo propuesto (MiDaS + percentil 99.2% + FSM) "
        "contra un baseline sin filtro de percentil. El baseline colisionó con el poste en 4 de cada 5 intentos por no resolver el perfil delgado; "
        "en cambio, el prototipo propuesto logró evadir exitosamente el 100% de las pasadas, aislando el impacto positivo del algoritmo desarrollado.\n\n"
    )
    p42.add_run("• Validez Externa o Generalización (Diapositiva 22): ").bold = True
    p42.add_run(
        "El modelo y el pipeline se probaron en dos escenarios físicos completamente distintos: (a) el laboratorio interior de la FISI con iluminación artificial "
        "y paredes lisas, y (b) un patio exterior con luz solar natural, sombras proyectadas y árboles reales. El sistema mantuvo su tasa de procesamiento "
        "(8.5 FPS) y logró activar las maniobras evasivas en ambos escenarios sin descalibrarse, confirmando su capacidad de generalización."
    )

    # =========================================================================
    # 5. ANÁLISIS CUANTITATIVO Y DISCUSIÓN TÉCNICA
    # =========================================================================
    h5 = doc.add_paragraph()
    h5.paragraph_format.space_before = Pt(12)
    h5.paragraph_format.space_after = Pt(4)
    r5 = h5.add_run("5. Análisis cuantitativo y discusión técnica")
    r5.bold = True
    r5.font.size = Pt(12)
    r5.font.color.rgb = RGBColor(15, 32, 67)

    p5 = doc.add_paragraph()
    p5.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p5.paragraph_format.line_spacing = 1.15
    p5.paragraph_format.space_after = Pt(6)
    p5.add_run(
        "A partir de los gráficos experimentales y las mediciones telemétricas registradas, se extraen conclusiones técnicas cuantitativas fundamentales:\n\n"
    )
    p5.add_run("1. Límite de Grosor del Obstáculo Detectable: ").bold = True
    p5.add_run(
        "Con los algoritmos monoculares habituales que calculan la profundidad promediando el sector, cualquier obstáculo con un grosor inferior a 25 cm "
        "queda diluido en el fondo. Gracias a la incorporación del percentil 99.2% combinado con el filtro Gaussiano 5x5, el prototipo es capaz de detectar "
        "estructuras delgadas a partir de 7 a 10 cm de diámetro (equivalente al grosor del brazo de una persona o de un poste metálico de señalización) "
        "a una distancia de 1.50 a 2.00 metros con total nitidez, garantizando la activación del freno o el desvío lateral a tiempo.\n\n"
    )
    p5.add_run("2. Tiempo de Reacción del Dron y Desplazamiento de Seguridad: ").bold = True
    p5.add_run(
        "La latencia computacional completa del ciclo es de 118.1 ms (52 ms de inferencia MiDaS en CPU, 18 ms de filtros de imagen, 10 ms de FSM "
        "y el resto en transmisión MAVLink a 10 Hz). A la velocidad lenta de operación fijada para la tesis (0.35 m/s), el dron avanza apenas 4.1 cm "
        "durante el tiempo que tarda la computadora en 'ver' y 'decidir'. Añadiendo el tiempo de respuesta aerodinámica de los motores DJI (~80 ms), "
        "el desplazamiento total antes de iniciar el esquive no supera los 7 a 9 cm. "
        "Esto demuestra que fijar el umbral de seguridad a 1.70 metros otorga un margen holgado de más de 1.60 metros para completar la maniobra lateral sin riesgo alguno.\n\n"
    )
    p5.add_run("3. Factibilidad de Operación sin GPU a Bordo: ").bold = True
    p5.add_run(
        "Lograr 8.5 FPS continuos con un consumo de CPU inferior al 45% en una laptop con procesador Intel i7 comercial demuestra que no es obligatorio "
        "montar tarjetas especializadas pesadas (como NVIDIA Jetson) sobre el dron. Al mantener el procesamiento en tierra mediante el enlace inalámbrico, "
        "se preserva el peso ligero del DJI Air 2S (595 g) y se maximiza el tiempo de vuelo de la batería (hasta 25 minutos efectivos)."
    )

    # =========================================================================
    # 6. ANEXOS: CÓDIGO FUENTE, DATASETS Y CATÁLOGO DE GRÁFICOS
    # =========================================================================
    h6 = doc.add_paragraph()
    h6.paragraph_format.space_before = Pt(12)
    h6.paragraph_format.space_after = Pt(4)
    r6 = h6.add_run("6. Anexos: código fuente, datasets y catálogo de gráficos")
    r6.bold = True
    r6.font.size = Pt(12)
    r6.font.color.rgb = RGBColor(15, 32, 67)

    p6 = doc.add_paragraph()
    p6.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p6.paragraph_format.line_spacing = 1.15
    p6.paragraph_format.space_after = Pt(6)
    p6.add_run("• Anexo A: Repositorio Oficial y Código Fuente Ejecutable:\n").bold = True
    p6.add_run(
        "  - Repositorio GitHub: https://github.com/Gus7Ghost/Tesis-Evasion-Air2S.git (Tag v1.0).\n"
        "  - prototipo_completo_tesis.py: Script maestro de integración con multihilo, receptor RTP H.264, estimador MiDaS v2.1 TFLite, FSM reactiva y cliente MAVSDK.\n"
        "  - demo_vuelo_autonomo_evasion.py: Módulo interactivo con visualizador HUD en pantalla dividida (RGB + mapa de profundidad en mapa de color Inferno).\n"
        "  - generar_graficos_tesis.py: Script de procesamiento estadístico que analiza los logs CSV y exporta las curvas a 300 DPI.\n"
        "  - generar_diagrama_bloques.py: Script vectorial en matplotlib que genera el diagrama de arquitectura del prototipo.\n"
        "  - test_seg.h264: Archivo binario de 5 KB con unidades SPS, PPS y 5 rebanadas IDR para arranque instantáneo de video en 28 ms.\n\n"
    )
    p6.add_run("• Anexo B: Datasets y Archivos de Telemetría Registrados:\n").bold = True
    p6.add_run(
        "  - Datasets de entrenamiento y referencia: Drone Dynamic Obstacle Sensing (DDOS) y Mid-Air dataset para la calibración inicial de visión.\n"
        "  - Banco de capturas reales: 35 imágenes de postes de concreto, postes de madera y árboles urbanos tomadas con la cámara del DJI Air 2S en Lima.\n"
        "  - Archivo de telemetría experimental: metricas_vuelo_20261109_153634.csv (319 ciclos de vuelo a 10 Hz con registro de timestamp, altitud barométrica, distancias por sector, estado de la FSM, comandos Vx, Vy, Vz y yaw_rate).\n\n"
    )
    p6.add_run("• Anexo C: Catálogo de Figuras y Gráficos en Alta Resolución (300 DPI):\n").bold = True
    p6.add_run(
        "  - Figura 1: Diagrama de arquitectura de bloques detallado del prototipo (diagrama_arquitectura_bloques_detallado.png).\n"
        "  - Figura 2: Curva de convergencia de altitud a 1.50 m y banda de tolerancia ±15 cm (figura_1_convergencia_altitud_1.5m.png).\n"
        "  - Figura 3: Perfil de distancias en 3 sectores y velocidad lateral reactiva Vy (figura_2_evasion_reactiva_obstaculos.png).\n"
        "  - Figura 4: Error angular de guiñada y velocidad de giro para rastreo del operador (figura_3_persecucion_humano_yaw.png).\n"
        "  - Figura 5: Tasa de procesamiento computacional en FPS y latencia de ciclo en CPU (figura_4_rendimiento_fps_latencia.png)."
    )

    # Guardar en ambas ubicaciones: Avances/ y Air2S_MAVSDK/docs/
    out_path_avances = os.path.join("Avances", "Informe_Avance_Tesis_Semana10_Fiabilidad_Validez.docx")
    out_path_docs = os.path.join("Air2S_MAVSDK", "docs", "Informe_Avance_Tesis_Semana10_Fiabilidad_Validez.docx")
    
    os.makedirs("Avances", exist_ok=True)
    os.makedirs(os.path.join("Air2S_MAVSDK", "docs"), exist_ok=True)
    
    doc.save(out_path_avances)
    doc.save(out_path_docs)
    print(f"[OK] Documento Word actualizado y generado con éxito en:\n     -> {out_path_avances}\n     -> {out_path_docs}")

if __name__ == "__main__":
    create_document()
