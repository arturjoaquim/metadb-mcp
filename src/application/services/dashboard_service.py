"""Serviço de orquestração para o dashboard Web.

Encapsula regras de negócio, chamadas de segurança e operações de banco
de dados para desacoplar a camada de controllers (interfaces) da
infraestrutura.
"""

from typing import Any, Dict, List, Optional, Type

from infrastructure.database.daos.connection_dao import ConnectionDAO
from infrastructure.database.daos.metadata_dao import MetadataDAO
from infrastructure.security.auth_service import AuthService
from infrastructure.database.secure_connection import SecureConnectionManager
from application.services.sync_service import SyncService


class DashboardServiceError(Exception):
    """Exceção para erros na camada de serviço do dashboard."""
    pass


class DashboardService:
    """Orquestrador das operações do painel web."""

    def __init__(
        self,
        secure_conn: SecureConnectionManager,
        auth_svc: AuthService,
        sync_svc: SyncService,
        connection_dao_class: Type[ConnectionDAO] = ConnectionDAO,
        metadata_dao_class: Type[MetadataDAO] = MetadataDAO,
    ) -> None:
        self._secure_conn = secure_conn
        self._auth_svc = auth_svc
        self.sync_service = sync_svc
        self._connection_dao_class = connection_dao_class
        self._metadata_dao_class = metadata_dao_class

    def is_unlocked(self) -> bool:
        """Verifica se o banco de dados seguro está desbloqueado."""
        return bool(self._secure_conn.is_unlocked)

    def database_exists(self) -> bool:
        """Verifica se o banco de dados já foi criado."""
        return self._auth_svc.database_exists()

    def verify_token(self, auth_token: str) -> Optional[Dict[str, Any]]:
        """Verifica a validade de um token JWT."""
        return self._auth_svc.verify_token(auth_token)

    def register(self, username: str, password: str) -> str:
        """Registra um novo usuário e inicializa o gerenciador de banco."""
        token = self._auth_svc.register(username, password)
        return token

    def login(self, username: str, password: str) -> str:
        """Autentica o usuário e inicializa o gerenciador de banco."""
        token = self._auth_svc.login(username, password)
        return token

    def logout(self) -> None:
        """Bloqueia a conexão segura."""
        self._secure_conn.lock()

    def get_connections(self) -> List[Dict[str, Any]]:
        """Recupera as conexões salvas."""
        if not self.is_unlocked():
            raise DashboardServiceError("Banco de dados bloqueado.")
        
        session = self._secure_conn.get_session()
        try:
            return self._connection_dao_class(session).get_all()
        finally:
            session.close()

    def get_tables(
        self,
        db_type: str,
        host: str,
        port: int,
        user: str,
        password: str,
        dbname: str,
        conn_name: str,
        driver_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Testa conexão e retorna tabelas remotas e informações de sincronização."""
        if not self.is_unlocked():
            raise DashboardServiceError("Banco de dados bloqueado.")

        if not self.sync_service.test_connection(
            db_type, host, port, user, password, dbname, driver_path=driver_path
        ):
            raise DashboardServiceError("Falha na conexão com o banco de dados. Verifique as credenciais.")

        tables = self.sync_service.get_all_tables(
            db_type, host, port, user, password, dbname, driver_path=driver_path
        )
        
        session = self._secure_conn.get_session()
        try:
            synced_tables = self._metadata_dao_class(session).get_synced_tables_by_connection_name(conn_name)
        finally:
            session.close()
            
        return {"tables": tables, "synced_tables": synced_tables}

    def sync_tables(
        self,
        conn_name: str,
        tables_to_sync: List[str],
        db_type: str,
        host: str,
        port: int,
        user: str,
        password: str,
        dbname: str,
        driver_path: Optional[str] = None,
        sensitive_tables: Optional[List[str]] = None,
        sample_size: int = 10,
    ) -> None:
        """Sincroniza tabelas do banco remoto para o cache local."""
        if not self.is_unlocked():
            raise DashboardServiceError("Banco de dados bloqueado.")
        
        self.sync_service.sync_tables(
            conn_name=conn_name,
            tables_to_sync=tables_to_sync,
            db_type=db_type,
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=dbname,
            driver_path=driver_path,
            sensitive_tables=sensitive_tables,
            sample_size=sample_size,
        )


