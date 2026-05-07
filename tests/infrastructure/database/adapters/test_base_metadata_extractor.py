import pytest
from unittest.mock import MagicMock, patch
from infrastructure.database.adapters.base_metadata_extractor import BaseMetadataExtractor

class ConcreteExtractor(BaseMetadataExtractor):
    def initialize_drivers(self) -> None:
        pass
    def build_connection_string(self) -> str:
        return "sqlite:///:memory:"
    def get_all_tables(self):
        return []
    def get_default_schema(self, inspector):
        return "public"

@pytest.fixture
def extractor():
    return ConcreteExtractor("host", 5432, "user", "pass", "dbname")

@patch("infrastructure.database.adapters.base_metadata_extractor.inspect")
def test_extract_columns(mock_inspect, extractor):
    mock_inspector = MagicMock()
    mock_inspect.return_value = mock_inspector
    mock_inspector.get_columns.return_value = [
        {"name": "ID", "type": "INTEGER", "nullable": False, "default": "nextval", "comment": "Primary Key"},
        {"name": "NAME", "type": "VARCHAR(255)", "nullable": True, "comment": None}
    ]
    
    cols = extractor.extract_columns("users", schema="public")
    
    assert len(cols) == 2
    assert cols[0].name == "id"
    assert cols[0].data_type == "INTEGER"
    assert cols[0].is_nullable is False
    assert cols[0].default_value == "nextval"
    assert cols[0].comment == "primary key"
    
    assert cols[1].name == "name"
    assert cols[1].is_nullable is True
    assert cols[1].comment is None

@patch("infrastructure.database.adapters.base_metadata_extractor.inspect")
def test_extract_indexes(mock_inspect, extractor):
    mock_inspector = MagicMock()
    mock_inspect.return_value = mock_inspector
    mock_inspector.get_indexes.return_value = [
        {"name": "IDX_NAME", "column_names": ["NAME"], "unique": True}
    ]
    
    idxs = extractor.extract_indexes("users", schema="public")
    
    assert len(idxs) == 1
    assert idxs[0].name == "idx_name"
    assert idxs[0].columns == ["name"]
    assert idxs[0].is_unique is True

@patch("infrastructure.database.adapters.base_metadata_extractor.inspect")
def test_extract_pk_constraint(mock_inspect, extractor):
    mock_inspector = MagicMock()
    mock_inspect.return_value = mock_inspector
    mock_inspector.get_pk_constraint.return_value = {
        "name": "PK_USERS", "constrained_columns": ["ID"]
    }
    
    pk = extractor.extract_pk_constraint("users", schema="public")
    
    assert pk.name == "pk_users"
    assert pk.constraint_type == "PRIMARY KEY"
    assert pk.columns == ["id"]

@patch("infrastructure.database.adapters.base_metadata_extractor.inspect")
def test_extract_foreign_keys(mock_inspect, extractor):
    mock_inspector = MagicMock()
    mock_inspect.return_value = mock_inspector
    mock_inspector.get_foreign_keys.return_value = [
        {
            "name": "FK_USERS_DEPT",
            "constrained_columns": ["DEPT_ID"],
            "referred_table": "DEPARTMENTS",
            "referred_columns": ["ID"]
        }
    ]
    
    fks = extractor.extract_foreign_keys("users", schema="public")
    
    assert len(fks) == 1
    assert fks[0].name == "fk_users_dept"
    assert fks[0].ref_table == "departments"
    assert fks[0].ref_columns == ["id"]
