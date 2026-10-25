import os

from flask import Flask

from . import db
from .routes import bp


def create_app(database=None):
    app = Flask(__name__)
    app.config["DATABASE"] = database or os.environ.get("PARQUEADERO_DB", "parqueadero.db")
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "cambiar-en-produccion")
    con = db.connect(app.config["DATABASE"])
    db.init_db(con)
    db.seed_demo(con)
    con.close()
    app.register_blueprint(bp)
    return app
