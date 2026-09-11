-- ============================================================
-- ESQUEMA: Gestión Inteligente CESFAM
-- Motor: PostgreSQL (Neon)
-- 17 tablas — Catálogos, Agenda y Atención Clínica,
-- Inventario y Abastecimiento, Acceso y Auditoría,
-- Inteligencia de Negocios
--
-- Re-ejecutable: elimina las tablas si existen y las vuelve a crear.
-- Ejecutar ESTE archivo PRIMERO, luego datos_sinteticos_cesfam.sql,
-- y por último sp_kpi_cesfam.sql.
-- ============================================================

BEGIN;

-- ---- Limpieza (orden inverso a las dependencias) ----
DROP TABLE IF EXISTS notificaciones_alerta   CASCADE;
DROP TABLE IF EXISTS metas_kpi               CASCADE;
DROP TABLE IF EXISTS historial_kpi           CASCADE;
DROP TABLE IF EXISTS auditoria_accesos       CASCADE;
DROP TABLE IF EXISTS usuarios_sistema        CASCADE;
DROP TABLE IF EXISTS movimientos_inventario  CASCADE;
DROP TABLE IF EXISTS inventario_insumos      CASCADE;
DROP TABLE IF EXISTS citas_medicas           CASCADE;
DROP TABLE IF EXISTS bloques_agenda          CASCADE;
DROP TABLE IF EXISTS profesionales           CASCADE;
DROP TABLE IF EXISTS pacientes               CASCADE;
DROP TABLE IF EXISTS areas_especialidad      CASCADE;
DROP TABLE IF EXISTS feriados                CASCADE;
DROP TABLE IF EXISTS proveedores             CASCADE;
DROP TABLE IF EXISTS motivos_inasistencia    CASCADE;
DROP TABLE IF EXISTS roles                   CASCADE;
DROP TABLE IF EXISTS sectores                CASCADE;

-- ================= CATÁLOGOS =================

