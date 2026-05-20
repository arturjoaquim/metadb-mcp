import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from application.services.sync_service import SyncService, SyncServiceError
from infrastructure.database.adapters.oracle_metadata_extractor import OracleMetadataExtractor
from infrastructure.database.daos.connection_dao import ConnectionDAO
from infrastructure.database.daos.metadata_dao import MetadataDAO
from infrastructure.database.secure_connection import SecureConnectionManager
from infrastructure.database.models import Base

@pytest.fixture
def memory_db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    yield session
    session.close()

@pytest.fixture
def mock_secure_conn(memory_db_session):
    mock = MagicMock(spec=SecureConnectionManager)
    # Sempre retornar a mesma sessão em memória para testar o commit/rollback
    mock.get_session.return_value = memory_db_session
    return mock

@pytest.fixture
def mock_oracle_engine():
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    return mock_engine, mock_conn

class TestSyncServiceOracleIntegration:
    @patch("infrastructure.database.adapters.oracle_metadata_extractor.os.path.isdir")
    @patch("infrastructure.database.adapters.oracle_metadata_extractor.oracledb")
    @patch.object(OracleMetadataExtractor, "get_engine")
    @patch.object(OracleMetadataExtractor, "extract_sample_rows")
    def test_sync_tables_isolated_commits_and_global_error(
        self,
        mock_extract_sample,
        mock_get_engine,
        mock_oracledb,
        mock_isdir,
        mock_secure_conn,
        mock_oracle_engine,
        memory_db_session
    ):
        mock_isdir.return_value = True
        mock_engine, mock_conn = mock_oracle_engine
        mock_get_engine.return_value = mock_engine
        
        # Simula amostras de dados vazias
        mock_extract_sample.return_value = []

        # Vamos simular que a consulta ao ALL_TAB_COLUMNS (preload) retorna algumas colunas
        def mock_execute(stmt, params=None):
            sql = str(stmt).upper()
            result_mock = MagicMock()
            if "ALL_TAB_COLUMNS" in sql:
                # OWNER, TABLE_NAME, COLUMN_NAME, DATA_TYPE, NULLABLE, DATA_DEFAULT, COMMENTS
                result_mock.__iter__.return_value = [
                    ("HR", "TABLE1", "COL1", "VARCHAR2", "Y", None, "Comment 1"),
                    ("HR", "TABLE2", "COL1", "NUMBER", "N", None, "Comment 2")
                ]
            elif "ALL_INDEXES" in sql:
                result_mock.__iter__.return_value = []
            elif "ALL_CONSTRAINTS" in sql:
                result_mock.__iter__.return_value = []
            elif "ALL_TAB_COMMENTS" in sql:
                result_mock.__iter__.return_value = []
            return result_mock
            
        mock_conn.execute.side_effect = mock_execute

        # Nossa factory retornará o OracleMetadataExtractor real
        def factory(*args, **kwargs):
            return OracleMetadataExtractor(
                host="localhost", port=1521, user="hr", password="pwd", dbname="orcl", driver_path="/fake/path"
            )

        service = SyncService(
            secure_conn=mock_secure_conn,
            extractor_factory=factory,
            connection_dao_class=ConnectionDAO,
            metadata_dao_class=MetadataDAO
        )

        # Para simular uma falha isolada, vamos forçar um erro na função extract_sample_rows apenas para TABLE2
        def side_effect_samples(table_name, schema, limit):
            if table_name == "TABLE2":
                raise Exception("Erro forçado na TABLE2")
            return [{"col1": "val1"}]
            
        mock_extract_sample.side_effect = side_effect_samples

        # Tenta sincronizar TABLE1 e TABLE2
        # TABLE1 deve ter sucesso (commit), TABLE2 deve falhar (rollback)
        # E no final, um SyncServiceError deve ser lançado por conta de TABLE2
        
        with pytest.raises(SyncServiceError) as exc_info:
            service.sync_tables(
                conn_name="OracleTest",
                tables_to_sync=["HR.TABLE1", "HR.TABLE2"],
                db_type="oracle",
                host="localhost",
                port=1521,
                user="hr",
                password="pwd",
                dbname="orcl",
                driver_path="/fake/path"
            )

        # Verifica se o erro global informa qual tabela falhou
        assert "TABLE2" in str(exc_info.value)
        assert "TABLE1" not in str(exc_info.value)

        # Verifica o estado do banco local (SQLite)
        from infrastructure.database.models import DBConnection, MetadataTable
        
        connections = memory_db_session.query(DBConnection).all()
        assert len(connections) == 1
        assert connections[0].name == "OracleTest"
        conn_id = connections[0].id

        # Verifica as tabelas: TABLE1 deve estar salva, mas TABLE2 não, devido ao isolamento
        tables = memory_db_session.query(MetadataTable).filter_by(connection_id=conn_id).all()
        
        assert len(tables) == 1
        assert tables[0].table_name == "table1"
        assert tables[0].schema_name == "hr"

        # A extração deve ter chamado o preload_metadata que fez o execute de ALL_TAB_COLUMNS
        assert any("ALL_TAB_COLUMNS" in str(call_args[0][0]).upper() for call_args in mock_conn.execute.call_args_list)
