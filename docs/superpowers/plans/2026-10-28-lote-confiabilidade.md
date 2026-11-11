# Lote de confiabilidade antes da rodada da Fase D — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:dispatching-parallel-agents to run Tasks 1–3 at the same time, each in its own worktree, and superpowers:subagent-driven-development's reviewer gate on each result before merging. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deixar o piloto mais confiável e mais leve para os cinco clientes de teste: o lembrete para de consultar o Cognito à toa, o build da web fica reproduzível e o portal carrega sem a sala do escritório, e o fluxo do portal ganha teste de ponta a ponta na CI.

**Architecture:** Três tarefas sem arquivo em comum, cada uma num branch a partir da `main`. O coordenador junta tudo num branch `lote-confiabilidade` e faz dois ajustes de integração no `ci.yml`: troca `npm install` por `npm ci` e confere o job novo de E2E. A CI do PR é a prova final.

**Tech Stack:** Python 3.12, FastAPI, pytest; React 19, Vite 6, TypeScript, Playwright 1.49; GitHub Actions; Docker Compose com Keycloak local.

**Spec:** a avaliação "o que podemos melhorar de código agora", itens 1 a 5, mais [AGENTS.md](../../../AGENTS.md) (Definition of Done) e [docs/mapa-do-codigo.md](../../mapa-do-codigo.md).

## Global Constraints

- Nunca adicionar `Co-Authored-By` nem atribuição de IA em commit ou PR.
- Mensagem de commit em português, frase no presente terminada em ponto.
- Nenhum dado real, credencial ou certificado. O E2E usa só os usuários do realm de desenvolvimento (`deploy/keycloak/realm-dev.json`, senha `dev-only-password`).
- Os agentes não rodam `docker compose`, que é compartilhado, e não instalam nada no venv `apps/api/.venv`. A API roda com `PYTHONPATH=src` a partir do worktree.
- O Node roda só em contêiner descartável: `docker run --rm -v "<worktree>/apps/web:/w" -w /w node:22-alpine sh -c "..."`.
- Cada agente commita só no próprio branch. Push, merge e deploy ficam com o coordenador.
- Não mudar regra de negócio, contrato da API nem texto de tela.

## Review Focus

1. **Lembrete quando o SES for ligado depois.** Se o envio estiver desligado, o pedido vencido não pode ganhar linha em `notification_log`. Quando o SES for ligado, o aviso tem de sair uma vez. A Task 1 testa que nada é gravado com o envio desligado.
2. **Envio desligado e diretório ligado.** O piloto tem Cognito e não tem SES. O teste da Task 1 usa um diretório que falha se for chamado, para provar que não há consulta.
3. **Login direto no portal.** O cliente que entra pelo portal não pode receber a tela branca enquanto o pedaço da página carrega, nem um erro se a rede falhar no meio. A Task 2 mostra o mesmo "Carregando sessão…" da tela de login durante o carregamento.
4. **Lockfile e plataforma.** Um `package-lock.json` gerado no Alpine precisa servir ao `ubuntu-latest` da CI e ao Dockerfile da web, que também é Alpine. A Task 2 gera o arquivo no `node:22-alpine` e confere que `npm ci` passa no mesmo contêiner.
5. **E2E dependente de ordem.** O teste do portal cria um pedido novo, com título único por `Date.now()`, em vez de depender de um pedido do seed. Ele pode rodar de novo na mesma base sem falhar.

---

### Task 1: Lembrete sem consulta inútil e aviso do Starlette

**Files:**
- Modify: `apps/api/src/contabil/identity/notices.py`, função `_send`, linhas 97 a 143
- Modify: `apps/api/pyproject.toml`, só se o pacote do passo 4 existir
- Test: `apps/api/tests/unit/test_notices.py` (novo; hoje não há teste unitário do aviso)

**Interfaces:**
- Consumes: `get_mailer() -> Mailer` e `UnavailableMailer` de `contabil/identity/mailer.py`; `get_user_directory()` de `contabil/identity/directory.py`.
- Produces: `_send(session, row, kind, notice_date) -> bool` com a mesma assinatura. Quando `get_mailer()` devolve `UnavailableMailer`, a função devolve `False` sem tocar na sessão nem no diretório.

- [ ] **Step 1:** Escrever o teste `test_send_skips_everything_when_mail_is_off` em `tests/unit/test_notices.py`:
  - `monkeypatch` de `contabil.identity.notices.get_mailer` para devolver `UnavailableMailer()`;
  - `monkeypatch` de `contabil.identity.notices.get_user_directory` para um objeto cujo `get_email` lança `AssertionError("diretório consultado")`;
  - uma sessão falsa cujos `scalar`, `scalars` e `add` lançam `AssertionError`;
  - um `row = SimpleNamespace(id="req_1", tenant_id="t", legal_entity_id="le", title="T", due_on=date(2026, 10, 20))`;
  - `assert _send(session, row, "overdue", date(2026, 10, 20)) is False`.
