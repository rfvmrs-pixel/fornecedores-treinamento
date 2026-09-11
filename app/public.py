"""Rotas públicas: acesso do fornecedor (login por categoria, cadastro,
treinamento e prova de Regras de Ouro)."""
import json
from datetime import datetime, timezone

from flask import (
    Blueprint, abort, current_app, flash, g, redirect, render_template,
    request, send_from_directory, session, url_for,
)
from werkzeug.security import check_password_hash

from .db import get_db
from .utils import (
    category_required, format_cpf, is_valid_cpf, only_digits, supplier_required,
)

bp = Blueprint("public", __name__)


@bp.route("/")
def index():
    if g.get("supplier"):
        return redirect(url_for("public.training"))
    if g.get("category"):
        return redirect(url_for("public.identify"))
    return redirect(url_for("public.login"))


@bp.route("/entrar", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        db = get_db()
        category = db.execute(
            "SELECT * FROM categories WHERE username = ? AND active = 1", (username,)
        ).fetchone()

        error = None
        if category is None or not check_password_hash(category["password_hash"], password):
            error = "Usuário ou senha da categoria inválidos."

        if error is None:
            session.clear()
            session["category_id"] = category["id"]
            return redirect(url_for("public.identify"))
        flash(error, "error")

    return render_template("public/login.html")


@bp.route("/sair")
def logout():
    session.clear()
    return redirect(url_for("public.login"))


@bp.route("/identificar", methods=("GET", "POST"))
@category_required
def identify():
    db = get_db()

    if request.method == "POST":
        nome = (request.form.get("nome") or "").strip()
        empresa = (request.form.get("empresa") or "").strip()
        funcao = (request.form.get("funcao") or "").strip()
        cpf_raw = request.form.get("cpf") or ""
        cpf = only_digits(cpf_raw)

        errors = []
        if not nome:
            errors.append("Informe seu nome completo.")
        if not empresa:
            errors.append("Informe o nome da empresa.")
        if not funcao:
            errors.append("Informe sua função.")
        if not is_valid_cpf(cpf):
            errors.append("CPF inválido. Verifique os números digitados.")

        if errors:
            for e in errors:
                flash(e, "error")
        else:
            existing = db.execute(
                "SELECT * FROM suppliers WHERE category_id = ? AND cpf = ?",
                (g.category["id"], cpf),
            ).fetchone()
            now = datetime.now(timezone.utc).isoformat()
            if existing:
                db.execute(
                    "UPDATE suppliers SET nome = ?, empresa = ?, funcao = ?, updated_at = ? "
                    "WHERE id = ?",
                    (nome, empresa, funcao, now, existing["id"]),
                )
                supplier_id = existing["id"]
            else:
                cur = db.execute(
                    "INSERT INTO suppliers (category_id, nome, empresa, funcao, cpf, "
                    "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (g.category["id"], nome, empresa, funcao, cpf, now, now),
                )
                supplier_id = cur.lastrowid
            db.commit()
            session["supplier_id"] = supplier_id
            return redirect(url_for("public.training"))

    return render_template("public/identify.html")


def _category_documents(db, category_id):
    """Retorna lista de procedimentos da categoria com os documentos vinculados."""
    procedures = db.execute(
        """
        SELECT p.id, p.code
        FROM procedures p
        JOIN category_procedures cp ON cp.procedure_id = p.id
        WHERE cp.category_id = ?
        ORDER BY p.code
        """,
        (category_id,),
    ).fetchall()

    result = []
    for proc in procedures:
        docs = db.execute(
            "SELECT * FROM documents WHERE procedure_id = ? ORDER BY uploaded_at DESC",
            (proc["id"],),
        ).fetchall()
        result.append({"procedure": proc, "documents": docs})
    return result


@bp.route("/treinamento", methods=("GET",))
@category_required
@supplier_required
def training():
    db = get_db()
    items = _category_documents(db, g.category["id"])

    read_rows = db.execute(
        "SELECT document_id FROM document_reads WHERE supplier_id = ?", (g.supplier["id"],)
    ).fetchall()
    read_ids = {r["document_id"] for r in read_rows}

    total_docs = sum(len(i["documents"]) for i in items)
    read_docs = sum(1 for i in items for d in i["documents"] if d["id"] in read_ids)
    all_read = total_docs > 0 and read_docs == total_docs

    if all_read and not g.supplier["training_confirmed_at"]:
        db.execute(
            "UPDATE suppliers SET training_confirmed_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), g.supplier["id"]),
        )
        db.commit()

    last_attempt = db.execute(
        "SELECT * FROM attempts WHERE supplier_id = ? ORDER BY finished_at DESC LIMIT 1",
        (g.supplier["id"],),
    ).fetchone()

    return render_template(
        "public/training.html",
        items=items,
        read_ids=read_ids,
        total_docs=total_docs,
        read_docs=read_docs,
        all_read=all_read,
        last_attempt=last_attempt,
    )


@bp.route("/treinamento/documento/<int:document_id>/lido", methods=("POST",))
@category_required
@supplier_required
def mark_read(document_id):
    db = get_db()
    doc = db.execute(
        """
        SELECT d.* FROM documents d
        JOIN category_procedures cp ON cp.procedure_id = d.procedure_id
        WHERE d.id = ? AND cp.category_id = ?
        """,
        (document_id, g.category["id"]),
    ).fetchone()
    if doc is None:
        abort(404)
    db.execute(
        "INSERT OR IGNORE INTO document_reads (supplier_id, document_id) VALUES (?, ?)",
        (g.supplier["id"], document_id),
    )
    db.commit()
    return redirect(url_for("public.training"))


@bp.route("/documentos/<path:filename>")
@category_required
@supplier_required
def serve_document(filename):
    db = get_db()
    doc = db.execute(
        """
        SELECT d.* FROM documents d
        JOIN category_procedures cp ON cp.procedure_id = d.procedure_id
        WHERE d.filename = ? AND cp.category_id = ?
        """,
        (filename, g.category["id"]),
    ).fetchone()
    if doc is None:
        abort(404)
    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"], filename, as_attachment=False,
        download_name=doc["original_filename"],
    )


