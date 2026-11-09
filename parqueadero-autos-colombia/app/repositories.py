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


def listar_celdas(con, tipo=None, estado=None):
    sql = """SELECT c.*,
                    (SELECT m.placa FROM movimiento m
                     WHERE m.celda_id=c.id AND m.estado='en_curso') AS placa
             FROM celda c WHERE 1=1"""
    args = []
    if tipo:
        sql += " AND c.tipo=?"; args.append(tipo)
    if estado:
        sql += " AND c.estado=?"; args.append(estado)
    return con.execute(sql + " ORDER BY c.codigo", args).fetchall()


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


# ====================== Iteración 2: gestión de usuarios ======================

def _n(con, sql, args=()):
    return con.execute(sql, args).fetchone()[0]


# ---- clientes ----
def listar_clientes(con, q=None):
    sql, args = "SELECT * FROM cliente", []
    if q:
        sql += " WHERE nombre LIKE ? OR documento LIKE ?"
        args = [f"%{q}%", f"%{q}%"]
    return con.execute(sql + " ORDER BY nombre", args).fetchall()


def cliente_por_id(con, cliente_id):
    return con.execute("SELECT * FROM cliente WHERE id=?", (cliente_id,)).fetchone()


def cliente_por_documento(con, documento):
    return con.execute("SELECT * FROM cliente WHERE documento=?", (documento,)).fetchone()


def crear_cliente(con, nombre, documento, telefono, email):
    cur = con.execute("INSERT INTO cliente(nombre,documento,telefono,email) VALUES (?,?,?,?)",
                      (nombre, documento, telefono, email))
    return cur.lastrowid


def actualizar_cliente(con, cliente_id, nombre, documento, telefono, email):
    con.execute("UPDATE cliente SET nombre=?, documento=?, telefono=?, email=? WHERE id=?",
                (nombre, documento, telefono, email, cliente_id))


def eliminar_cliente(con, cliente_id):
    con.execute("DELETE FROM vehiculo WHERE cliente_id=?", (cliente_id,))
    con.execute("DELETE FROM cliente WHERE id=?", (cliente_id,))


def total_movimientos_cliente(con, cliente_id):
    return _n(con, """SELECT COUNT(*) FROM movimiento m
                      JOIN vehiculo v ON v.placa=m.placa WHERE v.cliente_id=?""", (cliente_id,))


def total_mensualidades_cliente(con, cliente_id):
    return _n(con, "SELECT COUNT(*) FROM mensualidad WHERE cliente_id=?", (cliente_id,))


def total_dentro_cliente(con, cliente_id):
    return _n(con, """SELECT COUNT(*) FROM movimiento m
                      JOIN vehiculo v ON v.placa=m.placa
                      WHERE v.cliente_id=? AND m.estado='en_curso'""", (cliente_id,))


def mensualidad_vigente_detalle(con, cliente_id, hoy):
    return con.execute(
        """SELECT m.id, m.fecha_inicio, m.fecha_fin, m.valor, m.estado,
                  m.celda_id, c.codigo AS celda
           FROM mensualidad m LEFT JOIN celda c ON c.id=m.celda_id
           WHERE m.cliente_id=? AND m.estado='vigente' AND m.fecha_inicio<=? AND m.fecha_fin>=?
           ORDER BY m.fecha_fin DESC LIMIT 1""", (cliente_id, hoy, hoy)).fetchone()


def mensualidad_por_id(con, mensualidad_id):
    return con.execute("SELECT * FROM mensualidad WHERE id=?", (mensualidad_id,)).fetchone()


# ---- vehículos ----
def listar_vehiculos(con, cliente_id=None):
    sql = """SELECT v.*, cl.nombre AS cliente,
                    EXISTS(SELECT 1 FROM movimiento m
                           WHERE m.placa=v.placa AND m.estado='en_curso') AS dentro
             FROM vehiculo v JOIN cliente cl ON cl.id=v.cliente_id"""
    args = []
    if cliente_id:
        sql += " WHERE v.cliente_id=?"; args.append(cliente_id)
    return con.execute(sql + " ORDER BY v.placa", args).fetchall()


def crear_vehiculo(con, placa, tipo, marca, color, cliente_id):
    con.execute("INSERT INTO vehiculo(placa,tipo,marca,color,cliente_id) VALUES (?,?,?,?,?)",
                (placa, tipo, marca, color, cliente_id))