- [ ] **Step 2:** Rodar `cd apps/api && PYTHONPATH=src $PY -m pytest tests/unit/test_notices.py -q` e esperar FAIL com "diretório consultado" ou com o assert da sessão.
- [ ] **Step 3:** No começo de `_send`, obter `mailer = get_mailer()`. Se `isinstance(mailer, UnavailableMailer)`, registrar `logger.info("notice skipped kind=%s request=%s reason=mail_off", kind, row.id)` e devolver `False`. O resto da função segue igual, sem o segundo `get_mailer()`.
- [ ] **Step 4:** Rodar o teste e esperar PASS. Rodar `PYTHONPATH=src $PY -m pytest tests/unit -q -p no:warnings` e `PYTHONPATH=src $PY -m pyflakes src`: tudo verde e nenhuma linha do pyflakes.
- [ ] **Step 5:** Aviso do Starlette: rodar `PYTHONPATH=src $PY -m pytest tests/unit -q` sem `-p no:warnings` e copiar o texto exato do aviso. Rodar `$PY -m pip index versions httpx2`.
  - Se o pacote existir: acrescentar `"httpx2>=<versão atual>,<próxima major>"` às dependências do projeto, onde já está o `httpx`, e não instalar no venv compartilhado. Anotar no retorno que o coordenador precisa rodar a integração.
  - Se não existir: acrescentar em `[tool.pytest.ini_options]` um `filterwarnings` que ignora só essa mensagem, com um comentário em português dizendo por quê e até quando.
- [ ] **Step 6:** Commit com a mensagem `Não consulta o diretório quando o aviso por e-mail está desligado.`

### Task 2: Web com lockfile e portal carregado à parte

**Files:**
- Create: `apps/web/package-lock.json`
- Modify: `apps/web/Dockerfile:16` (`npm install` vira `npm ci`)
- Modify: `apps/web/src/App.tsx` (imports de `PortalPage` e `RastroShell`)
- Modify: `apps/web/vite.config.ts`, só se o passo 4 pedir

**Interfaces:**
- Produces: `apps/web/package-lock.json`, que o coordenador usa para trocar `npm install` por `npm ci` nos jobs `web` e `e2e` do `ci.yml`.

- [ ] **Step 1:** Gerar o lockfile com `docker run --rm -v "<worktree>/apps/web:/w" -w /w node:22-alpine sh -c "npm install --no-audit --no-fund && npm ci --no-audit --no-fund && npm run lint"`. O `npm ci` precisa passar com o lockfile recém-gerado.
- [ ] **Step 2:** Trocar `RUN npm install && npm run build` por `RUN npm ci && npm run build` no `apps/web/Dockerfile`. O Dockerfile já faz `COPY . ./` antes, então o lockfile entra na imagem sem outra mudança. Se existir `apps/web/.dockerignore`, conferir que ele não exclui o `package-lock.json`.
- [ ] **Step 3:** No `App.tsx`, carregar sob demanda as duas telas:
  - `const PortalPage = lazy(() => import("./pages/PortalPage").then((m) => ({ default: m.PortalPage })));`
  - o mesmo para `RastroShell` de `./rastro/RastroShell`.

  Onde `Shell` decide entre as duas, envolver numa `<Suspense fallback={<LoginScreen pending />}>`. O `rastro.css` continua importado no `App.tsx`.
- [ ] **Step 4:** Rodar `npm run build` no mesmo contêiner e ler a saída.
  - Esperado: um pedaço separado para o portal e outro para a sala, e nenhum acima de 500 kB.
  - Se ainda houver pedaço acima de 500 kB, acrescentar em `vite.config.ts` um `build.rollupOptions.output.manualChunks` que separa `react`, `react-dom`, `react-router-dom` e `@tanstack/react-query` num pedaço `vendor`, e rodar de novo.
  - Anotar no retorno o tamanho de cada pedaço.
- [ ] **Step 5:** Rodar `npm run lint` e `npm run build` de novo e esperar zero erro. Apagar `node_modules` e `dist` do worktree e conferir que `git status` mostra só os arquivos desta task.
- [ ] **Step 6:** Commit com a mensagem `Fixa as dependências da web e carrega o portal sem a sala do escritório.`

### Task 3: E2E do portal e job na CI

**Files:**
- Create: `apps/web/e2e/portal.spec.ts`
- Modify: `apps/web/e2e/company.ts`, se precisar de um ajudante de login compartilhado
- Modify: `.github/workflows/ci.yml` (job novo `e2e`)
- Modify: componentes do portal e de Pendências (`apps/web/src/pages/PortalPage.tsx`, `RequestThread.tsx`, `DocumentRequestsPage.tsx`), só para acrescentar `data-testid` onde não houver papel ou rótulo estável

