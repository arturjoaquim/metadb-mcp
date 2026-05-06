import json
from typing import Any, List, Optional, Tuple, Dict
from sqlalchemy.orm import Session

from infrastructure.database.models import (
    DBConnection,
    MetadataTable,
    MetadataColumn,
    MetadataConstraint,
    MetadataIndex,
    MetadataSample,
)
from infrastructure.database.adapters.extracted_metadata import (
    ExtractedColumn,
    ExtractedIndex,
    ExtractedConstraint,
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
    ) -> List[MetadataTable]:
        query = self.session.query(MetadataTable).filter(MetadataTable.table_name == table_name)
        if schema:
            query = query.filter(MetadataTable.schema_name == schema)
        if dbname:
            query = query.join(
                DBConnection, MetadataTable.connection_id == DBConnection.id
            ).filter(DBConnection.dbname == dbname)
        return query.all()

    def get_synced_tables_by_connection_name(self, conn_name: str) -> List[Dict[str, Any]]:
        """Retorna as tabelas sincronizadas de uma conexão com metadados de sensibilidade.

        Cada item contém: name (str), is_sensitive (bool), sample_size (int).
        """
        conn = self.session.query(DBConnection).filter_by(name=conn_name).first()
        if not conn:
            return []
        tables = self.session.query(MetadataTable).filter_by(connection_id=conn.id).all()
        result: List[Dict[str, Any]] = []
        for t in tables:
            name = f"{t.schema_name}.{t.table_name}" if t.schema_name else t.table_name
            result.append({
                "name": name,
                "is_sensitive": bool(t.is_sensitive),
                "sample_size": t.sample_size,
            })
        return result

    def get_all_tables(self) -> List[MetadataTable]:
        """Retorna todas as tabelas sincronizadas."""
        return self.session.query(MetadataTable).all()

    def get_columns_by_table_id(self, table_id: int) -> List[MetadataColumn]:
        """Retorna as colunas de uma tabela específica."""
        return self.session.query(MetadataColumn).filter_by(table_id=table_id).all()

    def get_indexes_by_table_id(self, table_id: int) -> List[MetadataIndex]:
        """Retorna os índices de uma tabela específica."""
        return self.session.query(MetadataIndex).filter_by(table_id=table_id).all()

    def get_constraints_by_table_id(self, table_id: int) -> List[MetadataConstraint]:
        """Retorna as constraints de uma tabela específica."""
        return self.session.query(MetadataConstraint).filter_by(table_id=table_id).all()

    def get_samples_by_table_id(self, table_id: int) -> List[MetadataSample]:
        """Retorna as amostras de dados de uma tabela específica."""
        return self.session.query(MetadataSample).filter_by(table_id=table_id).all()

    def search_metadata(self, query: str) -> Tuple[List[MetadataTable], List[Any]]:
        """Realiza busca textual nos nomes e comentários de tabelas e colunas.
        
        Retorna uma tupla contendo (lista_de_tabelas, lista_de_colunas_com_nomes_tabelas).
        """
        from sqlalchemy import or_
        search_term = f"%{query.lower()}%"

        # Buscar tabelas
        tables = (
            self.session.query(MetadataTable)
            .filter(
                or_(
                    MetadataTable.table_name.ilike(search_term),
                    MetadataTable.comment.ilike(search_term)
                )
            )
            .all()
        )

        # Buscar colunas
        columns = (
            self.session.query(MetadataColumn, MetadataTable.table_name, MetadataTable.schema_name)
            .join(MetadataTable, MetadataColumn.table_id == MetadataTable.id)
            .filter(
                or_(
                    MetadataColumn.column_name.ilike(search_term),
                    MetadataColumn.comment.ilike(search_term)
                )
            )
            .all()
        )

        return tables, columns

    def delete_table_metadata(self, table: MetadataTable) -> None:
        """Remove todos os metadados vinculados a uma tabela antes de re-sincronizar."""
        self.session.query(MetadataColumn).filter_by(table_id=table.id).delete()
        self.session.query(MetadataConstraint).filter_by(table_id=table.id).delete()
        self.session.query(MetadataIndex).filter_by(table_id=table.id).delete()
        self.session.query(MetadataSample).filter_by(table_id=table.id).delete()
        self.session.delete(table)
        self.session.flush()

    def get_existing_table(self, conn_id: int, table_name: str, schema_name: str) -> Optional[MetadataTable]:
        return (
            self.session.query(MetadataTable)
            .filter_by(
                connection_id=conn_id, table_name=table_name, schema_name=schema_name
            )
            .first()
        )

    def save_table_metadata(
        self,
        conn_id: int,
        table_name: str,
        schema: Optional[str],
        comment: Optional[str],
        columns: List[ExtractedColumn],
        indexes: List[ExtractedIndex],
        constraints: List[ExtractedConstraint],
        samples: List[Dict[str, Any]],
        is_sensitive: bool = False,
        sample_size: int = 10,
    ) -> MetadataTable:
        """Salva todos os metadados de uma tabela no cache local."""
        existing_table = self.get_existing_table(conn_id, table_name, schema)
        if existing_table:
            self.delete_table_metadata(existing_table)

        metadata_table = MetadataTable(
            connection_id=conn_id,
            table_name=table_name,
            schema_name=schema,
            comment=comment.lower() if comment else None,
            is_sensitive=1 if is_sensitive else 0,
            sample_size=sample_size,
        )
        self.session.add(metadata_table)
        self.session.flush()

        # Colunas
        for col in columns:
            metadata_col = MetadataColumn(
                table_id=metadata_table.id,
                column_name=col.name,
                data_type=col.data_type,
                is_nullable=1 if col.is_nullable else 0,
                default_value=col.default_value,
                comment=col.comment,
            )
            self.session.add(metadata_col)

        # Índices
        for idx in indexes:
            metadata_idx = MetadataIndex(
                table_id=metadata_table.id,
                index_name=idx.name,
                columns=json.dumps(idx.columns, ensure_ascii=False),
                is_unique=1 if idx.is_unique else 0,
            )
            self.session.add(metadata_idx)

        # Constraints
        for const in constraints:
            metadata_const = MetadataConstraint(
                table_id=metadata_table.id,
                constraint_name=const.name,
                constraint_type=const.constraint_type,
                columns=json.dumps(const.columns, ensure_ascii=False),
                ref_table=const.ref_table,
                ref_columns=json.dumps(const.ref_columns, ensure_ascii=False) if const.ref_columns else None,
            )
            self.session.add(metadata_const)

        # Amostras
        for row_dict in samples:
            metadata_sample = MetadataSample(
                table_id=metadata_table.id,
                row_data=json.dumps(row_dict, ensure_ascii=False, default=str),
            )
            self.session.add(metadata_sample)

        self.session.flush()
        return metadata_table
