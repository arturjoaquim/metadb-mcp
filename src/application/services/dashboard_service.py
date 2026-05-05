"""Serviço de orquestração para o dashboard Web.

Encapsula regras de negócio, chamadas de segurança e operações de banco
de dados para desacoplar a camada de controllers (interfaces) da
infraestrutura.
"""

from typing import Any, Dict, List, Optional

from infrastructure import database
from infrastructure.security.auth_service import auth_service, AuthenticationError


class DashboardServiceError(Exception):
    """Exceção para erros na camada de serviço do dashboard."""
    pass


class DashboardService:
    """Orquestrador das operações do painel web."""

    def is_unlocked(self) -> bool:
        """Verifica se o banco de dados seguro está desbloqueado."""
        return bool(database.secure_connection.is_unlocked)

    def database_exists(self) -> bool:
        """Verifica se o banco de dados já foi criado."""
        return auth_service.database_exists()

    def verify_token(self, auth_token: str) -> Optional[Dict[str, Any]]:
        """Verifica a validade de um token JWT."""
        return auth_service.verify_token(auth_token)

    def register(self, username: str, password: str) -> str:
        """Registra um novo usuário e inicializa o gerenciador de banco."""
        token = auth_service.register(username, password)
        database.initialize_db_manager()
        return token

    def login(self, username: str, password: str) -> str:
        """Autentica o usuário e inicializa o gerenciador de banco."""
        token = auth_service.login(username, password)
        database.initialize_db_manager()
        return token

    def logout(self) -> None:
        """Bloqueia a conexão segura."""
        database.secure_connection.lock()

    def get_connections(self) -> List[Dict[str, Any]]:
        """Recupera as conexões salvas."""
        if not database.db_manager:
            raise DashboardServiceError("Database manager não inicializado.")
        return database.db_manager.get_connections()

    def get_tables(
        self, db_type: str, host: str, port: int, user: str, password: str, dbname: str, conn_name: str
    ) -> Dict[str, List[str]]:
        """Testa conexão e retorna tabelas remotas e sincronizadas."""
        if not database.db_manager:
            raise DashboardServiceError("Database manager não inicializado.")

        if not database.db_manager.test_connection(db_type, host, port, user, password, dbname):
            raise DashboardServiceError("Falha na conexão com o banco de dados. Verifique as credenciais.")

        tables = database.db_manager.get_all_tables(db_type, host, port, user, password, dbname)
        synced_tables = database.db_manager.get_synced_tables_by_name(conn_name)
        return {"tables": tables, "synced_tables": synced_tables}

    def sync_tables(
        self, conn_name: str, tables_to_sync: List[str], db_type: str, host: str, port: int, user: str, password: str, dbname: str
    ) -> None:
        """Sincroniza tabelas do banco remoto para o cache local."""
        if not database.db_manager:
            raise DashboardServiceError("Database manager não inicializado.")
        
        database.db_manager.sync_tables(
            conn_name=conn_name,
            tables_to_sync=tables_to_sync,
            db_type=db_type,
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=dbname,
        )


dashboard_service = DashboardService()
