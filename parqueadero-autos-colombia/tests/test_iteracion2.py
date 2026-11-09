"""Pruebas de la Iteración 2: gestión de usuarios y gestión de celdas."""
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app import create_app


class Base(unittest.TestCase):
    def setUp(self):
        self.ruta = str(Path(tempfile.mkdtemp()) / "test.db")
        self.app = create_app(self.ruta)
        self.admin = self.sesion("admin", "admin1234")

    def sesion(self, usuario, password):
        c = self.app.test_client()
        c.post("/api/login", json={"usuario": usuario, "password": password})
        return c

    def sql(self, consulta, args=()):
        con = sqlite3.connect(self.ruta)
        con.execute("PRAGMA foreign_keys = ON")
        cur = con.execute(consulta, args)
        con.commit()
        con.close()
        return cur.lastrowid

    def cliente_con_vehiculo(self, doc, placa, tipo="carro", mensualidad=True):
        cid = self.admin.post("/api/clientes", json={"nombre": "Cliente " + doc, "documento": doc}).json["id"]
        self.admin.post("/api/vehiculos", json={"placa": placa, "tipo": tipo, "cliente_id": cid})
        mid = None
        if mensualidad:
            hoy = date.today()
            mid = self.sql(
                "INSERT INTO mensualidad(cliente_id,fecha_inicio,fecha_fin,valor,estado) VALUES (?,?,?,?,?)",
                (cid, (hoy - timedelta(days=2)).isoformat(), (hoy + timedelta(days=20)).isoformat(), 100000, "vigente"))
        return cid, mid


class Permisos(Base):
    def test_sin_sesion_401(self):
        c = self.app.test_client()
        for url in ("/api/clientes", "/api/operadores", "/api/celdas/resumen"):
            self.assertEqual(c.get(url).status_code, 401)

    def test_operador_recibe_403_en_funciones_de_administrador(self):
        op = self.sesion("operador", "1234")
        self.assertEqual(op.get("/api/clientes").status_code, 403)
        self.assertEqual(op.post("/api/celdas", json={"codigo": "Z1", "tipo": "carro"}).status_code, 403)
        self.assertEqual(op.get("/api/operadores").status_code, 403)
        self.assertEqual(op.put("/api/celdas/1/estado", json={"estado": "mantenimiento"}).status_code, 403)

    def test_operador_sigue_usando_porteria_y_consultas_de_celdas(self):
        op = self.sesion("operador", "1234")
        self.assertEqual(op.post("/api/entradas", json={"placa": "ABC123"}).status_code, 201)
        self.assertEqual(op.get("/api/celdas?tipo=moto").status_code, 200)
        self.assertEqual(op.get("/api/celdas/resumen").status_code, 200)

    def test_administrador_hereda_funciones_del_operador(self):
        self.assertEqual(self.admin.post("/api/entradas", json={"placa": "ABC123"}).status_code, 201)

    def test_login_devuelve_rol(self):
        r = self.app.test_client().post("/api/login", json={"usuario": "admin", "password": "admin1234"})
        self.assertEqual(r.json["rol"], "administrador")


