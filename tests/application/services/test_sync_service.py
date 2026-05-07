import pytest
from unittest.mock import MagicMock
from application.services.sync_service import SyncService

class TestSyncService:
    @pytest.fixture
    def mock_secure_conn(self):
        mock = MagicMock()
        mock.get_session.return_value = MagicMock()
        return mock

    @pytest.fixture
    def mock_extractor(self):
        mock = MagicMock()
        mock.get_engine.return_value = MagicMock()
        mock.get_default_schema.return_value = "public"
        mock.get_inspector.return_value = MagicMock()
        return mock

    def test_sync_tables_skips_samples_for_sensitive_tables(self, mock_secure_conn, mock_extractor):
        # Setup
        mock_metadata_dao_class = MagicMock()
        mock_metadata_dao = mock_metadata_dao_class.return_value
        
        service = SyncService(
            mock_secure_conn, 
            lambda *args, **kwargs: mock_extractor,
            metadata_dao_class=mock_metadata_dao_class
        )
        
        # Sincronizar uma tabela sensível e uma normal
        sensitive_table = "public.sensitive"
        normal_table = "public.normal"
        
        service.sync_tables(
            "conn", [sensitive_table, normal_table], "postgres", "h", 5432, "u", "p", "db",
            sensitive_tables=[sensitive_table],
            sample_size=5
        )
        
        # Verificar se extract_sample_rows foi chamado apenas para a tabela normal
        # O extractor é chamado com orig_table_name, não com o nome completo
        mock_extractor.extract_sample_rows.assert_called_once_with("normal", schema="public", limit=5)
        
        # Verificar se save_table_metadata foi chamado com is_sensitive correto
        assert mock_metadata_dao.save_table_metadata.call_count == 2
        
        # Chamada para a tabela sensível
        sensitive_call = [c for c in mock_metadata_dao.save_table_metadata.call_args_list if c.kwargs["table_name"] == "sensitive"][0]
        assert sensitive_call.kwargs["is_sensitive"] is True
        assert sensitive_call.kwargs["samples"] == []
        
        # Chamada para a tabela normal
        normal_call = [c for c in mock_metadata_dao.save_table_metadata.call_args_list if c.kwargs["table_name"] == "normal"][0]
        assert normal_call.kwargs["is_sensitive"] is False
        assert normal_call.kwargs["sample_size"] == 5

    def test_sync_tables_uses_default_sample_size(self, mock_secure_conn, mock_extractor):
        mock_metadata_dao_class = MagicMock()
        service = SyncService(
            mock_secure_conn, 
            lambda *args, **kwargs: mock_extractor,
            metadata_dao_class=mock_metadata_dao_class
        )
        
        service.sync_tables("conn", ["users"], "postgres", "h", 5432, "u", "p", "db")
        
        mock_extractor.extract_sample_rows.assert_called_once_with("users", schema="public", limit=10)

    def test_sync_tables_propagates_driver_path_to_dao(self, mock_secure_conn, mock_extractor):
        """Verifica que driver_path é repassado corretamente pela factory e ao DAO."""
        mock_conn_dao_class = MagicMock()
        mock_conn_dao = mock_conn_dao_class.return_value
        mock_conn_dao.save.return_value = 1

        mock_metadata_dao_class = MagicMock()

        captured_kwargs = {}
        def factory_spy(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return mock_extractor

        service = SyncService(
            mock_secure_conn,
            factory_spy,
            connection_dao_class=mock_conn_dao_class,
            metadata_dao_class=mock_metadata_dao_class,
        )

        service.sync_tables(
            "conn", ["users"], "oracle", "h", 1521, "u", "p", "orcl",
            driver_path="/opt/oracle/instantclient",
        )

        # Verificar que a factory recebeu driver_path
        assert captured_kwargs.get("driver_path") == "/opt/oracle/instantclient"

        # Verificar que o DAO recebeu driver_path
        mock_conn_dao.save.assert_called_once_with(
            "conn", "oracle", "h", 1521, "u", "orcl",
            driver_path="/opt/oracle/instantclient",
        )

    def test_sync_tables_is_case_insensitive_for_sensitive_tables(self, mock_secure_conn, mock_extractor):
        """Verifica que a identificação de tabelas sensíveis ignora a caixa."""
        mock_metadata_dao_class = MagicMock()
        mock_metadata_dao = mock_metadata_dao_class.return_value
        
        service = SyncService(
            mock_secure_conn, 
            lambda *args, **kwargs: mock_extractor,
            metadata_dao_class=mock_metadata_dao_class
        )
        
        # Nome original com maiúsculo (como vem do Oracle)
        # Marcado como sensível em minúsculo (como o frontend pode enviar)
        original_table = "PUBLIC.EMPLOYEES"
        sensitive_marker = "public.employees"
        
        service.sync_tables(
            "conn", [original_table], "oracle", "h", 1521, "u", "p", "db",
            sensitive_tables=[sensitive_marker]
        )
        
        # Deve ter identificado como sensível apesar da diferença de caixa
        call = mock_metadata_dao.save_table_metadata.call_args
        assert call.kwargs["is_sensitive"] is True
        # E deve ter salvo como minúsculo no cache
        assert call.kwargs["table_name"] == "employees"
        assert call.kwargs["schema"] == "public"
