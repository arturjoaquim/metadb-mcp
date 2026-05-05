Ao desenvolver ou refatorar o projeto MetaDB MCP, siga estritamente a arquitetura proposta baseada nas seguintes regras de responsabilidade e estruturação:

1. **Camada Infrastructure (`infrastructure`)**
   - **Banco de Dados**: Todas as operações de banco de dados, conexão, adapters (PostgreSQL, Oracle, etc.), gerenciadores e query builders devem ficar EXCLUSIVAMENTE dentro do pacote `infrastructure/database`.
   - **Segurança**: Lógicas de autenticação, criptografia (SQLCipher, keyring, JWT) e afins devem ficar em `infrastructure/security`.
   - Nenhuma regra de negócio ou orquestração da aplicação deve vazar para a camada de infraestrutura.

2. **Camada Application (`application`)**
   - **Orquestração e Serviços**: Esta camada é responsável por orquestrar os casos de uso da aplicação, chamando os componentes da `infrastructure` ou `interfaces` conforme necessário.
   - Qualquer fluxo de negócio coordenado (como sincronização complexa, fluxo de login consolidado) deve ser implementado em serviços dentro desta camada.

3. **Camada Interfaces (`interfaces`)**
   - **Controladores**: Os controllers (rotas web e MCP stdio) devem ficar nesta camada, recebendo requisições e delegando a orquestração para `application` ou instâncias configuradas.
   - **DTOs**: Todos os modelos de entrada (requests) e saída (responses) que não sejam modelos diretos de banco de dados devem residir em `interfaces/dtos`.
   - **Módulos Web**: Arquivos estáticos (CSS, JS) e templates HTML devem ficar em `interfaces/web`.

4. **Módulo Shared (`shared`)**
   - **Utilidades**: Funções comuns, constantes, utilitários de tratamento de erros, formatadores e logs que podem ser reutilizados entre `infrastructure`, `application` e `interfaces` devem ser colocados em `shared`.
   - **Abstração de Repetições**: Ao notar blocos lógicos repetitivos em múltiplos pontos do código, refatore-os extraindo para utilidades dentro do módulo `shared`.

Sempre siga a estrutura de pastas estabelecida. Não recrie diretórios fora destes escopos.
