"""
Dashboard de Inteligencia de Negocios — Gestión Inteligente CESFAM
Prototipo académico. Ejecutar con:  streamlit run app.py
"""
import datetime as dt

import plotly.express as px
import streamlit as st

import db

st.set_page_config(page_title="Gestión Inteligente CESFAM", layout="wide")

COLOR_SEMAFORO = {"Verde": "#16a34a", "Amarillo": "#ca8a04", "Rojo": "#dc2626"}
FONDO_SEMAFORO = {"Verde": "#f0fdf4", "Amarillo": "#fefce8", "Rojo": "#fef2f2"}

KPI_LABELS = {
    "KPI-01": "Tasa de inasistencia",
    "KPI-02": "Tiempo de espera",
    "KPI-03": "Ocupación de agenda",
    "KPI-04": "Productos en stock crítico",
    "KPI-05": "Quiebres de stock activos",
}

# Código de KPI y sentido de "mejor" (para comparar contra metas_kpi):
# "menor" = menor valor es mejor ; "mayor" = mayor valor es mejor
KPI_CODE = {
    "inasistencia": "KPI-01", "espera": "KPI-02", "ocupacion": "KPI-03",
    "stock_critico": "KPI-04", "quiebres": "KPI-05",
}
KPI_DIRECCION = {
    "inasistencia": "menor", "espera": "menor", "ocupacion": "mayor",
    "stock_critico": "menor", "quiebres": "menor",
}


def periodo_actual() -> str:
    hoy = dt.date.today()
    return f"{hoy.year}-Q{(hoy.month - 1) // 3 + 1}"


def linea_meta(code: str, valor_real: float, sufijo: str = "") -> str | None:
    meta = db.obtener_meta(KPI_CODE[code], periodo_actual())
    if meta is None:
        return None
    direccion = KPI_DIRECCION[code]
    cumple = valor_real <= meta if direccion == "menor" else valor_real >= meta
    estado = "cumple la meta" if cumple else "no cumple la meta"
    return f"Meta: {meta:g}{sufijo} — {estado}"

# ---------------------------------------------------------------
# Perfiles de usuario (RNF-03): qué ve cada rol.
# Definido según la sección 7 del informe (Usuarios del Sistema).
# ---------------------------------------------------------------
ROLE_INFO = {
    "Equipo Directivo": {
        "descripcion": "Visión ejecutiva del rendimiento global del establecimiento.",
        "kpis": ["inasistencia", "espera", "ocupacion", "stock_critico", "quiebres"],
        "tendencia": ["KPI-01", "KPI-02", "KPI-03", "KPI-04", "KPI-05"],
        "inventario": True,
    },
    "Encargado de Gestión": {
        "descripcion": "Cuellos de botella en la atención y balance de carga de trabajo.",
        "kpis": ["espera", "ocupacion"],
        "tendencia": ["KPI-02", "KPI-03"],
        "inventario": False,
    },
    "Responsable de Abastecimiento": {
        "descripcion": "Niveles de inventario y prevención de quiebres de stock.",
        "kpis": ["stock_critico", "quiebres"],
        "tendencia": ["KPI-04", "KPI-05"],
        "inventario": True,
    },
    "Personal Administrativo": {
        "descripcion": "Agendamiento diario: inasistencias y cupos disponibles.",
        "kpis": ["inasistencia", "ocupacion"],
        "tendencia": ["KPI-01", "KPI-03"],
        "inventario": False,
    },
}


# ---------------------------------------------------------------
# Componentes de UI
# ---------------------------------------------------------------
def render_kpi_card(col, titulo: str, valor: str, semaforo: str, detalle: str = "",
                     meta_texto: str | None = None):
    color = COLOR_SEMAFORO.get(semaforo, "#94a3b8")
    fondo = FONDO_SEMAFORO.get(semaforo, "#f8fafc")
    meta_html = ""
    if meta_texto:
        meta_html = (
            f'<div style="font-size:11px;color:#334155;margin-top:6px;'
            f'padding-top:6px;border-top:1px solid rgba(0,0,0,.08);">{meta_texto}</div>'
        )
    with col:
        st.markdown(
            f"""
            <div style="background:{fondo};border-left:6px solid {color};
                        border-radius:8px;padding:14px 16px;min-height:150px;">
                <div style="font-size:13px;color:#475569;font-weight:600;">{titulo}</div>
                <div style="font-size:30px;font-weight:700;color:#0f172a;margin-top:4px;">
                    {valor}
                </div>
                <div style="font-size:12px;color:{color};font-weight:600;margin-top:6px;">
                    ● {semaforo}
                </div>
                <div style="font-size:11px;color:#64748b;margin-top:2px;">{detalle}</div>
                {meta_html}
            </div>
            """,
            unsafe_allow_html=True,
        )


