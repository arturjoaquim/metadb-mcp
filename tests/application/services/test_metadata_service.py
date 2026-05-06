import pytest
from unittest.mock import MagicMock
from application.services.metadata_service import MetadataService
from infrastructure.database.models import MetadataTable

@pytest.fixture
def metadata_service() -> MetadataService:
    secure_conn = MagicMock()
    # Mocking the session and query chain
    session = MagicMock()
    secure_conn.get_session.return_value = session
    return MetadataService(secure_conn)

def test_get_table_description_found(metadata_service: MetadataService) -> None:
    # Setup
    mock_table = MetadataTable(table_name="users", schema_name="public", comment="Tabela de usuários")
    metadata_service._metadata_dao_class = MagicMock()
    metadata_service._metadata_dao_class.return_value.get_tables.return_value = [mock_table]
    
    # Execute
    result = metadata_service.get_table_description("users")
    
    # Assert
    assert "Descrição da tabela public.users:" in result
    assert "- Comentário: Tabela de usuários" in result
    assert "- Sensível: NÃO" in result

def test_search_metadata_unified(metadata_service: MetadataService) -> None:
    """Valida a busca unificada por nome e comentário."""
    # Setup
    mock_table = MetadataTable(table_name="users", schema_name="public", comment="Dados de clientes")
    session = metadata_service._secure_conn.get_session()
    # Mock for table search (matches both name and comment)
    session.query.return_value.filter.return_value.all.side_effect = [[mock_table], []]
    
    # Execute
    result = metadata_service.search_metadata("user")
    
    # Assert
    assert "Tabelas encontradas (nome ou comentário):" in result
    assert "public.users: Dados de clientes" in result

def test_get_domain_context_sensitive_protection(metadata_service: MetadataService) -> None:
    """Valida que get_domain_context protege tabelas marcadas como sensíveis."""
    # Setup
    mock_table = MetadataTable(table_name="sensitive", schema_name="public", is_sensitive=1)
    metadata_service._metadata_dao_class = MagicMock()
    metadata_service._metadata_dao_class.return_value.get_tables.return_value = [mock_table]
    
    # Execute
    result = metadata_service.get_domain_context("sensitive")
    
    # Assert
    assert "está marcada como sensível" in result
    assert "não foram coletadas" in result
