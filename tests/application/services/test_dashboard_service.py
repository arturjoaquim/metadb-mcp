from unittest.mock import MagicMock, patch
import pytest
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

    def test_get_tables_persists_connection(self):
        """get_tables deve salvar a conexão no DAO após sucesso no teste e listagem."""
        service = self._setup_service()
        
        # Mocks para o estado desbloqueado e sucesso na conexão
        service.is_unlocked = MagicMock(return_value=True)
        self.mock_sync_svc.test_connection.return_value = True
        self.mock_sync_svc.get_all_tables.return_value = ["table1"]
        
        # Mocks para o DAO e Sessão
        mock_session = MagicMock()
        self.mock_secure_conn.get_session.return_value = mock_session
        mock_conn_dao = MagicMock()
        self.mock_conn_dao_class.return_value = mock_conn_dao
        
        # Execução
        service.get_tables(
            db_type="oracle",
            host="localhost",
            port=1521,
            user="hr",
            password="pwd",
            dbname="xe",
            conn_name="MinhaConexao",
            driver_path="/opt/driver"
        )
        
        # Verificação: O DAO.save deve ter sido chamado com os parâmetros corretos
        mock_conn_dao.save.assert_called_once_with(
            name="MinhaConexao",
            db_type="oracle",
            host="localhost",
            port=1521,
            user="hr",
            dbname="xe",
            driver_path="/opt/driver"
        )
        
        # Verificação: A sessão foi fechada
        mock_session.close.assert_called_once()