def get_card_data(code: str, fecha_inicio, fecha_fin, id_area, id_sector):
    """Devuelve (titulo, valor, semaforo, detalle, meta_texto) para el KPI dado."""
    if code == "inasistencia":
        d = db.kpi_inasistencia(fecha_inicio, fecha_fin, id_area, id_sector).iloc[0]
        valor_real = float(d["tasa_inasistencia"])
        return (
            "Tasa de inasistencia", f"{valor_real:.1f}%", d["nivel_semaforo"],
            f"{d['inasistencias']} de {d['citas_evaluables']} citas",
            linea_meta(code, valor_real, "%"),
        )
    if code == "espera":
        d = db.kpi_tiempo_espera(fecha_inicio, fecha_fin, id_area, id_sector).iloc[0]
        valor_real = float(d["espera_promedio_min"])
        return (
            "Tiempo prom. de espera", f"{valor_real:.0f} min", d["nivel_semaforo"],
            f"{d['total_atenciones']} atenciones",
            linea_meta(code, valor_real, " min"),
        )
    if code == "ocupacion":
        d = db.kpi_ocupacion_agenda(fecha_inicio, fecha_fin, id_area, id_sector).iloc[0]
        valor_real = float(d["ocupacion_pct"])
        return (
            "Ocupación de agenda", f"{valor_real:.1f}%", d["nivel_semaforo"],
            f"{d['bloques_utilizados']} de {d['bloques_ofertados']} bloques",
            linea_meta(code, valor_real, "%"),
        )
    if code == "stock_critico":
        d = db.kpi_stock_critico().iloc[0]
        valor_real = float(d["productos_stock_critico"])
        return (
            "Productos en stock crítico", f"{valor_real:.0f}", d["nivel_semaforo"],
            "stock ≤ mínimo",
            linea_meta(code, valor_real),
        )
    if code == "quiebres":
        d = db.kpi_quiebres_stock().iloc[0]
        valor_real = float(d["quiebres_activos"])
        return (
            "Quiebres de stock activos", f"{valor_real:.0f}", d["nivel_semaforo"],
            "stock en 0",
            linea_meta(code, valor_real),
        )
    raise ValueError(f"KPI desconocido: {code}")


# ---------------------------------------------------------------
# Barra lateral — Perfil (RNF-03) y filtros globales (RF-02)
# ---------------------------------------------------------------
st.sidebar.title("Sesión")
perfil = st.sidebar.selectbox("Perfil de usuario", list(ROLE_INFO.keys()))
rol = ROLE_INFO[perfil]
st.sidebar.caption(rol["descripcion"])

st.sidebar.divider()
st.sidebar.title("Filtros")

usa_fecha_area = any(k in rol["kpis"] for k in ("inasistencia", "espera", "ocupacion"))

if usa_fecha_area:
    fecha_inicio = st.sidebar.date_input("Desde", value=dt.date(2026, 7, 1))
    fecha_fin = st.sidebar.date_input("Hasta", value=dt.date(2026, 9, 30))

    sectores_df = db.listar_sectores()
    opciones_sector = {"Todos los sectores": None}
    opciones_sector.update(dict(zip(sectores_df["nombre_sector"], sectores_df["id_sector"])))
    sector_sel = st.sidebar.selectbox("Sector del CESFAM", list(opciones_sector.keys()))
    id_sector = opciones_sector[sector_sel]

    # La lista de especialidades se acota al sector elegido, para no
    # dejar combinar sector + especialidad de otro sector (0 resultados).
    areas_df = db.listar_areas(id_sector)
    opciones_area = {"Todas las áreas": None}
    opciones_area.update(dict(zip(areas_df["nombre_area"], areas_df["id_area"])))
    area_sel = st.sidebar.selectbox("Especialidad", list(opciones_area.keys()))
    id_area = opciones_area[area_sel]
else:
    fecha_inicio = fecha_fin = id_area = id_sector = None
    st.sidebar.caption(
        "Este perfil solo ve indicadores de inventario, que reflejan el "
        "estado actual y no usan filtro de fecha ni de especialidad."
    )

# ---------------------------------------------------------------
# Encabezado
# ---------------------------------------------------------------
st.title("Gestión Inteligente CESFAM")
st.caption(f"Dashboard de Inteligencia de Negocios — perfil: {perfil}")

# ---------------------------------------------------------------
# Tarjetas KPI (RF-01, RF-03) — solo las que corresponden al perfil
# ---------------------------------------------------------------
cols = st.columns(len(rol["kpis"]))
for col, code in zip(cols, rol["kpis"]):
    titulo, valor, semaforo, detalle, meta_texto = get_card_data(
        code, fecha_inicio, fecha_fin, id_area, id_sector
    )
    render_kpi_card(col, titulo, valor, semaforo, detalle, meta_texto)

st.divider()

# ---------------------------------------------------------------
# Tendencia histórica (gráfico) — a partir de historial_kpi
# ---------------------------------------------------------------
st.subheader("Tendencia")

kpis_disponibles = rol["tendencia"]
kpi_sel = st.selectbox(
    "Indicador", kpis_disponibles, format_func=lambda k: KPI_LABELS[k]
)

hist = db.run_query(
    """
    SELECT fecha_calculo, valor_calculado, nivel_semaforo
    FROM historial_kpi
    WHERE codigo_kpi = %s
    ORDER BY fecha_calculo
    """,
    (kpi_sel,),
)

if hist.empty:
    st.info("Sin historial registrado para este indicador todavía.")
else:
    fig = px.line(hist, x="fecha_calculo", y="valor_calculado", markers=True,
                  color_discrete_sequence=["#2563eb"])
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=320,
                       xaxis_title="", yaxis_title=KPI_LABELS[kpi_sel])
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------
# Detalle de inventario (RF-04) — solo para perfiles con acceso
# ---------------------------------------------------------------
if rol["inventario"]:
    st.divider()
    st.subheader("Detalle de inventario")

    inv = db.run_query(
        """
        SELECT codigo_producto, nombre_producto, stock_actual, stock_minimo,
               CASE
                   WHEN stock_actual = 0 THEN 'Rojo'
                   WHEN stock_actual <= stock_minimo THEN 'Amarillo'
                   ELSE 'Verde'
               END AS nivel_semaforo
        FROM inventario_insumos
        ORDER BY nivel_semaforo, nombre_producto
        """
    )

    filtro_semaforo = st.multiselect(
        "Filtrar por semáforo", ["Rojo", "Amarillo", "Verde"], default=["Rojo", "Amarillo"]
    )
    st.dataframe(
        inv[inv["nivel_semaforo"].isin(filtro_semaforo)] if filtro_semaforo else inv,
        use_container_width=True, hide_index=True,
    )
