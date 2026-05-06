"""Serviço de metadados do MetaDB MCP.

Este módulo encapsula as operações de banco de dados relacionadas aos metadados
sincronizados, fornecendo uma interface para a camada de controladores (MCP).
"""

from typing import Any, List, Optional, Tuple, Type
from infrastructure.database.secure_connection import SecureConnectionManager
from infrastructure.database.daos.metadata_dao import MetadataDAO
from infrastructure.database.daos.connection_dao import ConnectionDAO
from infrastructure.database.models import (
    MetadataTable,
)


class MetadataServiceError(Exception):
    """Exceção base para erros no MetadataService."""
    pass


class MetadataService:
    """Serviço responsável por coordenar buscas e consultas de metadados.
    
    Abstrai o acesso aos modelos SQLAlchemy do cache local.
    """

    def __init__(
        self,
        secure_conn: SecureConnectionManager,
        metadata_dao_class: Type[MetadataDAO] = MetadataDAO,
        connection_dao_class: Type[ConnectionDAO] = ConnectionDAO,
    ) -> None:
        self._secure_conn = secure_conn
        self._metadata_dao_class = metadata_dao_class
        self._connection_dao_class = connection_dao_class

    def is_database_unlocked(self) -> bool:
        """Verifica se o banco de dados está inicializado e desbloqueado."""
        return bool(self._secure_conn.is_unlocked)

    def _validate_tables(
        self, session: Any, tables: List[MetadataTable], table_name: str
    ) -> Tuple[Optional[MetadataTable], Optional[str]]:
        if not tables:
            return (
                None,
                f"Tabela '{table_name}' não encontrada no cache com os filtros fornecidos.",
            )
        if len(tables) > 1:
            options = []
            conn_dao = self._connection_dao_class(session)
            for t in tables:
                conn = conn_dao.get_by_id(int(str(t.connection_id)))
                dbname = conn.dbname if conn else "Desconhecido"
                options.append(f"schema: '{t.schema_name}', dbname: '{dbname}'")
            return (
                None,
                f"Ambiguidade detectada. A tabela '{table_name}' existe em múltiplos contextos. Por favor refine sua busca passando os argumentos 'schema' e/ou 'dbname'. Opções disponíveis:\n"
                + "\n".join(f"- {opt}" for opt in options),
            )
        return tables[0], None

    def list_sync_tables(self) -> str:
        """Retorna uma lista formatada de todas as tabelas sincronizadas."""
        if not self.is_database_unlocked():
            raise MetadataServiceError("Banco bloqueado.")
            
        session = self._secure_conn.get_session()
        try:
            tables = self._metadata_dao_class(session).get_all_tables()
            if not tables:
                return "Nenhuma tabela sincronizada no momento."

            result = [f"- {t.schema_name}.{t.table_name}" for t in tables]
            return "Tabelas sincronizadas:\n" + "\n".join(result)
        finally:
            session.close()

    def get_table_columns(self, table_name: str, schema: Optional[str] = None, dbname: Optional[str] = None) -> str:
        """Retorna as colunas de uma tabela formatadas."""
        table_name = table_name.lower()
        if schema:
            schema = schema.lower()
            
        session = self._secure_conn.get_session()
        try:
            metadata_dao = self._metadata_dao_class(session)
            tables = metadata_dao.get_tables(table_name, schema, dbname)
            table, error_msg = self._validate_tables(session, tables, table_name)
            if error_msg or not table:
                return str(error_msg)

            columns = metadata_dao.get_columns_by_table_id(int(str(table.id)))
            result = [f"Colunas de {table_name}:"]
            for col in columns:
                nullable = "NULL" if col.is_nullable else "NOT NULL"
                result.append(f"- {col.column_name}: {col.data_type} ({nullable})")
            return "\n".join(result)
        finally:
            session.close()

    def get_table_indexes(self, table_name: str, schema: Optional[str] = None, dbname: Optional[str] = None) -> str:
        """Retorna os índices de uma tabela formatados."""
        table_name = table_name.lower()
        if schema:
            schema = schema.lower()
            
        session = self._secure_conn.get_session()
        try:
            metadata_dao = self._metadata_dao_class(session)
            tables = metadata_dao.get_tables(table_name, schema, dbname)
            table, error_msg = self._validate_tables(session, tables, table_name)
            if error_msg or not table:
                return str(error_msg)

            indexes = metadata_dao.get_indexes_by_table_id(int(str(table.id)))
            if not indexes:
                return f"Nenhum índice encontrado para '{table_name}'."

            result = [f"Índices de {table_name}:"]
            for idx in indexes:
                unique_str = "ÚNICO" if idx.is_unique else "NÃO ÚNICO"
                result.append(f"- {idx.index_name} ({unique_str}): colunas = {idx.columns}")
            return "\n".join(result)
        finally:
            session.close()

    def get_table_constraints(self, table_name: str, schema: Optional[str] = None, dbname: Optional[str] = None) -> str:
        """Retorna as constraints de uma tabela formatadas."""
        table_name = table_name.lower()
        if schema:
            schema = schema.lower()
            
        session = self._secure_conn.get_session()
        try:
            metadata_dao = self._metadata_dao_class(session)
            tables = metadata_dao.get_tables(table_name, schema, dbname)
            table, error_msg = self._validate_tables(session, tables, table_name)
            if error_msg or not table:
                return str(error_msg)

            constraints = metadata_dao.get_constraints_by_table_id(int(str(table.id)))
            if not constraints:
                return f"Nenhuma constraint encontrada para '{table_name}'."

            result = [f"Constraints de {table_name}:"]
            for const in constraints:
                if const.constraint_type == "FOREIGN KEY":
                    result.append(
                        f"- {const.constraint_name} ({const.constraint_type}): {const.columns} referenciando {const.ref_table}({const.ref_columns})"
                    )
                else:
                    result.append(
                        f"- {const.constraint_name} ({const.constraint_type}): {const.columns}"
                    )
            return "\n".join(result)
        finally:
            session.close()

    def get_domain_context(self, table_name: str, schema: Optional[str] = None, dbname: Optional[str] = None) -> str:
        """Retorna amostras de dados de uma tabela formatadas."""
        table_name = table_name.lower()
        if schema:
            schema = schema.lower()
            
        session = self._secure_conn.get_session()
        try:
            metadata_dao = self._metadata_dao_class(session)
            tables = metadata_dao.get_tables(table_name, schema, dbname)
            table, error_msg = self._validate_tables(session, tables, table_name)
            if error_msg or not table:
                return str(error_msg)

            samples = metadata_dao.get_samples_by_table_id(int(str(table.id)))
            if not samples:
                return f"Nenhuma amostra de dados encontrada para '{table_name}'."

            result = [f"Amostras de dados para {table_name}:"]
            for s in samples:
                result.append(s.row_data) # type: ignore
            return "\n".join(result)
        finally:
            session.close()

    def get_table_description(self, table_name: str, schema: Optional[str] = None, dbname: Optional[str] = None) -> str:
        """Retorna o comentário descritivo de uma tabela específica."""
        table_name = table_name.lower()
        if schema:
            schema = schema.lower()
            
        session = self._secure_conn.get_session()
        try:
            tables = self._metadata_dao_class(session).get_tables(table_name, schema, dbname)
            table, error_msg = self._validate_tables(session, tables, table_name)
            if error_msg or not table:
                return str(error_msg)

            comment = table.comment if table.comment else "Sem comentário disponível."
            return f"Descrição da tabela {table.schema_name}.{table.table_name}: {comment}"
        finally:
            session.close()

    def search_metadata(self, query: str) -> str:
        """Realiza busca textual nos nomes e comentários de tabelas e colunas."""
        query = query.lower()
        session = self._secure_conn.get_session()
        try:
            result = []
            metadata_dao = self._metadata_dao_class(session)
            tables, columns = metadata_dao.search_metadata(query)

            if tables:
                result.append("Tabelas encontradas (nome ou comentário):")
                for t in tables:
                    comment = f": {t.comment}" if t.comment else ""
                    result.append(f"- {t.schema_name}.{t.table_name}{comment}")

            if columns:
                result.append("\nColunas encontradas (nome ou comentário):")
                for col, tbl_name, sch_name in columns:
                    comment = f": {col.comment}" if col.comment else ""
                    result.append(f"- {col.column_name} (na tabela {sch_name}.{tbl_name}){comment}")

            if not result:
                return f"Nenhum resultado encontrado para o termo '{query}' em nomes ou comentários."

            return "\n".join(result)
        finally:
            session.close()


