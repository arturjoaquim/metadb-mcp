# MetaDB MCP (Meta Database Model Context Protocol)

O **MetaDB MCP** é um servidor local que implementa o Model Context Protocol (MCP). Ele atua como uma ponte (bridge) entre seus bancos de dados (Oracle e PostgreSQL) e assistentes de IA (como Cursor, Kiro, Cline, Gemini CLI, etc).

Em vez de expor suas credenciais ou permitir acesso direto ao banco de dados pela IA, este projeto extrai e armazena metadados (esquemas, tabelas, colunas, chaves primárias/estrangeiras, índices e amostras de domínio) de forma segura em um banco SQLite local (`mcp_cache.db`). A IA então consulta esses metadados via **stdio** (transporte padrão do MCP) usando as ferramentas (tools) disponibilizadas pelo protocolo.

## 🚀 Como Utilizar o Projeto

### 1. Iniciar o Servidor

O MetaDB MCP inicia **dois componentes no mesmo processo**:
- **Servidor MCP (stdio)**: comunicação JSON-RPC via stdin/stdout para os editores/agentes de IA.
- **Dashboard Web**: interface de gerenciamento acessível no navegador.

1. Abra um terminal no diretório raiz do projeto.
2. Ative o seu ambiente virtual (se aplicável):
   ```bash
   source venv/bin/activate
   ```
3. Execute o servidor:
   ```bash
   python3 main.py
   ```
   *(O processo ficará aguardando mensagens JSON-RPC via stdin — isso é o comportamento esperado do transporte stdio)*

**Argumentos de linha de comando disponíveis:**

| Argumento     | Padrão        | Descrição                          |
|---------------|---------------|------------------------------------|
| `--host`      | `127.0.0.1`   | Endereço de bind do servidor web   |
| `--port`      | `8000`        | Porta do servidor web              |
| `--log-file`  | `metadb_mcp.log` | Caminho do arquivo de log       |

Exemplo com porta customizada:
```bash
python3 main.py --port 9000
```

### 2. Sincronizar Tabelas (Painel de Controle)

Antes que a IA possa consultar os metadados, você precisa popular o cache local selecionando explicitamente quais dados devem ser liberados:

1. Acesse o dashboard no seu navegador: `http://127.0.0.1:8000` (ou a porta configurada).
2. Configure sua conexão com o banco de dados informando as credenciais. **Atenção:** as senhas são utilizadas apenas em memória durante a extração e nunca são salvas.
3. Clique em **Listar Tabelas** para carregar a estrutura do banco.
4. Selecione as tabelas cujo contexto você deseja disponibilizar.
5. Clique em **Sincronizar Selecionadas**.
   *(Isso salvará a estrutura e uma amostra segura dessas tabelas no SQLite local)*

---

## 🔌 Configuração do Editor / IDE

O MetaDB MCP utiliza transporte **stdio** — o padrão mais amplamente suportado pelos clientes MCP. O editor inicia o processo `python3 main.py` e se comunica via stdin/stdout.

### Cursor IDE

1. Abra as **Cursor Settings** (Configurações).
2. Vá até a aba **Features** → seção **MCP Servers**.
3. Clique em **+ Add new MCP server**.
4. Preencha os dados:
   - **Name**: `bridge-db-mcp` (ou `MetaDB-Control-Plane`)
   - **Type**: `command`
   - **Command**: `python3 /caminho/absoluto/para/main.py`
5. Salve e verifique se o status consta como "Connected".

### Kiro / Cline / Roo Code / Agentes Similares

Para agentes que utilizam arquivos JSON de configuração:

```json
{
  "mcpServers": {
    "bridge-db-mcp": {
      "command": "python3",
      "args": ["/caminho/absoluto/para/main.py"],
      "cwd": "/caminho/absoluto/para/diretorio/do/projeto"
    }
  }
}
```

> **Nota:** O `cwd` é importante para que o servidor encontre os diretórios `web/` e o banco `mcp_cache.db`.

### Gemini CLI

```json
{
  "mcpServers": {
    "bridge-db-mcp": {
      "command": "python3",
      "args": ["/caminho/absoluto/para/main.py"]
    }
  }
}
```

---

## 📋 Logs

Todas as saídas do servidor web (Uvicorn), bibliotecas e código do dashboard são redirecionadas para um arquivo de log. Por padrão, o arquivo é `metadb_mcp.log` no diretório do projeto.

Para acompanhar os logs em tempo real:
```bash
tail -f metadb_mcp.log
```

---

## 📜 Regras e Boas Práticas para a IA (Rules)

Para que o agente de inteligência artificial saiba utilizar essa integração corretamente e proativamente, é **altamente recomendado** adicionar uma regra de contexto no seu editor/projeto.

Recomendamos que você adicione ou associe o arquivo **[`utils-for-client/rule-suggestion.md`](./utils-for-client/rule-suggestion.md)** como uma "Rule" (Regra), "Custom Instruction" ou dentro do seu `.cursorrules`.

**Esta regra orienta a IA a:**
1. Consultar obrigatoriamente as funções do MCP `bridge-db-mcp` antes de supor qualquer estrutura do banco de dados.
2. Listar as tabelas disponíveis e buscar detalhes (DDL, relacionamentos, etc.) antes de gerar ou sugerir qualquer query SQL.
3. Não "alucinar" ou tentar adivinhar nomes de colunas ou tabelas, informando quando um dado não está sincronizado.
