# Changelog
Todos os registros de modificação notáveis deste projeto serão documentados neste arquivo.

O formato baseia-se em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/), e este projeto adere ao [Semantic Versioning](https://semver.org/).

## [3.0.3] - 2026-05-03
### Fixed
- Erro `AttributeError: 'NoneType' object has no attribute 'test_connection'` no `main.py` corrigido ajustando a importação do `db_manager` para refletir sua inicialização tardia de forma correta.

## [3.0.2] - 2026-05-03
### Fixed
- Erro `keyring.errors.NoKeyringError` em ambientes Linux corrigido com a adição da dependência `keyrings.alt`.

## [3.0.1] - 2026-05-03
### Fixed
- Erro `TypeError: Cannot read properties of null (reading 'addEventListener')` no script de frontend (`script.js`) resolvido com checagem de nulidade em elementos DOM.

## [3.0.0] - 2026-05-03
### Added
- Telas de Cadastro Inicial e Login no dashboard web para proteção do console.
- Autenticação por token JWT (`HttpOnly` cookie) para proteção da API REST do dashboard.
- Inicialização dinâmica da conexão de banco de dados (`DatabaseManager`) apenas após autenticação e desbloqueio bem-sucedido.
- Suporte a armazenamento de segredos sensíveis com `keyring` (dependente de D-Bus/Secret Service API no Linux; limitação identificada em ambientes puramente headless, a ser tratada no futuro).

### Changed
- Banco de dados local migrado de SQLite padrão para **SQLCipher**, garantindo criptografia em repouso AES-256 para todas as conexões armazenadas e metadados.
- Criação e validação do banco centralizadas no `SecureConnectionManager` que gerencia o ciclo de vida da KDF.
- Ferramentas do MCP (`mcp_server.py`) agora validam se o banco local está ativo e desbloqueado, retornando mensagem explícita caso contrário.

### Security
- A senha local e a master key não são armazenadas em nenhum arquivo ou banco.
- Utilização de **Argon2id** (256MB) para Key Derivation Function (KDF), evitando força-bruta e usando as credenciais do usuário apenas em runtime para desbloquear o `sqlcipher`.

## [2.0.0] - 2026-05-03
### Changed
- Transporte MCP migrado de SSE (Server-Sent Events) para stdio nativo.
- Servidor web (dashboard) e servidor MCP agora executam no mesmo processo Python, em threads separadas.
- Stdout e stderr globais são redirecionados para arquivo de log para evitar contaminação do protocolo stdio.
- Argumentos de linha de comando (`--host`, `--port`, `--log-file`) adicionados para configuração flexível.

### Removed
- Montagem SSE removida do FastAPI (`/mcp/sse`).
- Script proxy `sse_proxy.py` removido (obsoleto com stdio nativo).

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
