import json
from typing import List

from sqlalchemy import inspect, text

from infrastructure.database.models import (
    SyncTable,
    SyncColumn,
    SyncConstraint,
    SyncIndex,
    SyncSample,
)
from infrastructure.database.adapters.base_metadata_extractor import BaseMetadataExtractor
from typing import Callable, Type

from infrastructure.database.daos.connection_dao import ConnectionDAO
from infrastructure.database.daos.sync_dao import SyncDAO
from infrastructure.database.secure_connection import SecureConnectionManager


class SyncServiceError(Exception):
    pass


class SyncService:
    """Serviço de orquestração de sincronização de metadados.

    Responsável por interagir com adaptadores de banco de dados e coordenar a
    persistência usando DAOs.
    """

    def __init__(
        self,
        secure_conn: SecureConnectionManager,
        extractor_factory: Callable[..., BaseMetadataExtractor],
        connection_dao_class: Type[ConnectionDAO] = ConnectionDAO,
        sync_dao_class: Type[SyncDAO] = SyncDAO,
    ) -> None:
        self.secure_conn = secure_conn
        self._extractor_factory = extractor_factory
        self._connection_dao_class = connection_dao_class
        self._sync_dao_class = sync_dao_class

    def test_connection(
        self, db_type: str, host: str, port: int, user: str, password: str, dbname: str
    ) -> bool:
        """Testa conexão com um banco remoto."""
        adapter = self._extractor_factory(db_type, host, port, user, password, dbname)
        return adapter.test_connection()

    def get_all_tables(
        self, db_type: str, host: str, port: int, user: str, password: str, dbname: str
    ) -> List[str]:
        """Lista todas as tabelas do banco remoto."""
        adapter = self._extractor_factory(db_type, host, port, user, password, dbname)
        return adapter.get_all_tables()

    def sync_tables(
        self,
        conn_name: str,
        tables_to_sync: List[str],
        db_type: str,
        host: str,
        port: int,
        user: str,
        password: str,
        dbname: str,
    ) -> None:
        """Orquestra a sincronização de metadados do banco remoto para o cache local."""
        
        session = self.secure_conn.get_session()
        try:
            conn_dao = self._connection_dao_class(session)
            conn_id = conn_dao.save(conn_name, db_type, host, port, user, dbname)
            
            adapter = self._extractor_factory(db_type, host, port, user, password, dbname)
            engine = adapter.get_engine()
            inspector = inspect(engine)
            default_schema = adapter.get_default_schema(inspector)

            sync_dao = self._sync_dao_class(session)

            for table_item in tables_to_sync:
                if "." in table_item:
                    orig_schema, orig_table_name = table_item.split(".", 1)
                else:
                    orig_schema = default_schema
                    orig_table_name = table_item

                # Usar nomes em minúsculo para o cache local
                schema = orig_schema.lower() if orig_schema else None
                table_name = orig_table_name.lower()

                existing_table = sync_dao.get_existing_table(conn_id, table_name, schema)
                if existing_table:
                    sync_dao.delete_table_metadata(existing_table)

                table_comment = adapter.get_table_comment(inspector, orig_table_name, orig_schema)
                if table_comment:
                    table_comment = table_comment.lower()

                sync_table = SyncTable(
                    connection_id=conn_id,
                    table_name=table_name,
                    schema_name=schema,
                    comment=table_comment,
                )
                session.add(sync_table)
                session.flush()

                # Colunas
                columns = inspector.get_columns(orig_table_name, schema=orig_schema)
                for col in columns:
                    data_type_str = str(col["type"])
                    sync_col = SyncColumn(
                        table_id=sync_table.id,
                        column_name=str(col["name"]).lower(),
                        data_type=data_type_str,
                        is_nullable=1 if col.get("nullable", True) else 0,
                        default_value=str(col.get("default", ""))
                        if col.get("default")
                        else None,
                        comment=col.get("comment").lower() if col.get("comment") else None,
                    )
                    session.add(sync_col)

                # Índices
                indexes = inspector.get_indexes(orig_table_name, schema=orig_schema)
                for idx in indexes:
                    sync_idx = SyncIndex(
                        table_id=sync_table.id,
                        index_name=str(idx["name"]).lower(),
                        columns=json.dumps([c.lower() for c in idx.get("column_names", [])], ensure_ascii=False),
                        is_unique=1 if idx.get("unique", False) else 0,
                    )
                    session.add(sync_idx)

                # Constraints (PK, FK)
                pk = inspector.get_pk_constraint(orig_table_name, schema=orig_schema)
                if pk and pk.get("constrained_columns"):
                    sync_pk = SyncConstraint(
                        table_id=sync_table.id,
                        constraint_name=str(pk.get("name", "PK")).lower(),
                        constraint_type="PRIMARY KEY",
                        columns=json.dumps([c.lower() for c in pk.get("constrained_columns", [])], ensure_ascii=False),
                    )
                    session.add(sync_pk)

                fks = inspector.get_foreign_keys(orig_table_name, schema=orig_schema)
                for fk in fks:
                    sync_fk = SyncConstraint(
                        table_id=sync_table.id,
                        constraint_name=str(fk.get("name", "FK")).lower(),
                        constraint_type="FOREIGN KEY",
                        columns=json.dumps([c.lower() for c in fk.get("constrained_columns", [])], ensure_ascii=False),
                        ref_table=str(fk.get("referred_table")).lower() if fk.get("referred_table") else None,
                        ref_columns=json.dumps([c.lower() for c in fk.get("referred_columns", [])], ensure_ascii=False),
                    )
                    session.add(sync_fk)

                # Amostra de domínio (10 linhas)
                with engine.connect() as db_conn:
                    # usar text() para sqlalchemy 2.0+
                    stmt = text(
                        f"SELECT * FROM {orig_schema}.{orig_table_name}"
                        if orig_schema
                        else f"SELECT * FROM {orig_table_name}"
                    )
                    result = db_conn.execute(stmt)
                    rows = result.fetchmany(10)
                    keys = result.keys()

                    for row in rows:
                        row_dict = {
                            str(k).lower(): (v.decode("utf-8", errors="replace") if isinstance(v, bytes) else v)
                            for k, v in zip(keys, row)
                        }

                        sync_sample = SyncSample(
                            table_id=sync_table.id,
                            row_data=json.dumps(row_dict, ensure_ascii=False, default=str),
                        )
                        session.add(sync_sample)

            session.commit()

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