class Clientes(Base):
    def test_registrar_buscar_y_modificar(self):
        r = self.admin.post("/api/clientes", json={"nombre": "Marta Díaz", "documento": "2001", "email": "marta@mail.com"})
        self.assertEqual(r.status_code, 201)
        cid = r.json["id"]
        self.assertEqual(len(self.admin.get("/api/clientes?q=Marta").json), 1)
        self.assertEqual(len(self.admin.get("/api/clientes?q=2001").json), 1)
        self.assertEqual(self.admin.get("/api/clientes?q=zzzz").json, [])
        r = self.admin.put(f"/api/clientes/{cid}", json={"telefono": "3110000000"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json["telefono"], "3110000000")
        self.assertEqual(r.json["nombre"], "Marta Díaz")

    def test_validaciones(self):
        self.assertEqual(self.admin.post("/api/clientes", json={"documento": "1"}).status_code, 400)
        self.assertEqual(self.admin.post("/api/clientes", json={"nombre": "X"}).status_code, 400)
        r = self.admin.post("/api/clientes", json={"nombre": "X", "documento": "9", "email": "malo"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("email", r.json["error"])

    def test_documento_duplicado(self):
        self.assertEqual(self.admin.post("/api/clientes", json={"nombre": "Otro", "documento": "1001"}).status_code, 409)
        cid = self.admin.post("/api/clientes", json={"nombre": "Nuevo", "documento": "3001"}).json["id"]
        self.assertEqual(self.admin.put(f"/api/clientes/{cid}", json={"documento": "1001"}).status_code, 409)

    def test_cliente_inexistente(self):
        self.assertEqual(self.admin.put("/api/clientes/999", json={"nombre": "X"}).status_code, 404)
        self.assertEqual(self.admin.delete("/api/clientes/999").status_code, 404)

    def test_vehiculos_y_mensualidad_del_cliente(self):
        r = self.admin.get("/api/clientes/1/vehiculos").json
        self.assertEqual(r["vehiculos"][0]["placa"], "ABC123")
        self.assertEqual(r["mensualidad"]["celda"], "A1")
        self.assertIsNone(self.admin.get("/api/clientes/2/vehiculos").json["mensualidad"])

    def test_eliminar_sin_historial_y_con_historial(self):
        cid, _ = self.cliente_con_vehiculo("4001", "QWE123", mensualidad=False)
        self.assertEqual(self.admin.delete(f"/api/clientes/{cid}").status_code, 200)
        self.assertEqual(self.admin.get(f"/api/clientes/{cid}").status_code, 404)
        r = self.admin.delete("/api/clientes/1")
        self.assertEqual(r.status_code, 409)

    def test_no_elimina_cliente_con_movimientos(self):
        cid, _ = self.cliente_con_vehiculo("4002", "RTY123", mensualidad=False)
        self.sql("INSERT INTO movimiento(placa,celda_id,operador_entrada_id,fecha_entrada,estado,fecha_salida) "
                 "VALUES ('RTY123',1,1,'2026-01-01T08:00:00','finalizado','2026-01-01T09:00:00')")
        r = self.admin.delete(f"/api/clientes/{cid}")
        self.assertEqual(r.status_code, 409)
        self.assertIn("movimientos", r.json["error"])


class Vehiculos(Base):
    def test_registrar_y_usar_en_entrada(self):
        cid, _ = self.cliente_con_vehiculo("5001", "mno-123")
        self.assertEqual(self.admin.get(f"/api/vehiculos?cliente_id={cid}").json[0]["placa"], "MNO123")
        # sin celda asignada la entrada se rechaza; se asigna y luego funciona
        self.assertEqual(self.admin.post("/api/entradas", json={"placa": "MNO123"}).status_code, 404)

    def test_validaciones(self):
        post = lambda **d: self.admin.post("/api/vehiculos", json=d).status_code
        self.assertEqual(post(placa="12", tipo="carro", cliente_id=1), 400)
        self.assertEqual(post(placa="AAA111", tipo="bus", cliente_id=1), 400)
        self.assertEqual(post(placa="AAA111", tipo="carro"), 400)
        self.assertEqual(post(placa="AAA111", tipo="carro", cliente_id=999), 404)
        self.assertEqual(post(placa="ABC123", tipo="carro", cliente_id=1), 409)
        self.assertEqual(post(placa="AAA111", tipo="carro", cliente_id=1), 201)

    def test_modificar_y_placa_bloqueada(self):
        r = self.admin.put("/api/vehiculos/ABC123", json={"color": "Azul", "marca": "Kia", "placa": "ZZZ999"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json["color"], "Azul")
        self.assertEqual(r.json["placa"], "ABC123")

    def test_no_cambia_tipo_si_esta_dentro(self):
        self.admin.post("/api/entradas", json={"placa": "ABC123"})
        r = self.admin.put("/api/vehiculos/ABC123", json={"tipo": "moto"})
        self.assertEqual(r.status_code, 409)

    def test_no_cambia_tipo_si_la_celda_asignada_es_de_otro_tipo(self):
        self.assertEqual(self.admin.put("/api/vehiculos/ABC123", json={"tipo": "moto"}).status_code, 409)

    def test_eliminar_vehiculo(self):
        cid, _ = self.cliente_con_vehiculo("5002", "UIO123", mensualidad=False)
        self.assertEqual(self.admin.delete("/api/vehiculos/UIO123").status_code, 200)
        self.assertEqual(self.admin.delete("/api/vehiculos/UIO123").status_code, 404)
        self.assertEqual(self.admin.delete("/api/vehiculos/ABC123").status_code, 409)


class Operadores(Base):
    def test_crear_y_listar_sin_hash(self):
        r = self.admin.post("/api/operadores", json={"nombre": "Pedro", "usuario": "pedro", "password": "clave1234"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json["rol"], "operador")
        self.assertNotIn("password_hash", r.json)
        for o in self.admin.get("/api/operadores").json:
            self.assertNotIn("password_hash", o)

    def test_validaciones(self):
        post = lambda **d: self.admin.post("/api/operadores", json=d).status_code
        self.assertEqual(post(nombre="A", usuario="a", password="corta"), 400)
        self.assertEqual(post(nombre="A", usuario="a", password="clave1234", rol="jefe"), 400)
        self.assertEqual(post(usuario="a", password="clave1234"), 400)
        self.assertEqual(post(nombre="A", usuario="operador", password="clave1234"), 409)

    def test_cuenta_desactivada_no_inicia_sesion(self):
        oid = self.admin.post("/api/operadores", json={"nombre": "Ana", "usuario": "ana", "password": "clave1234"}).json["id"]
        self.assertEqual(self.app.test_client().post("/api/login", json={"usuario": "ana", "password": "clave1234"}).status_code, 200)
        r = self.admin.put(f"/api/operadores/{oid}", json={"activo": False})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.app.test_client().post("/api/login", json={"usuario": "ana", "password": "clave1234"}).status_code, 401)

    def test_cambiar_rol(self):
        oid = self.admin.post("/api/operadores", json={"nombre": "Eva", "usuario": "eva", "password": "clave1234"}).json["id"]
        self.admin.put(f"/api/operadores/{oid}", json={"rol": "administrador"})
        eva = self.sesion("eva", "clave1234")
        self.assertEqual(eva.get("/api/clientes").status_code, 200)

    def test_no_puede_desactivarse_a_si_mismo(self):
        admin_id = [o for o in self.admin.get("/api/operadores").json if o["usuario"] == "admin"][0]["id"]
        self.assertEqual(self.admin.put(f"/api/operadores/{admin_id}", json={"activo": False}).status_code, 409)
        self.assertEqual(self.admin.put(f"/api/operadores/{admin_id}", json={"rol": "operador"}).status_code, 409)

    def test_cambiar_password(self):
        c = self.sesion("operador", "1234")
        self.assertEqual(c.post("/api/cambiar-password", json={"actual": "mala", "nueva": "nueva1234"}).status_code, 400)
        self.assertEqual(c.post("/api/cambiar-password", json={"actual": "1234", "nueva": "corta"}).status_code, 400)
        self.assertEqual(c.post("/api/cambiar-password", json={"actual": "1234", "nueva": "nueva1234"}).status_code, 200)
        self.assertEqual(self.app.test_client().post("/api/login", json={"usuario": "operador", "password": "1234"}).status_code, 401)
        self.assertEqual(self.app.test_client().post("/api/login", json={"usuario": "operador", "password": "nueva1234"}).status_code, 200)


class Celdas(Base):
    def test_registrar_celda(self):
        r = self.admin.post("/api/celdas", json={"codigo": "b1", "tipo": "carro"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json["codigo"], "B1")
        self.assertEqual(r.json["estado"], "libre")
        self.assertEqual(self.admin.post("/api/celdas", json={"codigo": "B1", "tipo": "carro"}).status_code, 409)
        self.assertEqual(self.admin.post("/api/celdas", json={"codigo": "B2", "tipo": "avion"}).status_code, 400)
        self.assertEqual(self.admin.post("/api/celdas", json={"tipo": "carro"}).status_code, 400)

    def test_filtros_y_vehiculo_que_ocupa(self):
        self.admin.post("/api/entradas", json={"placa": "ABC123"})
        motos = self.admin.get("/api/celdas?tipo=moto").json
        self.assertEqual({c["tipo"] for c in motos}, {"moto"})
        ocupadas = self.admin.get("/api/celdas?estado=ocupada").json
        self.assertEqual([(c["codigo"], c["placa"]) for c in ocupadas], [("A1", "ABC123")])
        self.assertEqual(self.admin.get("/api/celdas?tipo=carro&estado=ocupada").json, ocupadas)
        self.assertEqual(self.admin.get("/api/celdas?tipo=moto&estado=ocupada").json, [])

    def test_resumen_coincide_con_la_lista(self):
        self.admin.post("/api/entradas", json={"placa": "ABC123"})
        r = self.admin.get("/api/celdas/resumen").json
        lista = self.admin.get("/api/celdas").json
        self.assertEqual(r["total"], len(lista))
        self.assertEqual(r["por_estado"]["ocupada"], 1)
        self.assertEqual(r["por_tipo"]["carro"]["total"], 6)
        self.assertEqual(r["por_tipo"]["moto"]["total"], 3)
        self.assertEqual(sum(r["por_estado"].values()), r["total"])

    def test_mantenimiento(self):
        self.assertEqual(self.admin.put("/api/celdas/1/estado", json={"estado": "mantenimiento"}).status_code, 200)
        r = self.admin.post("/api/entradas", json={"placa": "ABC123"})
        self.assertEqual(r.status_code, 409)  # la celda en mantenimiento no recibe entradas
        self.assertEqual(self.admin.put("/api/celdas/1/estado", json={"estado": "libre"}).status_code, 200)
        self.assertEqual(self.admin.post("/api/entradas", json={"placa": "ABC123"}).status_code, 201)

    def test_no_mantenimiento_si_ocupada(self):
        self.admin.post("/api/entradas", json={"placa": "ABC123"})
        self.assertEqual(self.admin.put("/api/celdas/1/estado", json={"estado": "mantenimiento"}).status_code, 409)
        self.assertEqual(self.admin.put("/api/celdas/1/estado", json={"estado": "libre"}).status_code, 409)
        self.assertEqual(self.admin.put("/api/celdas/1/estado", json={"estado": "ocupada"}).status_code, 400)

    def test_cambio_de_estado_queda_auditado(self):
        self.admin.put("/api/celdas/3/estado", json={"estado": "mantenimiento"})
        c = [x for x in self.admin.get("/api/celdas").json if x["id"] == 3][0]
        self.assertIsNotNone(c["actualizado_por"])
        self.assertIsNotNone(c["actualizado_en"])

    def test_modificar_celda(self):
        nueva = self.admin.post("/api/celdas", json={"codigo": "C1", "tipo": "carro"}).json["id"]
        r = self.admin.put(f"/api/celdas/{nueva}", json={"tipo": "moto"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json["tipo"], "moto")
        self.assertEqual(self.admin.put(f"/api/celdas/{nueva}", json={"codigo": "A1"}).status_code, 409)
        # A1 está asignada a una mensualidad vigente: no se cambia su tipo
        self.assertEqual(self.admin.put("/api/celdas/1", json={"tipo": "moto"}).status_code, 409)
        # ocupada: tampoco
        self.admin.post("/api/entradas", json={"placa": "ABC123"})
        self.assertEqual(self.admin.put("/api/celdas/1", json={"tipo": "moto"}).status_code, 409)

    def test_eliminar_celda(self):
        nueva = self.admin.post("/api/celdas", json={"codigo": "D1", "tipo": "carro"}).json["id"]
        self.assertEqual(self.admin.delete(f"/api/celdas/{nueva}").status_code, 200)
        self.assertEqual(self.admin.delete(f"/api/celdas/{nueva}").status_code, 404)
        self.assertEqual(self.admin.delete("/api/celdas/1").status_code, 409)  # tiene mensualidad
        self.admin.post("/api/entradas", json={"placa": "XYZ78A"})
        self.admin.post("/api/salidas", json={"placa": "XYZ78A"})
        libre_con_historial = [c for c in self.admin.get("/api/celdas").json if c["codigo"] == "M1"][0]["id"]
        self.assertEqual(self.admin.delete(f"/api/celdas/{libre_con_historial}").status_code, 409)


class AsignarCelda(Base):
    def test_asignar_y_usar_en_la_entrada(self):
        _, mid = self.cliente_con_vehiculo("6001", "ASD123")
        nueva = self.admin.post("/api/celdas", json={"codigo": "E1", "tipo": "carro"}).json["id"]
        r = self.admin.put(f"/api/mensualidades/{mid}/celda", json={"celda_id": nueva})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json["celda"], "E1")
        self.assertEqual(self.admin.post("/api/entradas", json={"placa": "ASD123"}).json["celda"], "E1")

    def test_tipo_incompatible(self):
        _, mid = self.cliente_con_vehiculo("6002", "FGH123")
        moto = [c for c in self.admin.get("/api/celdas?tipo=moto").json][1]["id"]
        self.assertEqual(self.admin.put(f"/api/mensualidades/{mid}/celda", json={"celda_id": moto}).status_code, 400)

    def test_celda_ya_asignada_a_otra_mensualidad(self):
        _, mid = self.cliente_con_vehiculo("6003", "JKL123")
        self.assertEqual(self.admin.put(f"/api/mensualidades/{mid}/celda", json={"celda_id": 1}).status_code, 409)

    def test_mensualidad_no_vigente_o_inexistente(self):
        self.assertEqual(self.admin.put("/api/mensualidades/2/celda", json={"celda_id": 3}).status_code, 409)
        self.assertEqual(self.admin.put("/api/mensualidades/999/celda", json={"celda_id": 3}).status_code, 404)
        self.assertEqual(self.admin.put("/api/mensualidades/1/celda", json={"celda_id": 999}).status_code, 404)
        self.assertEqual(self.admin.put("/api/mensualidades/1/celda", json={}).status_code, 400)

    def test_no_reasigna_si_el_vehiculo_esta_dentro(self):
        self.admin.post("/api/entradas", json={"placa": "ABC123"})
        self.assertEqual(self.admin.put("/api/mensualidades/1/celda", json={"celda_id": 3}).status_code, 409)

    def test_reasignar_cambia_la_celda_de_la_proxima_entrada(self):
        self.assertEqual(self.admin.put("/api/mensualidades/1/celda", json={"celda_id": 3}).status_code, 200)
        self.assertEqual(self.admin.post("/api/entradas", json={"placa": "ABC123"}).json["celda"], "A3")


class Migracion(unittest.TestCase):
    def test_base_de_la_iteracion_1_se_actualiza_sin_perder_datos(self):
        ruta = str(Path(tempfile.mkdtemp()) / "vieja.db")
        con = sqlite3.connect(ruta)
        con.executescript("""
            CREATE TABLE operador (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL,
                usuario TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
                activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0,1)));
            CREATE TABLE celda (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT NOT NULL UNIQUE,
                tipo TEXT NOT NULL CHECK (tipo IN ('carro','moto')),
                estado TEXT NOT NULL DEFAULT 'libre' CHECK (estado IN ('libre','ocupada','mantenimiento')));
            INSERT INTO operador(nombre,usuario,password_hash) VALUES ('Viejo','viejo','x');
            INSERT INTO celda(codigo,tipo) VALUES ('A1','carro');
        """)
        con.commit(); con.close()
        app = create_app(ruta)
        con = sqlite3.connect(ruta)
        usuarios = {r[0]: r[1] for r in con.execute("SELECT usuario, rol FROM operador")}
        self.assertEqual(usuarios["viejo"], "operador")
        self.assertEqual(usuarios["admin"], "administrador")
        self.assertEqual(con.execute("SELECT codigo FROM celda").fetchone()[0], "A1")
        con.close()


if __name__ == "__main__":
    unittest.main()
