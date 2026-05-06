import json
import sqlite3
import os
import pytest
from typing import Generator

@pytest.fixture
def temp_db() -> Generator[sqlite3.Connection, None, None]:
    db_path: str = "test_encoding_integration.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    conn: sqlite3.Connection = sqlite3.connect(db_path)
    yield conn
    conn.close()
    if os.path.exists(db_path):
        os.remove(db_path)

def test_json_encoding_persistence(temp_db: sqlite3.Connection) -> None:
    """Valida se o JSON com caracteres especiais é persistido corretamente sem escapes ASCII."""
    cursor: sqlite3.Cursor = temp_db.cursor()
    cursor.execute("CREATE TABLE test (data TEXT)")
    
    data: dict = {"key": "ação", "nested": {"val": "coração"}}
    
    # Simula a nova implementação com ensure_ascii=False
    json_data_utf8: str = json.dumps(data, ensure_ascii=False)
    
    cursor.execute("INSERT INTO test (data) VALUES (?)", (json_data_utf8,))
    temp_db.commit()
    
    cursor.execute("SELECT data FROM test")
    row = cursor.fetchone()
    
    # O dado recuperado deve ser idêntico ao original (string UTF-8, não escaped)
    assert row[0] == json_data_utf8
    
    # Verifica se o conteúdo decodificado é o dicionário original
    decoded_data: dict = json.loads(row[0])
    assert decoded_data == data
    assert "ação" in row[0]
    assert "\\u00e7" not in row[0]
