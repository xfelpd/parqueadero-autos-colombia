"""Capa de lógica de negocio: reglas de entrada, salida y novedades."""
import re
import sqlite3
from datetime import date

from werkzeug.security import check_password_hash, generate_password_hash

from . import repositories as repo

PLACA_RE = re.compile(r"^[A-Z]{3}\d{2}[A-Z0-9]$")
TIPOS_NOVEDAD = {"daño", "objeto_olvidado", "incidente", "otro"}


class ReglaNegocio(Exception):
    """Error de validación de negocio; `codigo` es el HTTP status sugerido."""
    def __init__(self, mensaje, codigo=400):
        super().__init__(mensaje)
        self.codigo = codigo


def normalizar_placa(placa):
    placa = (placa or "").strip().upper().replace("-", "").replace(" ", "")
    if not PLACA_RE.match(placa):
        raise ReglaNegocio("Formato de placa inválido (ej.: ABC123 o XYZ78A)")
    return placa


def registrar_entrada(con, placa, operador_id, celda_id=None):
    placa = normalizar_placa(placa)
    vehiculo = repo.vehiculo_por_placa(con, placa)
    if not vehiculo:
        raise ReglaNegocio("El vehículo no está registrado en el sistema", 404)
    if repo.movimiento_en_curso(con, placa):
        raise ReglaNegocio("El vehículo ya se encuentra dentro del parqueadero", 409)
    mens = repo.mensualidad_vigente(con, vehiculo["cliente_id"], date.today().isoformat())
    if not mens:
        raise ReglaNegocio("El cliente no tiene mensualidad vigente", 403)

    celda_id = celda_id or mens["celda_id"]
    celda = repo.celda_por_id(con, celda_id) if celda_id else None
    if not celda:
        raise ReglaNegocio("No hay celda asignada o la celda no existe", 404)
    if celda["tipo"] != vehiculo["tipo"]:
        raise ReglaNegocio("La celda no corresponde al tipo de vehículo", 400)
    if celda["estado"] != "libre":
        raise ReglaNegocio(f"La celda {celda['codigo']} no está disponible ({celda['estado']})", 409)

    try:
        mov_id = repo.crear_movimiento(con, placa, celda["id"], operador_id)
        repo.actualizar_estado_celda(con, celda["id"], "ocupada")
        con.commit()
    except sqlite3.IntegrityError:
        con.rollback()
        raise ReglaNegocio("El vehículo ya se encuentra dentro del parqueadero", 409)
    return {"movimiento_id": mov_id, "placa": placa, "celda": celda["codigo"]}


def registrar_salida(con, placa, operador_id):
    placa = normalizar_placa(placa)
    mov = repo.movimiento_en_curso(con, placa)
    if not mov:
        raise ReglaNegocio("El vehículo no tiene una entrada activa", 404)
    repo.cerrar_movimiento(con, mov["id"], operador_id)
    repo.actualizar_estado_celda(con, mov["celda_id"], "libre")
    con.commit()
    cerrado = repo.movimiento_por_id(con, mov["id"])
    return {"movimiento_id": mov["id"], "placa": placa,
            "fecha_entrada": cerrado["fecha_entrada"], "fecha_salida": cerrado["fecha_salida"]}


def registrar_novedad(con, placa, operador_id, tipo, descripcion):
    placa = normalizar_placa(placa)
    if tipo not in TIPOS_NOVEDAD:
        raise ReglaNegocio("Tipo de novedad inválido")
    if not (descripcion or "").strip():
        raise ReglaNegocio("La descripción es obligatoria")
    mov = repo.movimiento_en_curso(con, placa) or repo.ultimo_movimiento(con, placa)
    if not mov:
        raise ReglaNegocio("El vehículo no tiene movimientos registrados", 404)
    nov_id = repo.crear_novedad(con, mov["id"], operador_id, tipo, descripcion.strip())
    con.commit()
    return {"novedad_id": nov_id, "movimiento_id": mov["id"]}


