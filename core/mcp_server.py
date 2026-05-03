from typing import Optional, List, Tuple, Any
from mcp.server.fastmcp import FastMCP
from . import database
from .database import (
    SyncTable,
    SyncColumn,
    SyncIndex,
    SyncConstraint,
    SyncSample,
)

mcp = FastMCP("metadb-control-plane")


def _require_unlocked() -> Optional[str]:
    """Retorna mensagem de erro se o banco está locked, None caso contrário."""
    if not database.secure_connection.is_unlocked or database.db_manager is None:
        return "⚠️ Banco de dados está bloqueado. Faça login no dashboard web para desbloquear."
    return None


def _validate_tables(
    session: Any, tables: List[SyncTable], table_name: str
) -> Tuple[Optional[SyncTable], Optional[str]]:
    if not tables:
        return (
            None,
            f"Tabela '{table_name}' não encontrada no cache com os filtros fornecidos.",
        )
    if len(tables) > 1:
        options = []
        for t in tables:
            conn = database.db_manager.get_dbconnection_by_id(session, t.connection_id)
            dbname = conn.dbname if conn else "Desconhecido"
            options.append(f"schema: '{t.schema_name}', dbname: '{dbname}'")
        return (
            None,
            f"Ambiguidade detectada. A tabela '{table_name}' existe em múltiplos contextos. Por favor refine sua busca passando os argumentos 'schema' e/ou 'dbname'. Opções disponíveis:\n"
            + "\n".join(f"- {opt}" for opt in options),
        )
    return tables[0], None


@mcp.tool()
async def list_sync_tables() -> str:
    """Lista todas as tabelas disponíveis no cache local que foram previamente autorizadas e sincronizadas pelo usuário.
    Use esta ferramenta como primeiro passo para entender o escopo do banco de dados antes de detalhar colunas ou constraints.
    Argumentos:
        Nenhum.
    Retorno:
        Lista formatada com '- schema.tabela'."""
    error = _require_unlocked()
    if error:
        return error
        
    session = database.db_manager.get_session()
    try:
        tables = session.query(SyncTable).all()
        if not tables:
            return "Nenhuma tabela sincronizada no momento."

        result = [f"- {t.schema_name}.{t.table_name}" for t in tables]
        return "Tabelas sincronizadas:\n" + "\n".join(result)
    finally:
        session.close()


@mcp.tool()
async def get_table_columns(
    table_name: str, schema: Optional[str] = None, dbname: Optional[str] = None
) -> str:
    """Retorna o esquema detalhado (colunas, tipos de dados e nulidade) de uma tabela específica.
    Utilize esta ferramenta para construir queries SQL precisas e entender a tipagem de cada campo.
    Argumentos:
        table_name (str): Nome exato da tabela (ex: 'users'). Obrigatório.
        schema (Optional[str]): Nome do schema (útil para evitar pegar tabelas com nomes iguais de outros schemas).
        dbname (Optional[str]): Nome do banco de dados da conexão (útil para desambiguação entre conexões diferentes).
    Retorno:
        Exemplo de Saída: '- id: INTEGER (NOT NULL)' ou mensagem de erro caso não encontrada."""
    error = _require_unlocked()
    if error:
        return error
        
    session = database.db_manager.get_session()
    try:
        tables = database.db_manager.get_tables(session, table_name, schema, dbname)
        table, error_msg = _validate_tables(session, tables, table_name)
        if error_msg:
            return error_msg

        columns = session.query(SyncColumn).filter_by(table_id=table.id).all()
        result = [f"Colunas de {table_name}:"]
        for col in columns:
            nullable = "NULL" if col.is_nullable else "NOT NULL"
            result.append(f"- {col.column_name}: {col.data_type} ({nullable})")
        return "\n".join(result)
    finally:
        session.close()


@mcp.tool()
async def get_table_indexes(
    table_name: str, schema: Optional[str] = None, dbname: Optional[str] = None
) -> str:
    """Lista todos os índices de uma tabela, indicando unicidade e colunas indexadas.
    Útil para identificar quais colunas são otimizadas para filtros (WHERE) e ordenação (ORDER BY).
    Argumentos:
        table_name (str): Nome exato da tabela. Obrigatório.
        schema (Optional[str]): Nome do schema. Opcional, mas recomendado para desambiguação.
        dbname (Optional[str]): Nome do banco de dados. Opcional, mas recomendado para desambiguação.
    Retorno:
        Lista detalhada de índices com suas colunas ou mensagem caso a tabela não exista."""
    error = _require_unlocked()
    if error:
        return error
        
    session = database.db_manager.get_session()
    try:
        tables = database.db_manager.get_tables(session, table_name, schema, dbname)
        table, error_msg = _validate_tables(session, tables, table_name)
        if error_msg:
            return error_msg

        indexes = session.query(SyncIndex).filter_by(table_id=table.id).all()
        if not indexes:
            return f"Nenhum índice encontrado para '{table_name}'."

        result = [f"Índices de {table_name}:"]
        for idx in indexes:
            unique_str = "ÚNICO" if idx.is_unique else "NÃO ÚNICO"
            result.append(f"- {idx.index_name} ({unique_str}): colunas = {idx.columns}")
        return "\n".join(result)
    finally:
        session.close()


