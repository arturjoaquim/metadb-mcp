# Migração do Transporte MCP: SSE → stdio (com Web Console no mesmo processo)

## Contexto

Atualmente o projeto utiliza FastAPI (Uvicorn) para servir tanto o dashboard web quanto o transporte MCP via SSE (`/mcp/sse`). Os editores que não suportam SSE dependem de um proxy (`sse_proxy.py`) que traduz stdio↔SSE.

A mudança proposta elimina o SSE como transporte MCP e o substitui por **stdio nativo**, o que é o padrão preferido pela maioria dos clientes MCP (Cursor, Claude Desktop, Gemini CLI, etc.). O dashboard web continuará disponível no mesmo processo, servido por Uvicorn em uma **thread separada**.

---

## Análise de Risco: Isolamento de stdout

> [!IMPORTANT]
> O transporte stdio utiliza `sys.stdout` para comunicação JSON-RPC. Qualquer saída espúria (logs do uvicorn, prints, etc.) corromperia o protocolo.

**Estratégia de isolamento:**
1. **Antes de iniciar qualquer componente**, salvar uma referência ao `sys.stdout` e `sys.stdin` originais.
2. **Redirecionar `sys.stdout` e `sys.stderr`** globais para `os.devnull` (ou para um arquivo de log), impedindo que qualquer código (uvicorn, SQLAlchemy, etc.) escreva no stdout original.
3. O transporte stdio do MCP receberá as referências **originais** de stdin/stdout salvas anteriormente, usando-as diretamente para a comunicação JSON-RPC.
4. Configurar o Uvicorn com `log_config=None` e `access_log=False` para silenciar completamente seus logs na saída padrão.

---

## Alterações Propostas

### Componente: Ponto de Entrada

#### [MODIFY] [main.py](file:///home/artur/ambiente-de-trabalho/workspace_python/mcp_metadb/main.py)

Reestruturação completa do `main.py` para:

1. **Remover** a montagem do SSE (`app.mount("/mcp", mcp.sse_app())`).
2. **Criar a função `run_web_server()`** que inicia o Uvicorn **numa thread daemon** com logs silenciados:
   - `log_config=None` para suprimir output do uvicorn
   - `access_log=False`
   - A thread será `daemon=True` para encerrar automaticamente com o processo principal
3. **Criar a função `run_stdio_mcp()`** que executa `mcp.run_stdio_async()` usando as referências originais de stdin/stdout:
   - Antes de iniciar qualquer coisa, capturar `sys.stdout` e `sys.stdin` originais
   - Redirecionar `sys.stdout` e `sys.stderr` para um **arquivo de log** (`metadb_mcp.log` no diretório do projeto)
   - Passar os file descriptors originais para o `stdio_server()` como streams customizadas via `anyio.wrap_file`
4. **Adicionar `argparse`** para argumentos de linha de comando:
   - `--host` (padrão: `127.0.0.1`)
   - `--port` (padrão: `8000`)
   - `--log-file` (padrão: `metadb_mcp.log`)
5. **Fluxo do `main`:**
   ```
   1. Parsear argumentos (argparse)
   2. Capturar stdin/stdout originais
   3. Abrir arquivo de log e redirecionar sys.stdout e sys.stderr → arquivo de log
   4. Iniciar thread daemon com uvicorn (web dashboard) usando host/port dos argumentos
   5. Executar asyncio.run(run_stdio_mcp()) no thread principal (bloqueante)
   ```

---

### Componente: Servidor MCP

#### [MODIFY] [mcp_server.py](file:///home/artur/ambiente-de-trabalho/workspace_python/mcp_metadb/core/mcp_server.py)

- **Nenhuma alteração funcional** — as tools registradas permanecem idênticas.
- A instância `mcp = FastMCP("metadb-control-plane")` continua como está.
- O método `run_stdio_async()` já existe no FastMCP e será invocado pelo `main.py`.

---

### Componente: Dependências

#### [MODIFY] [requirements.txt](file:///home/artur/ambiente-de-trabalho/workspace_python/mcp_metadb/requirements.txt)

- Sem novas dependências necessárias. `anyio` já é dependência transitiva do `mcp`.
- Avaliar se `uvicorn[standard]` é necessário ou se o `uvicorn` básico já instalado é suficiente.

---

### Componente: Documentação

#### [MODIFY] [README.md](file:///home/artur/ambiente-de-trabalho/workspace_python/mcp_metadb/README.md)

Atualizar toda a documentação para refletir:
1. **Como iniciar o servidor**: agora basta executar `python3 main.py` — o servidor web e o MCP stdio iniciam juntos.
2. **Configuração do editor**: o tipo de transporte agora é `stdio` (command), não mais `sse`.
3. **Remover** a seção sobre o proxy SSE, que se torna desnecessário.
4. **Exemplos de configuração JSON** atualizados para stdio.

#### [DELETE] [sse_proxy.py](file:///home/artur/ambiente-de-trabalho/workspace_python/mcp_metadb/utils-for-client/sse_proxy.py)

O proxy SSE→stdio se torna obsoleto com a adoção de stdio nativo.

---

### Componente: Changelog

#### [MODIFY] [CHANGELOG.md](file:///home/artur/ambiente-de-trabalho/workspace_python/mcp_metadb/CHANGELOG.md)

Nova versão **2.0.0** (Breaking Change — altera o mecanismo de transporte):

```markdown
## [2.0.0] - 2026-05-03
### Changed
- Transporte MCP migrado de SSE (Server-Sent Events) para stdio nativo.
- Servidor web (dashboard) e servidor MCP agora executam no mesmo processo Python, em threads separadas.
- Stdout e stderr globais são redirecionados para evitar contaminação do protocolo stdio.

### Removed
- Montagem SSE removida do FastAPI (`/mcp/sse`).
- Script proxy `sse_proxy.py` removido (obsoleto com stdio nativo).
```

---

## Decisões Tomadas

> [!NOTE]
> **Porta do servidor web**: Configurável via argumento de linha de comando `--port` (padrão: `8000`), seguindo o padrão do uvicorn.

> [!NOTE]
> **Arquivo de log**: Todas as saídas (uvicorn, bibliotecas, código do console web) serão redirecionadas para um arquivo de log (`metadb_mcp.log` por padrão, configurável via `--log-file`).

---

## Plano de Verificação

### Testes Automatizados
- Verificar que o processo inicia sem erros: `python3 main.py` (observar que o processo fica bloqueado esperando stdin — comportamento esperado do stdio).
- Enviar uma mensagem JSON-RPC de inicialização via stdin e verificar resposta válida no stdout.

### Verificação Manual
1. Configurar o editor (ex: Cursor) para usar o novo comando stdio e validar que as tools MCP são reconhecidas.
2. Acessar `http://127.0.0.1:8000` no navegador e confirmar que o dashboard web funciona normalmente.
3. Confirmar que nenhum log do uvicorn aparece no stdout (apenas mensagens JSON-RPC do MCP).
