import os
import pytest
from pathlib import Path
from unittest.mock import patch

# Ajusta o DB_FILE_PATH para os testes para não sobrescrever o real
import infrastructure.database.secure_connection as secure_connection_module
secure_connection_module.DB_FILE_PATH = Path("test_mcp_cache.db")

from infrastructure.security.auth_service import AuthService, AuthenticationError
from infrastructure.database import secure_connection


@pytest.fixture(autouse=True)
def cleanup():
    test_db = Path("test_mcp_cache.db")
    
    with patch("infrastructure.security.auth_service.DB_FILE_PATH", test_db), \
         patch("infrastructure.database.secure_connection.DB_FILE_PATH", test_db):
        # Antes de cada teste
        if test_db.exists():
            os.remove(test_db)
        secure_connection.lock()
        
        yield
        
        # Depois de cada teste
        if test_db.exists():
            os.remove(test_db)
        secure_connection.lock()


def test_auth_flow_success():
    auth = AuthService(secure_connection)
    
    # Mock do keyring para não sujar o SO
    mock_storage = {}
    
    def mock_set_password(service, username, password):
        mock_storage[username] = password
        
    def mock_get_password(service, username):
        return mock_storage.get(username)
        
    def mock_delete_password(service, username):
        if username in mock_storage:
            del mock_storage[username]
    
    with patch("infrastructure.security.auth_service.keyring.set_password", side_effect=mock_set_password), \
         patch("infrastructure.security.auth_service.keyring.get_password", side_effect=mock_get_password), \
         patch("infrastructure.security.auth_service.keyring.delete_password", side_effect=mock_delete_password):
        
        # 1. Register
        token1 = auth.register("testuser", "senha123")
        assert token1 is not None
        assert auth.database_exists()
        assert secure_connection.is_unlocked
        
        # Logout
        secure_connection.lock()
        assert not secure_connection.is_unlocked
        
        # 2. Login
        token2 = auth.login("testuser", "senha123")
        assert token2 is not None
        assert secure_connection.is_unlocked
        
        # 3. Verify
        payload = auth.verify_token(token2)
        assert payload is not None
        assert payload["sub"] == "testuser"


def test_auth_flow_wrong_password():
    auth = AuthService(secure_connection)
    mock_storage = {}
    
    def mock_set_password(service, username, password):
        mock_storage[username] = password
        
    def mock_get_password(service, username):
        return mock_storage.get(username)
    
    with patch("infrastructure.security.auth_service.keyring.set_password", side_effect=mock_set_password), \
         patch("infrastructure.security.auth_service.keyring.get_password", side_effect=mock_get_password):
        
        # Register
        auth.register("testuser", "senha123")
        secure_connection.lock()
        
        # Login wrong password
        with pytest.raises(AuthenticationError):
            auth.login("testuser", "senha_errada")
        
        assert not secure_connection.is_unlocked
