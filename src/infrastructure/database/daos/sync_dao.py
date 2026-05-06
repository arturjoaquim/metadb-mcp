from typing import List, Optional
from sqlalchemy.orm import Session

from infrastructure.database.models import (
    DBConnection,
    SyncTable,
    SyncColumn,
    SyncConstraint,
    SyncIndex,
    SyncSample,
)


class SyncDAO:
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
