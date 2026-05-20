import urllib.parse
from typing import List, Any, Set, Dict, Optional, Tuple
from sqlalchemy import text
from .base_metadata_extractor import BaseMetadataExtractor
from .extracted_metadata import ExtractedColumn, ExtractedIndex, ExtractedConstraint
import oracledb
import os

# Schemas internos/de sistema do Oracle que devem ser excluídos da listagem.
ORACLE_SYSTEM_SCHEMAS: Set[str] = {
    "SYS", "SYSTEM", "DBSNMP", "OUTLN", "MDSYS", "ORDSYS", "ORDDATA",
    "CTXSYS", "ANONYMOUS", "XDB", "DVSYS", "LBACSYS", "WMSYS", "EXFSYS",
    "DBSFWUSER", "APPQOSSYS", "GSMADMIN_INTERNAL", "OJVMSYS", "OLAPSYS",
    "DVF", "AUDSYS", "REMOTE_SCHEDULER_AGENT", "SI_INFORMTN_SCHEMA", "GGSYS",
    "SYS$UMF", "APEX_PUBLIC_USER", "FLOWS_FILES", "ORDS_PUBLIC_USER",
    "ORDS_METADATA", "XS$NULL", "VECSYS",
}

ORACLE_SYSTEM_SCHEMA_PREFIXES = ("APEX_", "FLOWS_", "ORDS_")


