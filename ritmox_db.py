"""Aplicação obrigatória do esquema PostgreSQL a cada transação.

Supabase Session Pooler pode ignorar PGOPTIONS na abertura da conexão.
Em vez de depender da configuração inicial, restringimos o search_path
com SET LOCAL antes de qualquer comando dentro de CADA transação.
Não há fallback ao schema public para as tabelas de usuário.
"""
from __future__ import annotations

import re

from sqlalchemy import event


def install_schema_guard(engine, schema: str) -> None:
    """Falha de forma fechada se não conseguir selecionar o esquema esperado."""
    if not re.fullmatch(r"ritmox(?:_auth|_u_[1-9][0-9]*)?", schema):
        raise ValueError("Esquema PostgreSQL não permitido.")

    # Validado antes da interpolação: identificador limitado a caracteres seguros.
    statement = f'SET LOCAL search_path TO "{schema}"'

    @event.listens_for(engine, "begin")
    def _select_and_verify_schema(connection) -> None:
        # O evento begin ocorre antes de consultas, reflection, inserts e commits.
        # SET LOCAL expira automaticamente ao finalizar a transação (inclusive rollback).
        connection.exec_driver_sql(statement)
        actual = connection.exec_driver_sql("SELECT current_schema()").scalar_one()
        if actual != schema:
            raise RuntimeError(
                "RITMOX: bloqueada transação fora do esquema PostgreSQL autorizado."
            )
