# Changelog
Todos os registros de modificação notáveis deste projeto serão documentados neste arquivo.

O formato baseia-se em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/), e este projeto adere ao [Semantic Versioning](https://semver.org/).

## [1.1.0] - 2026-04-27
### Added
- Script proxy `sse_proxy.py` (`utils-for-client/sse_proxy.py`) e documentação de integração com *stdio* para editores que não suportam conexão nativa via SSE.
- Colunas `comment` nos modelos ORM (`SyncTable` e `SyncColumn`) para extração e persistência de comentários nativos do banco de dados.
- Parâmetros opcionais `schema` e `dbname` nas ferramentas MCP (`get_table_columns`, `get_table_indexes`, `get_table_constraints`, `get_domain_context`) para lidar com colisões de nomes.
- Lógica de validação de ambiguidade em `_validate_tables` no `mcp_server.py`, que instrui o agente caso existam múltiplas tabelas com o mesmo nome em diferentes contextos.

### Changed
- O arquivo de regras foi renomeado e movido para `utils-for-client/rule-suggestion.md`.
- Transformação do antigo arquivo `INSTRUCOES_EDITOR.md` em um guia consolidado (`README.md`), incluindo configuração de proxy.
- Otimização da camada de rotas (`mcp_server.py`) delegando as consultas ao banco inteiramente ao repositório `DatabaseManager.get_tables`.
- Atualização massiva de todas as `docstrings` no `mcp_server.py`, explicitando parâmetros, formatos esperados e fornecendo instruções claras para a IA.
- Refatoração da extração de comentários centralizando o método `get_table_comment` na classe abstrata `BaseDBAdapter`.

### Removed
- Métodos duplicados para obtenção de comentários nos adapters específicos (`oracle_adapter.py` e `postgres_adapter.py`) em favor da implementação universal do SQLAlchemy.
