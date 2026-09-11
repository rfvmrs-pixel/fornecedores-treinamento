# Sistema de Treinamento e Avaliação de Fornecedores — Triunfo

Aplicação web (Python/Flask + SQLite) para treinamento e avaliação de fornecedores
por categoria: leitura de ITs/POPs e prova de Regras de Ouro no modelo Petrobras,
adaptada.

## O que o sistema faz

- **Acesso por link único**, sem precisar de conta Google/Microsoft/Claude — qualquer
  fornecedor com o usuário/senha da sua categoria consegue entrar.
- **Login por categoria**: o Admin cria um usuário e senha para cada categoria de
  fornecedor (ex: "Vigilância Patrimonial", "TPS", "LON I"...). Ao entrar com essas
  credenciais, o sistema já sabe a categoria do fornecedor.
- **Cadastro do fornecedor**: após o login da categoria, o fornecedor preenche
  Nome, Empresa, Função e CPF (com validação do dígito verificador). Se ele já usou
  esse CPF antes nessa categoria, seu cadastro e histórico são recuperados
  automaticamente (permite refazer a prova sem duplicar cadastro).
- **Treinamento automático por categoria**: assim que o fornecedor se identifica, o
  sistema já mostra a lista de ITs/POPs obrigatórios daquela categoria (pré-carregada
  a partir do Excel `PL_SGI_MTFCR08 Anexo V`), puxando os documentos que o Admin
  enviou para cada procedimento.
- **Confirmação de leitura**: o fornecedor precisa confirmar a leitura de cada
  documento antes de a prova ser liberada.
- **Prova de Regras de Ouro** no layout do modelo Petrobras (cabeçalho com
  Nome/Empresa/Data + questões de múltipla escolha), com aprovação exigindo 100%
  de acerto e número de tentativas ilimitado.
- **Painel Admin**: dashboard com todos os fornecedores, categoria, CPF, datas,
  notas e status (aprovado/reprovado/pendente); cadastro/edição de categorias e
  suas credenciais; upload de ITs/POPs; banco de perguntas da prova (CRUD
  completo); inclusão e exclusão manual de fornecedores.

> ℹ️ **Sobre as perguntas da prova**: o sistema já sobe com as **10 perguntas
> oficiais** da Avaliação de Regras de Ouro, transcritas do modelo em PDF
> fornecido (mesmo texto e alternativas, só com o nome da empresa ajustado
> para Triunfo). Se precisar ajustar o texto de alguma pergunta no futuro,
> entre em **Admin → Prova (perguntas)** — não é necessário nenhum
> desenvolvedor para isso.

## Por que isto é uma aplicação separada (e não uma página dentro do Claude)

Pensamos inicialmente em publicar isso como uma página hospedada pelo Claude, mas
esse tipo de página só permite acesso a pessoas já logadas na organização Claude do
usuário — o que inviabilizaria o acesso de fornecedores externos por um link
simples. Por isso o sistema foi construído como uma aplicação Flask independente,
que vocês hospedam onde quiserem e fica acessível por qualquer pessoa com o link,
sem exigir conta em nenhum serviço da Anthropic.

## Estrutura do projeto

```
fornecedores-treinamento/
├── app/
│   ├── __init__.py        # fábrica da aplicação Flask
│   ├── db.py               # acesso ao SQLite
│   ├── schema.sql           # estrutura das tabelas
│   ├── seed.py               # popula categorias/procedimentos/admin/perguntas
│   ├── seed_matrix.json       # dados extraídos do Excel da Matriz de Treinamento
│   ├── utils.py                # validação de CPF, controle de sessão/login
│   ├── public.py                # rotas do fornecedor
│   ├── admin.py                  # rotas do painel administrativo
│   ├── templates/                 # HTML (Jinja2)
│   ├── static/css/style.css        # estilo visual
│   └── uploads/procedimentos/       # onde os PDFs enviados pelo Admin ficam salvos
├── instance/                         # banco SQLite fica aqui (criado automaticamente)
├── requirements.txt
├── Procfile                           # para deploy em Render/Railway/Heroku-like
├── wsgi.py                             # ponto de entrada para gunicorn
├── run.py                               # ponto de entrada para rodar localmente
└── .env.example
```

## Rodando localmente (para testar antes de publicar)

Pré-requisitos: Python 3.10+.

```bash
cd fornecedores-treinamento
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

export SECRET_KEY="uma-chave-aleatoria-aqui"      # Windows (PowerShell): $env:SECRET_KEY="..."
python3 -m flask --app app setup                   # cria e popula o banco (1x apenas)

python3 run.py
```

Acesse `http://localhost:5000`. As credenciais geradas automaticamente (login do
Admin e de cada categoria) ficam salvas em **`CREDENCIAIS_GERADAS.txt`** na raiz do
projeto — abra esse arquivo, copie as senhas, distribua aos fornecedores/equipe e
depois pode apagar o arquivo (ele não é necessário para o funcionamento do
sistema, é só para você ver as senhas geradas uma vez).

