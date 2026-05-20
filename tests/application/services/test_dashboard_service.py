from unittest.mock import MagicMock
from application.services.dashboard_service import DashboardService


class TestDashboardService:
    """Testes para o DashboardService."""

    def _setup_service(self):
        self.mock_secure_conn = MagicMock()
        self.mock_auth_svc = MagicMock()
        self.mock_sync_svc = MagicMock()
        self.mock_conn_dao_class = MagicMock()
        self.mock_metadata_dao_class = MagicMock()
        
        return DashboardService(
            secure_conn=self.mock_secure_conn,
            auth_svc=self.mock_auth_svc,
            sync_svc=self.mock_sync_svc,
            connection_dao_class=self.mock_conn_dao_class,
            metadata_dao_class=self.mock_metadata_dao_class,
        )

    def test_get_tables_returns_tables_and_synced_tables(self):
        """get_tables deve retornar as tabelas remotas e as tabelas já sincronizadas."""
        service = self._setup_service()
        
        # Mocks para o estado desbloqueado e sucesso na conexão
        service.is_unlocked = MagicMock(return_value=True)
        self.mock_sync_svc.test_connection.return_value = True
        self.mock_sync_svc.get_all_tables.return_value = ["table1"]
        
        # Mocks para o DAO e Sessão
        mock_session = MagicMock()
        self.mock_secure_conn.get_session.return_value = mock_session
        mock_metadata_dao = MagicMock()
        mock_metadata_dao.get_synced_tables_by_connection_name.return_value = ["table1"]
        self.mock_metadata_dao_class.return_value = mock_metadata_dao
        
        # Execução
        res = service.get_tables(
            db_type="oracle",
            host="localhost",
            port=1521,
            user="hr",
            password="pwd",
            dbname="xe",
            conn_name="MinhaConexao",
            driver_path="/opt/driver"
        )
        
        # Verificação
        assert res == {"tables": ["table1"], "synced_tables": ["table1"]}
        mock_metadata_dao.get_synced_tables_by_connection_name.assert_called_once_with("MinhaConexao")
        mock_session.close.assert_called_once()
