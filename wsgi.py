"""Ponto de entrada WSGI para servidores de produção (gunicorn, etc.).

Exemplo (Procfile / Render / Railway):
    gunicorn wsgi:app
"""
from app import create_app

app = create_app()
