# MetaDB MCP (Meta Database Model Context Protocol)

O **MetaDB MCP** é um servidor local que implementa o Model Context Protocol (MCP). Ele atua como uma ponte (bridge) entre seus bancos de dados (Oracle e PostgreSQL) e assistentes de IA (como Cursor, Kiro, Cline, etc).

Em vez de expor suas credenciais ou permitir acesso direto ao banco de dados pela IA, este projeto extrai e armazena metadados (esquemas, tabelas, colunas, chaves primárias/estrangeiras, índices e amostras de domínio) de forma segura em um banco SQLite local (`mcp_cache.db`). A IA então consulta esses metadados via SSE (Server-Sent Events) usando as ferramentas (tools) disponibilizadas pelo protocolo.

## 🚀 Como Utilizar o Projeto

### 1. Iniciar o Servidor

1. Abra um terminal no diretório raiz do projeto.
2. Ative o seu ambiente virtual (se aplicável):
   ```bash
   source venv/bin/activate
   ```
3. Execute o servidor FastAPI através do Uvicorn:
   ```bash
   uvicorn main:app --host 127.0.0.1 --port 8000
   ```
   *(Importante: O servidor deve permanecer rodando em background para que a integração com o editor funcione)*

### 2. Sincronizar Tabelas (Painel de Controle)

Antes que a IA possa consultar os metadados, você precisa popular o cache local selecionando explicitamente quais dados devem ser liberados:

1. Acesse o dashboard no seu navegador: `http://127.0.0.1:8000`.
2. Configure sua conexão com o banco de dados informando as credenciais. **Atenção:** as senhas são utilizadas apenas em memória durante a extração e nunca são salvas.
3. Clique em **Listar Tabelas** para carregar a estrutura do banco.
4. Selecione as tabelas cujo contexto você deseja disponibilizar.
5. Clique em **Sincronizar Selecionadas**.
   *(Isso salvará a estrutura e uma amostra segura dessas tabelas no SQLite local)*

---

## 🔌 Configuração do Editor / IDE

Nosso servidor expõe os metadados via **SSE** (`http://127.0.0.1:8000/mcp/sse`). Siga as instruções abaixo para conectar o seu assistente de IA.

### Cursor IDE

O Cursor possui suporte nativo para adicionar servidores MCP:

1. Abra as **Cursor Settings** (Configurações).
2. Vá até a aba **Features** -> seção **MCP Servers**.
3. Clique em **+ Add new MCP server**.
4. Preencha os dados:
   - **Name**: `bridge-db-mcp` (ou `MetaDB-Control-Plane`)
   - **Type**: `sse`
   - **URL**: `http://127.0.0.1:8000/mcp/sse`
5. Salve e verifique se o status consta como "Connected" (bolinha verde indicando sucesso).

### Kiro / Cline / Roo Code / Agentes Similares

Para agentes que utilizam interfaces ou arquivos JSON de configuração:

**Opção A: Via Interface (ex: Kiro)**
1. Abra as configurações de MCP do agente.
2. Clique em **Add MCP Server**.
3. Selecione o transporte: **SSE**.
4. URL: `http://127.0.0.1:8000/mcp/sse`

**Opção B: Via Arquivo JSON (`mcp_settings.json` ou similar)**
Adicione a seguinte entrada ao arquivo de configuração do seu agente:
```json
{
  "mcpServers": {
    "bridge-db-mcp": {
      "type": "sse",
      "url": "http://127.0.0.1:8000/mcp/sse"
    }
  }
}
```

### Editores sem suporte a SSE (Uso de Stdio Proxy)

Caso o seu editor de código ou assistente de IA não ofereça suporte a conexões MCP via SSE (Server-Sent Events) e exija a comunicação via `stdio`, você pode utilizar o proxy fornecido com o projeto.
O script `utils-for-client/sse_proxy.py` atua como um tradutor, redirecionando as mensagens stdio do editor para a URL SSE do servidor local.

Para configurá-lo (assumindo que o servidor FastAPI já está rodando), configure seu MCP para usar comandos em vez de URLs:

**No Cursor ou via Interface:**
- **Type**: `command`
- **Command**: `python` (ou o caminho completo para o seu interpretador Python)
- **Args**: `caminho/absoluto/para/utils-for-client/sse_proxy.py`

**Via Arquivo JSON (`mcp_settings.json`):**
```json
{
  "mcpServers": {
    "bridge-db-mcp-stdio": {
      "command": "python",
      "args": ["/caminho/absoluto/para/utils-for-client/sse_proxy.py"]
    }
  }
}
```

---

## 📜 Regras e Boas Práticas para a IA (Rules)

Para que o agente de inteligência artificial saiba utilizar essa integração corretamente e proativamente, é **altamente recomendado** adicionar uma regra de contexto no seu editor/projeto.

Recomendamos que você adicione ou associe o arquivo **[`utils-for-client/rule-suggestion.md`](./utils-for-client/rule-suggestion.md)** como uma "Rule" (Regra), "Custom Instruction" ou dentro do seu `.cursorrules`.

**Esta regra orienta a IA a:**
1. Consultar obrigatoriamente as funções do MCP `bridge-db-mcp` antes de supor qualquer estrutura do banco de dados.
2. Listar as tabelas disponíveis e buscar detalhes (DDL, relacionamentos, etc.) antes de gerar ou sugerir qualquer query SQL.
3. Não "alucinar" ou tentar adivinhar nomes de colunas ou tabelas, informando quando um dado não está sincronizado.
