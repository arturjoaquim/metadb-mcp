from abc import ABC, abstractmethod
from typing import List, Any, Optional
from sqlalchemy import create_engine


class BaseMetadataExtractor(ABC):
    def __init__(self, host: str, port: int, user: str, password: str, dbname: str):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.dbname = dbname

    @abstractmethod
    def build_connection_string(self) -> str:
        """Retorna a string de conexão sqlalchemy."""
        pass

    def get_engine(self) -> Any:
        conn_str = self.build_connection_string()
        return create_engine(conn_str)

    def test_connection(self) -> bool:
        engine = self.get_engine()
        try:
            with engine.connect():
                return True
        except Exception as e:
            print(f"Erro ao conectar: {e}")
            return False

    @abstractmethod
    def get_all_tables(self) -> List[str]:
        """Retorna a lista de todas as tabelas e views do banco de dados."""
        pass

    @abstractmethod
    def get_default_schema(self, inspector: Any) -> str:
        """Retorna o schema padrão a ser utilizado para inspeção de tabelas e views."""
        pass

    def get_table_comment(
        self, inspector: Any, table_name: str, schema: str
    ) -> Optional[str]:
        """Retorna o comentário da tabela."""
        try:
            comment_dict = inspector.get_table_comment(table_name, schema=schema)
            return comment_dict.get("text")
        except Exception as e:
            print(f"Erro ao obter comentário da tabela {table_name}: {e}")
            return None
