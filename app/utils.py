"""Funções utilitárias: validação de CPF, decoradores de acesso, helpers."""
import functools
import re

from flask import flash, g, redirect, session, url_for

from .db import get_db


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def format_cpf(cpf: str) -> str:
    d = only_digits(cpf)
    if len(d) != 11:
        return cpf
    return f"{d[0:3]}.{d[3:6]}.{d[6:9]}-{d[9:11]}"


def is_valid_cpf(cpf: str) -> bool:
    """Validação de CPF pelo algoritmo oficial de dígitos verificadores."""
    d = only_digits(cpf)
    if len(d) != 11:
        return False
    if d == d[0] * 11:
        return False

    def calc_digit(digits, weight_start):
        total = sum(int(dig) * w for dig, w in zip(digits, range(weight_start, 1, -1)))
        resto = (total * 10) % 11
        return 0 if resto == 10 else resto

    digit1 = calc_digit(d[:9], 10)
    if digit1 != int(d[9]):
        return False
    digit2 = calc_digit(d[:10], 11)
    if digit2 != int(d[10]):
        return False
    return True


# ---------------------------------------------------------------------------
# Contexto de sessão: categoria (fornecedor em processo de login),
# fornecedor autenticado, admin autenticado.
# ---------------------------------------------------------------------------

def load_logged_in_category():
    category_id = session.get("category_id")
    g.category = None
    if category_id is not None:
        db = get_db()
        g.category = db.execute(
            "SELECT * FROM categories WHERE id = ? AND active = 1", (category_id,)
        ).fetchone()
        if g.category is None:
            session.pop("category_id", None)


def load_logged_in_supplier():
    supplier_id = session.get("supplier_id")
    g.supplier = None
    if supplier_id is not None:
        db = get_db()
        g.supplier = db.execute(
            "SELECT * FROM suppliers WHERE id = ?", (supplier_id,)
        ).fetchone()
        if g.supplier is None:
            session.pop("supplier_id", None)


def load_logged_in_admin():
    admin_id = session.get("admin_id")
    g.admin = None
    if admin_id is not None:
        db = get_db()
        g.admin = db.execute(
            "SELECT * FROM admin_users WHERE id = ?", (admin_id,)
        ).fetchone()
        if g.admin is None:
            session.pop("admin_id", None)


def category_required(view):
    @functools.wraps(view)
    def wrapped(**kwargs):
        if g.get("category") is None:
            flash("Faça login com o usuário e senha da sua categoria para continuar.", "warning")
            return redirect(url_for("public.login"))
        return view(**kwargs)

    return wrapped


def supplier_required(view):
    @functools.wraps(view)
    def wrapped(**kwargs):
        if g.get("supplier") is None:
            flash("Preencha seus dados para continuar.", "warning")
            return redirect(url_for("public.login"))
        return view(**kwargs)

    return wrapped


def admin_required(view):
    @functools.wraps(view)
    def wrapped(**kwargs):
        if g.get("admin") is None:
            return redirect(url_for("admin.login"))
        return view(**kwargs)

    return wrapped
