# Plano de Implementação - Refatoração de Arquitetura

Este plano descreve as etapas para reorganizar o projeto "MetaDB MCP" em uma estrutura mais clara e modular baseada em responsabilidades (`infrastructure`, `application`, `interfaces`, `shared`), conforme solicitado. Como a aplicação não possui domínio rico, a camada de `domain` foi dispensada.

## User Review Required
> [!IMPORTANT]
> Verifique se a distribuição de pacotes a seguir está de acordo com as suas expectativas antes de prosseguirmos com a execução.

## Estrutura Proposta

A organização final dos diretórios ficará da seguinte forma:

```text
mcp_metadb/
├── application/                # Orquestração e serviços
│   └── services/               # Serviços que orquestram a aplicação
├── infrastructure/             # Acesso a banco, segurança e tecnologias externas
│   ├── database/               # (Antigo core/database)
│   │   ├── base_adapter.py
│   │   ├── manager.py
│   │   ├── models.py
│   │   ├── oracle_adapter.py
│   │   ├── postgres_adapter.py
│   │   └── secure_connection.py
│   └── security/
│       └── auth_service.py     # (Antigo core/auth_service.py)
├── interfaces/                 # Portas de entrada para a aplicação
│   ├── dtos/                   # Modelos de request/response (retirados do main.py)
│   │   └── requests.py
│   ├── controllers/            # Controladores de rotas e protocolo
│   │   ├── web_controller.py   # Rotas FastAPI (retiradas do main.py)
│   │   └── mcp_controller.py   # (Antigo core/mcp_server.py)
│   └── web/                    # (Movido do diretório raiz)
│       ├── static/
│       └── templates/
├── shared/                     # Utilidades e abstrações reutilizáveis entre módulos
│   └── utils/                  
├── main.py                     # Entrypoint simplificado (orquestração e setup do servidor)
└── ... (outros arquivos: testes, requirements, etc)
```

## Proposed Changes

Abaixo estão as modificações por pacote:

### Agent Skills (Rules)
- **[NEW]** `.agents/rules/architecture.md`: Criação de uma nova skill instruindo que:
  - Regras de banco de dados devem ficar em `infrastructure/database`.
  - Orquestração da aplicação deve ficar na camada `application`.
  - DTOs de entrada/saída, controllers e módulos web devem ficar na camada `interfaces`.
  - Códigos utilitários reutilizáveis devem ficar no módulo `shared`.

### Infrastructure
Criação do pacote `infrastructure` para abrigar banco de dados e segurança.
- **[NEW]** `infrastructure/__init__.py`, `infrastructure/database/__init__.py`, `infrastructure/security/__init__.py`
- **[MODIFY]** Mover e renomear imports em `core/database/*` para `infrastructure/database/` e `core/auth_service.py` para `infrastructure/security/auth_service.py`.

### Application
Isolamento da lógica de orquestração do sistema em serviços dedicados.
- **[NEW]** `application/__init__.py`, `application/services/__init__.py`
- **[NEW]** Criar classes ou módulos em `application` para assumir o papel de orquestradores das operações que coordenam `infrastructure` (ex: fluxo de sync, fluxo de login), tirando essa responsabilidade de outras camadas e controllers.

### Interfaces
Separação clara entre protocolo HTTP (FastAPI) e Stdio (MCP).
- **[NEW]** `interfaces/__init__.py`, `interfaces/dtos/__init__.py`, `interfaces/controllers/__init__.py`
- **[NEW]** `interfaces/dtos/requests.py`: Extração das classes `AuthRequest`, `ConnectionRequest` e `SyncRequest` de `main.py`.
- **[NEW]** `interfaces/controllers/web_controller.py`: Extração de todas as rotas e dependências FastAPI (`@app.get`, `@app.post`, `require_auth`) de `main.py`.
- **[MODIFY]** Mover `core/mcp_server.py` para `interfaces/controllers/mcp_controller.py` e atualizar os imports.
- **[MODIFY]** Mover o diretório `web/` inteiro para `interfaces/web/` e atualizar caminhos no FastAPI em `web_controller.py`.

### Shared
Criação do módulo para compartilhar utilitários globais e abstrair código repetitivo.
- **[NEW]** `shared/__init__.py`, `shared/utils/`
- **[MODIFY]** Refatorar e abstrair trechos com repetição de código no projeto atual (ex: tratamento de erros repetitivos, formatação de logs, ou inicializações) e alocá-los em `shared`, para que `interfaces`, `application` e `infrastructure` os reutilizem.

### Entrypoint (main.py)
Simplificação do `main.py` para atuar puramente como bootstrap.
- **[MODIFY]** `main.py`: Remover controllers, lógicas e dtos. Apenas importar as rotas do `web_controller.py`, inicializar a orquestração via `application` e disparar a aplicação HTTP e o MCP (`mcp_controller.py`).

### Cleanup
- **[DELETE]** Diretório `core/` será removido após todos os arquivos serem realocados.

## Verification Plan

### Automated Tests
- Rodar o pacote de testes local: `pytest` (ou comando equivalente). 
- Caso algum teste falhe por problemas de imports (provavelmente em `tests/`), estes testes precisarão ser atualizados.

### Manual Verification
- Iniciar a aplicação localmente (`python main.py`).
- Acessar o dashboard para garantir que os arquivos estáticos (`/static/...`) e templates (`/templates/...`) foram carregados corretamente a partir do novo diretório `interfaces/web/`.
- Fazer login/logout para confirmar as integrações de segurança e banco de dados.
- Realizar uma requisição de conexão e sincronização de dados simulada.
