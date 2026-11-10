#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador de Diagrama de Bloques Arquitectural de Alta Resolución (300 DPI)
Tesis de Ingeniería de Sistemas - UNI
Navegación Autónoma, Persecución y Evasión Reactiva a 1.5m (DJI Air 2S)
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, ArrowStyle
import os

def draw_block(ax, x, y, w, h, title, subtitle="", color="#FFFFFF", border="#1E293B", 
               title_color="#0F172A", text_color="#334155", title_size=10, text_size=8.5, lw=1.8):
    """Dibuja una caja de bloque elegante con bordes redondeados y texto centrado."""
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                         linewidth=lw, edgecolor=border, facecolor=color, zorder=3)
    ax.add_patch(box)
    
    if subtitle:
        ax.text(x + w / 2, y + h * 0.62, title, ha="center", va="center",
                fontsize=title_size, fontweight="bold", color=title_color, zorder=4)
        ax.text(x + w / 2, y + h * 0.32, subtitle, ha="center", va="center",
                fontsize=text_size, color=text_color, zorder=4, linespacing=1.2)
    else:
        ax.text(x + w / 2, y + h * 0.5, title, ha="center", va="center",
                fontsize=title_size, fontweight="bold", color=title_color, zorder=4)
    return box

def draw_subgraph_container(ax, x, y, w, h, title, tag, bg="#F1F5F9", border="#94A3B8"):
    """Dibuja un contenedor de módulo delimitado con encabezado identificador."""
    rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.03,rounding_size=0.12",
                          linewidth=2.0, edgecolor=border, facecolor=bg, linestyle="--", zorder=1)
    ax.add_patch(rect)
    
    # Etiqueta de encabezado
    header_w = min(w * 0.65, 3.8)
    header_box = FancyBboxPatch((x + 0.15, y + h - 0.42), header_w, 0.38,
                                boxstyle="round,pad=0.01,rounding_size=0.06",
                                linewidth=1.2, edgecolor=border, facecolor="#0F172A", zorder=2)
    ax.add_patch(header_box)
    ax.text(x + 0.15 + header_w / 2, y + h - 0.23, f"{tag}: {title}", ha="center", va="center",
            fontsize=9.5, fontweight="bold", color="#F8FAFC", zorder=3)

def draw_arrow(ax, p1, p2, label="", color="#2563EB", lw=2.2, rad=0.0, label_offset=(0, 0.15), 
               ha="center", va="bottom", fontsize=8.5, label_bg="#FFFFFF"):
    """Dibuja una flecha estilizada de alta visibilidad con etiqueta explicativa."""
    arrow = patches.FancyArrowPatch(
        p1, p2,
        connectionstyle=f"arc3,rad={rad}",
        arrowstyle="-|>,head_length=8,head_width=5",
        linewidth=lw,
        edgecolor=color,
        facecolor=color,
        zorder=5
    )
    ax.add_patch(arrow)
    
    # Punto circular de inicio para indicar claramente de dónde sale
    start_dot = patches.Circle(p1, 0.04, facecolor=color, edgecolor="#FFFFFF", linewidth=1.0, zorder=6)
    ax.add_patch(start_dot)
    
    if label:
        mid_x = (p1[0] + p2[0]) / 2 + label_offset[0]
        mid_y = (p1[1] + p2[1]) / 2 + label_offset[1]
        
        # Caja de fondo blanca para que la etiqueta sea 100% legible
        ax.text(mid_x, mid_y, label, ha=ha, va=va, fontsize=fontsize, fontweight="bold",
                color=color, zorder=7,
                bbox=dict(boxstyle="round,pad=0.2", facecolor=label_bg, edgecolor=color, alpha=0.92, lw=1.0))