@bp.route("/prova", methods=("GET",))
@category_required
@supplier_required
def exam():
    db = get_db()
    items = _category_documents(db, g.category["id"])
    total_docs = sum(len(i["documents"]) for i in items)

    if total_docs > 0 and not g.supplier["training_confirmed_at"]:
        flash("Conclua a leitura de todos os documentos de treinamento antes da prova.", "warning")
        return redirect(url_for("public.training"))

    questions = db.execute(
        "SELECT * FROM questions WHERE active = 1 ORDER BY order_index, id"
    ).fetchall()
    if not questions:
        flash("Ainda não há perguntas cadastradas para a prova. Contate o Admin.", "warning")
        return redirect(url_for("public.training"))

    started_at = datetime.now(timezone.utc).isoformat()
    return render_template("public/exam.html", questions=questions, started_at=started_at)


@bp.route("/prova", methods=("POST",))
@category_required
@supplier_required
def submit_exam():
    db = get_db()
    questions = db.execute(
        "SELECT * FROM questions WHERE active = 1 ORDER BY order_index, id"
    ).fetchall()
    if not questions:
        abort(400)

    started_at = request.form.get("started_at") or datetime.now(timezone.utc).isoformat()
    answers = {}
    score = 0
    for q in questions:
        given = request.form.get(f"q_{q['id']}")
        answers[str(q["id"])] = given
        if given == q["correct_option"]:
            score += 1

    total = len(questions)
    passed = 1 if score == total else 0  # aprovação exige 100% de acerto
    finished_at = datetime.now(timezone.utc).isoformat()

    cur = db.execute(
        "INSERT INTO attempts (supplier_id, category_id, score, total, passed, "
        "answers_json, started_at, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            g.supplier["id"], g.category["id"], score, total, passed,
            json.dumps(answers), started_at, finished_at,
        ),
    )
    db.commit()
    return redirect(url_for("public.result", attempt_id=cur.lastrowid))


@bp.route("/resultado/<int:attempt_id>")
@category_required
@supplier_required
def result(attempt_id):
    db = get_db()
    attempt = db.execute(
        "SELECT * FROM attempts WHERE id = ? AND supplier_id = ?",
        (attempt_id, g.supplier["id"]),
    ).fetchone()
    if attempt is None:
        abort(404)
    return render_template("public/result.html", attempt=attempt)


@bp.app_template_filter("cpf")
def cpf_filter(value):
    return format_cpf(value)


@bp.app_template_filter("datahora")
def datahora_filter(value):
    if not value:
        return "-"
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return value
    return dt.strftime("%d/%m/%Y %H:%M")
