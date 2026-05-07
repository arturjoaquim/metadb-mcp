from typing import List, Tuple, Callable, Type, Optional


from infrastructure.database.adapters.base_metadata_extractor import BaseMetadataExtractor
from infrastructure.database.daos.connection_dao import ConnectionDAO
from infrastructure.database.daos.metadata_dao import MetadataDAO
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
        metadata_dao_class: Type[MetadataDAO] = MetadataDAO,
    ) -> None:
        self.secure_conn = secure_conn
        self._extractor_factory = extractor_factory
        self._connection_dao_class = connection_dao_class
        self._metadata_dao_class = metadata_dao_class

    def test_connection(
        self,
        db_type: str,
        host: str,
        port: int,
        user: str,
        password: str,
        dbname: str,
        driver_path: Optional[str] = None,
    ) -> bool:
        """Testa conexão com um banco remoto."""
        adapter = self._extractor_factory(db_type, host, port, user, password, dbname, driver_path=driver_path)
        return adapter.test_connection()

    def get_all_tables(
        self,
        db_type: str,
        host: str,
        port: int,
        user: str,
        password: str,
        dbname: str,
        driver_path: Optional[str] = None,
    ) -> List[str]:
        """Lista todas as tabelas do banco remoto."""
        adapter = self._extractor_factory(db_type, host, port, user, password, dbname, driver_path=driver_path)
        return adapter.get_all_tables()

    def _parse_table_name(self, table_item: str, default_schema: str) -> Tuple[str, str]:
        """Faz o parse do nome da tabela e schema."""
        if "." in table_item:
            orig_schema, orig_table_name = table_item.split(".", 1)
        else:
            orig_schema = default_schema
            orig_table_name = table_item
        return orig_schema, orig_table_name

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
        driver_path: Optional[str] = None,
        sensitive_tables: Optional[List[str]] = None,
        sample_size: int = 10,
    ) -> None:
        """Orquestra a sincronização de metadados do banco remoto para o cache local."""
        
        session = self.secure_conn.get_session()
        try:
            conn_dao = self._connection_dao_class(session)
            conn_id = conn_dao.save(conn_name, db_type, host, port, user, dbname, driver_path=driver_path)
            
            adapter = self._extractor_factory(db_type, host, port, user, password, dbname, driver_path=driver_path)
            inspector = adapter.get_inspector()
            default_schema = adapter.get_default_schema(inspector)

            metadata_dao = self._metadata_dao_class(session)

            for table_item in tables_to_sync:
                orig_schema, orig_table_name = self._parse_table_name(table_item, default_schema)

                # Determinar se a tabela é sensível (comparação case-insensitive)
                is_sensitive = table_item.lower() in [t.lower() for t in (sensitive_tables or [])]

                # Extração via adapter
                columns = adapter.extract_columns(orig_table_name, schema=orig_schema)
                indexes = adapter.extract_indexes(orig_table_name, schema=orig_schema)
                pk = adapter.extract_pk_constraint(orig_table_name, schema=orig_schema)
                fks = adapter.extract_foreign_keys(orig_table_name, schema=orig_schema)
                
                # Coleta de amostras apenas se não for tabela sensível
                samples = [] if is_sensitive else adapter.extract_sample_rows(
                    orig_table_name, schema=orig_schema, limit=sample_size
                )
                
                table_comment = adapter.get_table_comment(inspector, orig_table_name, orig_schema)

                constraints = ([pk] if pk else []) + fks

                # Persistência via DAO
                metadata_dao.save_table_metadata(
                    conn_id=conn_id,
                    table_name=orig_table_name.lower(),
                    schema=orig_schema.lower() if orig_schema else None,
                    comment=table_comment,
                    columns=columns,
                    indexes=indexes,
                    constraints=constraints,
                    samples=samples,
                    is_sensitive=is_sensitive,
                    sample_size=sample_size,
                )

            session.commit()

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
