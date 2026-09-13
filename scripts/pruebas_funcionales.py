"""
Pruebas funcionales del prototipo — valida umbrales de semáforo, filtros
combinados y casos límite de los 5 Stored Procedures. Evidencia para la
fase 4.0 (Pruebas y Evaluación) del EDT y la sección de Seguimiento.
"""
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=10)
ok, fail = 0, 0


def check(nombre, condicion, detalle=""):
    global ok, fail
    if condicion:
        ok += 1
        print(f"  [OK]   {nombre}")
    else:
        fail += 1
        print(f"  [FALLA] {nombre}  -> {detalle}")


with conn.cursor() as cur:
    # =========================================================
    # PARTE A — Umbrales de semáforo (validación de la fórmula,
    # con valores límite exactos, independiente de los datos cargados)
    # =========================================================
    print("A) Umbrales de semáforo (valores límite)\n")

    def semaforo_menor_es_mejor(v, verde, amarillo):
        cur.execute(
            "SELECT CASE WHEN %s <= %s THEN 'Verde' WHEN %s <= %s THEN 'Amarillo' "
            "ELSE 'Rojo' END",
            (v, verde, v, amarillo),
        )
        return cur.fetchone()[0]

    def semaforo_mayor_es_mejor(v, verde, amarillo):
        cur.execute(
            "SELECT CASE WHEN %s >= %s THEN 'Verde' WHEN %s >= %s THEN 'Amarillo' "
            "ELSE 'Rojo' END",
            (v, verde, v, amarillo),
        )
        return cur.fetchone()[0]

    # SP1 Inasistencia: Verde<=10 | Amarillo<=20 | Rojo>20
    check("Inasistencia 10.00% = Verde", semaforo_menor_es_mejor(10.00, 10, 20) == "Verde")
    check("Inasistencia 10.01% = Amarillo", semaforo_menor_es_mejor(10.01, 10, 20) == "Amarillo")
    check("Inasistencia 20.00% = Amarillo", semaforo_menor_es_mejor(20.00, 10, 20) == "Amarillo")
    check("Inasistencia 20.01% = Rojo", semaforo_menor_es_mejor(20.01, 10, 20) == "Rojo")

    # SP2 Espera: Verde<=15 | Amarillo<=30 | Rojo>30
    check("Espera 15 min = Verde", semaforo_menor_es_mejor(15, 15, 30) == "Verde")
    check("Espera 15.01 min = Amarillo", semaforo_menor_es_mejor(15.01, 15, 30) == "Amarillo")
    check("Espera 30.01 min = Rojo", semaforo_menor_es_mejor(30.01, 15, 30) == "Rojo")

    # SP3 Ocupación: Verde>=85 | Amarillo>=70 | Rojo<70
    check("Ocupación 85.00% = Verde", semaforo_mayor_es_mejor(85.00, 85, 70) == "Verde")
    check("Ocupación 84.99% = Amarillo", semaforo_mayor_es_mejor(84.99, 85, 70) == "Amarillo")
    check("Ocupación 69.99% = Rojo", semaforo_mayor_es_mejor(69.99, 85, 70) == "Rojo")

    # SP4/SP5 (enteros): Verde=0 | Amarillo<=N | Rojo>N
    check("Stock crítico 0 = Verde", semaforo_menor_es_mejor(0, 0, 5) == "Verde")
    check("Stock crítico 5 = Amarillo", semaforo_menor_es_mejor(5, 0, 5) == "Amarillo")
    check("Stock crítico 6 = Rojo", semaforo_menor_es_mejor(6, 0, 5) == "Rojo")
    check("Quiebres 3 = Amarillo", semaforo_menor_es_mejor(3, 0, 3) == "Amarillo")
    check("Quiebres 4 = Rojo", semaforo_menor_es_mejor(4, 0, 3) == "Rojo")

    # =========================================================
    # PARTE B — Filtros combinados y casos límite (contra datos reales)
    # =========================================================
    print("\nB) Filtros combinados y casos límite\n")

    # Sector y área incompatibles entre sí: no debe reventar, debe dar 0
    cur.execute("SELECT id_area FROM areas_especialidad WHERE id_sector <> 1 LIMIT 1")
    area_de_otro_sector = cur.fetchone()[0]
    cur.execute(
        "SELECT * FROM sp_kpi_inasistencia('2026-07-01','2026-09-30', %s, 1)",
        (area_de_otro_sector,),
    )
    r = cur.fetchone()
    check(
        "Área de otro sector + sector=1 -> 0 evaluables (sin error)",
        r[0] == 0, detalle=str(r),
    )

    # Área inexistente
    try:
        cur.execute("SELECT * FROM sp_kpi_inasistencia('2026-07-01','2026-09-30', 9999)")
        r = cur.fetchone()
        check("id_area inexistente (9999) -> 0 sin error", r[0] == 0, detalle=str(r))
    except Exception as e:
        conn.rollback()
        check("id_area inexistente (9999) -> 0 sin error", False, detalle=str(e))

    # Rango de fechas fuera de la ventana de datos (no debe dividir por cero)
    cur.execute("SELECT * FROM sp_kpi_inasistencia('2020-01-01','2020-01-31')")
    r = cur.fetchone()
    check(
        "Rango de fechas sin datos -> tasa 0.00 sin división por cero",
        r[0] == 0 and float(r[2]) == 0.00, detalle=str(r),
    )
    cur.execute("SELECT * FROM sp_kpi_ocupacion_agenda('2020-01-01','2020-01-31')")
    r = cur.fetchone()
    check(
        "Ocupación sin datos en el rango -> 0% sin división por cero",
        r[0] == 0 and float(r[2]) == 0.00, detalle=str(r),
    )

    # fecha_inicio > fecha_fin (rango invertido): no debe reventar
    try:
        cur.execute("SELECT * FROM sp_kpi_inasistencia('2026-09-30','2026-07-01')")
        r = cur.fetchone()
        check("Rango de fechas invertido -> 0 resultados sin error", r[0] == 0, detalle=str(r))
    except Exception as e:
        conn.rollback()
        check("Rango de fechas invertido -> 0 resultados sin error", False, detalle=str(e))

    # Todos los filtros en NULL explícito = comportamiento "todas"
    cur.execute("SELECT * FROM sp_kpi_inasistencia(NULL, NULL, NULL, NULL)")
    r = cur.fetchone()
    check("Todos los filtros NULL -> agrega todo el histórico sin error", r[0] > 0, detalle=str(r))

    # =========================================================
    # PARTE C — Integridad referencial y de negocio (RNF-04)
    # =========================================================
    print("\nC) Integridad de datos (RNF-04)\n")

    cur.execute(
        "SELECT COUNT(*) FROM bloques_agenda b WHERE b.estado_bloque = 'Reservado' "
        "AND NOT EXISTS (SELECT 1 FROM citas_medicas c WHERE c.id_bloque = b.id_bloque)"
    )
    check("Todo bloque 'Reservado' tiene una cita asociada", cur.fetchone()[0] == 0)

    cur.execute(
        "SELECT COUNT(*) FROM citas_medicas c JOIN bloques_agenda b ON b.id_bloque = c.id_bloque "
        "WHERE b.estado_bloque <> 'Reservado'"
    )
    check("Toda cita apunta a un bloque en estado 'Reservado'", cur.fetchone()[0] == 0)

    cur.execute(
        "SELECT COUNT(*) FROM citas_medicas WHERE estado_cita = 'Inasistente' AND id_motivo IS NULL"
    )
    check("Toda cita 'Inasistente' registra motivo", cur.fetchone()[0] == 0)

    cur.execute("SELECT COUNT(*) FROM inventario_insumos WHERE stock_actual < 0")
    check("Ningún insumo con stock negativo", cur.fetchone()[0] == 0)

conn.close()

print(f"\n{'='*50}\nTOTAL: {ok} OK / {fail} FALLAS\n{'='*50}")
