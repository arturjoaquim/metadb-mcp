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
                    schema, table_name = table_item.split(".", 1)
                else:
                    schema = default_schema
                    table_name = table_item

                existing_table = sync_dao.get_existing_table(conn_id, table_name, schema)
                if existing_table:
                    sync_dao.delete_table_metadata(existing_table)

                table_comment = adapter.get_table_comment(inspector, table_name, schema)

                sync_table = SyncTable(
                    connection_id=conn_id,
                    table_name=table_name,
                    schema_name=schema,
                    comment=table_comment,
                )
                session.add(sync_table)
                session.flush()

                # Colunas
                columns = inspector.get_columns(table_name, schema=schema)
                for col in columns:
                    data_type_str = str(col["type"])
                    sync_col = SyncColumn(
                        table_id=sync_table.id,
                        column_name=col["name"],
                        data_type=data_type_str,
                        is_nullable=1 if col.get("nullable", True) else 0,
                        default_value=str(col.get("default", ""))
                        if col.get("default")
                        else None,
                        comment=col.get("comment"),
                    )
                    session.add(sync_col)

                # Índices
                indexes = inspector.get_indexes(table_name, schema=schema)
                for idx in indexes:
                    sync_idx = SyncIndex(
                        table_id=sync_table.id,
                        index_name=idx["name"],
                        columns=json.dumps(idx.get("column_names", [])),
                        is_unique=1 if idx.get("unique", False) else 0,
                    )
                    session.add(sync_idx)

                # Constraints (PK, FK)
                pk = inspector.get_pk_constraint(table_name, schema=schema)
                if pk and pk.get("constrained_columns"):
                    sync_pk = SyncConstraint(
                        table_id=sync_table.id,
                        constraint_name=pk.get("name", "PK"),
                        constraint_type="PRIMARY KEY",
                        columns=json.dumps(pk.get("constrained_columns", [])),
                    )
                    session.add(sync_pk)

                fks = inspector.get_foreign_keys(table_name, schema=schema)
                for fk in fks:
                    sync_fk = SyncConstraint(
                        table_id=sync_table.id,
                        constraint_name=fk.get("name", "FK"),
                        constraint_type="FOREIGN KEY",
                        columns=json.dumps(fk.get("constrained_columns", [])),
                        ref_table=fk.get("referred_table"),
                        ref_columns=json.dumps(fk.get("referred_columns", [])),
                    )
                    session.add(sync_fk)

                # Amostra de domínio (10 linhas)
                with engine.connect() as db_conn:
                    # usar text() para sqlalchemy 2.0+
                    stmt = text(
                        f"SELECT * FROM {schema}.{table_name}"
                        if schema
                        else f"SELECT * FROM {table_name}"
                    )
                    result = db_conn.execute(stmt)
                    rows = result.fetchmany(10)
                    keys = result.keys()

                    for row in rows:
                        row_dict = dict(zip(keys, row))
                        for k, v in row_dict.items():
                            row_dict[k] = str(v)

                        sync_sample = SyncSample(
                            table_id=sync_table.id,
                            row_data=json.dumps(row_dict),
                        )
                        session.add(sync_sample)

            session.commit()

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
