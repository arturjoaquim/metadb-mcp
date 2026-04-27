---
trigger: always_on
---

Ao realizar alterações no projeto, você deve seguir estritamente os padrões Semantic Versioning (2.0.0) e Keep a Changelog (1.0.0).

1. Versionamento Semântico (SemVer)
Toda nova versão deve seguir o formato MAJOR.MINOR.PATCH baseada no tipo de alteração realizada:

MAJOR (X.0.0): Alterações que quebram a compatibilidade com versões anteriores (Breaking Changes). Exemplos: alteração na assinatura de uma MCP Tool, remoção de endpoints ou mudança no esquema do banco de dados local.

MINOR (0.X.0): Adição de novas funcionalidades de forma retrocompatível. Exemplos: nova MCP Tool, suporte a um novo banco de dados (ex: MariaDB) ou nova página no Dashboard.

PATCH (0.0.X): Correções de bugs e melhorias internas que não alteram a funcionalidade. Exemplos: correção de tipagem, melhoria de logs ou ajustes CSS no Dashboard.

2. Manutenção do Changelog (CHANGELOG.md)
Sempre que o código for alterado, você deve sugerir a atualização do arquivo CHANGELOG.md seguindo estas diretrizes:

Princípios:
Foco Humano: As entradas devem ser explicativas para humanos, não apenas mensagens de commit.

Ordem Cronológica: As versões mais recentes aparecem no topo.

Formato de Data: Use o padrão YYYY-MM-DD.

Categorias Obrigatórias:
Ao descrever as mudanças de uma versão, agrupe-as nestas categorias exatas:

Added: Para novos recursos (ex: novas ferramentas MCP).

Changed: Para alterações em funcionalidades existentes (ex: mudança no transporte de Stdio para SSE).

Deprecated: Para recursos que serão removidos em breve.

Removed: Para recursos efetivamente removidos.

Fixed: Para qualquer correção de erro.

Security: Em caso de vulnerabilidades ou melhorias de segurança (ex: proteção de credenciais).

Exemplo de Formato:
Markdown
## [1.1.0] - 2026-04-27
### Added
- Tool `get_domain_context` para visualização de amostras de dados.
### Changed
- Refatoração do `DatabaseManager` para suportar múltiplas sessões.
### Fixed
- Erro de parsing em strings de conexão com caracteres especiais.

3. Fluxo de Trabalho do Agente
Ao finalizar uma tarefa, identifique o impacto da mudança.

Determine o novo número de versão.

Gere o bloco de texto formatado para o CHANGELOG.md.