# ===================== Iteración 2: constantes y utilidades =====================
TIPOS_VEHICULO = {"carro", "moto"}
ROLES = {"administrador", "operador"}
PASSWORD_MIN = 8
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _txt(valor):
    return "" if valor is None else str(valor).strip()


def _hoy():
    return date.today().isoformat()


def _tipo(valor):
    tipo = _txt(valor).lower()
    if tipo not in TIPOS_VEHICULO:
        raise ReglaNegocio("El campo tipo debe ser 'carro' o 'moto'")
    return tipo


# ===================== Iteración 2: clientes (RF-13 a RF-15, RF-18, RF-19) =====================
def _datos_cliente(d, actual=None):
    base = dict(actual) if actual else {}
    nombre = _txt(d.get("nombre", base.get("nombre")))
    documento = _txt(d.get("documento", base.get("documento")))
    telefono = _txt(d.get("telefono", base.get("telefono"))) or None
    email = _txt(d.get("email", base.get("email"))) or None
    if not nombre:
        raise ReglaNegocio("El campo nombre es obligatorio")
    if not documento:
        raise ReglaNegocio("El campo documento es obligatorio")
    if email and not EMAIL_RE.match(email):
        raise ReglaNegocio("El campo email no tiene un formato válido")
    return nombre, documento, telefono, email


def registrar_cliente(con, d):
    nombre, documento, telefono, email = _datos_cliente(d)
    if repo.cliente_por_documento(con, documento):
        raise ReglaNegocio("Ya existe un cliente con ese documento", 409)
    try:
        cliente_id = repo.crear_cliente(con, nombre, documento, telefono, email)
        con.commit()
    except sqlite3.IntegrityError:
        con.rollback()
        raise ReglaNegocio("Ya existe un cliente con ese documento", 409)
    return dict(repo.cliente_por_id(con, cliente_id))


def listar_clientes(con, q=None):
    return [dict(c) for c in repo.listar_clientes(con, _txt(q) or None)]


def obtener_cliente(con, cliente_id):
    cliente = repo.cliente_por_id(con, cliente_id)
    if not cliente:
        raise ReglaNegocio("El cliente no existe", 404)
    return cliente


def modificar_cliente(con, cliente_id, d):
    actual = obtener_cliente(con, cliente_id)
    nombre, documento, telefono, email = _datos_cliente(d, actual)
    otro = repo.cliente_por_documento(con, documento)
    if otro and otro["id"] != actual["id"]:
        raise ReglaNegocio("Ya existe otro cliente con ese documento", 409)
    try:
        repo.actualizar_cliente(con, actual["id"], nombre, documento, telefono, email)
        con.commit()
    except sqlite3.IntegrityError:
        con.rollback()
        raise ReglaNegocio("Ya existe otro cliente con ese documento", 409)
    return dict(repo.cliente_por_id(con, actual["id"]))


def vehiculos_y_mensualidad(con, cliente_id):
    cliente = obtener_cliente(con, cliente_id)
    vehiculos = [dict(v, dentro=bool(v["dentro"])) for v in repo.listar_vehiculos(con, cliente["id"])]
    mens = repo.mensualidad_vigente_detalle(con, cliente["id"], _hoy())
    return {"cliente": dict(cliente), "vehiculos": vehiculos,
            "mensualidad": dict(mens) if mens else None}


def eliminar_cliente(con, cliente_id):
    cliente = obtener_cliente(con, cliente_id)
    if repo.total_movimientos_cliente(con, cliente["id"]):
        raise ReglaNegocio("No se puede eliminar: el cliente tiene movimientos registrados", 409)
    if repo.mensualidad_vigente_detalle(con, cliente["id"], _hoy()):
        raise ReglaNegocio("No se puede eliminar: el cliente tiene una mensualidad vigente", 409)
    if repo.total_mensualidades_cliente(con, cliente["id"]):
        raise ReglaNegocio("No se puede eliminar: el cliente tiene mensualidades en su historial", 409)
    repo.eliminar_cliente(con, cliente["id"])
    con.commit()


