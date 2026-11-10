#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
UNIVERSIDAD NACIONAL DE INGENIERÍA - FACULTAD DE INGENIERÍA DE SISTEMAS
TESIS: NAVEGACIÓN AUTÓNOMA, PERSECUCIÓN Y EVASIÓN REACTIVA A 1.5 METROS
DRON: DJI AIR 2S | CONTROLADOR: MAVSDK & ROSETTADRONE
================================================================================
Punto de entrada principal (Entrypoint) del paquete Air2S_MAVSDK.
Ejecuta el prototipo completo de navegación, visión artificial, FSM de evasión y
telemetría en tiempo real.
================================================================================
"""

import sys
import os

# Asegurar que el directorio raíz y el subdirectorio estén en el path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from prototipo_completo_tesis import main

if __name__ == "__main__":
    main()
