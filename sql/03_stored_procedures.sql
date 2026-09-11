-- ============================================================
-- STORED PROCEDURES DE KPI — Gestión Inteligente CESFAM
-- Motor: PostgreSQL (Neon)
-- 5 procedimientos, uno por cada KPI del Dashboard (RF-01)
--
-- Nota de implementación: se implementan como FUNCIONES PL/pgSQL
-- que retornan una tabla, para poder consumirlas desde Streamlit
-- con psycopg2 mediante:  SELECT * FROM sp_kpi_xxx(...);
-- El término "Stored Procedure" se usa en el sentido amplio del
-- informe (lógica de negocio almacenada en el motor).
--
-- Todos los SP clínicos (SP1–SP3) reciben:
--   p_fecha_inicio DATE  — inicio del período (NULL = sin límite)
--   p_fecha_fin    DATE   — fin del período   (NULL = sin límite)
--   p_id_area      INT    — filtro de especialidad (NULL = todas)
--   p_id_sector    INT    — filtro de sector del CESFAM (NULL = todos), en línea con RF-02
-- y devuelven, además del valor, el nivel de semáforo (Verde/Amarillo/Rojo).
--
-- Los umbrales de semáforo están definidos como constantes al inicio
-- de cada SP y son AJUSTABLES. La meta oficial de cada KPI se guarda
-- aparte en la tabla metas_kpi (para la línea "valor vs meta" de la tarjeta).
-- Códigos de KPI usados en historial_kpi / metas_kpi: KPI-01 .. KPI-05
-- ============================================================

-- Nota: CREATE OR REPLACE no reemplaza una función si cambia su firma
-- (cantidad de parámetros). Estos DROP evitan quedar con dos versiones
-- ambiguas de un mismo SP si este script se corre sobre una base que
-- ya tenía las versiones anteriores (sin p_id_sector).
DROP FUNCTION IF EXISTS sp_kpi_inasistencia(date, date, integer);
DROP FUNCTION IF EXISTS sp_kpi_tiempo_espera(date, date, integer);
DROP FUNCTION IF EXISTS sp_kpi_ocupacion_agenda(date, date, integer);