@mcp.tool()
async def get_table_constraints(
    table_name: str, schema: Optional[str] = None, dbname: Optional[str] = None
) -> str:
    """Retorna restrições de integridade, como Chaves Primárias (PRIMARY KEY) e Chaves Estrangeiras (FOREIGN KEY).
    ESSENCIAL para entender como realizar JOINs entre tabelas e identificar identificadores únicos.
    Argumentos:
        table_name (str): Nome exato da tabela. Obrigatório.
        schema (Optional[str]): Nome do schema. Opcional, mas recomendado.
        dbname (Optional[str]): Nome do banco de dados. Opcional, mas recomendado.
    Retorno:
        Detalhes das constraints, incluindo tabelas e colunas referenciadas em caso de FK."""
    error = _require_unlocked()
    if error:
        return error
        
    session = database.db_manager.get_session()
    try:
        tables = database.db_manager.get_tables(session, table_name, schema, dbname)
        table, error_msg = _validate_tables(session, tables, table_name)
        if error_msg:
            return error_msg

        constraints = session.query(SyncConstraint).filter_by(table_id=table.id).all()
        if not constraints:
            return f"Nenhuma constraint encontrada para '{table_name}'."

        result = [f"Constraints de {table_name}:"]
        for const in constraints:
            if const.constraint_type == "FOREIGN KEY":
                result.append(
                    f"- {const.constraint_name} ({const.constraint_type}): {const.columns} referenciando {const.ref_table}({const.ref_columns})"
                )
            else:
                result.append(
                    f"- {const.constraint_name} ({const.constraint_type}): {const.columns}"
                )
        return "\n".join(result)
    finally:
        session.close()


@mcp.tool()
async def get_domain_context(
    table_name: str, schema: Optional[str] = None, dbname: Optional[str] = None
) -> str:
    """Fornece uma visão prática dos dados reais (amostra de 10 linhas) para entender o domínio de negócio.
    Use esta ferramenta quando o nome da coluna for ambíguo ou para entender padrões de valores (ex: formatos de data, enums, prefixos).
    Argumentos:
        table_name (str): Nome exato da tabela. Obrigatório.
        schema (Optional[str]): Nome do schema. Opcional, mas recomendado.
        dbname (Optional[str]): Nome do banco de dados. Opcional, mas recomendado.
    Retorno:
        Dados da amostra em formato JSON ou string, representando as linhas originais."""
    error = _require_unlocked()
    if error:
        return error
        
    session = database.db_manager.get_session()
    try:
        tables = database.db_manager.get_tables(session, table_name, schema, dbname)
        table, error_msg = _validate_tables(session, tables, table_name)
        if error_msg:
            return error_msg

        samples = session.query(SyncSample).filter_by(table_id=table.id).all()
        if not samples:
            return f"Nenhuma amostra de dados encontrada para '{table_name}'."

        result = [f"Amostras de dados para {table_name}:"]
        for s in samples:
            result.append(s.row_data)
        return "\n".join(result)
    finally:
        session.close()


@mcp.tool()
async def search_metadata(query: str) -> str:
    """Realiza uma busca textual por termos específicos nos nomes de tabelas e colunas do cache.
    Use esta ferramenta para localizar onde uma informação específica pode estar armazenada quando você não conhece o nome da tabela.
    Argumentos:
        query (str): Termo de busca (ex: 'email', 'price', 'customer'). Obrigatório.
    Retorno:
        Lista com as tabelas e colunas que contém o termo pesquisado em seus nomes."""
    error = _require_unlocked()
    if error:
        return error
        
    session = database.db_manager.get_session()
    try:
        result = []
        search_term = f"%{query}%"

        # Buscar tabelas
        tables = (
            session.query(SyncTable)
            .filter(SyncTable.table_name.ilike(search_term))
            .all()
        )
        if tables:
            result.append("Tabelas encontradas:")
            for t in tables:
                result.append(f"- {t.table_name}")

        # Buscar colunas
        columns = (
            session.query(SyncColumn, SyncTable.table_name)
            .join(SyncTable, SyncColumn.table_id == SyncTable.id)
            .filter(SyncColumn.column_name.ilike(search_term))
            .all()
        )
        if columns:
            result.append("\nColunas encontradas:")
            for col, tbl_name in columns:
                result.append(f"- {col.column_name} (na tabela {tbl_name})")

        if not result:
            return f"Nenhum resultado encontrado para o termo '{query}'."

        return "\n".join(result)
    finally:
        session.close()
