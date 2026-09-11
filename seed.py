"""Popula o banco com dados iniciais:
 - categorias de fornecedores e procedimentos (extraídos da Matriz de Treinamento)
 - um usuário admin master
 - as 10 perguntas oficiais da Avaliação de Regras de Ouro (conteúdo idêntico ao
   modelo em PDF fornecido pela Triunfo, com o nome da empresa ajustado)
"""
import json
import secrets
import string
import unicodedata
from pathlib import Path

from werkzeug.security import generate_password_hash

from .db import get_db

SEED_FILE = Path(__file__).parent / "seed_matrix.json"


def _gen_password(length=8):
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _slugify_username(name: str, sector: str, used: set) -> str:
    ascii_name = _strip_accents(name).lower().replace(" ", ".")
    base = "".join(ch for ch in ascii_name if ch.isalnum() or ch == ".")
    base = base.strip(".")[:24] or "categoria"
    candidate = base
    n = 2
    while candidate in used:
        candidate = f"{base}{n}"
        n += 1
    used.add(candidate)
    return candidate


# Conteúdo oficial da Avaliação de Regras de Ouro, transcrito literalmente do
# modelo em PDF fornecido pela Triunfo (mesmas perguntas e alternativas do
# modelo original — apenas o rótulo da empresa foi trocado de "Petrobras" para
# "Triunfo" onde ele aparece como nome do programa).
#
# NOTA sobre a Questão 10: no PDF original as alternativas "b" e "d" estão
# ambas escritas como "Isolamento de Energias" (erro de digitação do próprio
# documento fonte). Mantido de propósito, sem correção, por pedido explícito
# de reproduzir o material exatamente como está.
#
# As Questões 2, 6 e 9 do PDF original trazem um pequeno ícone/figura em vez
# de texto (cinto de segurança, prancheta com lápis, e pessoa em movimento,
# respectivamente). Como este app não tem a imagem original em alta
# resolução, o enunciado foi adaptado para descrever o ícone em palavras.
GOLDEN_RULE_QUESTIONS = [
    dict(
        text="Quais das regras abaixo NÃO É uma Regra de Ouro Triunfo?",
        option_a="Permissão para Trabalho",
        option_b="Isolamento de Energias",
        option_c="Trabalho em Altura",
        option_d="Espaço Liberado",
        correct_option="d",
    ),
    dict(
        text=(
            "A figura abaixo demonstrada (ícone de cinto de segurança) representa que regra "
            "das Regras de Ouro Triunfo?"
        ),
        option_a="Posicionamento Seguro",
        option_b="Equipamentos de Proteção Individual",
        option_c="Segurança no Trânsito",
        option_d="Atenção às Mudanças",
        correct_option="c",
    ),
    dict(
        text=(
            "A afirmação \"Somente execute trabalhos em equipamentos ou instalações após "
            "certificar-se de que todas as fontes de energia tenham sido isoladas de forma "
            "segura.\" caracteriza a seguinte Regra de Ouro Triunfo:"
        ),
        option_a="Isolamento de Energias",
        option_b="Álcool e outras drogas",
        option_c="Trabalho em Altura",
        option_d="Espaço Confinado",
        correct_option="a",
    ),
    dict(
        text=(
            "Suponha que um colega de trabalho seu, durante a hora do almoço, ofereça a você "
            "um copo de cerveja, alegando que é sexta-feira e você merece comemorar. Você "
            "analisa esta situação e percebe que uma das Regras de Ouro não está sendo "
            "respeitada, pois logo depois do almoço, você irá retornar ao seu ambiente de "
            "trabalho. Que Regra de Ouro é esta que não foi seguida?"
        ),
        option_a="Posicionamento Seguro",
        option_b="Álcool e outras drogas",
        option_c="Atmosferas Explosivas",
        option_d="Equipamentos de Proteção Individual",
        correct_option="b",
    ),
    dict(
        text=(
            "Em determinada situação de trabalho, próximo de equipamentos da área de "
            "destilação de petróleo de uma refinaria, um colega de trabalho seu afirma que "
            "\"nunca se deve entrar em local com atmosfera explosiva e obedeça sempre aos "
            "alarmes e à sinalização\". A que Regra de Ouro seu colega está se referindo?"
        ),
        option_a="Espaço Confinado",
        option_b="Isolamento de Energias",
        option_c="Atmosferas Explosivas",
        option_d="Álcool e outras drogas",
        correct_option="c",
    ),
    dict(
        text=(
            "A figura abaixo demonstrada (ícone de prancheta com lápis) representa que regra "
            "das Regras de Ouro Triunfo?"
        ),
        option_a="Espaço Confinado",
        option_b="Equipamentos de Proteção Individual",
        option_c="Posicionamento Seguro",
        option_d="Atenção às Mudanças",
        correct_option="d",
    ),
    dict(
        text=(
            "Suponha que em uma determinada situação de trabalho, uma equipe de manutenção "
            "esteja realizando uma soldagem em uma tubulação de aço, próximo à área de "
            "movimentação de cargas de uma plataforma de petróleo FPSO. Em determinado "
            "momento, você percebe que as cargas que estão sendo movimentadas passam por "
            "cima desta equipe, posicionando todos estes trabalhadores embaixo das cargas "
            "que estão sendo içadas. Diante desta situação, qual a Regra de Ouro que não "
            "está sendo respeitada por esta equipe?"
        ),
        option_a="Posicionamento Seguro",
        option_b="Álcool e outras drogas",
        option_c="Atmosferas Explosivas",
        option_d="Isolamento de Energias",
        correct_option="a",
    ),
    dict(
        text=(
            "A afirmação \"Somente trabalhe com Permissão para Trabalho válida, liberada no "
            "campo e de seu total entendimento.\" caracteriza a seguinte Regra de Ouro "
            "Triunfo:"
        ),
        option_a="Isolamento de Energias",
        option_b="Permissão para Trabalho",
        option_c="Trabalho em Altura",
        option_d="Equipamentos de Proteção Individual",
        correct_option="b",
    ),
    dict(
        text=(
            "A figura abaixo demonstrada (ícone de pessoa em movimento/se afastando) "
            "representa que regra das Regras de Ouro Triunfo?"
        ),
        option_a="Atmosferas Explosivas",
        option_b="Equipamentos de Proteção Individual",
        option_c="Posicionamento Seguro",
        option_d="Trabalho em Altura",
        correct_option="c",
    ),
    dict(
        text=(
            "Suponha que em uma determinada situação de trabalho, um colega seu esteja te "
            "auxiliando a fazer um corte em uma chapa de metal, utilizando uma esmerilhadeira "
            "e uma serra manual. Em determinado momento, devido ao suor em suas mãos, você e "
            "seu colega retirem as luvas, para secar as mãos e continuar o serviço. No "
            "entanto, como somente falta cortar 1 cm de metal, vocês resolvem continuar o "
            "corte sem as luvas. Analisando esta situação, qual regra das Regras de Ouro "
            "você acha que não está sendo seguida?"
        ),
        option_a="Equipamentos de Proteção Individual",
        option_b="Isolamento de Energias",
        option_c="Posicionamento Seguro",
        option_d="Isolamento de Energias",
        correct_option="a",
    ),
]


