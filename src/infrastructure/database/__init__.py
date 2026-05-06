"""Pacote de acesso a dados do MetaDB MCP.

Exporta o ``SecureConnectionManager`` (singleton global) e os modelos ORM.
A orquestração agora ocorre nas camadas de serviços de aplicação e os acessos
através de DAOs.
"""

from .models import (
    AppConfig,
    Base,
    DBConnection,
    MetadataColumn,
    MetadataConstraint,
    MetadataIndex,
    MetadataSample,
    MetadataTable,
)
from .secure_connection import SecureConnectionManager

# Singleton global do gerenciador de conexão segura
secure_connection: SecureConnectionManager = SecureConnectionManager()

__all__: list[str] = [
    "secure_connection",
    "SecureConnectionManager",
    "Base",
    "AppConfig",
    "DBConnection",
    "MetadataTable",
    "MetadataColumn",
    "MetadataConstraint",
    "MetadataIndex",
    "MetadataSample",
]
