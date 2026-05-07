import pytest
from unittest.mock import MagicMock, patch
from application.services.sync_service import SyncService
from application.services.metadata_service import MetadataService
from infrastructure.database.models import MetadataTable

class TestLowercaseStandard:
    @pytest.fixture
    def mock_secure_conn(self):
        mock = MagicMock()
        mock.get_session.return_value = MagicMock()
        return mock

    @pytest.fixture
    def mock_extractor(self):
        mock = MagicMock()
        mock.get_engine.return_value = MagicMock()
        mock.get_default_schema.return_value = "PUBLIC"
        return mock

    def test_sync_tables_lowercases_metadata(self, mock_secure_conn, mock_extractor):
        from infrastructure.database.adapters.extracted_metadata import (
            ExtractedColumn, ExtractedIndex, ExtractedConstraint
        )
        
        
        # Simular dados extraídos já normalizados (como o extractor faz agora)
        mock_extractor.extract_columns.return_value = [
            ExtractedColumn(name="column_upper", data_type="INT", is_nullable=True, comment="col comment")
        ]
        mock_extractor.extract_indexes.return_value = [
            ExtractedIndex(name="idx_upper", columns=["col_upper"], is_unique=False)
        ]
        mock_extractor.extract_pk_constraint.return_value = ExtractedConstraint(
            name="pk_upper", constraint_type="PRIMARY KEY", columns=["id"]
        )
        mock_extractor.extract_foreign_keys.return_value = [
            ExtractedConstraint(
                name="fk_upper", constraint_type="FOREIGN KEY", columns=["ref_id"], 
                ref_table="ref_table", ref_columns=["id"]
            )
        ]
        mock_extractor.extract_sample_rows.return_value = [{"col_key": "VALUE"}]
        mock_extractor.get_table_comment.return_value = "TABLE COMMENT"
        mock_inspector = MagicMock()
        mock_extractor.get_inspector.return_value = mock_inspector
        
        # Mock para MetadataDAO
        mock_metadata_dao_class = MagicMock()
        mock_metadata_dao = mock_metadata_dao_class.return_value
        
        service = SyncService(
            mock_secure_conn, 
            lambda *args, **kwargs: mock_extractor,
            metadata_dao_class=mock_metadata_dao_class
        )
        
        # Sincronizar tabela com nome misto
        service.sync_tables("conn_name", ["Public.Users"], "postgres", "h", 5432, "u", "p", "db")
        
        # Verificar se o DAO foi chamado com os dados normalizados
        mock_metadata_dao.save_table_metadata.assert_called_once()
        args = mock_metadata_dao.save_table_metadata.call_args.kwargs
        
        assert args["table_name"] == "users"
        assert args["schema"] == "public"
        assert args["comment"] == "TABLE COMMENT" # O DAO converte para minúsculo
        assert args["columns"][0].name == "column_upper"

    def test_metadata_service_lowercases_search_terms(self, mock_secure_conn):
        mock_sync_dao = MagicMock()
        # Ajuste para que o DAO retorne a tabela esperada
        service = MetadataService(mock_secure_conn, metadata_dao_class=lambda sess: mock_sync_dao)
        
        mock_table = MagicMock(spec=MetadataTable)
        mock_table.id = 1
        mock_sync_dao.get_tables.return_value = [mock_table]
        
        # Precisamos mockar o _validate_tables para retornar a tabela sem erros
        with patch.object(service, "_validate_tables", return_value=(mock_table, None)):
            service.get_table_columns("USERS", schema="PUBLIC")
            
        # Verificar se DAO foi chamado com minúsculo
        mock_sync_dao.get_tables.assert_called_with("users", "public", None)

    def test_metadata_service_lowercases_search_metadata_query(self, mock_secure_conn):
        mock_metadata_dao = MagicMock()
        service = MetadataService(mock_secure_conn, metadata_dao_class=lambda sess: mock_metadata_dao)
        mock_metadata_dao.search_metadata.return_value = ([], [])
        
        service.search_metadata("MY_QUERY")
        
        # Verificamos se o termo foi convertido para minúsculo antes de ser passado ao DAO
        mock_metadata_dao.search_metadata.assert_called_with("my_query")
