@echo off
chcp 65001 >nul
title Tesis UNI - Enlace DJI Air 2S (Laptop / Tablet)
cd /d "%~dp0"

echo ======================================================================
echo   UNIVERSIDAD NACIONAL DE INGENIERÍA - FACULTAD DE INGENIERÍA DE SISTEMAS
echo   TESIS: NAVEGACIÓN AUTÓNOMA, PERSECUCIÓN Y EVASIÓN REACTIVA (DJI AIR 2S)
echo ======================================================================
echo.
echo [*] Iniciando interfaz interactiva de configuración de red...
echo.

call ".\Codigo_Tesis_Evasion\venv\Scripts\activate.bat"
python prototipo_completo_tesis.py --drone

if errorlevel 1 (
    echo.
    echo [!] Sesión finalizada o interrumpida.
    pause
)
