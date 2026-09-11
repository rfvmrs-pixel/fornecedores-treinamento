"""Camada de acesso ao banco de dados (SQLite puro, sem ORM)."""
import sqlite3
from pathlib import Path

import click
from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    schema_path = Path(__file__).parent / "schema.sql"
    with open(schema_path, "r", encoding="utf-8") as f:
        db.executescript(f.read())
    db.commit()


@click.command("init-db")
def init_db_command():
    """Apaga os dados existentes e recria as tabelas."""
    init_db()
    click.echo("Banco de dados inicializado.")


@click.command("seed-db")
def seed_db_command():
    """Popula o banco com categorias, procedimentos e as perguntas oficiais da prova."""
    from . import seed

    seed.run()
    click.echo("Banco de dados populado com dados iniciais.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(seed_db_command)
