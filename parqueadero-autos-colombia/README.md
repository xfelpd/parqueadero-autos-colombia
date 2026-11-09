# Parqueadero "Autos Colombia"

Sistema web (Flask + SQLite) organizado en capas: presentación (`routes.py`, `templates/`),
lógica de negocio (`services.py`) y acceso a datos (`repositories.py`, `db.py`, `schema.sql`).

- **Iteración 1:** entrada y salida de vehículos, novedades, historial y estado de celdas.
- **Iteración 2:** gestión de usuarios (clientes, vehículos y cuentas del sistema con roles) y gestión de celdas.

## Ejecutar
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py            # http://127.0.0.1:5000
python -m unittest discover -s tests -v   # pruebas automáticas (también funciona con pytest)
```

Cuentas de demostración (cámbielas desde «Mi cuenta»):

| Rol | Usuario | Clave |
|---|---|---|
| Operador | `operador` | `1234` |
| Administrador | `admin` | `admin1234` |

Si ya tiene una base `parqueadero.db` de la Iteración 1, al iniciar la aplicación se agregan solas las
columnas nuevas (rol y auditoría) y se crea la cuenta `admin`; los datos existentes se conservan.

Datos de demostración: placas `ABC123` (mensualidad vigente), `DEF456` (vencida), `XYZ78A` (moto, vigente).

## Roles
- **Operador:** portería (entradas, salidas, novedades), consulta de celdas y cambio de su contraseña.
- **Administrador:** todo lo del operador, más la gestión de clientes, vehículos, cuentas y celdas.
  Un operador que llama a una función de administrador recibe `403`; sin sesión recibe `401`.

## Endpoints

### Iteración 1
| Método | Ruta | Descripción |
|---|---|---|
| POST | /api/login, /api/logout | Sesión (el login devuelve el rol) |
| POST | /api/entradas | Registrar entrada `{placa, celda_id?}` |
| POST | /api/salidas | Registrar salida `{placa}` |
| POST | /api/novedades | Registrar novedad `{placa, tipo, descripcion}` |
| GET | /api/movimientos/activos | Vehículos dentro del parqueadero |
| GET | /api/movimientos | Historial (`placa`, `desde`, `hasta`) |
| GET | /api/celdas | Estado de las celdas (ahora con filtros `tipo` y `estado` y el vehículo que la ocupa) |

### Iteración 2 – gestión de usuarios (administrador)
| Método | Ruta | Descripción | RF |
|---|---|---|---|
| GET, POST | /api/clientes | Buscar (`q`) y registrar clientes | RF-13, RF-14 |
| GET, PUT, DELETE | /api/clientes/{id} | Consultar, modificar y eliminar (con restricciones) | RF-15, RF-19 |
| GET | /api/clientes/{id}/vehiculos | Vehículos del cliente y su mensualidad vigente | RF-18 |
| GET, POST | /api/vehiculos | Listar (`cliente_id`) y registrar vehículos | RF-16 |
| PUT, DELETE | /api/vehiculos/{placa} | Modificar (la placa no cambia) y eliminar | RF-17, RF-19 |
| GET, POST | /api/operadores | Listar y crear cuentas | RF-20, RF-21 |
| PUT | /api/operadores/{id} | Cambiar nombre, rol o activar/desactivar | RF-20, RF-21 |
| POST | /api/cambiar-password | Cambiar la propia contraseña (cualquier rol) `{actual, nueva}` | RF-22 |

### Iteración 2 – gestión de celdas
| Método | Ruta | Descripción | RF |
|---|---|---|---|
| POST | /api/celdas | Registrar celda `{codigo, tipo}` (admin) | RF-23 |
| PUT | /api/celdas/{id} | Modificar código y tipo (admin) | RF-25 |
| PUT | /api/celdas/{id}/estado | `{estado: "mantenimiento" \| "libre"}` (admin) | RF-26 |
| DELETE | /api/celdas/{id} | Eliminar celda sin historial (admin) | RF-28 |
| PUT | /api/mensualidades/{id}/celda | Asignar o reasignar celda `{celda_id}` (admin) | RF-27 |
| GET | /api/celdas/resumen | Totales por estado y por tipo (cualquier rol) | RF-29 |