class OracleMetadataExtractor(BaseMetadataExtractor):
    """Extrator de metadados para bancos Oracle.

    Utiliza oracledb em modo thick (com Instant Client) quando um
    ``driver_path`` é fornecido, ou em modo thin caso contrário.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._preloaded_columns: Dict[str, Dict[str, List[ExtractedColumn]]] = {}
        self._preloaded_indexes: Dict[str, Dict[str, List[ExtractedIndex]]] = {}
        self._preloaded_pks: Dict[str, Dict[str, ExtractedConstraint]] = {}
        self._preloaded_fks: Dict[str, Dict[str, List[ExtractedConstraint]]] = {}
        self._preloaded_comments: Dict[str, Dict[str, str]] = {}
        self._is_preloaded: bool = False

    def initialize_drivers(self) -> None:
        """Inicializa o Oracle Instant Client caso um caminho tenha sido fornecido.

        Quando ``driver_path`` não é informado, nenhuma ação é realizada e o
        oracledb opera em modo thin.
        """
        if not self.driver_path:
            return

        expanded_path: str = os.path.expanduser(self.driver_path.strip())
        normalized_path: str = os.path.normpath(expanded_path)

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

        excluded_owners: List[str] = list(ORACLE_SYSTEM_SCHEMAS)
        placeholders: str = ", ".join(f":owner_{i}" for i in range(len(excluded_owners)))
        bind_params: dict = {f"owner_{i}": owner for i, owner in enumerate(excluded_owners)}

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
                    if not self._is_system_schema(owner):
                        tables.append(f"{owner}.{table_name}")
        except Exception as e:
            print(f"Erro ao obter tabelas do oracle via ALL_TABLES: {e}")

        return tables

    def preload_metadata(self, tables: List[str], default_schema: str) -> None:
        """Busca de uma só vez metadados (colunas, índices, constraints) para as tabelas solicitadas."""
        owners = set()
        table_names = set()

        for t in tables:
            if "." in t:
                o, n = t.split(".", 1)
            else:
                o, n = default_schema, t
            owners.add(o.upper())
            table_names.add(n.upper())

        if not owners or not table_names:
            return

        engine = self.get_engine()
        # Transform items to lists to be safe, oracle IN max is 1000 but we'll assume < 1000 tables for now.
        o_list = list(owners)
        t_list = list(table_names)
        
        # Helper to chunk queries if there are more than 999 tables
        def chunked_list(lst: List[str], n: int = 999) -> List[List[str]]:
            return [lst[i:i + n] for i in range(0, len(lst), n)]
            
        t_chunks = chunked_list(t_list)

        try:
            with engine.connect() as conn:
                for chunk in t_chunks:
                    # Binds
                    o_binds = {f"o_{i}": val for i, val in enumerate(o_list)}
                    t_binds = {f"t_{i}": val for i, val in enumerate(chunk)}
                    binds = {**o_binds, **t_binds}
                    
                    o_ph = ", ".join(f":o_{i}" for i in range(len(o_list)))
                    t_ph = ", ".join(f":t_{i}" for i in range(len(chunk)))

                    # 1. Carregar colunas
                    q_cols = text(f"""
                        SELECT c.OWNER, c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE, c.NULLABLE, c.DATA_DEFAULT, cm.COMMENTS
                        FROM ALL_TAB_COLUMNS c
                        LEFT JOIN ALL_COL_COMMENTS cm ON c.OWNER = cm.OWNER AND c.TABLE_NAME = cm.TABLE_NAME AND c.COLUMN_NAME = cm.COLUMN_NAME
                        WHERE c.OWNER IN ({o_ph}) AND c.TABLE_NAME IN ({t_ph})
                    """)
                    for r in conn.execute(q_cols, binds):
                        o, t, c_name, d_type, nulls, default_v, comment = str(r[0]), str(r[1]), str(r[2]), str(r[3]), str(r[4]), r[5], r[6]
                        if o not in self._preloaded_columns:
                            self._preloaded_columns[o] = {}
                        if t not in self._preloaded_columns[o]:
                            self._preloaded_columns[o][t] = []
                        self._preloaded_columns[o][t].append(ExtractedColumn(
                            name=c_name.lower(),
                            data_type=d_type,
                            is_nullable=nulls == "Y",
                            default_value=str(default_v).strip() if default_v is not None else None,
                            comment=str(comment).lower() if comment else None,
                        ))

                    # 2. Carregar Índices
                    q_idx = text(f"""
                        SELECT i.OWNER, i.TABLE_NAME, i.INDEX_NAME, i.UNIQUENESS, c.COLUMN_NAME
                        FROM ALL_INDEXES i
                        JOIN ALL_IND_COLUMNS c ON i.OWNER = c.INDEX_OWNER AND i.INDEX_NAME = c.INDEX_NAME
                        WHERE i.TABLE_OWNER IN ({o_ph}) AND i.TABLE_NAME IN ({t_ph})
                        ORDER BY c.COLUMN_POSITION
                    """)
                    raw_indexes: Dict[str, Dict[str, Dict[str, dict]]] = {}
                    for r in conn.execute(q_idx, binds):
                        o, t, idx_name, uniq, c_name = str(r[0]), str(r[1]), str(r[2]), str(r[3]), str(r[4])
                        if o not in raw_indexes:
                            raw_indexes[o] = {}
                        if t not in raw_indexes[o]:
                            raw_indexes[o][t] = {}
                        if idx_name not in raw_indexes[o][t]:
                            raw_indexes[o][t][idx_name] = {"unique": uniq == "UNIQUE", "cols": []}
                        raw_indexes[o][t][idx_name]["cols"].append(c_name.lower())
                    
                    for o, t_dict in raw_indexes.items():
                        if o not in self._preloaded_indexes:
                            self._preloaded_indexes[o] = {}
                        for t, idx_dict in t_dict.items():
                            self._preloaded_indexes[o][t] = [
                                ExtractedIndex(name=name.lower(), columns=info["cols"], is_unique=info["unique"])
                                for name, info in idx_dict.items()
                            ]

                    # 3. Carregar Constraints (PK/FK)
                    q_cons = text(f"""
                        SELECT c.OWNER, c.TABLE_NAME, c.CONSTRAINT_NAME, c.CONSTRAINT_TYPE, 
                               cc.COLUMN_NAME, rc.OWNER as REF_OWNER, rc.TABLE_NAME as REF_TABLE, rcc.COLUMN_NAME as REF_COLUMN
                        FROM ALL_CONSTRAINTS c
                        JOIN ALL_CONS_COLUMNS cc ON c.OWNER = cc.OWNER AND c.CONSTRAINT_NAME = cc.CONSTRAINT_NAME
                        LEFT JOIN ALL_CONSTRAINTS rc ON c.R_OWNER = rc.OWNER AND c.R_CONSTRAINT_NAME = rc.CONSTRAINT_NAME
                        LEFT JOIN ALL_CONS_COLUMNS rcc ON rc.OWNER = rcc.OWNER AND rc.CONSTRAINT_NAME = rcc.CONSTRAINT_NAME AND cc.POSITION = rcc.POSITION
                        WHERE c.OWNER IN ({o_ph}) AND c.TABLE_NAME IN ({t_ph}) AND c.CONSTRAINT_TYPE IN ('P', 'R')
                        ORDER BY cc.POSITION
                    """)
                    raw_cons: Dict[str, Dict[str, Dict[str, dict]]] = {}
                    for r in conn.execute(q_cons, binds):
                        o, t, c_name, c_type, c_col, _r_owner, r_table, r_col = str(r[0]), str(r[1]), str(r[2]), str(r[3]), str(r[4]), r[5], r[6], r[7]
                        if o not in raw_cons:
                            raw_cons[o] = {}
                        if t not in raw_cons[o]:
                            raw_cons[o][t] = {}
                        if c_name not in raw_cons[o][t]:
                            raw_cons[o][t][c_name] = {"type": "PRIMARY KEY" if c_type == "P" else "FOREIGN KEY", "cols": [], "ref_table": str(r_table).lower() if r_table else None, "ref_cols": []}
                        raw_cons[o][t][c_name]["cols"].append(c_col.lower())
                        if r_col:
                            raw_cons[o][t][c_name]["ref_cols"].append(str(r_col).lower())
                            
                    for o, t_dict in raw_cons.items():
                        if o not in self._preloaded_pks:
                            self._preloaded_pks[o] = {}
                        if o not in self._preloaded_fks:
                            self._preloaded_fks[o] = {}
                        for t, cons_dict in t_dict.items():
                            fks = []
                            for name, info in cons_dict.items():
                                ec = ExtractedConstraint(
                                    name=name.lower(),
                                    constraint_type=info["type"],
                                    columns=info["cols"],
                                    ref_table=info["ref_table"],
                                    ref_columns=info["ref_cols"] if info["ref_cols"] else None
                                )
                                if info["type"] == "PRIMARY KEY":
                                    self._preloaded_pks[o][t] = ec
                                else:
                                    fks.append(ec)
                            if fks:
                                self._preloaded_fks[o][t] = fks

                    # 4. Carregar Comments de Tabela
                    q_tab_com = text(f"""
                        SELECT OWNER, TABLE_NAME, COMMENTS
                        FROM ALL_TAB_COMMENTS
                        WHERE OWNER IN ({o_ph}) AND TABLE_NAME IN ({t_ph}) AND COMMENTS IS NOT NULL
                    """)
                    for r in conn.execute(q_tab_com, binds):
                        o, t, com = str(r[0]), str(r[1]), str(r[2])
                        if o not in self._preloaded_comments:
                            self._preloaded_comments[o] = {}
                        self._preloaded_comments[o][t] = com

            self._is_preloaded = True
        except Exception as e:
            print(f"Erro durante o pré-carregamento no Oracle: {e}")

    def _get_schema_and_table(self, table_name: str, schema: Optional[str] = None) -> Tuple[str, str]:
        """Normaliza e retorna o schema e nome da tabela em letras maiúsculas."""
        s = schema.upper() if schema else self.user.upper()
        t = table_name.upper()
        return s, t

    def extract_columns(self, table_name: str, schema: Optional[str] = None) -> List[ExtractedColumn]:
        """Extrai as colunas da tabela utilizando os metadados pré-carregados se disponíveis,
        caso contrário recorre à implementação padrão baseada no inspector.
        """
        if self._is_preloaded:
            s, t = self._get_schema_and_table(table_name, schema)
            return self._preloaded_columns.get(s, {}).get(t, [])
        return super().extract_columns(table_name, schema)

    def extract_indexes(self, table_name: str, schema: Optional[str] = None) -> List[ExtractedIndex]:
        """Extrai os índices da tabela utilizando os metadados pré-carregados se disponíveis,
        caso contrário recorre à implementação padrão baseada no inspector.
        """
        if self._is_preloaded:
            s, t = self._get_schema_and_table(table_name, schema)
            return self._preloaded_indexes.get(s, {}).get(t, [])
        return super().extract_indexes(table_name, schema)

    def extract_pk_constraint(self, table_name: str, schema: Optional[str] = None) -> Optional[ExtractedConstraint]:
        """Extrai a constraint de chave primária utilizando os metadados pré-carregados se disponíveis,
        caso contrário recorre à implementação padrão baseada no inspector.
        """
        if self._is_preloaded:
            s, t = self._get_schema_and_table(table_name, schema)
            return self._preloaded_pks.get(s, {}).get(t)
        return super().extract_pk_constraint(table_name, schema)

    def extract_foreign_keys(self, table_name: str, schema: Optional[str] = None) -> List[ExtractedConstraint]:
        """Extrai as constraints de chaves estrangeiras utilizando os metadados pré-carregados se disponíveis,
        caso contrário recorre à implementação padrão baseada no inspector.
        """
        if self._is_preloaded:
            s, t = self._get_schema_and_table(table_name, schema)
            return self._preloaded_fks.get(s, {}).get(t, [])
        return super().extract_foreign_keys(table_name, schema)

    def get_table_comment(self, inspector: Any, table_name: str, schema: str) -> Optional[str]:
        """Obtém o comentário da tabela utilizando os metadados pré-carregados se disponíveis,
        caso contrário recorre à implementação padrão baseada no inspector.
        """
        if self._is_preloaded:
            s, t = self._get_schema_and_table(table_name, schema)
            return self._preloaded_comments.get(s, {}).get(t)
        return super().get_table_comment(inspector, table_name, schema)
