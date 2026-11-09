"""Capa de presentación: API REST + página principal."""
from functools import wraps

from flask import Blueprint, current_app, jsonify, render_template, request, session
from werkzeug.security import check_password_hash

from . import db, repositories as repo, services

bp = Blueprint("api", __name__)


def con():
    return db.connect(current_app.config["DATABASE"])


def requiere_login(f):
    @wraps(f)
    def inner(*a, **kw):
        if "operador_id" not in session:
            return jsonify(error="Debe iniciar sesión"), 401
        return f(*a, **kw)
    return inner


def requiere_admin(f):
    """Solo el rol administrador (RNF-10): sin sesión -> 401, operador -> 403."""
    @wraps(f)
    def inner(*a, **kw):
        if "operador_id" not in session:
            return jsonify(error="Debe iniciar sesión"), 401
        if session.get("rol") != "administrador":
            return jsonify(error="No tiene permisos para esta operación"), 403
        return f(*a, **kw)
    return inner


def cuerpo():
    return request.get_json(force=True, silent=True) or {}


@bp.errorhandler(services.ReglaNegocio)
def regla(e):
    return jsonify(error=str(e)), e.codigo


@bp.get("/")
def index():
    return render_template("index.html")


@bp.post("/api/login")
def login():
    d = request.get_json(force=True, silent=True) or {}
    c = con()
    op = repo.operador_por_usuario(c, d.get("usuario", ""))
    if not op or not check_password_hash(op["password_hash"], d.get("password", "")):
        return jsonify(error="Usuario o contraseña incorrectos"), 401
    session["operador_id"] = op["id"]
    session["rol"] = op["rol"]
    return jsonify(nombre=op["nombre"], rol=op["rol"])


@bp.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@bp.post("/api/entradas")
@requiere_login
def entrada():
    d = request.get_json(force=True, silent=True) or {}
    r = services.registrar_entrada(con(), d.get("placa"), session["operador_id"], d.get("celda_id"))
    return jsonify(r), 201


@bp.post("/api/salidas")
@requiere_login
def salida():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(services.registrar_salida(con(), d.get("placa"), session["operador_id"]))


@bp.post("/api/novedades")
@requiere_login
def novedad():
    d = request.get_json(force=True, silent=True) or {}
    r = services.registrar_novedad(con(), d.get("placa"), session["operador_id"],
                                   d.get("tipo"), d.get("descripcion"))
    return jsonify(r), 201


@bp.get("/api/movimientos/activos")
@requiere_login
def activos():
    return jsonify([dict(r) for r in repo.listar_activos(con())])


@bp.get("/api/movimientos")
@requiere_login
def historial():
    placa = request.args.get("placa")
    placa = services.normalizar_placa(placa) if placa else None
    rows = repo.historial(con(), placa, request.args.get("desde"), request.args.get("hasta"))
    return jsonify([dict(r) for r in rows])


@bp.get("/api/celdas")
@requiere_login
def celdas():
    return jsonify(services.listar_celdas(con(), request.args.get("tipo"), request.args.get("estado")))


# ===================== Iteración 2: gestión de usuarios =====================
@bp.post("/api/cambiar-password")
@requiere_login
def cambiar_password():
    d = cuerpo()
    services.cambiar_password(con(), session["operador_id"], d.get("actual"), d.get("nueva"))
    return jsonify(ok=True)


@bp.get("/api/clientes")
@requiere_admin
def clientes_listar():
    return jsonify(services.listar_clientes(con(), request.args.get("q")))


@bp.post("/api/clientes")
@requiere_admin
def clientes_crear():
    return jsonify(services.registrar_cliente(con(), cuerpo())), 201


@bp.get("/api/clientes/<int:cliente_id>")
@requiere_admin
def clientes_obtener(cliente_id):
    return jsonify(dict(services.obtener_cliente(con(), cliente_id)))


@bp.put("/api/clientes/<int:cliente_id>")
@requiere_admin
def clientes_modificar(cliente_id):
    return jsonify(services.modificar_cliente(con(), cliente_id, cuerpo()))


@bp.delete("/api/clientes/<int:cliente_id>")
@requiere_admin
def clientes_eliminar(cliente_id):
    services.eliminar_cliente(con(), cliente_id)
    return jsonify(ok=True)


@bp.get("/api/clientes/<int:cliente_id>/vehiculos")
@requiere_admin
def clientes_vehiculos(cliente_id):
    return jsonify(services.vehiculos_y_mensualidad(con(), cliente_id))


@bp.get("/api/vehiculos")
@requiere_admin
def vehiculos_listar():
    return jsonify(services.listar_vehiculos(con(), request.args.get("cliente_id", type=int)))


@bp.post("/api/vehiculos")
@requiere_admin
def vehiculos_crear():
    return jsonify(services.registrar_vehiculo(con(), cuerpo())), 201


@bp.put("/api/vehiculos/<placa>")
@requiere_admin
def vehiculos_modificar(placa):
    return jsonify(services.modificar_vehiculo(con(), placa, cuerpo()))


@bp.delete("/api/vehiculos/<placa>")
@requiere_admin
def vehiculos_eliminar(placa):
    services.eliminar_vehiculo(con(), placa)
    return jsonify(ok=True)


@bp.get("/api/operadores")
@requiere_admin
def operadores_listar():
    return jsonify(services.listar_operadores(con()))


@bp.post("/api/operadores")
@requiere_admin
def operadores_crear():
    return jsonify(services.crear_operador(con(), cuerpo(), session["operador_id"])), 201


@bp.put("/api/operadores/<int:operador_id>")
@requiere_admin
def operadores_modificar(operador_id):
    return jsonify(services.modificar_operador(con(), operador_id, cuerpo(), session["operador_id"]))


# ===================== Iteración 2: gestión de celdas =====================
@bp.get("/api/celdas/resumen")
@requiere_login
def celdas_resumen():
    return jsonify(services.resumen_celdas(con()))


@bp.post("/api/celdas")
@requiere_admin
def celdas_crear():
    return jsonify(services.registrar_celda(con(), cuerpo(), session["operador_id"])), 201


@bp.put("/api/celdas/<int:celda_id>")
@requiere_admin
def celdas_modificar(celda_id):
    return jsonify(services.modificar_celda(con(), celda_id, cuerpo(), session["operador_id"]))


@bp.put("/api/celdas/<int:celda_id>/estado")
@requiere_admin
def celdas_estado(celda_id):
    return jsonify(services.cambiar_estado_celda(con(), celda_id, cuerpo().get("estado"), session["operador_id"]))


@bp.delete("/api/celdas/<int:celda_id>")
@requiere_admin
def celdas_eliminar(celda_id):
    services.eliminar_celda(con(), celda_id)
    return jsonify(ok=True)


@bp.put("/api/mensualidades/<int:mensualidad_id>/celda")
@requiere_admin
def mensualidad_asignar_celda(mensualidad_id):
    return jsonify(services.asignar_celda(con(), mensualidad_id, cuerpo().get("celda_id")))