def actualizar_vehiculo(con, placa, tipo, marca, color, cliente_id):
    con.execute("UPDATE vehiculo SET tipo=?, marca=?, color=?, cliente_id=? WHERE placa=?",
                (tipo, marca, color, cliente_id, placa))


def eliminar_vehiculo(con, placa):
    con.execute("DELETE FROM vehiculo WHERE placa=?", (placa,))


def total_movimientos_placa(con, placa):
    return _n(con, "SELECT COUNT(*) FROM movimiento WHERE placa=?", (placa,))


# ---- operadores (cuentas del sistema) ----
def operador_por_id(con, operador_id):
    return con.execute("SELECT * FROM operador WHERE id=?", (operador_id,)).fetchone()


def usuario_existe(con, usuario):
    return con.execute("SELECT id FROM operador WHERE usuario=?", (usuario,)).fetchone()


def listar_operadores(con):
    """No incluye password_hash (RNF-11)."""
    return con.execute(
        """SELECT id, nombre, usuario, rol, activo, creado_en, actualizado_en
           FROM operador ORDER BY nombre""").fetchall()


def crear_operador(con, nombre, usuario, password_hash, rol, creado_por):
    cur = con.execute(
        """INSERT INTO operador(nombre,usuario,password_hash,rol,creado_por,creado_en)
           VALUES (?,?,?,?,?,?)""", (nombre, usuario, password_hash, rol, creado_por, ahora()))
    return cur.lastrowid


def actualizar_operador(con, operador_id, nombre, rol, activo, actualizado_por):
    con.execute(
        """UPDATE operador SET nombre=?, rol=?, activo=?, actualizado_por=?, actualizado_en=?
           WHERE id=?""", (nombre, rol, activo, actualizado_por, ahora(), operador_id))


def actualizar_password(con, operador_id, password_hash):
    con.execute("UPDATE operador SET password_hash=?, actualizado_por=?, actualizado_en=? WHERE id=?",
                (password_hash, operador_id, ahora(), operador_id))


def total_administradores_activos(con):
    return _n(con, "SELECT COUNT(*) FROM operador WHERE rol='administrador' AND activo=1")


# ====================== Iteración 2: gestión de celdas ======================

def celda_por_codigo(con, codigo):
    return con.execute("SELECT * FROM celda WHERE codigo=?", (codigo,)).fetchone()


def crear_celda(con, codigo, tipo, operador_id):
    cur = con.execute(
        "INSERT INTO celda(codigo,tipo,actualizado_por,actualizado_en) VALUES (?,?,?,?)",
        (codigo, tipo, operador_id, ahora()))
    return cur.lastrowid


def actualizar_celda(con, celda_id, codigo, tipo, operador_id):
    con.execute("UPDATE celda SET codigo=?, tipo=?, actualizado_por=?, actualizado_en=? WHERE id=?",
                (codigo, tipo, operador_id, ahora(), celda_id))


def cambiar_estado_celda(con, celda_id, estado, operador_id):
    """Cambio de estado hecho por un administrador, con auditoría (RNF-16)."""
    con.execute("UPDATE celda SET estado=?, actualizado_por=?, actualizado_en=? WHERE id=?",
                (estado, operador_id, ahora(), celda_id))


def eliminar_celda(con, celda_id):
    con.execute("DELETE FROM celda WHERE id=?", (celda_id,))


def total_movimientos_celda(con, celda_id):
    return _n(con, "SELECT COUNT(*) FROM movimiento WHERE celda_id=?", (celda_id,))


def total_mensualidades_celda(con, celda_id):
    return _n(con, "SELECT COUNT(*) FROM mensualidad WHERE celda_id=?", (celda_id,))


def mensualidad_vigente_de_celda(con, celda_id, hoy, excepto_id=0):
    return con.execute(
        """SELECT * FROM mensualidad
           WHERE celda_id=? AND estado='vigente' AND fecha_fin>=? AND id<>? LIMIT 1""",
        (celda_id, hoy, excepto_id)).fetchone()


def asignar_celda_mensualidad(con, mensualidad_id, celda_id):
    con.execute("UPDATE mensualidad SET celda_id=? WHERE id=?", (celda_id, mensualidad_id))


def resumen_celdas(con):
    return con.execute(
        "SELECT tipo, estado, COUNT(*) AS n FROM celda GROUP BY tipo, estado").fetchall()
