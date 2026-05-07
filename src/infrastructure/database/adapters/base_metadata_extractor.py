from abc import ABC, abstractmethod
from typing import List, Any, Optional, Dict
from sqlalchemy import create_engine, inspect, text
from .extracted_metadata import ExtractedColumn, ExtractedIndex, ExtractedConstraint


class BaseMetadataExtractor(ABC):
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        dbname: str,
        driver_path: Optional[str] = None,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.dbname = dbname
        self.driver_path = driver_path

    @abstractmethod
    def initialize_drivers(self) -> None:
        """Inicializa os drivers necessários para a conexão com o banco de dados."""
        pass

    @abstractmethod
    def build_connection_string(self) -> str:
        """Retorna a string de conexão sqlalchemy."""
        pass

    def get_engine(self) -> Any:
        self.initialize_drivers()
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

    def get_inspector(self) -> Any:
        """Retorna um objeto inspector do SQLAlchemy para o engine atual."""
        return inspect(self.get_engine())

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

    def extract_columns(
        self, table_name: str, schema: Optional[str] = None
    ) -> List[ExtractedColumn]:
        """Extrai e normaliza as colunas de uma tabela."""
        inspector = self.get_inspector()
        columns = inspector.get_columns(table_name, schema=schema)
        return [
            ExtractedColumn(
                name=str(col["name"]).lower(),
                data_type=str(col["type"]),
                is_nullable=bool(col.get("nullable", True)),
                default_value=str(col.get("default", ""))
                if col.get("default")
                else None,
                comment=col.get("comment").lower() if col.get("comment") else None,
            )
            for col in columns
        ]

    def extract_indexes(
        self, table_name: str, schema: Optional[str] = None
    ) -> List[ExtractedIndex]:
        """Extrai e normaliza os índices de uma tabela."""
        inspector = self.get_inspector()
        indexes = inspector.get_indexes(table_name, schema=schema)
        return [
            ExtractedIndex(
                name=str(idx["name"]).lower(),
                columns=[c.lower() for c in idx.get("column_names", [])],
                is_unique=bool(idx.get("unique", False)),
            )
            for idx in indexes
        ]

    def extract_pk_constraint(
        self, table_name: str, schema: Optional[str] = None
    ) -> Optional[ExtractedConstraint]:
        """Extrai a constraint de chave primária."""
        inspector = self.get_inspector()
        pk = inspector.get_pk_constraint(table_name, schema=schema)
        if pk and pk.get("constrained_columns"):
            return ExtractedConstraint(
                name=str(pk.get("name", "PK")).lower(),
                constraint_type="PRIMARY KEY",
                columns=[c.lower() for c in pk.get("constrained_columns", [])],
            )
        return None

    def extract_foreign_keys(
        self, table_name: str, schema: Optional[str] = None
    ) -> List[ExtractedConstraint]:
        """Extrai as constraints de chave estrangeira."""
        inspector = self.get_inspector()
        fks = inspector.get_foreign_keys(table_name, schema=schema)
        return [
            ExtractedConstraint(
                name=str(fk.get("name", "FK")).lower(),
                constraint_type="FOREIGN KEY",
                columns=[c.lower() for c in fk.get("constrained_columns", [])],
                ref_table=str(fk.get("referred_table")).lower()
                if fk.get("referred_table")
                else None,
                ref_columns=[c.lower() for c in fk.get("referred_columns", [])],
            )
            for fk in fks
        ]

    def extract_sample_rows(
        self, table_name: str, schema: Optional[str] = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Extrai uma amostra de dados da tabela."""
        engine = self.get_engine()
        samples = []
        try:
            with engine.connect() as db_conn:
                stmt = text(
                    f"SELECT * FROM {schema}.{table_name}"
                    if schema
                    else f"SELECT * FROM {table_name}"
                )
                result = db_conn.execute(stmt)
                rows = result.fetchmany(limit)
                keys = result.keys()

                for row in rows:
                    row_dict = {
                        str(k).lower(): (
                            v.decode("utf-8", errors="replace")
                            if isinstance(v, bytes)
                            else v
                        )
                        for k, v in zip(keys, row)
                    }
                    samples.append(row_dict)
        except Exception as e:
            print(f"Erro ao obter amostras da tabela {table_name}: {e}")
        return samples
