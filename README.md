# Gestión Inteligente CESFAM

Prototipo de Inteligencia de Negocios (Dashboard) para apoyar la gestión de un
CESFAM. Proyecto académico — asignatura Desarrollo y Gestión de un Proyecto
Informático.

## Stack

- **Base de datos:** PostgreSQL en Neon (17 tablas + 5 Stored Procedures en PL/pgSQL)
- **Backend/Frontend:** Python + Streamlit
- **Gráficos:** Plotly
- **Conexión:** psycopg2

## Estructura

```
cesfam/
├── app.py                     # Dashboard (interfaz)
├── db.py                      # Conexión y wrappers de los 5 SP
├── requirements.txt
├── .env                       # DATABASE_URL (NO subir a git)
├── .env.example                # plantilla sin credenciales
└── sql/
    ├── 01_schema.sql           # 17 tablas
    ├── 02_datos_sinteticos.sql # datos de prueba
    └── 03_stored_procedures.sql
```

## Cómo correrlo

```bash
python3 -m venv venv
source venv/bin/activate          # en fish: source venv/bin/activate.fish
pip install -r requirements.txt
cp .env.example .env              # y completa tu DATABASE_URL de Neon
streamlit run app.py
```

Se abre en `http://localhost:8501`.

## Base de datos

Ejecutar en orden, sobre el proyecto de Neon, desde DBeaver u otro cliente SQL:

1. `sql/01_schema.sql`
2. `sql/02_datos_sinteticos.sql`
3. `sql/03_stored_procedures.sql`
