"""Capa de lógica de negocio: reglas de entrada, salida y novedades."""
import re
import sqlite3
from datetime import date

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
