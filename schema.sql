PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS operador (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre        TEXT    NOT NULL,
    usuario       TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    activo        INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0,1))
);

CREATE TABLE IF NOT EXISTS cliente (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre    TEXT NOT NULL,
    documento TEXT NOT NULL UNIQUE,
    telefono  TEXT,
    email     TEXT
);

CREATE TABLE IF NOT EXISTS vehiculo (
    placa      TEXT PRIMARY KEY,
    tipo       TEXT NOT NULL CHECK (tipo IN ('carro','moto')),
    marca      TEXT,
    color      TEXT,
    cliente_id INTEGER NOT NULL REFERENCES cliente(id)
);

CREATE TABLE IF NOT EXISTS celda (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE,
    tipo   TEXT NOT NULL CHECK (tipo IN ('carro','moto')),
    estado TEXT NOT NULL DEFAULT 'libre'
           CHECK (estado IN ('libre','ocupada','mantenimiento'))
);

CREATE TABLE IF NOT EXISTS mensualidad (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id   INTEGER NOT NULL REFERENCES cliente(id),
    celda_id     INTEGER REFERENCES celda(id),
    fecha_inicio TEXT NOT NULL,
    fecha_fin    TEXT NOT NULL,
    valor        INTEGER NOT NULL CHECK (valor >= 0),
    estado       TEXT NOT NULL DEFAULT 'vigente'
                 CHECK (estado IN ('vigente','vencida','cancelada'))
);

CREATE TABLE IF NOT EXISTS movimiento (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    placa                 TEXT    NOT NULL REFERENCES vehiculo(placa),
    celda_id              INTEGER NOT NULL REFERENCES celda(id),
    operador_entrada_id   INTEGER NOT NULL REFERENCES operador(id),
    operador_salida_id    INTEGER REFERENCES operador(id),
    fecha_entrada         TEXT    NOT NULL,
    fecha_salida          TEXT,
    estado                TEXT    NOT NULL DEFAULT 'en_curso'
                          CHECK (estado IN ('en_curso','finalizado'))
);
-- Un vehículo no puede tener dos movimientos en curso a la vez
CREATE UNIQUE INDEX IF NOT EXISTS ux_mov_placa_en_curso
    ON movimiento(placa) WHERE estado = 'en_curso';

CREATE TABLE IF NOT EXISTS novedad (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    movimiento_id INTEGER NOT NULL REFERENCES movimiento(id),
    operador_id   INTEGER NOT NULL REFERENCES operador(id),
    tipo          TEXT NOT NULL CHECK (tipo IN ('daño','objeto_olvidado','incidente','otro')),
    descripcion   TEXT NOT NULL,
    fecha         TEXT NOT NULL
);