def main():
    fig = plt.figure(figsize=(24, 14), dpi=300)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 24)
    ax.set_ylim(0, 14)
    ax.axis("off")
    fig.patch.set_facecolor("#FFFFFF")

    # ==================== ENCABEZADO PRINCIPAL ====================
    header_bg = FancyBboxPatch((0.5, 12.8), 23.0, 1.0, boxstyle="round,pad=0.02,rounding_size=0.08",
                               facecolor="#0F172A", edgecolor="#1E293B", lw=2)
    ax.add_patch(header_bg)
    ax.text(12.0, 13.45, "ARQUITECTURA DE BLOQUES DETALLADA: SISTEMA AUTÓNOMO DE NAVEGACIÓN Y EVASIÓN REACTIVA",
            ha="center", va="center", fontsize=15, fontweight="bold", color="#FFFFFF")
    ax.text(12.0, 13.05, "Universidad Nacional de Ingeniería | Tesis Dron DJI Air 2S | Pipeline Sense-Plan-Act a 1.50 Metros",
            ha="center", va="center", fontsize=11, color="#94A3B8")

    # =========================================================================
    # COLUMNA 1: HARDWARE FÍSICO Y PUENTE ROSETTADRONE (X: 0.5 a 4.5)
    # =========================================================================
    draw_subgraph_container(ax, 0.6, 7.0, 3.8, 5.5, "PLATAFORMA AÉREA", "1. DRON", bg="#F8FAFC", border="#64748B")
    draw_block(ax, 0.9, 10.3, 3.2, 1.4, "Cámara Monocular Gimbal", "Sensor CMOS 1''\n1080p @ 30 FPS / FOV 88°", color="#F1F5F9", border="#334155")
    draw_block(ax, 0.9, 7.5, 3.2, 1.5, "Autopiloto DJI & Sensores", "IMU + Barómetro + GPS\nControl Óptico / Deadband ~0.2 m/s", color="#F1F5F9", border="#334155")

    draw_subgraph_container(ax, 0.6, 0.6, 3.8, 5.8, "PUENTE MÓVIL (RosettaDrone)", "2. ANDROID", bg="#F8FAFC", border="#64748B")
    draw_block(ax, 0.9, 4.7, 3.2, 1.1, "Enlace Físico USB AOA", "DJI SDK Bridge a Control Remoto", color="#E2E8F0", border="#475569")
    draw_block(ax, 0.9, 2.7, 3.2, 1.4, "Transmisor RTP de Video", "Servidor H.264 UDP 5600\nFragmentación NAL FU-A", color="#EFF6FF", border="#3B82F6", title_color="#1D4ED8")
    draw_block(ax, 0.9, 0.9, 3.2, 1.4, "Traductor MAVLink", "Rosetta MAVLink UDP 19980\nSticks Virtuales / Telemetría", color="#FAF5FF", border="#8B5CF6", title_color="#6D28D9")

    # Flechas de hardware / enlace
    draw_arrow(ax, (2.5, 10.3), (2.5, 5.8), label="OcuSync 3.0 / H.264", color="#0284C7", lw=2.2, label_offset=(0.6, 1.8))
    draw_arrow(ax, (2.5, 4.7), (2.5, 4.1), color="#475569", lw=1.8)
    draw_arrow(ax, (2.1, 7.5), (2.1, 5.8), color="#64748B", lw=1.8)
    draw_arrow(ax, (2.9, 5.8), (2.9, 7.5), color="#64748B", lw=1.8)

    # =========================================================================
    # COLUMNA 2: MÓDULO A (INGESTA Y DECODIFICACIÓN ULTRA-BAJA LATENCIA)
    # =========================================================================
    draw_subgraph_container(ax, 4.8, 7.0, 5.2, 5.5, "INGESTA Y DECODIFICACIÓN", "MÓDULO A", bg="#F0FDF4", border="#22C55E")
    draw_block(ax, 5.1, 10.5, 4.6, 1.2, "1. Socket UDP 5600 & Desencapsulador", "Recepción datagramas RTP + Header 12B", color="#FFFFFF", border="#16A34A")
    draw_block(ax, 5.1, 8.8, 4.6, 1.3, "2. Reensamblador FU-A & Inyector", "Reconstrucción NAL + test_seg.h264\n(SPS + PPS + 5x IDR en 0.028 s)", color="#DCFCE7", border="#15803D", title_color="#14532D")
    draw_block(ax, 5.1, 7.3, 4.6, 1.1, "3. OpenCV VideoCapture + FreshFrameReader", "Búfer=1 | Hilo desacoplado (Cero retardo)", color="#FFFFFF", border="#16A34A")

    # Flechas internas Módulo A
    draw_arrow(ax, (4.1, 3.4), (5.1, 11.1), label="Flujo RTP UDP 5600", color="#0284C7", lw=2.6, rad=-0.2, label_offset=(0.1, 0.4))
    draw_arrow(ax, (7.4, 10.5), (7.4, 10.1), color="#16A34A", lw=2.0)
    draw_arrow(ax, (7.4, 8.8), (7.4, 8.4), color="#16A34A", lw=2.0)

    # =========================================================================
    # COLUMNA 3: PERCEPCIÓN EN PARALELO (MÓDULOS B Y C) (X: 10.4 a 16.6)
    # =========================================================================
    # MÓDULO B: PROFUNDIDAD 3D
    draw_subgraph_container(ax, 10.4, 6.7, 6.2, 5.8, "PERCEPCIÓN PROFUNDIDAD 3D (MiDaS)", "MÓDULO B", bg="#FEF2F2", border="#EF4444")
    draw_block(ax, 10.7, 10.7, 5.6, 1.1, "1. Preprocesamiento de Entrada", "Resize 256x256 RGB | Normalizado [0.0, 1.0]", color="#FFFFFF", border="#DC2626")
    draw_block(ax, 10.7, 9.1, 5.6, 1.2, "2. Inferencia TFLite MiDaS v2.1 Small", "XNNPACK CPU (4 Hilos) | Latencia: 52 ms\nTensor Disparidad Relativa 256x256", color="#FEE2E2", border="#B91C1C", title_color="#7F1D1D")
    draw_block(ax, 10.7, 7.8, 5.6, 0.95, "3. Filtro Gaussiano 5x5 (σ = 1.0)", "Atenuación de ruido térmico y granular", color="#FFFFFF", border="#DC2626")
    draw_block(ax, 10.7, 6.9, 5.6, 0.75, "4. Extractor Percentil 99.2% + Calibración Métrica", "Sectorización [Izq, Centro, Der] en [0.35m, 5.50m]", color="#FEF2F2", border="#B91C1C")

    # Flechas internas Módulo B
    draw_arrow(ax, (9.7, 7.85), (10.7, 11.25), label="Frame RGB Puro\n(1920x1080)", color="#16A34A", lw=2.5, rad=-0.15, label_offset=(0.1, 0.3))
    draw_arrow(ax, (13.5, 10.7), (13.5, 10.3), color="#DC2626", lw=2.0)
    draw_arrow(ax, (13.5, 9.1), (13.5, 8.75), color="#DC2626", lw=2.0)
    draw_arrow(ax, (13.5, 7.8), (13.5, 7.65), color="#DC2626", lw=2.0)

    # MÓDULO C: RASTREO HUMANO
    draw_subgraph_container(ax, 10.4, 0.6, 6.2, 5.8, "RASTREO HUMANO ANTI-CONTRALUZ", "MÓDULO C", bg="#EFF6FF", border="#3B82F6")
    draw_block(ax, 10.7, 4.7, 5.6, 1.1, "1. Luma + CLAHE Adaptativo Local", "ClipLimit = 2.5, Grid = 8x8 (Tolerancia Sombras/Luz)", color="#FFFFFF", border="#2563EB")
    draw_block(ax, 10.7, 2.9, 5.6, 1.4, "2. Clasificador en Cascada Optimizado", "Rastreo facial y corporal del operador\nSupresión de no máximos / Bounding Box", color="#DBEAFE", border="#1D4ED8", title_color="#1E3A8A")
    draw_block(ax, 10.7, 0.9, 5.6, 1.6, "3. Centroide y Error Angular de Guiñada", "Normalización respecto al centro óptico\nθ_err = ((x_c - X_0)/X_0) * (FOV_h / 2) [FOV=88°]", color="#FFFFFF", border="#2563EB")

    # Flechas internas Módulo C
    draw_arrow(ax, (9.7, 7.4), (10.7, 5.25), label="Frame RGB Puro", color="#16A34A", lw=2.2, rad=0.15, label_offset=(0.2, -0.3))
    draw_arrow(ax, (13.5, 4.7), (13.5, 4.3), color="#2563EB", lw=2.0)
    draw_arrow(ax, (13.5, 2.9), (13.5, 2.5), color="#2563EB", lw=2.0)

    # =========================================================================
    # COLUMNA 4: MÓDULO D (PLANIFICADOR FSM Y CONTROL DE VUELO MAVSDK)
    # =========================================================================
    draw_subgraph_container(ax, 17.0, 0.6, 6.5, 11.9, "CONTROL Y PLANIFICACIÓN ASÍNCRONA", "MÓDULO D", bg="#FFFBEB", border="#F59E0B")
    
    # FSM 3 Sectores
    draw_block(ax, 17.3, 8.8, 5.9, 3.1, "Máquina de Estados Finita Reactiva (FSM)", 
               "• FRENO CRÍTICO (d_cen < 0.85 m):\n  Hover inmediato, v_x=0, v_y=0, ω_yaw=0\n\n" +
               "• EVASIÓN REACTIVA (0.85m <= d_cen < 1.70 m):\n  v_x=0 m/s, v_y = ±0.35 m/s hacia max(d_izq, d_der)\n\n" +
               "• SEGUIMIENTO NOMINAL (d_cen >= 1.70 m):\n  Avance lento v_x = +0.35 m/s, ω_yaw = -K_p · θ_err",
               color="#FEF3C7", border="#D97706", title_color="#78350F", title_size=10.5, text_size=8.5, lw=2.0)

    # Compensador de Altitud
    draw_block(ax, 17.3, 4.8, 5.9, 3.4, "Compensador de Zona Muerta DJI (Altitud)", 
               "• Objetivo de Vuelo: 1.50 m (Error e_z = 1.50 - z_k)\n\n" +
               "• Deadband Interna del Firmware DJI: ~0.20 m/s\n\n" +
               "• Si e_z > 0.15 m (Dron bajo):\n  Inyección reforzada v_z = -0.30 a -0.45 m/s (NED)\n\n" +
               "• En Ventana de Tolerancia (1.50 ± 0.08 m):\n  Hover vertical automático v_z = 0.0 m/s",
               color="#FEF3C7", border="#D97706", title_color="#78350F", title_size=10.5, text_size=8.5, lw=2.0)

    # Controlador MAVSDK
    draw_block(ax, 17.3, 1.1, 5.9, 3.0, "Controlador MAVSDK (Bucle a 10 Hz)", 
               "• Ensamble del Vector Body-NED: [v_x, v_y, v_z, ω_yaw]\n\n" +
               "• MAVSDK: Offboard.set_velocity_body()\n\n" +
               "• Ráfaga UDP a RosettaDrone (MAVLink UDP 19980):\n  SET_POSITION_TARGET_LOCAL_NED (evita timeout >250ms)\n\n" +
               "• Modos de Seguridad: [ESPACIO] Freno | [L] Aterrizaje",
               color="#FDE68A", border="#B45309", title_color="#451A03", title_size=11, text_size=8.5, lw=2.2)

    # Flechas hacia Módulo D
    draw_arrow(ax, (16.3, 7.27), (17.3, 9.8), label="Distancias Métricas\n[d_izq, d_cen, d_der]", color="#DC2626", lw=2.6, rad=-0.1, label_offset=(-0.1, 0.45))
    draw_arrow(ax, (16.3, 1.7), (17.3, 9.1), label="Error Angular\nde Guiñada θ_err", color="#2563EB", lw=2.6, rad=0.18, label_offset=(0.2, -0.45))
    draw_arrow(ax, (20.25, 8.8), (20.25, 8.2), color="#D97706", lw=2.0)
    draw_arrow(ax, (20.25, 4.8), (20.25, 4.1), color="#D97706", lw=2.0)

    # =========================================================================
    # LAZOS DE REALIMENTACIÓN Y TELEMETRÍA (ENTRE MÓDULO D Y ROSETTADRONE)
    # =========================================================================
    # Telemetría de Rosetta a Módulo D (Altitud)
    draw_arrow(ax, (4.1, 1.6), (17.3, 6.2), label="Telemetría MAVLink (Altitud Barométrica z_k)", 
               color="#8B5CF6", lw=2.4, rad=-0.22, label_offset=(0, 0.45))

    # Comandos de Velocidad desde MAVSDK a RosettaDrone
    draw_arrow(ax, (17.3, 1.9), (4.1, 1.1), label="Comandos MAVLink Body-NED [v_x, v_y, v_z, ω_yaw] @ 10 Hz", 
               color="#B45309", lw=2.8, rad=0.18, label_offset=(0, -0.5))

    # RosettaDrone hacia el Dron
    draw_arrow(ax, (0.9, 1.6), (0.9, 7.5), label="Sticks Virtuales\n(AOA USB)", 
               color="#8B5CF6", lw=2.4, rad=0.25, label_offset=(-0.7, 0))

    # ==================== LEYENDA TÉCNICA DE FLECHAS ====================
    legend_bg = FancyBboxPatch((0.6, 0.08), 22.8, 0.45, boxstyle="round,pad=0.01,rounding_size=0.04",
                              facecolor="#F8FAFC", edgecolor="#CBD5E1", lw=1.2)
    ax.add_patch(legend_bg)
    
    legend_items = [
        ("Stream Video H.264 / RTP", "#0284C7"),
        ("Fotogramas RGB Limpios (RAM)", "#16A34A"),
        ("Percepción Profundidad 3D", "#DC2626"),
        ("Rastreo Humano & Error Yaw", "#2563EB"),
        ("Telemetría & Sticks DJI", "#8B5CF6"),
        ("Comandos Cinemáticos NED 10Hz", "#B45309")
    ]
    
    start_x = 1.0
    for name, col in legend_items:
        dot = patches.Circle((start_x, 0.3), 0.1, facecolor=col, edgecolor="#1E293B", lw=1.0)
        ax.add_patch(dot)
        ax.text(start_x + 0.22, 0.3, name, va="center", fontsize=8.5, fontweight="bold", color="#334155")
        start_x += 3.7

    out_dir = os.path.join("Air2S_MAVSDK", "docs", "graficos_tesis")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "diagrama_arquitectura_bloques_detallado.png")
    
    plt.savefig(out_path, dpi=300, bbox_inches="tight", facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close()
    print(f"[OK] Diagrama de bloques detallado generado con éxito en: {out_path}")

if __name__ == "__main__":
    main()
