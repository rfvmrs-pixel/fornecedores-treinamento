"""Rotas do painel administrativo."""
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from flask import (
    Blueprint, current_app, flash, g, redirect, render_template, request,
    send_from_directory, session, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from .db import get_db
from .utils import admin_required, only_digits

bp = Blueprint("admin", __name__, url_prefix="/admin")

ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "ppt", "pptx", "jpg", "jpeg", "png"}


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------

@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        db = get_db()
        admin = db.execute(
            "SELECT * FROM admin_users WHERE username = ?", (username,)
        ).fetchone()
        if admin is None or not check_password_hash(admin["password_hash"], password):
            flash("Usuário ou senha inválidos.", "error")
        else:
            session.clear()
            session["admin_id"] = admin["id"]
            return redirect(url_for("admin.dashboard"))
    return render_template("admin/login.html")


@bp.route("/sair")
def logout():
    session.clear()
    return redirect(url_for("admin.login"))


@bp.route("/senha", methods=("GET", "POST"))
@admin_required
def change_password():
    if request.method == "POST":
        current = request.form.get("current_password") or ""
        new = request.form.get("new_password") or ""
        confirm = request.form.get("confirm_password") or ""
        db = get_db()
        if not check_password_hash(g.admin["password_hash"], current):
            flash("Senha atual incorreta.", "error")
        elif len(new) < 6:
            flash("A nova senha deve ter pelo menos 6 caracteres.", "error")
        elif new != confirm:
            flash("A confirmação de senha não confere.", "error")
        else:
            db.execute(
                "UPDATE admin_users SET password_hash = ? WHERE id = ?",
                (generate_password_hash(new), g.admin["id"]),
            )
            db.commit()
            flash("Senha atualizada com sucesso.", "success")
            return redirect(url_for("admin.dashboard"))
    return render_template("admin/change_password.html")


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@bp.route("/")
@admin_required
def dashboard():
    db = get_db()
    category_filter = request.args.get("categoria", type=int)
    status_filter = request.args.get("status", "")
    search = (request.args.get("q") or "").strip()

    query = """
        SELECT s.*, c.name AS category_name,
               (SELECT COUNT(*) FROM attempts a WHERE a.supplier_id = s.id) AS num_tentativas,
               (SELECT a.score FROM attempts a WHERE a.supplier_id = s.id
                    ORDER BY a.finished_at DESC LIMIT 1) AS ultima_nota,
               (SELECT a.total FROM attempts a WHERE a.supplier_id = s.id
                    ORDER BY a.finished_at DESC LIMIT 1) AS ultima_total,
               (SELECT a.passed FROM attempts a WHERE a.supplier_id = s.id
                    ORDER BY a.finished_at DESC LIMIT 1) AS ultima_passed,
               (SELECT a.finished_at FROM attempts a WHERE a.supplier_id = s.id
                    ORDER BY a.finished_at DESC LIMIT 1) AS ultima_data
        FROM suppliers s
        JOIN categories c ON c.id = s.category_id
        WHERE 1 = 1
    """
    params = []
    if category_filter:
        query += " AND s.category_id = ?"
        params.append(category_filter)
    if search:
        query += " AND (s.nome LIKE ? OR s.empresa LIKE ? OR s.cpf LIKE ?)"
        like = f"%{search}%"
        params += [like, like, only_digits(search) or like]
    query += " ORDER BY s.created_at DESC"

    suppliers = db.execute(query, params).fetchall()

    def status_of(row):
        if row["num_tentativas"] == 0:
            return "pendente"
        return "aprovado" if row["ultima_passed"] else "reprovado"

    suppliers = [dict(row, status=status_of(row)) for row in suppliers]
    if status_filter:
        suppliers = [s for s in suppliers if s["status"] == status_filter]

    categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()

    total_fornecedores = len(suppliers)
    total_aprovados = sum(1 for s in suppliers if s["status"] == "aprovado")
    total_reprovados = sum(1 for s in suppliers if s["status"] == "reprovado")
    total_pendentes = sum(1 for s in suppliers if s["status"] == "pendente")

    return render_template(
        "admin/dashboard.html",
        suppliers=suppliers,
        categories=categories,
        category_filter=category_filter,
        status_filter=status_filter,
        search=search,
        total_fornecedores=total_fornecedores,
        total_aprovados=total_aprovados,
        total_reprovados=total_reprovados,
        total_pendentes=total_pendentes,
    )


# ---------------------------------------------------------------------------
# Fornecedores
# ---------------------------------------------------------------------------

