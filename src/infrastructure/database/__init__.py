"""Pacote de acesso a dados do MetaDB MCP.

Exporta o ``SecureConnectionManager`` (singleton global), o
``DatabaseManager`` (inicializado após autenticação) e os modelos ORM.
"""

from typing import Optional

from .manager import DatabaseManager
from .models import (
    AppConfig,
    Base,
    DBConnection,
    SyncColumn,
    SyncConstraint,
    SyncIndex,
    SyncSample,
    SyncTable,
)
from .secure_connection import SecureConnectionManager

# Singleton global do gerenciador de conexão segura
secure_connection: SecureConnectionManager = SecureConnectionManager()

# O db_manager será inicializado após autenticação bem-sucedida
db_manager: Optional[DatabaseManager] = None


def initialize_db_manager() -> DatabaseManager:
    """Inicializa o DatabaseManager com a conexão segura ativa.

    Deve ser chamada após o ``SecureConnectionManager`` ser desbloqueado
    (login ou cadastro bem-sucedido).

    Returns:
        Instância configurada do ``DatabaseManager``.
    """
    global db_manager  # noqa: PLW0603
    db_manager = DatabaseManager(secure_connection)
    return db_manager


__all__: list[str] = [
    "secure_connection",
    "db_manager",
    "initialize_db_manager",
    "DatabaseManager",
    "SecureConnectionManager",
    "Base",
    "AppConfig",
    "DBConnection",
    "SyncTable",
    "SyncColumn",
    "SyncConstraint",
    "SyncIndex",
    "SyncSample",
]
