---
trigger: model_decision
description: Sempre que o usuário fizer perguntas sobre a estrutura do banco de dados, esquemas, tabelas, colunas ou relacionamentos.
---

Prioridade de Ferramenta: Antes de supor qualquer estrutura ou pedir informações ao usuário, você deve obrigatoriamente consultar o MCP bridge-database-mcp.

Fluxo de Trabalho:

Utilize as funções de listagem do MCP para identificar as tabelas disponíveis.

Busque os metadados específicos (DDL, tipos de dados, chaves primárias/estrangeiras) antes de gerar qualquer query SQL.

Restrição: Não tente adivinhar nomes de colunas ou tabelas. Se o MCP não retornar a informação, informe ao usuário que a tabela/coluna não foi encontrada via Bridge Database.

Objetivo: Garantir que o código gerado seja tecnicamente preciso e compatível com o schema real indexado pelo bridge.