@bp.route("/fornecedores/novo", methods=("GET", "POST"))
@admin_required
def new_supplier():
    db = get_db()
    categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()

    if request.method == "POST":
        category_id = request.form.get("category_id", type=int)
        nome = (request.form.get("nome") or "").strip()
        empresa = (request.form.get("empresa") or "").strip()
        funcao = (request.form.get("funcao") or "").strip()
        cpf = only_digits(request.form.get("cpf") or "")

        if not (category_id and nome and empresa and funcao and len(cpf) == 11):
            flash("Preencha todos os campos corretamente.", "error")
        else:
            now = datetime.utcnow().isoformat()
            try:
                db.execute(
                    "INSERT INTO suppliers (category_id, nome, empresa, funcao, cpf, "
                    "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (category_id, nome, empresa, funcao, cpf, now, now),
                )
                db.commit()
                flash("Fornecedor incluído com sucesso.", "success")
                return redirect(url_for("admin.dashboard"))
            except sqlite3.IntegrityError:
                flash("Já existe um fornecedor com este CPF nesta categoria.", "error")

    return render_template("admin/supplier_form.html", categories=categories)


@bp.route("/fornecedores/<int:supplier_id>")
@admin_required
def supplier_detail(supplier_id):
    db = get_db()
    supplier = db.execute(
        "SELECT s.*, c.name AS category_name FROM suppliers s "
        "JOIN categories c ON c.id = s.category_id WHERE s.id = ?",
        (supplier_id,),
    ).fetchone()
    if supplier is None:
        flash("Fornecedor não encontrado.", "error")
        return redirect(url_for("admin.dashboard"))

    attempts = db.execute(
        "SELECT * FROM attempts WHERE supplier_id = ? ORDER BY finished_at DESC",
        (supplier_id,),
    ).fetchall()

    read_docs = db.execute(
        """
        SELECT d.title, dr.read_at, p.code AS procedure_code
        FROM document_reads dr
        JOIN documents d ON d.id = dr.document_id
        JOIN procedures p ON p.id = d.procedure_id
        WHERE dr.supplier_id = ?
        ORDER BY dr.read_at
        """,
        (supplier_id,),
    ).fetchall()

    return render_template(
        "admin/supplier_detail.html", supplier=supplier, attempts=attempts, read_docs=read_docs
    )


@bp.route("/fornecedores/<int:supplier_id>/excluir", methods=("POST",))
@admin_required
def delete_supplier(supplier_id):
    db = get_db()
    db.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
    db.commit()
    flash("Fornecedor excluído.", "success")
    return redirect(url_for("admin.dashboard"))


# ---------------------------------------------------------------------------
# Categorias
# ---------------------------------------------------------------------------

@bp.route("/categorias")
@admin_required
def categories_list():
    db = get_db()
    categories = db.execute(
        """
        SELECT c.*,
               (SELECT COUNT(*) FROM category_procedures cp WHERE cp.category_id = c.id)
                   AS num_procedimentos,
               (SELECT COUNT(*) FROM suppliers s WHERE s.category_id = c.id) AS num_fornecedores
        FROM categories c
        ORDER BY c.name
        """
    ).fetchall()
    return render_template("admin/categories_list.html", categories=categories)


@bp.route("/categorias/nova", methods=("GET", "POST"))
@admin_required
def new_category():
    db = get_db()
    procedures = db.execute("SELECT * FROM procedures ORDER BY code").fetchall()

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        sector = (request.form.get("sector") or "").strip()
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""
        selected_procs = request.form.getlist("procedures")

        errors = []
        if not name:
            errors.append("Informe o nome da categoria.")
        if not username:
            errors.append("Informe o usuário de login.")
        if len(password) < 4:
            errors.append("A senha deve ter pelo menos 4 caracteres.")
        if db.execute("SELECT id FROM categories WHERE username = ?", (username,)).fetchone():
            errors.append("Já existe uma categoria com este usuário de login.")

        if errors:
            for e in errors:
                flash(e, "error")
        else:
            cur = db.execute(
                "INSERT INTO categories (name, sector, username, password_hash) "
                "VALUES (?, ?, ?, ?)",
                (name, sector, username, generate_password_hash(password)),
            )
            category_id = cur.lastrowid
            for pid in selected_procs:
                db.execute(
                    "INSERT OR IGNORE INTO category_procedures (category_id, procedure_id) "
                    "VALUES (?, ?)",
                    (category_id, int(pid)),
                )
            db.commit()
            flash("Categoria criada com sucesso.", "success")
            return redirect(url_for("admin.categories_list"))

    return render_template(
        "admin/category_form.html", category=None, procedures=procedures, selected_ids=set()
    )