-- ============================================================
-- SP1 — KPI-01: TASA DE INASISTENCIA
-- Fórmula: inasistencias / (atendidas + inasistentes) * 100
-- (los "Reagendado" se excluyen del denominador: no son ausencias)
-- Umbrales: Verde <= 10% | Amarillo <= 20% | Rojo > 20%
-- ============================================================
CREATE OR REPLACE FUNCTION sp_kpi_inasistencia(
    p_fecha_inicio DATE DEFAULT NULL,
    p_fecha_fin    DATE DEFAULT NULL,
    p_id_area      INTEGER DEFAULT NULL,
    p_id_sector    INTEGER DEFAULT NULL
)
RETURNS TABLE (
    citas_evaluables   INTEGER,
    inasistencias      INTEGER,
    tasa_inasistencia  NUMERIC(5,2),
    nivel_semaforo     TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    c_verde    CONSTANT NUMERIC := 10;   -- <= => Verde
    c_amarillo CONSTANT NUMERIC := 20;   -- <= => Amarillo ; > => Rojo
    v_evaluables INTEGER;
    v_inasis     INTEGER;
    v_tasa       NUMERIC(5,2);
BEGIN
    SELECT
        COUNT(*) FILTER (WHERE c.estado_cita IN ('Atendido','Inasistente')),
        COUNT(*) FILTER (WHERE c.estado_cita = 'Inasistente')
    INTO v_evaluables, v_inasis
    FROM citas_medicas c
    JOIN bloques_agenda b     ON b.id_bloque = c.id_bloque
    JOIN profesionales  p     ON p.id_profesional = b.id_profesional
    JOIN areas_especialidad a ON a.id_area = p.id_area
    WHERE b.fecha BETWEEN COALESCE(p_fecha_inicio, DATE '1900-01-01')
                      AND COALESCE(p_fecha_fin,    DATE '9999-12-31')
      AND (p_id_area   IS NULL OR p.id_area   = p_id_area)
      AND (p_id_sector IS NULL OR a.id_sector = p_id_sector);

    v_tasa := CASE WHEN COALESCE(v_evaluables,0) = 0 THEN 0
                   ELSE ROUND(v_inasis * 100.0 / v_evaluables, 2) END;

    RETURN QUERY SELECT
        COALESCE(v_evaluables,0),
        COALESCE(v_inasis,0),
        v_tasa,
        CASE
            WHEN v_tasa <= c_verde    THEN 'Verde'
            WHEN v_tasa <= c_amarillo THEN 'Amarillo'
            ELSE 'Rojo'
        END;
END;
$$;


-- ============================================================
-- SP2 — KPI-02: TIEMPO PROMEDIO DE ESPERA (minutos)
-- Fórmula: AVG( hora_atencion - bloque.hora_inicio ) sobre citas Atendidas.
-- Las esperas negativas (paciente atendido antes de la hora agendada)
-- se llevan a 0 para no distorsionar el promedio.
-- Umbrales: Verde <= 15 min | Amarillo <= 30 min | Rojo > 30 min
-- ============================================================
CREATE OR REPLACE FUNCTION sp_kpi_tiempo_espera(
    p_fecha_inicio DATE DEFAULT NULL,
    p_fecha_fin    DATE DEFAULT NULL,
    p_id_area      INTEGER DEFAULT NULL,
    p_id_sector    INTEGER DEFAULT NULL
)
RETURNS TABLE (
    total_atenciones     INTEGER,
    espera_promedio_min  NUMERIC(6,2),
    nivel_semaforo       TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    c_verde    CONSTANT NUMERIC := 15;
    c_amarillo CONSTANT NUMERIC := 30;
    v_n    INTEGER;
    v_prom NUMERIC(6,2);
BEGIN
    SELECT
        COUNT(*),
        COALESCE(AVG( GREATEST(
            EXTRACT(EPOCH FROM (c.hora_atencion - b.hora_inicio)) / 60.0, 0) ), 0)
    INTO v_n, v_prom
    FROM citas_medicas c
    JOIN bloques_agenda b     ON b.id_bloque = c.id_bloque
    JOIN profesionales  p     ON p.id_profesional = b.id_profesional
    JOIN areas_especialidad a ON a.id_area = p.id_area
    WHERE b.fecha BETWEEN COALESCE(p_fecha_inicio, DATE '1900-01-01')
                      AND COALESCE(p_fecha_fin,    DATE '9999-12-31')
      AND (p_id_area   IS NULL OR p.id_area   = p_id_area)
      AND (p_id_sector IS NULL OR a.id_sector = p_id_sector)
      AND c.estado_cita = 'Atendido'
      AND c.hora_atencion IS NOT NULL;

    RETURN QUERY SELECT
        COALESCE(v_n,0),
        ROUND(v_prom, 2),
        CASE
            WHEN v_prom <= c_verde    THEN 'Verde'
            WHEN v_prom <= c_amarillo THEN 'Amarillo'
            ELSE 'Rojo'
        END;
END;
$$;


-- ============================================================
-- SP3 — KPI-03: OCUPACIÓN DE AGENDA (%)
-- Fórmula: bloques 'Reservado' / bloques ofertados * 100
--   bloques ofertados = bloques del período con estado <> 'Bloqueado'
--                       y cuya fecha NO está en la tabla feriados.
-- Umbrales: Verde >= 85% | Amarillo >= 70% | Rojo < 70%
-- ============================================================
CREATE OR REPLACE FUNCTION sp_kpi_ocupacion_agenda(
    p_fecha_inicio DATE DEFAULT NULL,
    p_fecha_fin    DATE DEFAULT NULL,
    p_id_area      INTEGER DEFAULT NULL,
    p_id_sector    INTEGER DEFAULT NULL
)
RETURNS TABLE (
    bloques_ofertados  INTEGER,
    bloques_utilizados INTEGER,
    ocupacion_pct      NUMERIC(5,2),
    nivel_semaforo     TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    c_verde    CONSTANT NUMERIC := 85;   -- >= => Verde
    c_amarillo CONSTANT NUMERIC := 70;   -- >= => Amarillo ; < => Rojo
    v_ofertados  INTEGER;
    v_utilizados INTEGER;
    v_pct        NUMERIC(5,2);
BEGIN
    SELECT
        COUNT(*) FILTER (WHERE b.estado_bloque <> 'Bloqueado'),
        COUNT(*) FILTER (WHERE b.estado_bloque =  'Reservado')
    INTO v_ofertados, v_utilizados
    FROM bloques_agenda b
    JOIN profesionales p      ON p.id_profesional = b.id_profesional
    JOIN areas_especialidad a ON a.id_area = p.id_area
    WHERE b.fecha BETWEEN COALESCE(p_fecha_inicio, DATE '1900-01-01')
                      AND COALESCE(p_fecha_fin,    DATE '9999-12-31')
      AND (p_id_area   IS NULL OR p.id_area   = p_id_area)
      AND (p_id_sector IS NULL OR a.id_sector = p_id_sector)
      AND NOT EXISTS (SELECT 1 FROM feriados f WHERE f.fecha = b.fecha);

    v_pct := CASE WHEN COALESCE(v_ofertados,0) = 0 THEN 0
                  ELSE ROUND(v_utilizados * 100.0 / v_ofertados, 2) END;

    RETURN QUERY SELECT
        COALESCE(v_ofertados,0),
        COALESCE(v_utilizados,0),
        v_pct,
        CASE
            WHEN v_pct >= c_verde    THEN 'Verde'
            WHEN v_pct >= c_amarillo THEN 'Amarillo'
            ELSE 'Rojo'
        END;
END;
$$;


-- ============================================================
-- SP4 — KPI-04: PRODUCTOS EN STOCK CRÍTICO
-- Conteo de insumos en semáforo AMARILLO:
--   stock_actual > 0  AND  stock_actual <= stock_minimo
-- Es una foto del estado actual (no recibe rango de fechas).
-- Umbrales: Verde = 0 | Amarillo <= 5 | Rojo > 5
-- ============================================================
CREATE OR REPLACE FUNCTION sp_kpi_stock_critico()
RETURNS TABLE (
    productos_stock_critico INTEGER,
    nivel_semaforo          TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    c_amarillo CONSTANT INTEGER := 5;   -- <= => Amarillo ; > => Rojo ; 0 => Verde
    v_n INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_n
    FROM inventario_insumos
    WHERE stock_actual > 0
      AND stock_actual <= stock_minimo;

    RETURN QUERY SELECT
        COALESCE(v_n,0),
        CASE
            WHEN COALESCE(v_n,0) = 0          THEN 'Verde'
            WHEN v_n <= c_amarillo            THEN 'Amarillo'
            ELSE 'Rojo'
        END;
END;
$$;


-- ============================================================
-- SP5 — KPI-05: QUIEBRES DE STOCK ACTIVOS
-- Conteo de insumos en semáforo ROJO:  stock_actual = 0
-- Es una foto del estado actual (no recibe rango de fechas).
-- Umbrales: Verde = 0 | Amarillo <= 3 | Rojo > 3
-- ============================================================
CREATE OR REPLACE FUNCTION sp_kpi_quiebres_stock()
RETURNS TABLE (
    quiebres_activos INTEGER,
    nivel_semaforo   TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    c_amarillo CONSTANT INTEGER := 3;   -- <= => Amarillo ; > => Rojo ; 0 => Verde
    v_n INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_n
    FROM inventario_insumos
    WHERE stock_actual = 0;

    RETURN QUERY SELECT
        COALESCE(v_n,0),
        CASE
            WHEN COALESCE(v_n,0) = 0 THEN 'Verde'
            WHEN v_n <= c_amarillo   THEN 'Amarillo'
            ELSE 'Rojo'
        END;
END;
$$;


-- ============================================================
-- EJEMPLOS DE USO (desde DBeaver o psycopg2)
-- ============================================================
-- SELECT * FROM sp_kpi_inasistencia('2026-09-01','2026-09-30');               -- todas las áreas/sectores
-- SELECT * FROM sp_kpi_inasistencia('2026-09-01','2026-09-30', 3);            -- área id = 3
-- SELECT * FROM sp_kpi_inasistencia('2026-09-01','2026-09-30', NULL, 2);      -- sector id = 2, todas las áreas
-- SELECT * FROM sp_kpi_tiempo_espera('2026-09-01','2026-09-30');
-- SELECT * FROM sp_kpi_ocupacion_agenda('2026-09-01','2026-09-30');
-- SELECT * FROM sp_kpi_stock_critico();
-- SELECT * FROM sp_kpi_quiebres_stock();
