"""Modelos de requisição e resposta da aplicação."""

from typing import List
from pydantic import BaseModel


class AuthRequest(BaseModel):
    """Modelo para autenticação."""

    username: str
    password: str


class ConnectionRequest(BaseModel):
    """Modelo de dados para requisições de conexão ao banco."""

    conn_name: str
    db_type: str
    host: str
    port: int
    user: str
    password: str
    dbname: str


class SyncRequest(BaseModel):
    """Modelo de dados para requisições de sincronização de tabelas."""

    conn_name: str
    db_type: str
    host: str
    port: int
    user: str
    password: str
    dbname: str
    tables: List[str]
