"""
Medición de rendimiento de los 5 Stored Procedures (RNF-01: < 1,5 s por consulta).
Se ejecuta cada SP varias veces y se reporta tiempo mínimo, promedio y máximo,
sin contar el tiempo de conectar (se abre la conexión una sola vez, como en la app).
"""
import os
import time

import psycopg2
from dotenv import load_dotenv

load_dotenv()

REPETICIONES = 8
UMBRAL_MS = 1500

CASOS = [
    ("SP1 inasistencia (sin filtros)",
     "SELECT * FROM sp_kpi_inasistencia('2026-07-01','2026-09-30')"),
    ("SP1 inasistencia (+ área)",
     "SELECT * FROM sp_kpi_inasistencia('2026-07-01','2026-09-30', 3)"),
    ("SP1 inasistencia (+ sector)",
     "SELECT * FROM sp_kpi_inasistencia('2026-07-01','2026-09-30', NULL, 1)"),
    ("SP2 tiempo de espera (sin filtros)",
     "SELECT * FROM sp_kpi_tiempo_espera('2026-07-01','2026-09-30')"),
    ("SP3 ocupación de agenda (sin filtros)",
     "SELECT * FROM sp_kpi_ocupacion_agenda('2026-07-01','2026-09-30')"),
    ("SP4 stock crítico",
     "SELECT * FROM sp_kpi_stock_critico()"),
    ("SP5 quiebres de stock",
     "SELECT * FROM sp_kpi_quiebres_stock()"),
    ("Tendencia (historial_kpi, gráfico)",
     "SELECT fecha_calculo, valor_calculado, nivel_semaforo FROM historial_kpi "
     "WHERE codigo_kpi = 'KPI-01' ORDER BY fecha_calculo"),
    ("Detalle de inventario (tabla RF-04)",
     "SELECT codigo_producto, nombre_producto, stock_actual, stock_minimo, "
     "CASE WHEN stock_actual = 0 THEN 'Rojo' WHEN stock_actual <= stock_minimo THEN 'Amarillo' "
     "ELSE 'Verde' END AS nivel_semaforo FROM inventario_insumos "
     "ORDER BY nivel_semaforo, nombre_producto"),
]

t0 = time.perf_counter()
conn = psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=10)
t_conn = (time.perf_counter() - t0) * 1000
print(f"Tiempo de conexión inicial: {t_conn:.0f} ms (una sola vez por sesión, no por consulta)\n")

print(f"{'Consulta':42} {'min':>8} {'prom':>8} {'max':>8}   veredicto")
print("-" * 82)

peor_caso = 0.0
with conn.cursor() as cur:
    for nombre, sql in CASOS:
        tiempos = []
        for _ in range(REPETICIONES):
            t1 = time.perf_counter()
            cur.execute(sql)
            cur.fetchall()
            tiempos.append((time.perf_counter() - t1) * 1000)
        # se descarta la primera corrida (calienta el plan/caché) para el promedio
        calientes = tiempos[1:]
        mn, prom, mx = min(calientes), sum(calientes) / len(calientes), max(calientes)
        peor_caso = max(peor_caso, mx)
        veredicto = "OK" if mx <= UMBRAL_MS else "SUPERA UMBRAL"
        print(f"{nombre:42} {mn:7.1f}  {prom:7.1f}  {mx:7.1f}   {veredicto}")

conn.close()

print("-" * 82)
print(f"Umbral RNF-01: {UMBRAL_MS} ms | Peor caso observado: {peor_caso:.1f} ms")
print("RESULTADO GLOBAL:", "CUMPLE RNF-01" if peor_caso <= UMBRAL_MS else "NO CUMPLE RNF-01")
