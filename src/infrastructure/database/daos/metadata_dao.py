from typing import Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from infrastructure.database.models import (
    DBConnection,
    SyncTable,
    SyncColumn,
    SyncConstraint,
    SyncIndex,
    SyncSample,
)


class MetadataDAO:
    """DAO para gerenciamento de metadados sincronizados."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_tables(
        self,
        table_name: str,
        schema: Optional[str] = None,
        dbname: Optional[str] = None,
    ) -> List[SyncTable]:
        query = self.session.query(SyncTable).filter(SyncTable.table_name == table_name)
        if schema:
            query = query.filter(SyncTable.schema_name == schema)
        if dbname:
            query = query.join(
                DBConnection, SyncTable.connection_id == DBConnection.id
            ).filter(DBConnection.dbname == dbname)
        return query.all()

    def get_synced_tables_by_connection_name(self, conn_name: str) -> List[str]:
        conn = self.session.query(DBConnection).filter_by(name=conn_name).first()
        if not conn:
            return []
        tables = self.session.query(SyncTable).filter_by(connection_id=conn.id).all()
        result = []
        for t in tables:
            if t.schema_name:
                result.append(f"{t.schema_name}.{t.table_name}")
            else:
                result.append(t.table_name)
        return result

    def get_all_tables(self) -> List[SyncTable]:
        """Retorna todas as tabelas sincronizadas."""
        return self.session.query(SyncTable).all()

    def get_columns_by_table_id(self, table_id: int) -> List[SyncColumn]:
        """Retorna as colunas de uma tabela específica."""
        return self.session.query(SyncColumn).filter_by(table_id=table_id).all()

    def get_indexes_by_table_id(self, table_id: int) -> List[SyncIndex]:
        """Retorna os índices de uma tabela específica."""
        return self.session.query(SyncIndex).filter_by(table_id=table_id).all()

    def get_constraints_by_table_id(self, table_id: int) -> List[SyncConstraint]:
        """Retorna as constraints de uma tabela específica."""
        return self.session.query(SyncConstraint).filter_by(table_id=table_id).all()

    def get_samples_by_table_id(self, table_id: int) -> List[SyncSample]:
        """Retorna as amostras de dados de uma tabela específica."""
        return self.session.query(SyncSample).filter_by(table_id=table_id).all()

    def search_metadata(self, query: str) -> Tuple[List[SyncTable], List[Any]]:
        """Realiza busca textual nos nomes e comentários de tabelas e colunas.
        
        Retorna uma tupla contendo (lista_de_tabelas, lista_de_colunas_com_nomes_tabelas).
        """
        from sqlalchemy import or_
        search_term = f"%{query.lower()}%"

        # Buscar tabelas
        tables = (
            self.session.query(SyncTable)
            .filter(
                or_(
                    SyncTable.table_name.ilike(search_term),
                    SyncTable.comment.ilike(search_term)
                )
            )
            .all()
        )

        # Buscar colunas
        columns = (
            self.session.query(SyncColumn, SyncTable.table_name, SyncTable.schema_name)
            .join(SyncTable, SyncColumn.table_id == SyncTable.id)
            .filter(
                or_(
                    SyncColumn.column_name.ilike(search_term),
                    SyncColumn.comment.ilike(search_term)
                )
            )
            .all()
        )

        return tables, columns

    def delete_table_metadata(self, table: SyncTable) -> None:
        """Remove todos os metadados vinculados a uma tabela antes de re-sincronizar."""
        self.session.query(SyncColumn).filter_by(table_id=table.id).delete()
        self.session.query(SyncConstraint).filter_by(table_id=table.id).delete()
        self.session.query(SyncIndex).filter_by(table_id=table.id).delete()
        self.session.query(SyncSample).filter_by(table_id=table.id).delete()
        self.session.delete(table)
        self.session.flush()

    def get_existing_table(self, conn_id: int, table_name: str, schema_name: str) -> Optional[SyncTable]:
        return (
            self.session.query(SyncTable)
            .filter_by(
                connection_id=conn_id, table_name=table_name, schema_name=schema_name
            )
            .first()
        )
