import os
from typing import Optional
from mcp.server.fastmcp import FastMCP
from application.services.metadata_service import metadata_service

mcp = FastMCP("metadb-control-plane")


def _require_unlocked() -> Optional[str]:
    """Retorna mensagem de erro se o banco está locked, None caso contrário."""
    if not metadata_service.is_database_unlocked():
        web_url = os.environ.get("METADB_WEB_URL", "http://127.0.0.1:8000")
        return f"⚠️ Banco de dados está bloqueado. Faça login no dashboard web ({web_url}) para desbloquear."
    return None


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
        
    return metadata_service.list_sync_tables()


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
        
    return metadata_service.get_table_columns(table_name, schema, dbname)


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
        
    return metadata_service.get_table_indexes(table_name, schema, dbname)


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
        
    return metadata_service.get_table_constraints(table_name, schema, dbname)


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
        
    return metadata_service.get_domain_context(table_name, schema, dbname)


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
        
    return metadata_service.search_metadata(query)
