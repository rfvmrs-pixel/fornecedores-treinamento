import os
from pathlib import Path

from flask import Flask, g, render_template

from . import db as db_module
from . import utils


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    instance_path = Path(app.instance_path)
    instance_path.mkdir(parents=True, exist_ok=True)

    upload_folder = Path(app.root_path) / "uploads" / "procedimentos"
    upload_folder.mkdir(parents=True, exist_ok=True)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-change-me"),
        DATABASE=os.environ.get(
            "DATABASE_PATH", str(instance_path / "fornecedores.sqlite3")
        ),
        UPLOAD_FOLDER=str(upload_folder),
        MAX_CONTENT_LENGTH=25 * 1024 * 1024,  # 25 MB por upload
        EMPRESA_NOME=os.environ.get("EMPRESA_NOME", "Triunfo"),
    )

    if test_config is not None:
        app.config.from_mapping(test_config)

    db_module.init_app(app)

    @app.before_request
    def load_session_context():
        utils.load_logged_in_category()
        utils.load_logged_in_supplier()
        utils.load_logged_in_admin()

    @app.context_processor
    def inject_globals():
        return {
            "empresa_nome": app.config["EMPRESA_NOME"],
            "current_category": g.get("category"),
            "current_supplier": g.get("supplier"),
            "current_admin": g.get("admin"),
        }

    from . import public, admin

    app.register_blueprint(public.bp)
    app.register_blueprint(admin.bp)

    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    @app.cli.command("setup")
    def setup_command():
        """Inicializa e popula o banco em um único passo (uso: flask --app app setup)."""
        with app.app_context():
            db_module.init_db()
            from . import seed

            seed.run()
        print("Banco inicializado e populado com sucesso.")

    return app