@bp.route("/categorias/<int:category_id>/editar", methods=("GET", "POST"))
@admin_required
def edit_category(category_id):
    db = get_db()
    category = db.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
    if category is None:
        flash("Categoria não encontrada.", "error")
        return redirect(url_for("admin.categories_list"))

    procedures = db.execute("SELECT * FROM procedures ORDER BY code").fetchall()

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        sector = (request.form.get("sector") or "").strip()
        username = (request.form.get("username") or "").strip().lower()
        new_password = request.form.get("password") or ""
        active = 1 if request.form.get("active") == "on" else 0
        selected_procs = set(int(x) for x in request.form.getlist("procedures"))

        errors = []
        if not name:
            errors.append("Informe o nome da categoria.")
        if not username:
            errors.append("Informe o usuário de login.")
        conflict = db.execute(
            "SELECT id FROM categories WHERE username = ? AND id != ?", (username, category_id)
        ).fetchone()
        if conflict:
            errors.append("Já existe outra categoria com este usuário de login.")

        if errors:
            for e in errors:
                flash(e, "error")
        else:
            if new_password:
                db.execute(
                    "UPDATE categories SET name=?, sector=?, username=?, active=?, "
                    "password_hash=? WHERE id=?",
                    (name, sector, username, active, generate_password_hash(new_password),
                     category_id),
                )
            else:
                db.execute(
                    "UPDATE categories SET name=?, sector=?, username=?, active=? WHERE id=?",
                    (name, sector, username, active, category_id),
                )
            db.execute("DELETE FROM category_procedures WHERE category_id = ?", (category_id,))
            for pid in selected_procs:
                db.execute(
                    "INSERT OR IGNORE INTO category_procedures (category_id, procedure_id) "
                    "VALUES (?, ?)",
                    (category_id, pid),
                )
            db.commit()
            flash("Categoria atualizada.", "success")
            return redirect(url_for("admin.categories_list"))

    selected_ids = set(
        r["procedure_id"] for r in db.execute(
            "SELECT procedure_id FROM category_procedures WHERE category_id = ?", (category_id,)
        ).fetchall()
    )

    return render_template(
        "admin/category_form.html", category=category, procedures=procedures,
        selected_ids=selected_ids,
    )


@bp.route("/categorias/<int:category_id>/excluir", methods=("POST",))
@admin_required
def delete_category(category_id):
    db = get_db()
    has_suppliers = db.execute(
        "SELECT COUNT(*) c FROM suppliers WHERE category_id = ?", (category_id,)
    ).fetchone()["c"]
    if has_suppliers:
        flash(
            "Não é possível excluir: existem fornecedores cadastrados nesta categoria. "
            "Desative a categoria em vez de excluí-la.", "error",
        )
    else:
        db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        db.commit()
        flash("Categoria excluída.", "success")
    return redirect(url_for("admin.categories_list"))


# ---------------------------------------------------------------------------
# Procedimentos (ITs / POPs) e documentos
# ---------------------------------------------------------------------------

@bp.route("/procedimentos", methods=("GET", "POST"))
@admin_required
def procedures_list():
    db = get_db()

    if request.method == "POST" and request.form.get("action") == "novo_procedimento":
        code = (request.form.get("code") or "").strip()
        if code:
            try:
                db.execute("INSERT INTO procedures (code) VALUES (?)", (code,))
                db.commit()
                flash("Procedimento adicionado.", "success")
            except sqlite3.IntegrityError:
                flash("Já existe um procedimento com este código/nome.", "error")
        return redirect(url_for("admin.procedures_list"))

    procedures = db.execute(
        """
        SELECT p.*,
               (SELECT COUNT(*) FROM documents d WHERE d.procedure_id = p.id) AS num_docs,
               (SELECT COUNT(*) FROM category_procedures cp WHERE cp.procedure_id = p.id)
                   AS num_categorias
        FROM procedures p ORDER BY p.code
        """
    ).fetchall()
    documents_by_proc = {}
    for doc in db.execute("SELECT * FROM documents ORDER BY uploaded_at DESC").fetchall():
        documents_by_proc.setdefault(doc["procedure_id"], []).append(doc)

    return render_template(
        "admin/procedures_list.html", procedures=procedures, documents_by_proc=documents_by_proc
    )


@bp.route("/documentos/upload", methods=("POST",))
@admin_required
def upload_document():
    db = get_db()
    procedure_id = request.form.get("procedure_id", type=int)
    title = (request.form.get("title") or "").strip()
    file = request.files.get("file")

    if not procedure_id or not title or not file or file.filename == "":
        flash("Selecione o procedimento, um título e um arquivo.", "error")
        return redirect(url_for("admin.procedures_list"))

    if not _allowed_file(file.filename):
        flash("Tipo de arquivo não permitido. Use PDF, Word, PowerPoint ou imagem.", "error")
        return redirect(url_for("admin.procedures_list"))

    safe_name = secure_filename(file.filename)
    ext = safe_name.rsplit(".", 1)[1].lower()
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    dest = Path(current_app.config["UPLOAD_FOLDER"]) / stored_name
    file.save(dest)

    db.execute(
        "INSERT INTO documents (procedure_id, title, filename, original_filename) "
        "VALUES (?, ?, ?, ?)",
        (procedure_id, title, stored_name, safe_name),
    )
    db.commit()
    flash("Documento enviado com sucesso.", "success")
    return redirect(url_for("admin.procedures_list"))


