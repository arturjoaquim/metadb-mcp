# Changelog
Todos os registros de modificação notáveis deste projeto serão documentados neste arquivo.

O formato baseia-se em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/), e este projeto adere ao [Semantic Versioning](https://semver.org/).

## [5.3.0] - 2026-05-06
### Added
- Novos métodos no `SyncDAO` para consulta granular de colunas, índices, constraints, amostras e busca textual unificada, permitindo reaproveitamento de código em outros serviços.

### Changed
- Refatoração profunda do `MetadataService` para delegar todas as operações de banco de dados ao `SyncDAO`.
- Encapsulamento de lógicas complexas de busca e consulta de metadados dentro da camada de infraestrutura (`SyncDAO`).
- Remoção completa de dependências diretas de modelos SQLAlchemy e queries `session.query` na camada de aplicação (`MetadataService`), respeitando os princípios de Clean Architecture e SOLID.

## [5.2.0] - 2026-05-06
### Added
- Nova ferramenta MCP `get_table_description` para obter o comentário descritivo de uma tabela específica usando nome exato, schema e dbname.
- Ferramenta MCP `search_metadata` (unificada) para busca textual em nomes e comentários de tabelas e colunas.

### Changed
- Refatoração do `MetadataService` para unificar buscas por nome e comentário em um único método otimizado.
- Atualização das instruções das ferramentas `list_sync_tables` para orientar os modelos a utilizarem a ferramenta de busca (`search_metadata`) em vez de listar todas as tabelas.

## [5.1.1] - 2026-05-06
### Fixed
- Problemas de encoding ao salvar metadados e amostras no cache local, garantindo o uso de UTF-8 real e desativando sequências de escape JSON desnecessárias via `ensure_ascii=False`.
- Melhoria na serialização de amostras de dados para tratar corretamente objetos `bytes` e preservar valores `null` (None) em vez de convertê-los para strings.

### Changed
- Configuração explícita de UTF-8 no evento de conexão do SQLCipher (`PRAGMA encoding`) e na string de conexão do PostgreSQL (`client_encoding=utf8`).

## [5.1.0] - 2026-05-06
### Added
- Padronização de metadados para minúsculo no cache local, incluindo nomes de tabelas, esquemas, colunas, índices, constraints e **comentários**.
- Testes unitários para validar a integridade da padronização de caixa (lowercase) nos serviços de sincronização e metadados.

### Changed
- Refatoração do `SyncService` para persistir todos os identificadores e comentários sempre em minúsculo.
- Atualização do `MetadataService` para converter termos de busca (tabelas e esquemas) para minúsculo antes de consultar o banco de dados.

## [5.0.2] - 2026-05-06
### Fixed
- Correção dos scripts `start_mcp.sh` e `start_mcp.bat` para apontarem para o novo local do ponto de entrada (`src/main.py`), resolvendo o erro de arquivo não encontrado na inicialização.

## [5.0.1] - 2026-05-06
### Fixed
- Remoção de blocos `try...except` aninhados no `SyncService` que mascaravam falhas durante a extração de índices, constraints e amostras, garantindo a integridade da transação via rollback em caso de erro.

## [5.0.0] - 2026-05-06
### Added
- Módulo `providers.py` atuando como Composition Root para centralizar a injeção de dependências do projeto.
- Implementação de Injeção de Dependência por Construtor em todos os serviços (`application/services/`) e controladores.

### Changed
- Renomeação dos adaptadores de banco de dados para Extratores de Metadados (`BaseMetadataExtractor`, `PostgresMetadataExtractor`, `OracleMetadataExtractor`) para alinhar o nome à responsabilidade de extração de metadados.
- Refatoração completa dos serviços `SyncService`, `DashboardService`, `MetadataService` e `AuthService` para eliminar dependências globais e permitir testes com mocks.
- Atualização do `main.py` para utilizar o novo fluxo de inicialização baseado em provedores.

### Removed
- Arquivo `src/infrastructure/database/manager.py`, cujas responsabilidades foram distribuídas entre os novos serviços e DAOs.

## [4.2.0] - 2026-05-05
### Added
- Criação da diretriz de IA `.agents/skills/software-quality/SKILL.md` que instrui a criação obrigatória de testes automatizados e o rigoroso seguimento dos princípios SOLID e Inversão de Dependência (Dependency Inversion) durante o desenvolvimento.

### Changed
- Estrutura das skills (`architecture` e `software-quality`) atualizada para o formato oficial de diretórios contendo arquivos `SKILL.md` com YAML frontmatter.

## [4.1.0] - 2026-05-04
### Changed
- Separação das lógicas de acesso a dados contidas em `src/infrastructure/database/manager.py` para DAOs específicos em `src/infrastructure/database/daos/` (`ConnectionDAO` e `SyncDAO`), diminuindo o acoplamento e o tamanho do gerenciador.

## [4.0.1] - 2026-05-04
### Fixed
- Erro `RuntimeError: Directory 'interfaces/web/static' does not exist` resolvido utilizando caminhos absolutos baseados na localização do arquivo atual (`pathlib.Path(__file__)`) para os diretórios `static` e `templates`, evitando problemas ao rodar o script fora da raiz do projeto.

## [4.0.0] - 2026-05-04
### Added
- Criação de nova estrutura de projeto modular baseada em separação de responsabilidades (Clean Architecture style).
- Todos os pacotes (`application`, `infrastructure`, `interfaces`, `shared`) e o `main.py` encapsulados na pasta `src/`.
- Criação do pacote `infrastructure` contendo as regras de `database` e `security`.
- Criação da camada `interfaces` armazenando DTOs (`requests.py`), Web (`web/`) e os Controladores FastAPI e MCP (`web_controller.py` e `mcp_controller.py`).
- Criação do módulo `shared` com o pacote de utilitários de rede `network.py`.
- Criação do pacote `application` visando hospedar a orquestração do sistema. Adição do `MetadataService` (`metadata_service.py`) que abstrai a lógica de chamadas ao banco antes pertencentes aos controllers.
- Inclusão da diretriz de IA `.agents/skills/architecture.md` (promovida de rule para skill).

### Changed
- Organização do diretório de testes (`tests/`) para espelhar a árvore de pacotes do `src/` (ex: `tests/infrastructure/security/`).
- Refatoração do `mcp_controller.py` para não realizar acesso direto ao banco, aderindo de fato à nova arquitetura ao injetar/delegar solicitações de dados ao `MetadataService`.
- Refatoração do `main.py` para atuar puramente como bootstrap da aplicação, inicializando middlewares, instanciando rotas de controlers e iniciando servidores em threads separadas.
- Remoção do diretório centralizado `core/` em favor da estrutura modular em `src/`.

## [3.2.0] - 2026-05-04
### Added
- Seleção dinâmica de porta (`find_free_port`) para o servidor web no `main.py`, permitindo múltiplas execuções simultâneas do MCP sem conflito.
- Logs aprimorados durante a inicialização do MCP, indicando o endereço exato do dashboard.

### Changed
- Mensagem de erro de "banco de dados bloqueado" no `mcp_server.py` agora informa a URL exata do dashboard (ex: `http://127.0.0.1:8001`) para facilitar o desbloqueio quando múltiplas instâncias da IDE estão abertas.

## [3.1.1] - 2026-05-04
### Fixed
- Correção no script do dashboard (`script.js`) para garantir a limpeza completa de formulários e área de visualização de tabelas após o logout, impedindo que dados de conexão permaneçam no DOM (tela) de forma residual.

## [3.1.0] - 2026-05-04
### Added
- Scripts de inicialização automática `start_mcp.sh` (Unix) e `start_mcp.bat` (Windows) para configuração plug-and-play do servidor MCP. Esses scripts criam o ambiente virtual (`venv`) e instalan as dependências automaticamente caso não existam.

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
