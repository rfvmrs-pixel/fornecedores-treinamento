-- Sistema de Treinamento e Avaliação de Fornecedores
-- Schema SQLite

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS document_reads;
DROP TABLE IF EXISTS attempts;
DROP TABLE IF EXISTS questions;
DROP TABLE IF EXISTS documents;
DROP TABLE IF EXISTS category_procedures;
DROP TABLE IF EXISTS suppliers;
DROP TABLE IF EXISTS procedures;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS admin_users;
DROP TABLE IF EXISTS settings;

CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    sector TEXT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE procedures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE
);

CREATE TABLE category_procedures (
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    procedure_id INTEGER NOT NULL REFERENCES procedures(id) ON DELETE CASCADE,
    PRIMARY KEY (category_id, procedure_id)
);

CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    procedure_id INTEGER NOT NULL REFERENCES procedures(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    nome TEXT NOT NULL,
    empresa TEXT NOT NULL,
    funcao TEXT NOT NULL,
    cpf TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    training_confirmed_at TEXT,
    UNIQUE(category_id, cpf)
);

CREATE TABLE document_reads (
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    read_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (supplier_id, document_id)
);

CREATE TABLE questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    image_filename TEXT,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_option TEXT NOT NULL CHECK(correct_option IN ('a','b','c','d')),
    order_index INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL,
    score INTEGER NOT NULL,
    total INTEGER NOT NULL,
    passed INTEGER NOT NULL,
    answers_json TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL
);

CREATE TABLE admin_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);

CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX idx_documents_procedure ON documents(procedure_id);
CREATE INDEX idx_suppliers_category ON suppliers(category_id);
CREATE INDEX idx_attempts_supplier ON attempts(supplier_id);
CREATE INDEX idx_category_procedures_category ON category_procedures(category_id);
CREATE INDEX idx_category_procedures_procedure ON category_procedures(procedure_id);
