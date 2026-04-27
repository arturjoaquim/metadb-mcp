import urllib.parse
from typing import List, Any
from sqlalchemy import inspect
from .base_adapter import BaseDBAdapter


class OracleAdapter(BaseDBAdapter):
    def build_connection_string(self) -> str:
        encoded_password = urllib.parse.quote_plus(self.password)
        encoded_user = urllib.parse.quote_plus(self.user)
        return f"oracle+oracledb://{encoded_user}:{encoded_password}@{self.host}:{self.port}/?service_name={self.dbname}"

    def get_default_schema(self, inspector: Any) -> str:
        return self.user.upper()

    def get_all_tables(self) -> List[str]:
        engine = self.get_engine()
        inspector = inspect(engine)

        tables: List[str] = []
        try:
            schema = self.user.upper()
            for tbl in inspector.get_table_names(schema=schema):
                tables.append(f"{schema}.{tbl}" if schema else tbl)
            if not tables:
                for tbl in inspector.get_table_names():
                    tables.append(tbl)
        except Exception as e:
            print(f"Erro ao obter tabelas do oracle: {e}")
            tables = inspector.get_table_names()
        return tables
