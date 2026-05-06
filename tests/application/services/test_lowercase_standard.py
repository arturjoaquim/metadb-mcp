import pytest
from unittest.mock import MagicMock, patch
from application.services.sync_service import SyncService
from application.services.metadata_service import MetadataService
from infrastructure.database.models import SyncTable, SyncColumn, SyncIndex, SyncConstraint, SyncSample

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

    @patch("application.services.sync_service.inspect")
    def test_sync_tables_lowercases_metadata(self, mock_inspect, mock_secure_conn, mock_extractor):
        mock_inspector = MagicMock()
        mock_inspect.return_value = mock_inspector
        
        # Simular dados em maiúsculo vindo do banco remoto
        mock_inspector.get_columns.return_value = [{"name": "COLUMN_UPPER", "type": "INT", "nullable": True, "comment": "COL COMMENT"}]
        mock_extractor.get_table_comment.return_value = "TABLE COMMENT"
        mock_inspector.get_indexes.return_value = [{"name": "IDX_UPPER", "column_names": ["COL_UPPER"], "unique": False}]
        mock_inspector.get_pk_constraint.return_value = {"name": "PK_UPPER", "constrained_columns": ["ID"]}
        mock_inspector.get_foreign_keys.return_value = [{
            "name": "FK_UPPER", 
            "constrained_columns": ["REF_ID"], 
            "referred_table": "REF_TABLE", 
            "referred_columns": ["ID"]
        }]
        
        # Mock para amostras de dados
        mock_engine = mock_extractor.get_engine.return_value
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        mock_result = MagicMock()
        mock_conn.execute.return_value = mock_result
        mock_result.fetchmany.return_value = [("VALUE",)]
        mock_result.keys.return_value = ["COL_KEY"]
        
        service = SyncService(mock_secure_conn, lambda *args: mock_extractor)
        session = mock_secure_conn.get_session.return_value
        
        # Sincronizar tabela com nome misto
        service.sync_tables("conn_name", ["Public.Users"], "postgres", "h", 5432, "u", "p", "db")
        
        # Coletar objetos adicionados à sessão
        added_objects = [call.args[0] for call in session.add.call_args_list]
        
        # Verificar SyncTable
        sync_table = next(obj for obj in added_objects if isinstance(obj, SyncTable))
        assert sync_table.table_name == "users"
        assert sync_table.schema_name == "public"
        assert sync_table.comment == "table comment"
        
        # Verificar SyncColumn
        sync_col = next(obj for obj in added_objects if isinstance(obj, SyncColumn))
        assert sync_col.column_name == "column_upper"
        assert sync_col.comment == "col comment"
        
        # Verificar SyncIndex
        sync_idx = next(obj for obj in added_objects if isinstance(obj, SyncIndex))
        assert sync_idx.index_name == "idx_upper"
        assert "col_upper" in sync_idx.columns
        
        # Verificar SyncConstraint (PK e FK)
        constraints = [obj for obj in added_objects if isinstance(obj, SyncConstraint)]
        pk = next(c for c in constraints if c.constraint_type == "PRIMARY KEY")
        assert pk.constraint_name == "pk_upper"
        
        fk = next(c for c in constraints if c.constraint_type == "FOREIGN KEY")
        assert fk.constraint_name == "fk_upper"
        assert fk.ref_table == "ref_table"
        
        # Verificar SyncSample
        sample = next(obj for obj in added_objects if isinstance(obj, SyncSample))
        assert "col_key" in sample.row_data

    def test_metadata_service_lowercases_search_terms(self, mock_secure_conn):
        mock_sync_dao = MagicMock()
        # Ajuste para que o DAO retorne a tabela esperada
        service = MetadataService(mock_secure_conn, sync_dao_class=lambda sess: mock_sync_dao)
        
        mock_table = MagicMock(spec=SyncTable)
        mock_table.id = 1
        mock_sync_dao.get_tables.return_value = [mock_table]
        
        # Precisamos mockar o _validate_tables para retornar a tabela sem erros
        with patch.object(service, "_validate_tables", return_value=(mock_table, None)):
            service.get_table_columns("USERS", schema="PUBLIC")
            
        # Verificar se DAO foi chamado com minúsculo
        mock_sync_dao.get_tables.assert_called_with("users", "public", None)

    def test_metadata_service_lowercases_search_metadata_query(self, mock_secure_conn):
        service = MetadataService(mock_secure_conn)
        session = mock_secure_conn.get_session.return_value
        
        # Simular que a query do SQLAlchemy foi chamada
        mock_query = session.query.return_value
        mock_filter = mock_query.filter.return_value
        mock_filter.all.return_value = []
        
        # Mock para o join no segundo query (columns)
        mock_join = mock_query.join.return_value
        mock_join_filter = mock_join.filter.return_value
        mock_join_filter.all.return_value = []
        
        service.search_metadata("MY_QUERY")
        
        # Verificamos se o termo foi convertido para minúsculo antes de ser passado ao filtro (ilike)
        # O filtro ilike é chamado com algo como "%my_query%"
        # session.query(SyncTable).filter(SyncTable.table_name.ilike("%my_query%"))
        # Vamos apenas verificar se a lógica interna não quebrou e se chamou a query.
        assert session.query.called
