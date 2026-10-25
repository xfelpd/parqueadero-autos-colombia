"""Repositorios: únicas funciones que ejecutan SQL."""
from datetime import datetime


def ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def operador_por_usuario(con, usuario):
    return con.execute("SELECT * FROM operador WHERE usuario=? AND activo=1", (usuario,)).fetchone()


def vehiculo_por_placa(con, placa):
    return con.execute("SELECT * FROM vehiculo WHERE placa=?", (placa,)).fetchone()


def mensualidad_vigente(con, cliente_id, hoy):
    return con.execute(
        """SELECT * FROM mensualidad
           WHERE cliente_id=? AND estado='vigente' AND fecha_inicio<=? AND fecha_fin>=?
           ORDER BY fecha_fin DESC LIMIT 1""", (cliente_id, hoy, hoy)).fetchone()


def celda_por_id(con, celda_id):
    return con.execute("SELECT * FROM celda WHERE id=?", (celda_id,)).fetchone()


def listar_celdas(con):
    return con.execute("SELECT * FROM celda ORDER BY codigo").fetchall()


def actualizar_estado_celda(con, celda_id, estado):
    con.execute("UPDATE celda SET estado=? WHERE id=?", (estado, celda_id))


def movimiento_en_curso(con, placa):
    return con.execute("SELECT * FROM movimiento WHERE placa=? AND estado='en_curso'", (placa,)).fetchone()


def crear_movimiento(con, placa, celda_id, operador_id):
    cur = con.execute(
        "INSERT INTO movimiento(placa,celda_id,operador_entrada_id,fecha_entrada) VALUES (?,?,?,?)",
        (placa, celda_id, operador_id, ahora()))
    return cur.lastrowid


def cerrar_movimiento(con, mov_id, operador_id):
    con.execute(
        "UPDATE movimiento SET estado='finalizado', fecha_salida=?, operador_salida_id=? WHERE id=?",
        (ahora(), operador_id, mov_id))


def movimiento_por_id(con, mov_id):
    return con.execute("SELECT * FROM movimiento WHERE id=?", (mov_id,)).fetchone()


def listar_activos(con):
    return con.execute(
        """SELECT m.id, m.placa, c.codigo AS celda, m.fecha_entrada, cl.nombre AS cliente
           FROM movimiento m
           JOIN celda c ON c.id=m.celda_id
           JOIN vehiculo v ON v.placa=m.placa
           JOIN cliente cl ON cl.id=v.cliente_id
           WHERE m.estado='en_curso' ORDER BY m.fecha_entrada""").fetchall()


def historial(con, placa=None, desde=None, hasta=None):
    sql = """SELECT m.id, m.placa, c.codigo AS celda, m.fecha_entrada, m.fecha_salida, m.estado
             FROM movimiento m JOIN celda c ON c.id=m.celda_id WHERE 1=1"""
    args = []
    if placa:
        sql += " AND m.placa=?"; args.append(placa)
    if desde:
        sql += " AND date(m.fecha_entrada)>=date(?)"; args.append(desde)
    if hasta:
        sql += " AND date(m.fecha_entrada)<=date(?)"; args.append(hasta)
    return con.execute(sql + " ORDER BY m.fecha_entrada DESC", args).fetchall()


def crear_novedad(con, mov_id, operador_id, tipo, descripcion):
    cur = con.execute(
        "INSERT INTO novedad(movimiento_id,operador_id,tipo,descripcion,fecha) VALUES (?,?,?,?,?)",
        (mov_id, operador_id, tipo, descripcion, ahora()))
    return cur.lastrowid


def ultimo_movimiento(con, placa):
    return con.execute("SELECT * FROM movimiento WHERE placa=? ORDER BY id DESC LIMIT 1", (placa,)).fetchone()
