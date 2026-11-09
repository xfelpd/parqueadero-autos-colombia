"""Capa de acceso a datos: conexión SQLite y datos de demostración."""
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from werkzeug.security import generate_password_hash

SCHEMA = Path(__file__).resolve().parent.parent / "schema.sql"


def connect(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


# Columnas agregadas en la Iteración 2. Sirven para actualizar bases de datos
# creadas con la Iteración 1 sin perder sus datos (cambios solo aditivos).
COLUMNAS_NUEVAS = {
    "operador": [
        ("rol", "TEXT NOT NULL DEFAULT 'operador' CHECK (rol IN ('administrador','operador'))"),
        ("creado_por", "INTEGER REFERENCES operador(id)"),
        ("creado_en", "TEXT"),
        ("actualizado_por", "INTEGER REFERENCES operador(id)"),
        ("actualizado_en", "TEXT"),
    ],
    "celda": [
        ("actualizado_por", "INTEGER REFERENCES operador(id)"),
        ("actualizado_en", "TEXT"),
    ],
}


def init_db(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    migrar(con)
    con.commit()


def migrar(con: sqlite3.Connection) -> None:
    """Agrega las columnas de la Iteración 2 si la base viene de la Iteración 1."""
    for tabla, columnas in COLUMNAS_NUEVAS.items():
        existentes = {r["name"] for r in con.execute(f"PRAGMA table_info({tabla})")}
        for nombre, definicion in columnas:
            if nombre not in existentes:
                con.execute(f"ALTER TABLE {tabla} ADD COLUMN {nombre} {definicion}")
    con.commit()


def asegurar_admin(con: sqlite3.Connection) -> None:
    """Garantiza una cuenta de administrador de demostración (admin / admin1234)."""
    if con.execute("SELECT 1 FROM operador WHERE rol='administrador' AND activo=1").fetchone():
        return
    if con.execute("SELECT 1 FROM operador WHERE usuario='admin'").fetchone():
        return
    con.execute(
        "INSERT INTO operador(nombre,usuario,password_hash,rol,creado_en) VALUES (?,?,?,?,?)",
        ("Administrador Demo", "admin", generate_password_hash("admin1234"),
         "administrador", datetime.now().isoformat(timespec="seconds")))
    con.commit()


def seed_demo(con: sqlite3.Connection) -> None:
    """Datos de ejemplo (la gestión completa de clientes llega en la Iteración 2)."""
    if con.execute("SELECT COUNT(*) FROM operador").fetchone()[0]:
        return
    hoy = date.today()
    con.execute("INSERT INTO operador(nombre,usuario,password_hash) VALUES (?,?,?)",
                ("Operador Demo", "operador", generate_password_hash("1234")))
    con.executemany("INSERT INTO cliente(nombre,documento,telefono,email) VALUES (?,?,?,?)", [
        ("Laura Gómez", "1001", "3001112233", "laura@mail.com"),
        ("Carlos Pérez", "1002", "3002223344", "carlos@mail.com"),
        ("Ana Ríos", "1003", "3003334455", "ana@mail.com"),
    ])
    con.executemany("INSERT INTO celda(codigo,tipo) VALUES (?,?)",
                    [(f"A{i}", "carro") for i in range(1, 7)] +
                    [(f"M{i}", "moto") for i in range(1, 4)])
    con.executemany("INSERT INTO vehiculo(placa,tipo,marca,color,cliente_id) VALUES (?,?,?,?,?)", [
        ("ABC123", "carro", "Mazda", "Rojo", 1),
        ("DEF456", "carro", "Renault", "Gris", 2),
        ("XYZ78A", "moto", "Yamaha", "Negra", 3),
    ])
    vigente = (hoy - timedelta(days=5)).isoformat(), (hoy + timedelta(days=25)).isoformat()
    vencida = (hoy - timedelta(days=60)).isoformat(), (hoy - timedelta(days=30)).isoformat()
    con.executemany(
        "INSERT INTO mensualidad(cliente_id,celda_id,fecha_inicio,fecha_fin,valor,estado) VALUES (?,?,?,?,?,?)", [
            (1, 1, *vigente, 180000, "vigente"),
            (2, 2, *vencida, 180000, "vencida"),
            (3, 7, *vigente, 70000, "vigente"),
        ])
    con.commit()
