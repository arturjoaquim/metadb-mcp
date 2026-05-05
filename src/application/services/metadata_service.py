"""Serviço de metadados do MetaDB MCP.

Este módulo encapsula as operações de banco de dados relacionadas aos metadados
sincronizados, fornecendo uma interface para a camada de controladores (MCP).
"""

from typing import Any, List, Optional, Tuple
from infrastructure import database
from infrastructure.database.models import (
    SyncTable,
    SyncColumn,
    SyncIndex,
    SyncConstraint,
    SyncSample,
)


class MetadataServiceError(Exception):
    """Exceção base para erros no MetadataService."""
    pass


class MetadataService:
    """Serviço responsável por coordenar buscas e consultas de metadados.
    
    Abstrai o acesso aos modelos SQLAlchemy do cache local.
    """

    def is_database_unlocked(self) -> bool:
        """Verifica se o banco de dados está inicializado e desbloqueado."""
        return bool(database.secure_connection.is_unlocked and database.db_manager is not None)

    def _validate_tables(
        self, session: Any, tables: List[SyncTable], table_name: str
    ) -> Tuple[Optional[SyncTable], Optional[str]]:
        if not tables:
            return (
                None,
                f"Tabela '{table_name}' não encontrada no cache com os filtros fornecidos.",
            )
        if len(tables) > 1:
            options = []
            for t in tables:
                conn = database.db_manager.get_dbconnection_by_id(session, t.connection_id) # type: ignore
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
            
        session = database.db_manager.get_session() # type: ignore
        try:
            tables = session.query(SyncTable).all()
            if not tables:
                return "Nenhuma tabela sincronizada no momento."

            result = [f"- {t.schema_name}.{t.table_name}" for t in tables]
            return "Tabelas sincronizadas:\n" + "\n".join(result)
        finally:
            session.close()

    def get_table_columns(self, table_name: str, schema: Optional[str] = None, dbname: Optional[str] = None) -> str:
        """Retorna as colunas de uma tabela formatadas."""
        session = database.db_manager.get_session() # type: ignore
        try:
            tables = database.db_manager.get_tables(session, table_name, schema, dbname) # type: ignore
            table, error_msg = self._validate_tables(session, tables, table_name)
            if error_msg:
                return error_msg

            columns = session.query(SyncColumn).filter_by(table_id=table.id).all()
            result = [f"Colunas de {table_name}:"]
            for col in columns:
                nullable = "NULL" if col.is_nullable else "NOT NULL"
                result.append(f"- {col.column_name}: {col.data_type} ({nullable})")
            return "\n".join(result)
        finally:
            session.close()

    def get_table_indexes(self, table_name: str, schema: Optional[str] = None, dbname: Optional[str] = None) -> str:
        """Retorna os índices de uma tabela formatados."""
        session = database.db_manager.get_session() # type: ignore
        try:
            tables = database.db_manager.get_tables(session, table_name, schema, dbname) # type: ignore
            table, error_msg = self._validate_tables(session, tables, table_name)
            if error_msg:
                return error_msg

            indexes = session.query(SyncIndex).filter_by(table_id=table.id).all()
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
        session = database.db_manager.get_session() # type: ignore
        try:
            tables = database.db_manager.get_tables(session, table_name, schema, dbname) # type: ignore
            table, error_msg = self._validate_tables(session, tables, table_name)
            if error_msg:
                return error_msg

            constraints = session.query(SyncConstraint).filter_by(table_id=table.id).all()
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
        session = database.db_manager.get_session() # type: ignore
        try:
            tables = database.db_manager.get_tables(session, table_name, schema, dbname) # type: ignore
            table, error_msg = self._validate_tables(session, tables, table_name)
            if error_msg:
                return error_msg

            samples = session.query(SyncSample).filter_by(table_id=table.id).all()
            if not samples:
                return f"Nenhuma amostra de dados encontrada para '{table_name}'."

            result = [f"Amostras de dados para {table_name}:"]
            for s in samples:
                result.append(s.row_data)
            return "\n".join(result)
        finally:
            session.close()

    def search_metadata(self, query: str) -> str:
        """Realiza busca textual por termos específicos nos nomes de tabelas e colunas."""
        session = database.db_manager.get_session() # type: ignore
        try:
            result = []
            search_term = f"%{query}%"

            # Buscar tabelas
            tables = (
                session.query(SyncTable)
                .filter(SyncTable.table_name.ilike(search_term))
                .all()
            )
            if tables:
                result.append("Tabelas encontradas:")
                for t in tables:
                    result.append(f"- {t.table_name}")

            # Buscar colunas
            columns = (
                session.query(SyncColumn, SyncTable.table_name)
                .join(SyncTable, SyncColumn.table_id == SyncTable.id)
                .filter(SyncColumn.column_name.ilike(search_term))
                .all()
            )
            if columns:
                result.append("\nColunas encontradas:")
                for col, tbl_name in columns:
                    result.append(f"- {col.column_name} (na tabela {tbl_name})")

            if not result:
                return f"Nenhum resultado encontrado para o termo '{query}'."

            return "\n".join(result)
        finally:
            session.close()

metadata_service = MetadataService()