CREATE TABLE sectores (
    id_sector       SERIAL PRIMARY KEY,
    nombre_sector   VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE roles (
    id_rol          SERIAL PRIMARY KEY,
    nombre_rol      VARCHAR(50) NOT NULL UNIQUE,
    descripcion     VARCHAR(200)
);

CREATE TABLE motivos_inasistencia (
    id_motivo           SERIAL PRIMARY KEY,
    descripcion_motivo  VARCHAR(150) NOT NULL
);

CREATE TABLE proveedores (
    id_proveedor       SERIAL PRIMARY KEY,
    nombre_proveedor   VARCHAR(150) NOT NULL,
    telefono_contacto  VARCHAR(20)
);

CREATE TABLE feriados (
    id_feriado   SERIAL PRIMARY KEY,
    fecha        DATE NOT NULL UNIQUE,
    descripcion  VARCHAR(100)
);

-- ================= AGENDA Y ATENCIÓN CLÍNICA =================

CREATE TABLE areas_especialidad (
    id_area      SERIAL PRIMARY KEY,
    nombre_area  VARCHAR(100) NOT NULL,
    id_sector    INTEGER NOT NULL REFERENCES sectores(id_sector)
);

CREATE TABLE pacientes (
    id_paciente       SERIAL PRIMARY KEY,
    rut               VARCHAR(12) NOT NULL UNIQUE,
    nombres           VARCHAR(100) NOT NULL,
    apellidos         VARCHAR(100) NOT NULL,
    fecha_nacimiento  DATE NOT NULL,
    sexo              VARCHAR(10) CHECK (sexo IN ('M','F','Otro')),
    id_sector         INTEGER REFERENCES sectores(id_sector)
);

CREATE TABLE profesionales (
    id_profesional  SERIAL PRIMARY KEY,
    nombre          VARCHAR(150) NOT NULL,
    id_area         INTEGER NOT NULL REFERENCES areas_especialidad(id_area),
    box_asignado    VARCHAR(20)
);

CREATE TABLE bloques_agenda (
    id_bloque       SERIAL PRIMARY KEY,
    id_profesional  INTEGER NOT NULL REFERENCES profesionales(id_profesional),
    fecha           DATE NOT NULL,
    hora_inicio     TIME NOT NULL,
    hora_fin        TIME NOT NULL,
    estado_bloque   VARCHAR(20) CHECK (estado_bloque IN ('Disponible','Reservado','Bloqueado'))
);

CREATE TABLE citas_medicas (
    id_cita        SERIAL PRIMARY KEY,
    id_paciente    INTEGER NOT NULL REFERENCES pacientes(id_paciente),
    id_bloque      INTEGER NOT NULL UNIQUE REFERENCES bloques_agenda(id_bloque),
    id_motivo      INTEGER REFERENCES motivos_inasistencia(id_motivo),
    hora_atencion  TIME,
    estado_cita    VARCHAR(20) CHECK (estado_cita IN ('Atendido','Inasistente','Reagendado'))
);

-- ================= INVENTARIO Y ABASTECIMIENTO =================

CREATE TABLE inventario_insumos (
    id_insumo        SERIAL PRIMARY KEY,
    codigo_producto  VARCHAR(50) NOT NULL UNIQUE,
    nombre_producto  VARCHAR(150) NOT NULL,
    stock_actual     INTEGER NOT NULL CHECK (stock_actual >= 0),
    stock_minimo     INTEGER NOT NULL CHECK (stock_minimo >= 0),
    id_proveedor     INTEGER REFERENCES proveedores(id_proveedor)
);

CREATE TABLE movimientos_inventario (
    id_movimiento     SERIAL PRIMARY KEY,
    id_insumo         INTEGER NOT NULL REFERENCES inventario_insumos(id_insumo),
    tipo_movimiento   VARCHAR(20) CHECK (tipo_movimiento IN ('Entrada','Salida')),
    cantidad          INTEGER NOT NULL CHECK (cantidad > 0),
    fecha_movimiento  DATE NOT NULL
);

-- ================= ACCESO Y AUDITORÍA =================

CREATE TABLE usuarios_sistema (
    id_usuario  SERIAL PRIMARY KEY,
    nombre      VARCHAR(100) NOT NULL,
    email       VARCHAR(100) NOT NULL UNIQUE,
    id_rol      INTEGER NOT NULL REFERENCES roles(id_rol)
);

CREATE TABLE auditoria_accesos (
    id_acceso   SERIAL PRIMARY KEY,
    id_usuario  INTEGER NOT NULL REFERENCES usuarios_sistema(id_usuario),
    fecha_hora  TIMESTAMP NOT NULL DEFAULT NOW(),
    accion      VARCHAR(100) NOT NULL
);

-- ================= INTELIGENCIA DE NEGOCIOS =================

CREATE TABLE historial_kpi (
    id_registro      SERIAL PRIMARY KEY,
    codigo_kpi       VARCHAR(10) NOT NULL,
    fecha_calculo    DATE NOT NULL,
    id_area          INTEGER REFERENCES areas_especialidad(id_area),
    valor_calculado  DECIMAL(10,2) NOT NULL,
    nivel_semaforo   VARCHAR(10) CHECK (nivel_semaforo IN ('Verde','Amarillo','Rojo'))
);

CREATE TABLE metas_kpi (
    id_meta     SERIAL PRIMARY KEY,
    codigo_kpi  VARCHAR(10) NOT NULL,
    periodo     VARCHAR(20) NOT NULL,
    valor_meta  DECIMAL(10,2) NOT NULL
);

CREATE TABLE notificaciones_alerta (
    id_notificacion  SERIAL PRIMARY KEY,
    id_registro      INTEGER NOT NULL REFERENCES historial_kpi(id_registro),
    fecha_generada   TIMESTAMP NOT NULL DEFAULT NOW(),
    mensaje          VARCHAR(200) NOT NULL
);

COMMIT;

-- Verificación rápida: deben aparecer 17 filas
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY table_name;
