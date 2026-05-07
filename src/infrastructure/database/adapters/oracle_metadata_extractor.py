import urllib.parse
from typing import List, Any, Set
from sqlalchemy import text
from .base_metadata_extractor import BaseMetadataExtractor
import oracledb
import os

# Schemas internos/de sistema do Oracle que devem ser excluídos da listagem.
ORACLE_SYSTEM_SCHEMAS: Set[str] = {
    "SYS",
    "SYSTEM",
    "DBSNMP",
    "OUTLN",
    "MDSYS",
    "ORDSYS",
    "ORDDATA",
    "CTXSYS",
    "ANONYMOUS",
    "XDB",
    "DVSYS",
    "LBACSYS",
    "WMSYS",
    "EXFSYS",
    "DBSFWUSER",
    "APPQOSSYS",
    "GSMADMIN_INTERNAL",
    "OJVMSYS",
    "OLAPSYS",
    "DVF",
    "AUDSYS",
    "REMOTE_SCHEDULER_AGENT",
    "SI_INFORMTN_SCHEMA",
    "GGSYS",
    "SYS$UMF",
    "APEX_PUBLIC_USER",
    "FLOWS_FILES",
    "ORDS_PUBLIC_USER",
    "ORDS_METADATA",
    "XS$NULL",
}

# Prefixos de schemas do Oracle que devem ser excluídos da listagem.
ORACLE_SYSTEM_SCHEMA_PREFIXES = ("APEX_", "FLOWS_", "ORDS_")


class OracleMetadataExtractor(BaseMetadataExtractor):
    """Extrator de metadados para bancos Oracle.

    Utiliza oracledb em modo thick (com Instant Client) quando um
    ``driver_path`` é fornecido, ou em modo thin caso contrário.
    """

    def initialize_drivers(self) -> None:
        """Inicializa o Oracle Instant Client caso um caminho tenha sido fornecido.

        Quando ``driver_path`` não é informado, nenhuma ação é realizada e o
        oracledb opera em modo thin.
        """
        if not self.driver_path:
            return

        # Normaliza o caminho: remove espaços e resolve componentes redundantes
        normalized_path: str = os.path.normpath(self.driver_path.strip())

        # Em sistemas POSIX (Linux/macOS), tenta corrigir caminhos relativos
        # adicionando '/' no início. Em Windows, caminhos começam com letra de disco.
        if os.name != "nt" and not os.path.isabs(normalized_path):
            normalized_path = f"/{normalized_path}"

        self.driver_path = normalized_path

        if not os.path.isdir(self.driver_path):
            raise ValueError(
                f"O caminho do driver especificado não é um diretório válido: {self.driver_path}. "
                "Certifique-se de que o arquivo foi descompactado e o caminho está correto."
            )

        try:
            oracledb.init_oracle_client(lib_dir=self.driver_path)
        except oracledb.ProgrammingError:
            # O driver já foi inicializado anteriormente nesta execução do processo.
            # Como o oracledb só permite uma inicialização por processo, ignoramos.
            pass
        except Exception as e:
            print(f"Erro crítico ao inicializar Oracle Client (Modo Thick): {e}")
            raise e

    def build_connection_string(self) -> str:
        """Retorna a string de conexão SQLAlchemy para Oracle."""
        encoded_password = urllib.parse.quote_plus(self.password)
        encoded_user = urllib.parse.quote_plus(self.user)
        return f"oracle+oracledb://{encoded_user}:{encoded_password}@{self.host}:{self.port}/?service_name={self.dbname}"

    def get_default_schema(self, inspector: Any) -> str:
        """Retorna o schema padrão (usuário logado em caixa alta)."""
        return self.user.upper()

    def _is_system_schema(self, schema: str) -> bool:
        """Verifica se um schema pertence ao conjunto de schemas internos do Oracle."""
        upper_schema: str = schema.upper()
        if upper_schema in ORACLE_SYSTEM_SCHEMAS:
            return True
        return upper_schema.startswith(ORACLE_SYSTEM_SCHEMA_PREFIXES)

    def get_all_tables(self) -> List[str]:
        """Retorna todas as tabelas visíveis ao usuário conectado, excluindo schemas de sistema Oracle.

        Utiliza query direta em ``ALL_TABLES`` em vez de ``get_schema_names()`` +
        ``get_table_names(schema=X)``. Essa abordagem é mais correta para o Oracle
        porque:

        - ``get_schema_names()`` lista todos os usuários do banco (``ALL_USERS``),
          podendo retornar centenas de schemas sem permissão de acesso.
        - ``ALL_TABLES`` retorna apenas as tabelas *visíveis* ao usuário conectado,
          respeitando os privilégios ``SELECT`` concedidos.

        O filtro de schemas de sistema é aplicado diretamente na query SQL via
        lista de exclusão de ``OWNER``, mais a exclusão de prefixos conhecidos.
        """
        engine = self.get_engine()
        tables: List[str] = []

        # Monta lista de placeholders para os schemas da lista de exclusão exata
        excluded_owners: List[str] = list(ORACLE_SYSTEM_SCHEMAS)
        placeholders: str = ", ".join(
            f":owner_{i}" for i in range(len(excluded_owners))
        )
        bind_params: dict = {
            f"owner_{i}": owner for i, owner in enumerate(excluded_owners)
        }

        query: str = f"""
            SELECT OWNER, TABLE_NAME
            FROM ALL_TABLES
            WHERE OWNER NOT IN ({placeholders})
            ORDER BY OWNER, TABLE_NAME
        """

        try:
            with engine.connect() as conn:
                result = conn.execute(text(query), bind_params)
                for row in result:
                    owner: str = str(row[0])
                    table_name: str = str(row[1])
                    # Filtra também schemas com prefixos de sistema não cobertos pela lista exata
                    if not self._is_system_schema(owner):
                        tables.append(f"{owner}.{table_name}")
        except Exception as e:
            print(f"Erro ao obter tabelas do oracle via ALL_TABLES: {e}")

        return tables
