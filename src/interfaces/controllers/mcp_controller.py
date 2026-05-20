import os
from typing import Optional
from mcp.server.fastmcp import FastMCP
from application.services.metadata_service import MetadataService

def init_mcp_controller(metadata_service: MetadataService) -> FastMCP:
    mcp = FastMCP("metadb-control-plane")


    def _require_unlocked() -> Optional[str]:
        """Retorna mensagem de erro se o banco está locked, None caso contrário."""
        if not metadata_service.is_database_unlocked():
            web_url = os.environ.get("METADB_WEB_URL", "http://127.0.0.1:8000")
            return f"⚠️ Banco de dados está bloqueado. Faça login no dashboard web ({web_url}) para desbloquear."
        return None


    @mcp.tool()
    async def list_sync_tables() -> str:
        """Lista todas as tabelas sincronizadas no cache local.

        Use quando não souber nenhuma informação sobre as tabelas disponíveis. Se tiver um palpite ou conceito de negócio, prefira usar 'search_metadata' para busca direcionada.

        Argumentos:
            Nenhum.

        Retorno:
            Formato: Lista de tabelas em formato '- schema.tabela [🔒 SENSÍVEL]' (tag sensível aparece se aplicável)."""
        error = _require_unlocked()
        if error:
            return error
            
        return metadata_service.list_sync_tables()


    @mcp.tool()
    async def get_table_columns(
        table_name: str, schema: Optional[str] = None, dbname: Optional[str] = None
    ) -> str:
        """Retorna o esquema detalhado de uma tabela (colunas, tipos de dados e nulidade).

        Use para construir queries SQL precisas e entender a tipagem de cada campo antes de executar operações.

        Argumentos:
            table_name (str): Nome exato da tabela. Obrigatório.
            schema (Optional[str]): Nome do schema para desambiguação. Opcional.
            dbname (Optional[str]): Nome do banco de dados para desambiguação entre conexões. Opcional.

        Retorno:
            Formato: '- nome_coluna: TIPO_DADOS (NOT NULL|NULL)' em cada linha. Exemplo: '- id: INTEGER (NOT NULL)'."""
        error = _require_unlocked()
        if error:
            return error
            
        return metadata_service.get_table_columns(table_name, schema, dbname)


    @mcp.tool()
    async def get_table_indexes(
        table_name: str, schema: Optional[str] = None, dbname: Optional[str] = None
    ) -> str:
        """Lista índices de uma tabela, indicando unicidade e colunas indexadas.

        Use para identificar colunas otimizadas para filtros (WHERE), ordenação (ORDER BY) e melhorar performance de queries.

        Argumentos:
            table_name (str): Nome exato da tabela. Obrigatório.
            schema (Optional[str]): Nome do schema para desambiguação. Opcional.
            dbname (Optional[str]): Nome do banco de dados para desambiguação. Opcional.

        Retorno:
            Formato: '- nome_índice (ÚNICO|NÃO ÚNICO): colunas = col1, col2' em cada linha."""
        error = _require_unlocked()
        if error:
            return error
            
        return metadata_service.get_table_indexes(table_name, schema, dbname)


    @mcp.tool()
    async def get_table_constraints(
        table_name: str, schema: Optional[str] = None, dbname: Optional[str] = None
    ) -> str:
        """Retorna restrições de integridade: Chaves Primárias (PRIMARY KEY) e Estrangeiras (FOREIGN KEY).

        Use para entender relações entre tabelas, realizar JOINs corretos e identificar identificadores únicos.

        Argumentos:
            table_name (str): Nome exato da tabela. Obrigatório.
            schema (Optional[str]): Nome do schema para desambiguação. Opcional.
            dbname (Optional[str]): Nome do banco de dados para desambiguação. Opcional.

        Retorno:
            Formato: '- nome_constraint (TIPO): colunas referenciadas' em cada linha. FKs incluem tabela e coluna alvo."""
        error = _require_unlocked()
        if error:
            return error
            
        return metadata_service.get_table_constraints(table_name, schema, dbname)


    @mcp.tool()
    async def get_domain_context(
        table_name: str, schema: Optional[str] = None, dbname: Optional[str] = None
    ) -> str:
        """Fornece amostras de dados reais para compreender o domínio de negócio e padrões de valores.

        Use para validar entendimento de tipos de dados, formatos (datas, enums, prefixos) e ver dados reais. AVISO: Tabelas marcadas como SENSÍVEL não exibem amostras por proteção de segurança.

        Argumentos:
            table_name (str): Nome exato da tabela. Obrigatório.
            schema (Optional[str]): Nome do schema para desambiguação. Opcional.
            dbname (Optional[str]): Nome do banco de dados para desambiguação. Opcional.

        Retorno:
            Formato: Linhas de dados em formato string/JSON, ou aviso se tabela for sensível ou sem amostras."""
        error = _require_unlocked()
        if error:
            return error
            
        return metadata_service.get_domain_context(table_name, schema, dbname)


    @mcp.tool()
    async def get_table_info(
        table_name: str, schema: Optional[str] = None, dbname: Optional[str] = None
    ) -> str:
        """Retorna informações de uma tabela: comentário descritivo, sensibilidade e quantidade de amostras coletadas.

        Use para entender o propósito e contexto de negócio de uma tabela antes de explorar colunas e dados.

        Argumentos:
            table_name (str): Nome exato da tabela. Obrigatório.
            schema (Optional[str]): Nome do schema para desambiguação. Opcional.
            dbname (Optional[str]): Nome do banco de dados para desambiguação. Opcional.

        Retorno:
            Formato: Comentário descritivo, indicador de sensibilidade (SIM/NÃO) e número de amostras coletadas."""
        error = _require_unlocked()
        if error:
            return error
            
        return metadata_service.get_table_info(table_name, schema, dbname)


    @mcp.tool()
    async def search_metadata(query: str) -> str:
        """Busca textual em nomes e comentários de tabelas e colunas.

        Use para localizar tabelas ou colunas quando não souber o nome exato, mas tiver um palpite ou conceito de negócio (ex: 'email', 'cobrança', 'pedido').

        Argumentos:
            query (str): Termo de busca. Obrigatório.

        Retorno:
            Formato: Tabelas encontradas com seus comentários, seguidas de colunas encontradas com suas tabelas de origem."""
        error = _require_unlocked()
        if error:
            return error
            
        return metadata_service.search_metadata(query)




    @mcp.tool()
    async def get_column_comments(
        table_name: str, schema: Optional[str] = None, dbname: Optional[str] = None
    ) -> str:
        """Retorna comentários descritivos de todas as colunas de uma tabela.

        Use para entender a semântica e significado de cada coluna. Essencial para identificar corretamente quais colunas são relevantes para suas queries.

        Argumentos:
            table_name (str): Nome exato da tabela. Obrigatório.
            schema (Optional[str]): Nome do schema para desambiguação. Opcional.
            dbname (Optional[str]): Nome do banco de dados para desambiguação. Opcional.

        Retorno:
            Formato: '- nome_coluna - comentário descritivo' em cada linha. Exemplo: '- email - Endereço de email do usuário'."""
        error = _require_unlocked()
        if error:
            return error
            
        return metadata_service.get_column_comments(table_name, schema, dbname)

    return mcp