# ===================== Iteración 2: vehículos (RF-16 a RF-19) =====================
def registrar_vehiculo(con, d):
    placa = normalizar_placa(d.get("placa"))
    tipo = _tipo(d.get("tipo"))
    if d.get("cliente_id") in (None, ""):
        raise ReglaNegocio("El campo cliente_id es obligatorio")
    if not repo.cliente_por_id(con, d.get("cliente_id")):
        raise ReglaNegocio("El cliente no existe", 404)
    if repo.vehiculo_por_placa(con, placa):
        raise ReglaNegocio("Ya existe un vehículo con esa placa", 409)
    cliente_id = repo.cliente_por_id(con, d.get("cliente_id"))["id"]
    try:
        repo.crear_vehiculo(con, placa, tipo, _txt(d.get("marca")) or None,
                            _txt(d.get("color")) or None, cliente_id)
        con.commit()
    except sqlite3.IntegrityError:
        con.rollback()
        raise ReglaNegocio("Ya existe un vehículo con esa placa", 409)
    return dict(repo.vehiculo_por_placa(con, placa))


def listar_vehiculos(con, cliente_id=None):
    return [dict(v, dentro=bool(v["dentro"])) for v in repo.listar_vehiculos(con, cliente_id or None)]


def modificar_vehiculo(con, placa, d):
    placa = normalizar_placa(placa)
    actual = repo.vehiculo_por_placa(con, placa)
    if not actual:
        raise ReglaNegocio("El vehículo no existe", 404)
    tipo = _tipo(d.get("tipo", actual["tipo"]))
    marca = _txt(d.get("marca", actual["marca"])) or None
    color = _txt(d.get("color", actual["color"])) or None
    dueno = repo.cliente_por_id(con, d.get("cliente_id", actual["cliente_id"]))
    if not dueno:
        raise ReglaNegocio("El cliente no existe", 404)
    if tipo != actual["tipo"]:
        if repo.movimiento_en_curso(con, placa):
            raise ReglaNegocio("No se puede cambiar el tipo mientras el vehículo está dentro del parqueadero", 409)
        mens = repo.mensualidad_vigente_detalle(con, dueno["id"], _hoy())
        if mens and mens["celda_id"]:
            celda = repo.celda_por_id(con, mens["celda_id"])
            if celda["tipo"] != tipo:
                raise ReglaNegocio("La celda asignada a la mensualidad no corresponde al nuevo tipo", 409)
    repo.actualizar_vehiculo(con, placa, tipo, marca, color, dueno["id"])
    con.commit()
    return dict(repo.vehiculo_por_placa(con, placa))


def eliminar_vehiculo(con, placa):
    placa = normalizar_placa(placa)
    vehiculo = repo.vehiculo_por_placa(con, placa)
    if not vehiculo:
        raise ReglaNegocio("El vehículo no existe", 404)
    if repo.total_movimientos_placa(con, placa):
        raise ReglaNegocio("No se puede eliminar: el vehículo tiene movimientos registrados", 409)
    if repo.mensualidad_vigente_detalle(con, vehiculo["cliente_id"], _hoy()):
        raise ReglaNegocio("No se puede eliminar: el propietario tiene una mensualidad vigente", 409)
    repo.eliminar_vehiculo(con, placa)
    con.commit()


# ===================== Iteración 2: cuentas de operador (RF-20 a RF-22) =====================
def _publico(op):
    return {"id": op["id"], "nombre": op["nombre"], "usuario": op["usuario"], "rol": op["rol"],
            "activo": bool(op["activo"]), "creado_en": op["creado_en"],
            "actualizado_en": op["actualizado_en"]}


def _validar_password(password):
    if len(password or "") < PASSWORD_MIN:
        raise ReglaNegocio(f"El campo contraseña debe tener al menos {PASSWORD_MIN} caracteres")


def _validar_rol(rol):
    if rol not in ROLES:
        raise ReglaNegocio("El campo rol debe ser 'administrador' u 'operador'")


