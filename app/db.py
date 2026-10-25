"""Capa de acceso a datos: conexión SQLite y datos de demostración."""
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from werkzeug.security import generate_password_hash

SCHEMA = Path(__file__).resolve().parent.parent / "schema.sql"


def connect(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
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