@bp.route("/documentos/<int:document_id>/excluir", methods=("POST",))
@admin_required
def delete_document(document_id):
    db = get_db()
    doc = db.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if doc:
        path = Path(current_app.config["UPLOAD_FOLDER"]) / doc["filename"]
        db.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        db.commit()
        if path.exists():
            path.unlink()
        flash("Documento removido.", "success")
    return redirect(url_for("admin.procedures_list"))


@bp.route("/documentos/visualizar/<path:filename>")
@admin_required
def preview_document(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


# ---------------------------------------------------------------------------
# Perguntas da prova
# ---------------------------------------------------------------------------

@bp.route("/perguntas")
@admin_required
def questions_list():
    db = get_db()
    questions = db.execute("SELECT * FROM questions ORDER BY order_index, id").fetchall()
    return render_template("admin/questions_list.html", questions=questions)


def _question_form_data(form):
    return dict(
        text=(form.get("text") or "").strip(),
        option_a=(form.get("option_a") or "").strip(),
        option_b=(form.get("option_b") or "").strip(),
        option_c=(form.get("option_c") or "").strip(),
        option_d=(form.get("option_d") or "").strip(),
        correct_option=form.get("correct_option") or "a",
        order_index=form.get("order_index", type=int) or 0,
    )


@bp.route("/perguntas/nova", methods=("GET", "POST"))
@admin_required
def new_question():
    db = get_db()
    if request.method == "POST":
        data = _question_form_data(request.form)
        if not all([data["text"], data["option_a"], data["option_b"], data["option_c"],
                    data["option_d"]]):
            flash("Preencha o enunciado e as quatro alternativas.", "error")
        else:
            db.execute(
                "INSERT INTO questions (text, option_a, option_b, option_c, option_d, "
                "correct_option, order_index, active) VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
                (data["text"], data["option_a"], data["option_b"], data["option_c"],
                 data["option_d"], data["correct_option"], data["order_index"]),
            )
            db.commit()
            flash("Pergunta adicionada.", "success")
            return redirect(url_for("admin.questions_list"))
    return render_template("admin/question_form.html", question=None)


@bp.route("/perguntas/<int:question_id>/editar", methods=("GET", "POST"))
@admin_required
def edit_question(question_id):
    db = get_db()
    question = db.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
    if question is None:
        flash("Pergunta não encontrada.", "error")
        return redirect(url_for("admin.questions_list"))

    if request.method == "POST":
        data = _question_form_data(request.form)
        if not all([data["text"], data["option_a"], data["option_b"], data["option_c"],
                    data["option_d"]]):
            flash("Preencha o enunciado e as quatro alternativas.", "error")
        else:
            db.execute(
                "UPDATE questions SET text=?, option_a=?, option_b=?, option_c=?, option_d=?, "
                "correct_option=?, order_index=? WHERE id=?",
                (data["text"], data["option_a"], data["option_b"], data["option_c"],
                 data["option_d"], data["correct_option"], data["order_index"], question_id),
            )
            db.commit()
            flash("Pergunta atualizada.", "success")
            return redirect(url_for("admin.questions_list"))

    return render_template("admin/question_form.html", question=question)


@bp.route("/perguntas/<int:question_id>/excluir", methods=("POST",))
@admin_required
def delete_question(question_id):
    db = get_db()
    db.execute("DELETE FROM questions WHERE id = ?", (question_id,))
    db.commit()
    flash("Pergunta removida.", "success")
    return redirect(url_for("admin.questions_list"))


@bp.route("/perguntas/<int:question_id>/alternar", methods=("POST",))
@admin_required
def toggle_question(question_id):
    db = get_db()
    q = db.execute("SELECT active FROM questions WHERE id = ?", (question_id,)).fetchone()
    if q:
        db.execute(
            "UPDATE questions SET active = ? WHERE id = ?", (0 if q["active"] else 1, question_id)
        )
        db.commit()
    return redirect(url_for("admin.questions_list"))


@bp.app_template_filter("datahora")
def datahora_filter(value):
    if not value:
        return "-"
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return value
    return dt.strftime("%d/%m/%Y %H:%M")
