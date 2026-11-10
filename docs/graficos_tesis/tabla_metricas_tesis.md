# Resumen Estadístico de Resultados Experimentales de Vuelo (Capítulo 4)
*Fecha de Análisis:* 2026-11-09 15:32:46  
*Dataset Evaluado:* `319 ciclos de control`  

| Métrica de Desempeño | Valor Experimental Obtenido | Requisito / Consigna Nominal | Estado de Validación |
| :--- | :---: | :---: | :---: |
| **Altitud Media en Hover ($z$)** | `1.50 m` | `1.50 m` | **CUMPLE** |
| **Error Cuadrático Medio Altitud (RMSE)** | `3.5 cm` | $\leq 15.0\text{ cm}$ | **ÓPTIMO** |
| **Desviación Estándar de Altitud ($\sigma_z$)** | `\pm 3.5 cm` | $\leq 10.0\text{ cm}$ | **ESTABLE** |
| **Distancia Mínima de Aproximación Respetada** | `0.55 m` | $\geq 0.50\text{ m}$ | **SEGURO** |
| **Ciclos con Evasión Lateral Activa ($V_y$)** | `26 ciclos` | Activación reactiva | **VERIFICADO** |
| **Ciclos con Parada de Emergencia ($V=0$)** | `21 ciclos` | Activación ante $d < 0.85\text{m}$ | **SEGURO** |
| **Tasa Media de Procesamiento (FPS)** | `8.5 FPS` | $\geq 8.0\text{ FPS}$ | **TIEMPO REAL** |
| **Latencia Media Total de Ciclo** | `118.1 ms` | $\leq 120.0\text{ ms}$ | **CUMPLE** |
| **Percentil 95 de Latencia ($P_{95}$)** | `131.2 ms` | $\leq 150.0\text{ ms}$ | **CONFIABLE** |

### Conclusiones Clave para la Discusión de Tesis:
1. **Control de Altitud a 1.5 metros:** El algoritmo de compensación de zona muerta de DJI ($0.20\text{ m/s}$) mantuvo con éxito el dron dentro de la tolerancia de $\pm 15\text{ cm}$, eliminando el estancamiento previo a $50\text{ cm}$.
2. **Evasión Reactiva Tridimensional:** El filtrado Gaussiano combinado con el percentil 99.2% de disparidad resolvió obstáculos esbeltos (brazos y postes) activando la maniobra de desvío lateral a $0.35\text{ m/s}$ sin colisión.
3. **Viabilidad en Hardware Convencional:** La inferencia monocular con MiDaS v2.1 Small operando a `8.5 FPS` y `118.1 ms` confirma que la navegación reactiva es totalmente viable en CPU sin necesidad de GPUs pesadas a bordo.
