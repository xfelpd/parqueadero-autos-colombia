import tempfile
import unittest
from pathlib import Path

from app import create_app


def nuevo_cliente(login=True):
    tmp = tempfile.mkdtemp()
    c = create_app(str(Path(tmp) / "test.db")).test_client()
    if login:
        c.post("/api/login", json={"usuario": "operador", "password": "1234"})
    return c


def estados(c):
    return {x["codigo"]: x["estado"] for x in c.get("/api/celdas").json}


class FlujoEntradaSalida(unittest.TestCase):
    def setUp(self):
        self.c = nuevo_cliente()

    def test_requiere_login(self):
        c = nuevo_cliente(login=False)
        self.assertEqual(c.post("/api/entradas", json={"placa": "ABC123"}).status_code, 401)

    def test_login_invalido(self):
        c = nuevo_cliente(login=False)
        r = c.post("/api/login", json={"usuario": "operador", "password": "x"})
        self.assertEqual(r.status_code, 401)

    def test_entrada_y_salida_ok(self):
        r = self.c.post("/api/entradas", json={"placa": "abc-123"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json["celda"], "A1")
        self.assertEqual(estados(self.c)["A1"], "ocupada")
        self.assertEqual(len(self.c.get("/api/movimientos/activos").json), 1)
        r = self.c.post("/api/salidas", json={"placa": "ABC123"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json["fecha_salida"])
        self.assertEqual(estados(self.c)["A1"], "libre")

    def test_entrada_duplicada(self):
        self.c.post("/api/entradas", json={"placa": "ABC123"})
        self.assertEqual(self.c.post("/api/entradas", json={"placa": "ABC123"}).status_code, 409)

    def test_mensualidad_vencida(self):
        self.assertEqual(self.c.post("/api/entradas", json={"placa": "DEF456"}).status_code, 403)

    def test_vehiculo_no_registrado_y_placa_invalida(self):
        self.assertEqual(self.c.post("/api/entradas", json={"placa": "ZZZ999"}).status_code, 404)
        self.assertEqual(self.c.post("/api/entradas", json={"placa": "12"}).status_code, 400)

    def test_salida_sin_entrada(self):
        self.assertEqual(self.c.post("/api/salidas", json={"placa": "ABC123"}).status_code, 404)

    def test_novedad_e_historial(self):
        self.c.post("/api/entradas", json={"placa": "XYZ78A"})
        ok = self.c.post("/api/novedades", json={"placa": "XYZ78A", "tipo": "daño", "descripcion": "Espejo roto"})
        self.assertEqual(ok.status_code, 201)
        vacia = self.c.post("/api/novedades", json={"placa": "XYZ78A", "tipo": "daño", "descripcion": " "})
        self.assertEqual(vacia.status_code, 400)
        h = self.c.get("/api/movimientos?placa=XYZ78A").json
        self.assertEqual(len(h), 1)
        self.assertEqual(h[0]["estado"], "en_curso")


if __name__ == "__main__":
    unittest.main()