def listar_operadores(con):
    return [_publico(o) for o in repo.listar_operadores(con)]


def crear_operador(con, d, admin_id):
    nombre, usuario = _txt(d.get("nombre")), _txt(d.get("usuario"))
    rol = _txt(d.get("rol")) or "operador"
    if not nombre:
        raise ReglaNegocio("El campo nombre es obligatorio")
    if not usuario:
        raise ReglaNegocio("El campo usuario es obligatorio")
    _validar_password(d.get("password"))
    _validar_rol(rol)
    if repo.usuario_existe(con, usuario):
        raise ReglaNegocio("Ya existe una cuenta con ese usuario", 409)
    try:
        op_id = repo.crear_operador(con, nombre, usuario, generate_password_hash(d["password"]), rol, admin_id)
        con.commit()
    except sqlite3.IntegrityError:
        con.rollback()
        raise ReglaNegocio("Ya existe una cuenta con ese usuario", 409)
    return _publico(repo.operador_por_id(con, op_id))


def modificar_operador(con, operador_id, d, admin_id):
    actual = repo.operador_por_id(con, operador_id)
    if not actual:
        raise ReglaNegocio("La cuenta no existe", 404)
    nombre = _txt(d.get("nombre", actual["nombre"]))
    rol = _txt(d.get("rol", actual["rol"]))
    activo = d.get("activo", bool(actual["activo"]))
    if not nombre:
        raise ReglaNegocio("El campo nombre es obligatorio")
    _validar_rol(rol)
    if not isinstance(activo, (bool, int)):
        raise ReglaNegocio("El campo activo debe ser verdadero o falso")
    activo = 1 if activo else 0
    pierde_admin = rol != "administrador" or not activo
    if operador_id == admin_id and pierde_admin:
        raise ReglaNegocio("No puede desactivar su propia cuenta ni quitarse el rol de administrador", 409)
    if (actual["rol"] == "administrador" and actual["activo"] and pierde_admin
            and repo.total_administradores_activos(con) <= 1):
        raise ReglaNegocio("Debe existir al menos un administrador activo", 409)
    repo.actualizar_operador(con, operador_id, nombre, rol, activo, admin_id)
    con.commit()
    return _publico(repo.operador_por_id(con, operador_id))


def cambiar_password(con, operador_id, actual, nueva):
    op = repo.operador_por_id(con, operador_id)
    if not op or not check_password_hash(op["password_hash"], actual or ""):
        raise ReglaNegocio("La contraseña actual es incorrecta")
    _validar_password(nueva)
    repo.actualizar_password(con, operador_id, generate_password_hash(nueva))
    con.commit()


# ===================== Iteración 2: celdas (RF-23 a RF-29) =====================
def registrar_celda(con, d, admin_id):
    codigo = _txt(d.get("codigo")).upper()
    if not codigo:
        raise ReglaNegocio("El campo codigo es obligatorio")
    tipo = _tipo(d.get("tipo"))
    if repo.celda_por_codigo(con, codigo):
        raise ReglaNegocio("Ya existe una celda con ese código", 409)
    try:
        celda_id = repo.crear_celda(con, codigo, tipo, admin_id)
        con.commit()
    except sqlite3.IntegrityError:
        con.rollback()
        raise ReglaNegocio("Ya existe una celda con ese código", 409)
    return dict(repo.celda_por_id(con, celda_id))


def _celda(con, celda_id):
    celda = repo.celda_por_id(con, celda_id)
    if not celda:
        raise ReglaNegocio("La celda no existe", 404)
    return celda


def listar_celdas(con, tipo=None, estado=None):
    return [dict(c) for c in repo.listar_celdas(con, _txt(tipo) or None, _txt(estado) or None)]


