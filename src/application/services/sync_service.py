import logging
from typing import List, Tuple, Callable, Type, Optional, Any, Dict
from sqlalchemy.orm import Session

from infrastructure.database.adapters.base_metadata_extractor import (
    BaseMetadataExtractor,
)
from infrastructure.database.adapters.extracted_metadata import (
    ExtractedColumn,
    ExtractedIndex,
    ExtractedConstraint,
)
from infrastructure.database.daos.connection_dao import ConnectionDAO
from infrastructure.database.daos.metadata_dao import MetadataDAO
from infrastructure.database.secure_connection import SecureConnectionManager

logger: logging.Logger = logging.getLogger(__name__)


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
        adapter = self._extractor_factory(
            db_type, host, port, user, password, dbname, driver_path=driver_path
        )
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
        adapter = self._extractor_factory(
            db_type, host, port, user, password, dbname, driver_path=driver_path
        )
        return adapter.get_all_tables()

    def _parse_table_name(
        self, table_item: str, default_schema: str
    ) -> Tuple[str, str]:
        """Faz o parse do nome da tabela e schema."""
        if "." in table_item:
            orig_schema, orig_table_name = table_item.split(".", 1)
        else:
            orig_schema = default_schema
            orig_table_name = table_item
        return orig_schema, orig_table_name

    def _sync_single_table(
        self,
        table_item: str,
        adapter: BaseMetadataExtractor,
        metadata_dao: MetadataDAO,
        conn_id: int,
        default_schema: str,
        sensitive_tables: Optional[List[str]],
        sample_size: int,
    ) -> None:
        """Executa a extração e persistência dos metadados para uma única tabela."""
        orig_schema: str
        orig_table_name: str
        orig_schema, orig_table_name = self._parse_table_name(
            table_item, default_schema
        )
        logger.info(
            "Nome da tabela analisado -> Schema: '%s', Nome: '%s'.",
            orig_schema,
            orig_table_name,
        )

        # Determinar se a tabela é sensível (comparação case-insensitive)
        is_sensitive: bool = table_item.lower() in [
            t.lower() for t in (sensitive_tables or [])
        ]
        if is_sensitive:
            logger.info(
                "A tabela '%s.%s' foi marcada como SENSÍVEL. Amostras de dados não serão coletadas.",
                orig_schema,
                orig_table_name,
            )
        else:
            logger.info(
                "A tabela '%s.%s' não é sensível. Coleta de amostras ativada (limite: %d).",
                orig_schema,
                orig_table_name,
                sample_size,
            )

        # Extração via adapter
        logger.info("Extraindo colunas da tabela '%s.%s'.", orig_schema, orig_table_name)
        columns: List[ExtractedColumn] = adapter.extract_columns(
            orig_table_name, schema=orig_schema
        )
        logger.info(
            "Extraídas %d colunas para a tabela '%s.%s'.",
            len(columns),
            orig_schema,
            orig_table_name,
        )

        logger.info("Extraindo índices da tabela '%s.%s'.", orig_schema, orig_table_name)
        indexes: List[ExtractedIndex] = adapter.extract_indexes(
            orig_table_name, schema=orig_schema
        )
        logger.info(
            "Extraídos %d índices para a tabela '%s.%s'.",
            len(indexes),
            orig_schema,
            orig_table_name,
        )

        logger.info("Extraindo chave primária da tabela '%s.%s'.", orig_schema, orig_table_name)
        pk: Optional[ExtractedConstraint] = adapter.extract_pk_constraint(
            orig_table_name, schema=orig_schema
        )
        if pk:
            logger.info("Chave primária encontrada para a tabela '%s.%s'.", orig_schema, orig_table_name)
        else:
            logger.info("Nenhuma chave primária encontrada para a tabela '%s.%s'.", orig_schema, orig_table_name)

        logger.info("Extraindo chaves estrangeiras da tabela '%s.%s'.", orig_schema, orig_table_name)
        fks: List[ExtractedConstraint] = adapter.extract_foreign_keys(
            orig_table_name, schema=orig_schema
        )
        logger.info(
            "Extraídas %d chaves estrangeiras para a tabela '%s.%s'.",
            len(fks),
            orig_schema,
            orig_table_name,
        )

        # Coleta de amostras apenas se não for tabela sensível
        samples: List[Dict[str, Any]]
        if is_sensitive:
            samples = []
        else:
            logger.info("Coletando amostras de dados para a tabela '%s.%s'.", orig_schema, orig_table_name)
            samples = adapter.extract_sample_rows(
                orig_table_name, schema=orig_schema, limit=sample_size
            )
            logger.info(
                "Coletadas %d linhas de amostra para a tabela '%s.%s'.",
                len(samples),
                orig_schema,
                orig_table_name,
            )

        logger.info("Obtendo comentário descritivo da tabela '%s.%s'.", orig_schema, orig_table_name)
        table_comment: Optional[str] = adapter.get_table_comment(
            adapter.get_inspector(), orig_table_name, orig_schema
        )
        logger.info("Comentário descritivo obtido para a tabela '%s.%s'.", orig_schema, orig_table_name)

        constraints: List[ExtractedConstraint] = ([pk] if pk else []) + fks

        # Persistência via DAO
        logger.info("Persistindo metadados da tabela '%s.%s' no cache local.", orig_schema, orig_table_name)
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
        logger.info("Metadados da tabela '%s.%s' persistidos com sucesso.", orig_schema, orig_table_name)

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
        logger.info(
            "Iniciando sincronização de metadados para a conexão '%s' (tipo: %s). Banco de dados: %s. Tabelas solicitadas: %s.",
            conn_name,
            db_type,
            dbname,
            tables_to_sync,
        )

        logger.info("Obtendo sessão ativa do banco de dados seguro.")
        session: Session = self.secure_conn.get_session()
        try:
            logger.info("Persistindo informações de conexão no banco local.")
            conn_dao: ConnectionDAO = self._connection_dao_class(session)
            conn_id: int = conn_dao.save(
                conn_name, db_type, host, port, user, dbname, driver_path=driver_path
            )
            # Commit connection immediately so FKs work and it is persisted even if tables fail
            session.commit()
            logger.info("Informações de conexão salvas com sucesso.")

            logger.info("Inicializando extrator de metadados para o banco remoto.")
            adapter: BaseMetadataExtractor = self._extractor_factory(
                db_type, host, port, user, password, dbname, driver_path=driver_path
            )

            logger.info("Inspecionando banco de dados remoto.")
            inspector: Any = adapter.get_inspector()
            default_schema: str = adapter.get_default_schema(inspector)
            logger.info("Schema padrão identificado: '%s'.", default_schema)

            metadata_dao: MetadataDAO = self._metadata_dao_class(session)
            
            logger.info("Realizando pré-carregamento (se suportado) dos metadados das tabelas solicitadas.")
            if hasattr(adapter, "preload_metadata"):
                adapter.preload_metadata(tables_to_sync, default_schema)

            failed_tables: List[str] = []

            for table_item in tables_to_sync:
                try:
                    logger.info("Processando tabela: '%s'.", table_item)
                    self._sync_single_table(
                        table_item=table_item,
                        adapter=adapter,
                        metadata_dao=metadata_dao,
                        conn_id=conn_id,
                        default_schema=default_schema,
                        sensitive_tables=sensitive_tables,
                        sample_size=sample_size,
                    )
                    
                    # Faz o commit individual para esta tabela
                    session.commit()
                    logger.info("Transação confirmada para a tabela '%s'.", table_item)
                    
                except Exception as table_exc:
                    logger.error(
                        "Erro ao sincronizar a tabela '%s': %s. Realizando rollback apenas desta tabela.",
                        table_item,
                        table_exc,
                        exc_info=True,
                    )
                    session.rollback()
                    failed_tables.append(table_item)

            if failed_tables:
                error_msg = f"A sincronização falhou para as seguintes tabelas: {failed_tables}"
                logger.error(error_msg)
                raise SyncServiceError(error_msg)

            logger.info("Sincronização concluída. Todas as tabelas foram processadas com sucesso.")

        except SyncServiceError:
            # Exceção já tratada internamente
            raise
        except Exception as e:
            logger.error(
                "Erro fatal ocorrido durante a sincronização de tabelas.",
                exc_info=True,
            )
            session.rollback()
            raise SyncServiceError(f"Erro fatal na sincronização: {e}") from e
        finally:
            logger.info("Fechando a sessão do banco de dados local.")
            session.close()
