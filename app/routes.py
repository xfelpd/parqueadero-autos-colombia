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
    return jsonify(nombre=op["nombre"])


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
    return jsonify([dict(r) for r in repo.listar_celdas(con())])