def run():
    db = get_db()

    # --- Admin master -----------------------------------------------------
    admin_password = None
    existing_admin = db.execute("SELECT id FROM admin_users LIMIT 1").fetchone()
    if existing_admin is None:
        admin_password = _gen_password(10)
        db.execute(
            "INSERT INTO admin_users (username, password_hash) VALUES (?, ?)",
            ("admin", generate_password_hash(admin_password)),
        )

    # --- Categorias e procedimentos ----------------------------------------
    with open(SEED_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    procedure_ids = {}
    for code in data["procedures"]:
        row = db.execute("SELECT id FROM procedures WHERE code = ?", (code,)).fetchone()
        if row is None:
            cur = db.execute("INSERT INTO procedures (code) VALUES (?)", (code,))
            procedure_ids[code] = cur.lastrowid
        else:
            procedure_ids[code] = row["id"]

    used_usernames = set(
        r["username"] for r in db.execute("SELECT username FROM categories").fetchall()
    )

    credentials = []
    # dedup category display names (algumas linhas do Excel repetem nome com setores diferentes)
    name_count = {}
    for cat in data["categories"]:
        name_count[cat["name"]] = name_count.get(cat["name"], 0) + 1

    seen_names = {}
    for cat in data["categories"]:
        base_name = cat["name"]
        if name_count[base_name] > 1 and cat.get("sector"):
            display_name = f"{base_name} ({cat['sector']})"
        else:
            display_name = base_name

        existing = db.execute(
            "SELECT id FROM categories WHERE name = ?", (display_name,)
        ).fetchone()
        if existing is not None:
            continue

        username = _slugify_username(display_name, cat.get("sector") or "", used_usernames)
        password = _gen_password(8)
        cur = db.execute(
            "INSERT INTO categories (name, sector, username, password_hash) VALUES (?, ?, ?, ?)",
            (display_name, cat.get("sector"), username, generate_password_hash(password)),
        )
        category_id = cur.lastrowid
        credentials.append({"name": display_name, "username": username, "password": password})

        for code in cat["procedures"]:
            pid = procedure_ids.get(code)
            if pid:
                db.execute(
                    "INSERT OR IGNORE INTO category_procedures (category_id, procedure_id) "
                    "VALUES (?, ?)",
                    (category_id, pid),
                )

    # --- Perguntas oficiais da Avaliação de Regras de Ouro ------------------
    existing_q = db.execute("SELECT COUNT(*) c FROM questions").fetchone()["c"]
    if existing_q == 0:
        for i, q in enumerate(GOLDEN_RULE_QUESTIONS):
            db.execute(
                "INSERT INTO questions (text, option_a, option_b, option_c, option_d, "
                "correct_option, order_index, active) VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
                (
                    q["text"], q["option_a"], q["option_b"], q["option_c"], q["option_d"],
                    q["correct_option"], i,
                ),
            )

    db.commit()

    # --- Grava credenciais geradas em arquivo texto p/ o Admin consultar --
    if credentials or admin_password:
        out_path = Path(__file__).parent.parent / "CREDENCIAIS_GERADAS.txt"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("CREDENCIAIS GERADAS AUTOMATICAMENTE NO PRIMEIRO SETUP\n")
            f.write("Troque estas senhas assim que possível pelo painel Admin.\n")
            f.write("=" * 70 + "\n\n")
            if admin_password:
                f.write("ADMIN (painel /admin)\n")
                f.write("  usuario: admin\n")
                f.write(f"  senha:   {admin_password}\n\n")
            if credentials:
                f.write("LOGINS POR CATEGORIA DE FORNECEDOR (tela pública /entrar)\n")
                for c in credentials:
                    f.write(f"  - {c['name']}\n")
                    f.write(f"      usuario: {c['username']}\n")
                    f.write(f"      senha:   {c['password']}\n")
        print(f"Credenciais salvas em: {out_path}")
