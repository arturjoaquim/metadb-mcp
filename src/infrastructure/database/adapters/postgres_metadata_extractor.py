import urllib.parse
from typing import List, Any
from sqlalchemy import inspect
from .base_metadata_extractor import BaseMetadataExtractor


class PostgresMetadataExtractor(BaseMetadataExtractor):
    def build_connection_string(self) -> str:
        encoded_password = urllib.parse.quote_plus(self.password)
        encoded_user = urllib.parse.quote_plus(self.user)
        return f"postgresql+psycopg2://{encoded_user}:{encoded_password}@{self.host}:{self.port}/{self.dbname}?client_encoding=utf8"

    def get_default_schema(self, inspector: Any) -> str:
        return inspector.default_schema_name

    def get_all_tables(self) -> List[str]:
        engine = self.get_engine()
        inspector = inspect(engine)

        tables: List[str] = []
        try:
            schemas = inspector.get_schema_names()
            system_schemas = {"information_schema", "pg_catalog", "pg_toast"}
            for sch in schemas:
                if sch not in system_schemas and not sch.startswith("pg_"):
                    for tbl in inspector.get_table_names(schema=sch):
                        tables.append(f"{sch}.{tbl}")
        except Exception as e:
            print(f"Erro ao obter tabelas do postgresql: {e}")
            tables = inspector.get_table_names()
        return tables
