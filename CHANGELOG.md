# Changelog
Todos os registros de modificação notáveis deste projeto serão documentados neste arquivo.

O formato baseia-se em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/), e este projeto adere ao [Semantic Versioning](https://semver.org/).

## [7.2.0] - 2026-05-19
### Added
- Teste de integração (`test_sync_service_oracle.py`) para validar as transações isoladas e captura de erros globais no Oracle.
- Adicionado o método abstrato `preload_metadata` em `BaseMetadataExtractor` para viabilizar otimizações em lote na extração.

### Changed
- Refatoração da transação principal no `SyncService.sync_tables`. Agora a sincronização ocorre com commit isolado por tabela. Caso uma tabela falhe, ela não aborta ou invalida o processo das tabelas que já tiveram sucesso.
- O `SyncService.sync_tables` agora lança uma exceção global (`SyncServiceError`) ao final do processo listando todas as tabelas que não puderam ser sincronizadas.
- Otimização crítica de performance no `OracleMetadataExtractor`. As chamadas isoladas por tabela utilizando o *Inspector* (que demoravam consideravelmente) foram substituídas por um `preload_metadata` que executa consultas únicas otimizadas nas views do sistema (`ALL_TAB_COLUMNS`, `ALL_CONSTRAINTS`, `ALL_INDEXES`) trazendo em cache a metadados de todas as tabelas em batch antes da persistência local.

## [7.1.4] - 2026-05-19
### Changed
- Adicionado logging detalhado a cada etapa do processo de sincronização no método `SyncService.sync_tables`.

### Fixed
- Corrigida a inicialização de drivers do Oracle no extrator de metadados (`OracleMetadataExtractor`) dentro do ambiente de testes unitários mockando o método `os.path.isdir`.
- Corrigido teste obsoleto do `DashboardService.test_get_tables_persists_connection` para validar o retorno correto das tabelas e tabelas sincronizadas ao invés do salvamento de conexão.

### Security
- Removido o log do `username` do usuário nos logs de geração de salt, registro e login no `AuthService` para sanar vulnerabilidade de exposição de credenciais.

## [7.1.3] - 2026-05-07
### Fixed
- Corrigida a falha na exibição do estado de sincronização e sensibilidade das tabelas no dashboard. A solução implementa comparação *case-insensitive* entre os nomes retornados pelo banco remoto e os metadados do cache local.
- Preservação da visualização original dos nomes das tabelas (ex: nomes em maiúsculo no Oracle permanecem em maiúsculo na tela) enquanto garante a correta identificação do status de sincronização.
- Ajuste no `SyncService` para que a detecção de tabelas sensíveis durante a sincronização também ignore a caixa dos caracteres.

## [7.1.2] - 2026-05-07
### Fixed
- Corrigida a implementação de `OracleMetadataExtractor.get_all_tables()` que usava incorretamente `inspector.get_schema_names()` + `inspector.get_table_names(schema=X)`, uma abordagem que lista *todos os usuários do banco* (`ALL_USERS`) e tenta acessar tabelas de schemas sem permissão, retornando resultados incompletos ou incorretos.
- A nova implementação consulta diretamente a view `ALL_TABLES`, que retorna apenas as tabelas visíveis ao usuário conectado, com filtro de schemas de sistema aplicado na própria query SQL.
- Atualização dos testes unitários de `get_all_tables` para refletir a nova abordagem baseada em `engine.connect().execute()`.

## [7.1.1] - 2026-05-07
### Fixed
- Melhoria na estabilidade do `OracleMetadataExtractor`: agora valida a existência do diretório do driver e trata erros de inicialização duplicada do `oracledb.init_oracle_client`, evitando crashes em reconexões.


## [7.1.0] - 2026-05-07
### Added
- Campo opcional **Caminho do Driver** (`driver_path`) no dashboard para especificar o caminho absoluto do Oracle Instant Client. O campo é exibido condicionalmente apenas quando o tipo de banco é Oracle.
- Novo campo `driver_path` no modelo `DBConnection` (genérico, reutilizável por qualquer tipo de banco no futuro).
- Testes unitários para o `OracleMetadataExtractor`: validação de exclusão de schemas de sistema, comportamento do `initialize_drivers` com e sem `driver_path`, e propagação do `driver_path` pelo `SyncService`.

### Changed
- Refatoração do `OracleMetadataExtractor.get_all_tables()` para buscar tabelas de **todos os schemas**, excluindo ~30 schemas internos do Oracle (SYS, SYSTEM, XDB, APEX_*, etc.), igualando o comportamento ao `PostgresMetadataExtractor`.
- `OracleMetadataExtractor.initialize_drivers()` agora só chama `oracledb.init_oracle_client()` quando `driver_path` é fornecido; caso contrário, não faz nada (modo thin do oracledb).
- Propagação do `driver_path` por toda a cadeia: DTOs → WebController → DashboardService → SyncService → Factory → BaseMetadataExtractor → ConnectionDAO.

### Fixed
- Correção de testes pré-existentes: `ConcreteExtractor` em `test_base_metadata_extractor.py` agora implementa `initialize_drivers`, e lambdas de factory nos testes aceitam `**kwargs`.

## [7.0.0] - 2026-05-06
### Added
- Funcionalidade de **Tabelas Sensíveis**: usuários podem marcar tabelas para que amostras de dados não sejam coletadas durante a sincronização.
- Controle de **Tamanho da Amostra**: campo configurável no dashboard para definir a quantidade de linhas coletadas por tabela.
- Novos campos `is_sensitive` e `sample_size` no modelo `MetadataTable` para persistência das configurações por tabela.
- Exibição de sensibilidade e tamanho da amostra nas ferramentas MCP `list_sync_tables` e `get_table_description`.

### Changed
- [BREAKING CHANGE] Alteração no esquema do banco de dados local (`metadata_tables`). Bancos existentes precisam ser recriados.
- Atualização do `SyncService` e `DashboardService` para suportar os novos parâmetros de sincronização.
- Refatoração da ferramenta `get_domain_context` para proteger tabelas sensíveis.

### Fixed
- Proteção automática contra tabelas com menos registros que o tamanho de amostra solicitado (via `fetchmany`).
- Correção: tabelas marcadas como sensíveis agora mantêm o estado visual ao reconectar ao banco remoto, restaurando `is_sensitive` e `sample_size` do cache local.

## [6.1.0] - 2026-05-06
### Added
- Novas dataclasses em `extracted_metadata.py` para representar metadados extraídos de forma agnóstica ao ORM.
- Métodos de extração no `BaseMetadataExtractor` (`extract_columns`, `extract_indexes`, etc.) que encapsulam a lógica de inspeção do SQLAlchemy e normalizam os dados.
- Método `save_table_metadata` no `MetadataDAO` para encapsular a persistência completa de uma tabela e seus metadados (colunas, índices, constraints, amostras).

### Changed
- Refatoração do `SyncService` para remover o conhecimento direto de conceitos de banco de dados (SQLAlchemy Inspector, queries raw, criação de modelos ORM).
- O `SyncService` agora atua como um orquestrador puro, delegando a extração ao `Extractor` e a persistência ao `MetadataDAO`.
- Centralização da lógica de normalização para minúsculo na camada de infraestrutura (Extractors e DAOs).

## [6.0.0] - 2026-05-06
### Added
- Renomeação completa de todos os modelos ORM de metadados (`SyncTable`, `SyncColumn`, etc.) para `MetadataTable`, `MetadataColumn`, etc.

### Changed
- [BREAKING CHANGE] Renomeação dos nomes das tabelas no banco de dados local (`sync_tables` -> `metadata_tables`, etc.). Bancos existentes precisam ser recriados.
- Atualização de todas as chaves estrangeiras e referências no código para refletir a nova nomenclatura focada em metadados.

## [5.3.1] - 2026-05-06
### Changed
- Renomeação do `SyncDAO` para `MetadataDAO` e do arquivo `sync_dao.py` para `metadata_dao.py` para melhor clareza semântica e evitar confusão com o `SyncService`.
- Atualização de todas as referências e injeções de dependência para refletir o novo nome do DAO em todos os serviços e provedores.

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