**Interfaces:**
- Consumes:
  - os usuários do realm de desenvolvimento: `preparer`, `approver` e `cliente`. O `cliente` é ligado à Empresa Alfa pelo seed em `apps/api/src/contabil/seed/run.py:85-92`;
  - `chooseCompany(page, name)` de `e2e/company.ts`;
  - o padrão de login de `e2e/smoke.spec.ts:16-25`.
- Produces: o job `e2e` no `ci.yml`, que o coordenador ajusta para `npm ci` depois de juntar a Task 2.

- [ ] **Step 1:** Ler `DocumentRequestsPage.tsx`, `PortalPage.tsx` e `RequestThread.tsx` e listar os botões e campos usados no fluxo: "Pedir documento", envio de arquivo, "Devolver ao cliente", "Confirmar", conversa e lista de histórico. Para cada um, escolher `getByRole` ou `getByLabel` quando o rótulo for estável. Acrescentar `data-testid` só onde não houver.
- [ ] **Step 2:** Escrever `test("cliente envia, escritório devolve e confirma o pedido")` em `e2e/portal.spec.ts`:
  1. `preparer`, Empresa Alfa: abre Pendências, pede um documento com título `E2E portal ${Date.now()}` e prazo daqui a 7 dias, e sai.
  2. `cliente`: vê o título em aberto, envia um arquivo e escreve "Segue o arquivo." na conversa, e sai. O arquivo é um buffer em memória, com `setInputFiles({ name: "e2e.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 e2e") })`.
  3. `approver`: abre o pedido, vê a mensagem, usa "Devolver ao cliente" com o motivo "Arquivo ilegível, envie de novo.", e sai.
  4. `cliente`: vê o arquivo devolvido com o motivo, envia outro arquivo e sai.
  5. `approver`: usa "Confirmar".
  6. `cliente`: vê o pedido no histórico.

  Cada passo termina com um `expect` visível. O cliente entra pelo mesmo `login-button`; o `waitForURL` do cliente segue a rota que o `App.tsx` abre para o papel `client`, a ser lida no código.
- [ ] **Step 3:** Rodar `npm run lint` no contêiner `node:22-alpine` e esperar zero erro. O teste não roda localmente: precisa do compose no ar, e o compose é compartilhado. A prova é o job da CI.
- [ ] **Step 4:** Acrescentar ao `ci.yml` o job `e2e`, com `needs: []` e Node 22:
  1. `cp .env.example .env`;
  2. `docker compose up -d --build --wait web`;
  3. em `apps/web`: `npm install`, `npx playwright install --with-deps chromium` e `npx playwright test`;
  4. em `if: failure()`: `actions/upload-artifact@v4` com `apps/web/test-results` e `apps/web/playwright-report`, e `docker compose logs --no-color api web keycloak`.

  Conferir no `docker-compose.yml` que `web` publica `5173` e que o Keycloak publica `8080` no host, porque o `baseURL` e o emissor do token usam `localhost`.
- [ ] **Step 5:** Validar o YAML com `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml', encoding='utf-8'))"`.
- [ ] **Step 6:** Commit com a mensagem `Testa de ponta a ponta o pedido de documento pelo portal do cliente.`

## Coordenação

1. Despachar Tasks 1, 2 e 3 numa mensagem só, cada uma em worktree. Cada agente recebe a própria task, as Global Constraints e a Review Focus.
2. Revisar cada diff contra a task antes de juntar.
3. Criar `lote-confiabilidade` a partir da `main` e juntar os três branches. No `ci.yml`, trocar `npm install` por `npm ci` nos jobs `web` e `e2e`, porque o lockfile existe a partir da Task 2. Commit com a mensagem `Usa npm ci na CI agora que a web tem lockfile.`
4. Com o compose no ar, rodar `docker compose up -d --build api worker web` e `docker compose exec -T api pytest -q -p no:warnings -rs`: os 109 testes, mais o da Task 1, passam e nenhum é pulado.
5. Fazer push e abrir o PR. Se o E2E novo falhar, ler o relatório anexado à execução antes de mexer. Se os specs antigos de E2E também falharem, isso já existia antes deste lote: registrar no PR e tratar em seguida, sem misturar com o lote.
6. Depois do merge, fazer o deploy da API (Task 1) e da web (Task 2), com o deploy do PR #4 junto, se ainda estiver pendente.

## Verificação

- Local, no branch integrado:
  - unitários e pyflakes na API, além dos validadores de specs, de links, do OpenAPI e de contrato;
  - integração completa sem teste pulado;
  - lint e build da web no `node:22-alpine`, com nenhum pedaço acima de 500 kB.
- CI: os jobs `api-static`, `web`, `integration` e `e2e` verdes no PR.
- Piloto, depois do deploy:
  - o log da API, de hora em hora, mostra `reason=mail_off` e nenhuma chamada ao Cognito pelo lembrete;
  - o portal abre logado como `diego`, e na aba de rede só o pedaço do portal é baixado.