def modificar_celda(con, celda_id, d, admin_id):
    actual = _celda(con, celda_id)
    codigo = _txt(d.get("codigo", actual["codigo"])).upper()
    tipo = _tipo(d.get("tipo", actual["tipo"]))
    if not codigo:
        raise ReglaNegocio("El campo codigo es obligatorio")
    otra = repo.celda_por_codigo(con, codigo)
    if otra and otra["id"] != actual["id"]:
        raise ReglaNegocio("Ya existe otra celda con ese código", 409)
    if tipo != actual["tipo"]:
        if actual["estado"] == "ocupada":
            raise ReglaNegocio("No se puede cambiar el tipo de una celda ocupada", 409)
        if repo.mensualidad_vigente_de_celda(con, actual["id"], _hoy()):
            raise ReglaNegocio("No se puede cambiar el tipo: la celda está asignada a una mensualidad vigente", 409)
    repo.actualizar_celda(con, actual["id"], codigo, tipo, admin_id)
    con.commit()
    return dict(repo.celda_por_id(con, actual["id"]))


def cambiar_estado_celda(con, celda_id, estado, admin_id):
    estado = _txt(estado).lower()
    if estado not in {"libre", "mantenimiento"}:
        raise ReglaNegocio("El campo estado debe ser 'libre' o 'mantenimiento'")
    celda = _celda(con, celda_id)
    if celda["estado"] == "ocupada":
        raise ReglaNegocio(f"La celda {celda['codigo']} está ocupada: registre primero la salida del vehículo", 409)
    if celda["estado"] != estado:
        repo.cambiar_estado_celda(con, celda["id"], estado, admin_id)
        con.commit()
    return dict(repo.celda_por_id(con, celda["id"]))


def eliminar_celda(con, celda_id):
    celda = _celda(con, celda_id)
    if repo.total_movimientos_celda(con, celda["id"]):
        raise ReglaNegocio("No se puede eliminar: la celda tiene movimientos registrados", 409)
    if repo.total_mensualidades_celda(con, celda["id"]):
        raise ReglaNegocio("No se puede eliminar: la celda tiene mensualidades asociadas", 409)
    repo.eliminar_celda(con, celda["id"])
    con.commit()


def asignar_celda(con, mensualidad_id, celda_id):
    mens = repo.mensualidad_por_id(con, mensualidad_id)
    if not mens:
        raise ReglaNegocio("La mensualidad no existe", 404)
    hoy = _hoy()
    if mens["estado"] != "vigente" or mens["fecha_fin"] < hoy:
        raise ReglaNegocio("Solo se puede asignar celda a una mensualidad vigente", 409)
    if celda_id in (None, ""):
        raise ReglaNegocio("El campo celda_id es obligatorio")
    celda = _celda(con, celda_id)
    vehiculos = repo.listar_vehiculos(con, mens["cliente_id"])
    if any(v["tipo"] != celda["tipo"] for v in vehiculos):
        raise ReglaNegocio("La celda no corresponde al tipo de los vehículos del cliente")
    if repo.mensualidad_vigente_de_celda(con, celda["id"], hoy, excepto_id=mens["id"]):
        raise ReglaNegocio("La celda ya está asignada a otra mensualidad vigente", 409)
    if mens["celda_id"] != celda["id"] and repo.total_dentro_cliente(con, mens["cliente_id"]):
        raise ReglaNegocio("No se puede reasignar la celda mientras un vehículo del cliente esté dentro del parqueadero", 409)
    repo.asignar_celda_mensualidad(con, mens["id"], celda["id"])
    con.commit()
    return {"mensualidad_id": mens["id"], "celda_id": celda["id"], "celda": celda["codigo"]}


def resumen_celdas(con):
    estados = {"libre": 0, "ocupada": 0, "mantenimiento": 0}
    por_tipo = {t: dict(estados, total=0) for t in sorted(TIPOS_VEHICULO)}
    por_estado = dict(estados)
    for fila in repo.resumen_celdas(con):
        por_estado[fila["estado"]] += fila["n"]
        por_tipo[fila["tipo"]][fila["estado"]] += fila["n"]
        por_tipo[fila["tipo"]]["total"] += fila["n"]
    return {"total": sum(por_estado.values()), "por_estado": por_estado, "por_tipo": por_tipo}