> O comando `flask --app app setup` só deve ser rodado **uma vez**, na primeira
> vez que o banco é criado (em produção, geralmente após o primeiro deploy). Ele
> recria as tabelas do zero — não rode de novo depois que já existirem fornecedores
> cadastrados, ou os dados serão apagados.

## Publicando com um link público (deploy)

O projeto já vem pronto (`Procfile`, `wsgi.py`, `requirements.txt`) para qualquer
serviço que rode aplicações Python/WSGI. Duas opções simples e gratuitas para
começar:

### Opção A — Render.com (recomendado, tem plano gratuito)

1. Crie uma conta em render.com e um novo **Web Service**, apontando para um
   repositório Git com este projeto (crie um repo no GitHub/GitLab e suba esta
   pasta, ou use o "deploy manual" do Render enviando o zip).
2. Build command: `pip install -r requirements.txt`
3. Start command: `gunicorn wsgi:app`
4. Em "Environment", adicione a variável `SECRET_KEY` com um valor aleatório
   (gere com `python3 -c "import secrets; print(secrets.token_hex(32))"`), e
   opcionalmente `EMPRESA_NOME=Triunfo`.
5. **Disco persistente**: por padrão, o disco do Render é apagado a cada deploy.
   Como o banco SQLite e os arquivos enviados (ITs/POPs) precisam sobreviver aos
   deploys, adicione um **Persistent Disk** (Render → seu serviço → Disks) montado
   em `/var/data`, e defina a variável de ambiente
   `DATABASE_PATH=/var/data/fornecedores.sqlite3`. Os uploads de documentos ficam
   em `app/uploads/procedimentos` — se quiser que sobrevivam a deploys também,
   monte o disco nessa pasta ou ajuste `UPLOAD_FOLDER` em `app/__init__.py` para
   apontar para dentro do disco persistente.
6. Após o primeiro deploy, abra o "Shell" do Render (ou rode localmente contra o
   mesmo banco) e execute `flask --app app setup` uma única vez para criar as
   tabelas e gerar as credenciais iniciais.

### Opção B — Servidor próprio / VPS da empresa (Docker ou direto)

```bash
pip install -r requirements.txt
export SECRET_KEY="..."
export DATABASE_PATH=/caminho/persistente/fornecedores.sqlite3
flask --app app setup     # apenas na primeira vez
gunicorn -w 2 -b 0.0.0.0:8000 wsgi:app
```

Coloque atrás de um Nginx/Caddy com HTTPS (ex: Let's Encrypt) para ter um link
`https://treinamento.suaempresa.com.br` seguro — essencial já que o formulário
recebe CPF dos fornecedores.

### Opção C — Railway, PythonAnywhere ou outro host Python

O padrão é o mesmo: instalar `requirements.txt`, definir `SECRET_KEY` (e
`DATABASE_PATH`/`UPLOAD_FOLDER` apontando para um armazenamento persistente,
se o serviço não mantiver o disco entre deploys), rodar `flask --app app setup`
uma vez, e então subir com `gunicorn wsgi:app` (ou o processo equivalente do
serviço escolhido).

Se preferir, posso ajudar a fazer o deploy caso você me dê acesso a uma dessas
plataformas (ou a um servidor com SSH).

## Uso do dia a dia

### Para o fornecedor
1. Acessa o link do sistema.
2. Digita o usuário/senha da categoria (fornecido pela Triunfo).
3. Preenche Nome, Empresa, Função, CPF.
4. Lê cada IT/POP listado e confirma a leitura.
5. Faz a prova de Regras de Ouro (precisa acertar 100%; pode refazer quantas
   vezes precisar).

### Para o Admin
- **Fornecedores**: acompanhar quem já treinou, notas, datas, status; incluir ou
  excluir fornecedores manualmente.
- **Categorias**: criar novas categorias, definir/alterar login e senha, marcar
  quais ITs/POPs cada categoria exige, ativar/desativar uma categoria.
- **ITs / POPs**: cadastrar novos procedimentos e enviar (upload) os arquivos
  correspondentes — eles ficam disponíveis automaticamente para todas as
  categorias vinculadas.
- **Prova (perguntas)**: criar, editar, ativar/desativar e excluir as perguntas
  da Avaliação de Regras de Ouro. As 10 perguntas oficiais já vêm cadastradas;
  use esta tela se precisar ajustar o texto de alguma no futuro.

## Segurança e observações

- Senhas de categorias e do Admin são armazenadas com hash (`werkzeug.security`),
  nunca em texto puro.
- O sistema valida o CPF pelo algoritmo oficial de dígito verificador.
- Trocar a `SECRET_KEY` padrão é obrigatório antes de qualquer uso real — ela
  assina os cookies de sessão.
- Recomenda-se fortemente publicar atrás de HTTPS, já que o formulário coleta CPF.
- Como este é o primeiro setup, todas as senhas de categoria e do Admin são
  geradas automaticamente e salvas uma única vez em `CREDENCIAIS_GERADAS.txt`.
  Troque-as (Admin → Categorias → Editar, e Admin → Minha senha) assim que
  distribuir o acesso.
