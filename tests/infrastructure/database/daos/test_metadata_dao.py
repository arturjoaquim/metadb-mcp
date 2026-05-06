import pytest
import json
from unittest.mock import MagicMock
from infrastructure.database.daos.metadata_dao import MetadataDAO
from infrastructure.database.adapters.extracted_metadata import (
    ExtractedColumn,
    ExtractedIndex,
    ExtractedConstraint,
)
from infrastructure.database.models import MetadataTable, MetadataColumn

@pytest.fixture
def session():
    return MagicMock()

@pytest.fixture
def dao(session):
    return MetadataDAO(session)

def test_save_table_metadata(dao, session):
    # Setup
    conn_id = 1
    table_name = "users"
    schema = "public"
    comment = "User Table"
    columns = [ExtractedColumn("id", "INT", False, None, "PK")]
    indexes = [ExtractedIndex("idx_id", ["id"], True)]
    constraints = [ExtractedConstraint("pk_id", "PRIMARY KEY", ["id"])]
    samples = [{"id": 1, "name": "Test"}]
    
    # Mock get_existing_table to return None
    dao.get_existing_table = MagicMock(return_value=None)
    
    # Execute
    metadata_table = dao.save_table_metadata(
        conn_id, table_name, schema, comment, columns, indexes, constraints, samples
    )
    
    # Assert
    assert metadata_table.table_name == "users"
    assert metadata_table.comment == "user table"
    
    # Check calls to session.add
    # MetadataTable + MetadataColumn + MetadataIndex + MetadataConstraint + MetadataSample = 5 adds
    assert session.add.call_count == 5
    
    added_objs = [call.args[0] for call in session.add.call_args_list]
    
    assert any(isinstance(obj, MetadataTable) for obj in added_objs)
    assert any(isinstance(obj, MetadataColumn) for obj in added_objs)
    
    # Verify JSON serialization in added objects
    # Note: we need to find the specific objects to check their attributes
    for obj in added_objs:
        if isinstance(obj, MetadataColumn):
            assert obj.column_name == "id"
            assert obj.comment == "PK"
        elif hasattr(obj, "columns") and isinstance(obj.columns, str):
             # MetadataIndex or MetadataConstraint
             # The DAO uses json.dumps
             json.loads(obj.columns)
