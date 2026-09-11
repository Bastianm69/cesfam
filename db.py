"""
Capa de acceso a datos — Gestión Inteligente CESFAM.

Centraliza la conexión a PostgreSQL (Neon) y la ejecución de los
Stored Procedures (funciones PL/pgSQL) que calculan los 5 KPI.
"""
import os

import pandas as pd
import psycopg2
import streamlit as st
from dotenv import load_dotenv

load_dotenv()


@st.cache_resource(show_spinner=False)
def get_connection():
    """Conexión reutilizada entre reruns de Streamlit (una por sesión)."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        st.error(
            "No se encontró DATABASE_URL. Crea un archivo .env en la raíz "
            "del proyecto (ver .env.example)."
        )
        st.stop()
    return psycopg2.connect(database_url)


def run_query(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Ejecuta un SELECT (o SELECT * FROM sp_xxx(...)) y devuelve un DataFrame."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [c.name for c in cur.description]
            rows = cur.fetchall()
        return pd.DataFrame(rows, columns=cols)
    except psycopg2.Error:
        conn.rollback()
        raise


# ---------------------------------------------------------------
# Un wrapper por cada Stored Procedure (SP1-SP5).
# fecha_inicio/fecha_fin en formato 'YYYY-MM-DD'; id_area None = todas.
# ---------------------------------------------------------------

def kpi_inasistencia(fecha_inicio, fecha_fin, id_area=None, id_sector=None) -> pd.DataFrame:
    return run_query(
        "SELECT * FROM sp_kpi_inasistencia(%s, %s, %s, %s)",
        (fecha_inicio, fecha_fin, id_area, id_sector),
    )


def kpi_tiempo_espera(fecha_inicio, fecha_fin, id_area=None, id_sector=None) -> pd.DataFrame:
    return run_query(
        "SELECT * FROM sp_kpi_tiempo_espera(%s, %s, %s, %s)",
        (fecha_inicio, fecha_fin, id_area, id_sector),
    )


def kpi_ocupacion_agenda(fecha_inicio, fecha_fin, id_area=None, id_sector=None) -> pd.DataFrame:
    return run_query(
        "SELECT * FROM sp_kpi_ocupacion_agenda(%s, %s, %s, %s)",
        (fecha_inicio, fecha_fin, id_area, id_sector),
    )


def kpi_stock_critico() -> pd.DataFrame:
    return run_query("SELECT * FROM sp_kpi_stock_critico()")


def kpi_quiebres_stock() -> pd.DataFrame:
    return run_query("SELECT * FROM sp_kpi_quiebres_stock()")


def obtener_meta(codigo_kpi: str, periodo: str):
    """Meta oficial del KPI para el período dado (ej. '2026-Q3').
    Si no hay meta definida para ese período exacto, usa la más reciente
    disponible para ese KPI. Devuelve None si no hay ninguna."""
    df = run_query(
        "SELECT valor_meta FROM metas_kpi WHERE codigo_kpi = %s AND periodo = %s",
        (codigo_kpi, periodo),
    )
    if df.empty:
        df = run_query(
            "SELECT valor_meta FROM metas_kpi WHERE codigo_kpi = %s "
            "ORDER BY periodo DESC LIMIT 1",
            (codigo_kpi,),
        )
    return None if df.empty else float(df.iloc[0]["valor_meta"])


def listar_sectores() -> pd.DataFrame:
    return run_query(
        "SELECT id_sector, nombre_sector FROM sectores ORDER BY nombre_sector"
    )


def listar_areas(id_sector=None) -> pd.DataFrame:
    if id_sector is None:
        return run_query(
            "SELECT id_area, nombre_area FROM areas_especialidad ORDER BY nombre_area"
        )
    return run_query(
        """
        SELECT id_area, nombre_area FROM areas_especialidad
        WHERE id_sector = %s
        ORDER BY nombre_area
        """,
        (id_sector,),
    )
