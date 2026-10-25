# Parqueadero "Autos Colombia" – Iteración 1: entrada y salida de vehículos

Sistema web (Flask + SQLite) organizado en capas: presentación (`routes.py`, `templates/`),
lógica de negocio (`services.py`) y acceso a datos (`repositories.py`, `db.py`, `schema.sql`).

## Ejecutar
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py            # http://127.0.0.1:5000  (usuario: operador / clave: 1234)
python -m unittest discover -s tests -v   # pruebas automáticas (también funciona con pytest)
```

## Endpoints principales
| Método | Ruta | Descripción |
|---|---|---|
| POST | /api/login, /api/logout | Sesión del operador |
| POST | /api/entradas | Registrar entrada `{placa, celda_id?}` |
| POST | /api/salidas | Registrar salida `{placa}` |
| POST | /api/novedades | Registrar novedad `{placa, tipo, descripcion}` |
| GET | /api/movimientos/activos | Vehículos dentro del parqueadero |
| GET | /api/movimientos | Historial (`placa`, `desde`, `hasta`) |
| GET | /api/celdas | Estado de las celdas |

Datos de demostración: placas `ABC123` (mensualidad vigente), `DEF456` (vencida), `XYZ78A` (moto, vigente).
