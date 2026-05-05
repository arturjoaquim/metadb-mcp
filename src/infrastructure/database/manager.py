import json
from typing import List, Dict, Any, Optional

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from .models import (
    DBConnection,
    SyncTable,
    SyncColumn,
    SyncConstraint,
    SyncIndex,
    SyncSample,
)
from .base_adapter import BaseDBAdapter
from .postgres_adapter import PostgresAdapter
from .oracle_adapter import OracleAdapter

# Importação local para evitar dependência circular
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .secure_connection import SecureConnectionManager


class DatabaseManager:
    """Gerencia operações de negócio sobre o banco de metadados local.

    Recebe uma instância de ``SecureConnectionManager`` por injeção de
    dependência para obter sessions SQLAlchemy, sem conhecer detalhes
    de criptografia ou autenticação.
    """

    def __init__(self, secure_conn: "SecureConnectionManager") -> None:
        """Inicializa o DatabaseManager com a conexão segura.

        Args:
            secure_conn: Instância do gerenciador de conexão segura já
                         desbloqueada.
        """
        self._secure_conn = secure_conn

    def get_session(self) -> Session:
        """Retorna uma nova session SQLAlchemy via SecureConnectionManager."""
        return self._secure_conn.get_session()

    def get_tables(
        self,
        session: Any,
        table_name: str,
        schema: Optional[str] = None,
        dbname: Optional[str] = None,
    ) -> List[SyncTable]:
        query = session.query(SyncTable).filter(SyncTable.table_name == table_name)
        if schema:
            query = query.filter(SyncTable.schema_name == schema)
        if dbname:
            query = query.join(
                DBConnection, SyncTable.connection_id == DBConnection.id
            ).filter(DBConnection.dbname == dbname)
        return query.all()

    def get_dbconnection_by_id(
        self, session: Any, conn_id: int
    ) -> Optional[DBConnection]:
        return session.query(DBConnection).filter(DBConnection.id == conn_id).first()

    def _get_adapter(
        self, db_type: str, host: str, port: int, user: str, password: str, dbname: str
    ) -> BaseDBAdapter:
        if db_type == "postgresql":
            return PostgresAdapter(host, port, user, password, dbname)
        elif db_type == "oracle":
            return OracleAdapter(host, port, user, password, dbname)
        else:
            raise ValueError(f"Tipo de banco não suportado: {db_type}")

    def test_connection(
        self, db_type: str, host: str, port: int, user: str, password: str, dbname: str
    ) -> bool:
        adapter = self._get_adapter(db_type, host, port, user, password, dbname)
        return adapter.test_connection()

    def get_all_tables(
        self, db_type: str, host: str, port: int, user: str, password: str, dbname: str
    ) -> List[str]:
        adapter = self._get_adapter(db_type, host, port, user, password, dbname)
        return adapter.get_all_tables()

    def get_synced_tables_by_name(self, conn_name: str) -> List[str]:
        session = self.get_session()
        try:
            conn = session.query(DBConnection).filter_by(name=conn_name).first()
            if not conn:
                return []
            tables = session.query(SyncTable).filter_by(connection_id=conn.id).all()
            result = []
            for t in tables:
                if t.schema_name:
                    result.append(f"{t.schema_name}.{t.table_name}")
                else:
                    result.append(t.table_name)
            return result
        finally:
            session.close()

    def get_connections(self) -> List[Dict[str, Any]]:
        session = self.get_session()
        try:
            conns = session.query(DBConnection).all()
            return [
                {
                    "name": c.name,
                    "db_type": c.db_type,
                    "host": c.host,
                    "port": c.port,
                    "user": c.user,
                    "dbname": c.dbname,
                }
                for c in conns
            ]
        finally:
            session.close()

    def save_connection_info(
        self, name: str, db_type: str, host: str, port: int, user: str, dbname: str
    ) -> int:
        session = self.get_session()
        try:
            conn = session.query(DBConnection).filter_by(name=name).first()
            if not conn:
                conn = DBConnection(
                    name=name,
                    db_type=db_type,
                    host=host,
                    port=port,
                    user=user,
                    dbname=dbname,
                )
                session.add(conn)
            else:
                conn.db_type = db_type
                conn.host = host
                conn.port = port
                conn.user = user
                conn.dbname = dbname
            session.commit()
            return int(conn.id)
        finally:
            session.close()

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
        conn_id = self.save_connection_info(
            conn_name, db_type, host, port, user, dbname
        )

        adapter = self._get_adapter(db_type, host, port, user, password, dbname)
        engine = adapter.get_engine()
        inspector = inspect(engine)
        default_schema = adapter.get_default_schema(inspector)

        session = self.get_session()
        try:
            for table_item in tables_to_sync:
                if "." in table_item:
                    schema, table_name = table_item.split(".", 1)
                else:
                    schema = default_schema
                    table_name = table_item

                existing_table = (
                    session.query(SyncTable)
                    .filter_by(
                        connection_id=conn_id, table_name=table_name, schema_name=schema
                    )
                    .first()
                )
                if existing_table:
                    session.query(SyncColumn).filter_by(
                        table_id=existing_table.id
                    ).delete()
                    session.query(SyncConstraint).filter_by(
                        table_id=existing_table.id
                    ).delete()
                    session.query(SyncIndex).filter_by(
                        table_id=existing_table.id
                    ).delete()
                    session.query(SyncSample).filter_by(
                        table_id=existing_table.id
                    ).delete()
                    session.delete(existing_table)
                    session.flush()

                table_comment = adapter.get_table_comment(inspector, table_name, schema)

                sync_table = SyncTable(
                    connection_id=conn_id,
                    table_name=table_name,
                    schema_name=schema,
                    comment=table_comment,
                )
                session.add(sync_table)
                session.flush()

                try:
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
                    try:
                        pk = inspector.get_pk_constraint(table_name, schema=schema)
                        if pk and pk.get("constrained_columns"):
                            sync_pk = SyncConstraint(
                                table_id=sync_table.id,
                                constraint_name=pk.get("name", "PK"),
                                constraint_type="PRIMARY KEY",
                                columns=json.dumps(pk.get("constrained_columns", [])),
                            )
                            session.add(sync_pk)
                    except:
                        pass

                    try:
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
                    except:
                        pass

                    # Amostra de domínio (10 linhas)
                    with engine.connect() as db_conn:
                        try:
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
                        except Exception as e:
                            print(
                                f"Erro ao pegar amostra para tabela {table_name}: {e}"
                            )

                except Exception as e:
                    print(f"Erro ao inspecionar a tabela {table_name}: {e}")

            session.commit()

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
