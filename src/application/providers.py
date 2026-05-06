"""Composition Root — instancia e conecta todas as dependências."""



from infrastructure.database import secure_connection
from infrastructure.database.adapters import (
    BaseMetadataExtractor,
    PostgresMetadataExtractor,
    OracleMetadataExtractor,
)
from infrastructure.database.daos.connection_dao import ConnectionDAO
from infrastructure.database.daos.metadata_dao import MetadataDAO
from infrastructure.security.auth_service import AuthService

from application.services.sync_service import SyncService
from application.services.dashboard_service import DashboardService
from application.services.metadata_service import MetadataService


def create_metadata_extractor(
    db_type: str, host: str, port: int, user: str, password: str, dbname: str
) -> BaseMetadataExtractor:
    """Factory function para criação de extratores de metadados."""
    if db_type == "postgresql":
        return PostgresMetadataExtractor(host, port, user, password, dbname)
    elif db_type == "oracle":
        return OracleMetadataExtractor(host, port, user, password, dbname)
    raise ValueError(f"Tipo de banco não suportado: {db_type}")


# --- Instanciação com injeção via construtor ---

auth_service = AuthService(secure_conn=secure_connection)

sync_service = SyncService(
    secure_conn=secure_connection,
    extractor_factory=create_metadata_extractor,
    connection_dao_class=ConnectionDAO,
    metadata_dao_class=MetadataDAO,
)

dashboard_service = DashboardService(
    secure_conn=secure_connection,
    auth_svc=auth_service,
    sync_svc=sync_service,
    connection_dao_class=ConnectionDAO,
    metadata_dao_class=MetadataDAO,
)

metadata_service = MetadataService(
    secure_conn=secure_connection,
    metadata_dao_class=MetadataDAO,
    connection_dao_class=ConnectionDAO,
)
