# Conferências e sugestões — plano de implementação

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para executar este plano tarefa por tarefa. Os passos usam checkbox (`- [ ]`).

**Objetivo:** trazer para o sistema as cinco ideias da aula: alertas do extrato (A), conferências do balancete (B), resumo do mês para o empresário (C) e sugestão de contrapartida pelo histórico (D) e pelo Claude Haiku 5.5 (E). Nenhuma delas produz efeito contábil sem uma pessoa.

**Arquitetura:**
- A **Tarefa 0** prepara, no branch `conferencias-e-sugestoes`, o que as frentes dividiriam: configurações, dependências e o arquivo de limiares.
- Depois quatro frentes rodam em paralelo, cada uma no seu worktree criado a partir desse branch: **A** (`reconciliation/alerts.py`), **B** (`closing/checks.py`), **C** (módulo novo `client_summaries/`) e **D+E** (módulo novo `suggestions/`).
- A integração (Tarefas I1–I4) junta as frentes uma por vez e só então mexe no checklist, na SPEC, no OpenAPI e nos demais documentos comuns.

**Stack:** FastAPI, SQLAlchemy 2, Alembic, PostgreSQL com RLS forçada, worker com outbox, React/Vite com react-query e SDK `anthropic` em Python.

**Desenho:** [`docs/superpowers/specs/2026-11-14-conferencias-e-sugestoes-design.md`](../specs/2026-11-14-conferencias-e-sugestoes-design.md). Quem executa lê os dois documentos.

## Restrições globais

- Regras de `AGENTS.md`:
  - tenant e empresa isolados no serviço, não só no front;
  - tabela nova com `tenant_id`, `ENABLE` + `FORCE ROW LEVEL SECURITY`, policy `tenant_isolation` e grant para `contabil_app` (modelo: `alembic/versions/0018_withholding_payments.py`);
  - dinheiro em `Decimal`, serializado com `format_amount`/`format_signed`;
  - POST que muda estado usa `replay_guard` + `persist` (Idempotency-Key).
- Nada de CPF, CNPJ, nome, prompt ou resposta do modelo em log ou fixture.
- Limiares em `configs/conferencias.yaml`, versão `2026.11-provisorio`: `duplicate_payment_window_days: 3`, `own_transfer_window_days: 2`, `idle_balance_months: 3`.
- Sugestão é sempre "sugerida" (SPEC §7). A tela pré-seleciona e a pessoa confirma com o botão que já existe.
- Configuração E:
  - `CLAUDE_API_KEY` (vazia por padrão), `SUGGESTION_MODEL=claude-haiku-5-5`, `SUGGESTION_DAILY_LIMIT=500`;
  - lote de até 40 transações;
  - `effort: "low"`, `max_tokens=4096`, `timeout=30`, `max_retries=2`.
- Testes nunca chamam a rede. A chamada real só acontece em `python -m contabil.suggestions.smoke`, rodado à mão com autorização do usuário.
- Numeração reservada:
  - migrações `0022_client_summaries` (C) e `0023_account_suggestions` (E); nas frentes, as duas apontam para `0021_journal_line_guards` e E é religada na integração;
  - ADR 034 "Resumo do mês publicado para o cliente" (C) e ADR 035 "Sugestão de conta por modelo de linguagem" (E).
- Frentes **não** editam: `closing/checklist.py`, `docs/rastro/SPEC.md`, `schemas/openapi.yaml`, `docs/mapa-do-codigo.md`, `README.md`, o caderno do contador e `deploy/pilot/README.md`. Tudo isso fica para a integração.
- Commits em português, no estilo do histórico, sem linha de coautoria.
- Comandos de verificação (de `apps/api`):
  - `pytest tests/unit -q`
  - `python -m pyflakes src`
  - integração: `pytest tests/integration/<arquivo> -q`, com o compose no ar; quando o compose não estiver no ar, diga isso.

## Foco da revisão

1. **Caso de outra empresa no mesmo escritório.** Alerta, histórico e sugestão do modelo nunca cruzam `legal_entity_id`. Teste em A3 e E5.
2. **Cliente da empresa X pedindo o resumo da empresa Y, ou um resumo em rascunho ou retirado.** Responde 404, nunca o conteúdo. Teste em C3.
3. **Modelo devolve conta de outra empresa, inexistente, inativa ou não lançável, ou um id de transação que não foi enviado.** Descarta sem erro. Teste em E4.
4. **Pedido que passaria do teto diário, ou chave vazia.** 429 ou 503 sem criar operação. O worker também para antes do lote que estouraria o teto. Teste em E4 e E5.
5. **Competência reaberta com resumo publicado.** O resumo vira `withdrawn` na mesma transação, e o portal deixa de mostrá-lo. Teste em C3.

---

## Tarefa 0 — Base comum (no branch `conferencias-e-sugestoes`, antes das frentes)

**Arquivos:**
- Criar: `configs/conferencias.yaml`, `apps/api/src/contabil/platform/conferences.py`, `apps/api/tests/unit/test_conferences.py`
- Alterar: `apps/api/src/contabil/platform/settings.py`, `apps/api/pyproject.toml`, `Dockerfile`, `deploy/pilot/env.example`

**Interfaces produzidas:**
- `Thresholds` (dataclass frozen): `version: str`, `duplicate_payment_window_days: int`, `own_transfer_window_days: int`, `idle_balance_months: int`.
- `load_thresholds() -> Thresholds`, com `lru_cache`. Lê `Path(settings.configs_dir) / "conferencias.yaml"` ou, com `configs_dir` vazio, `Path(__file__).resolve().parents[5] / "configs" / "conferencias.yaml"`.
- `Settings`: `configs_dir: str = ""`, `claude_api_key: str = ""`, `suggestion_model: str = "claude-haiku-5-5"`, `suggestion_daily_limit: int = 500`.

- [ ] **Passo 1: Testes que falham** em `tests/unit/test_conferences.py`:
  - `test_load_thresholds_reads_versioned_file`: `version == "2026.11-provisorio"` e os valores 3, 2 e 3.
  - `test_load_thresholds_rejects_missing_key`: um YAML em `tmp_path` sem `idle_balance_months` (com `configs_dir` apontando para lá e `load_thresholds.cache_clear()`) levanta `ValueError` com o nome da chave.
  - `test_settings_suggestion_defaults`: `Settings()` tem `suggestion_model == "claude-haiku-5-5"`, `suggestion_daily_limit == 500` e `claude_api_key == ""`.
- [ ] **Passo 2:** `pytest tests/unit/test_conferences.py -q` deve FALHAR (módulo inexistente).
- [ ] **Passo 3:** criar `configs/conferencias.yaml` com `version` e as três chaves. Cada chave leva um comentário citando a pergunta do caderno que vai decidir o valor ("pergunta a criar na integração: limiar de duplicidade"). Implementar `conferences.py` e os campos de `Settings`.
  - Em `pyproject.toml`, `pyyaml>=6,<7` e `anthropic>=0.75,<1` vão para `dependencies` (runtime).
  - No `Dockerfile`, `CONFIGS_DIR=/configs` entra no bloco `ENV`.
  - Em `deploy/pilot/env.example`, entram `CLAUDE_API_KEY=` vazio, `SUGGESTION_MODEL` e `SUGGESTION_DAILY_LIMIT`.
- [ ] **Passo 4:** `pip install -e ".[dev]"` e `pytest tests/unit -q`. Deve PASSAR inteiro.
- [ ] **Passo 5: Commit** "Guarda os limiares das conferências em arquivo versionado e prepara a configuração da sugestão por IA."

Depois da Tarefa 0, criar quatro worktrees a partir de `conferencias-e-sugestoes`: `frente-a`, `frente-b`, `frente-c` e `frente-de`.

---

## Frente A — Alertas do extrato

### Tarefa A1: função pura `statement_alerts`

**Arquivos:** criar `apps/api/src/contabil/reconciliation/alerts.py`. Teste: `apps/api/tests/unit/test_statement_alerts.py`.

**Interfaces:**
- Consome: `Thresholds` (Tarefa 0) e `normalize_description` (`reconciliation/statement_parser.py`).
- Produz:
  - `AlertTx` (dataclass frozen): `transaction_id`, `bank_account_id`, `legal_entity_id`, `date: date`, `amount: Decimal`, `direction: str`, `description: str`.
  - `Alert` (dataclass frozen): `kind: Literal["duplicate_payment", "own_transfer"]`, `transaction_ids: tuple[str, ...]` (ordenados), `explanation: str`, `rule_version: str`.
  - `statement_alerts(transactions: Sequence[AlertTx], thresholds: Thresholds) -> list[Alert]`.
  - `alert_dict(alert: Alert) -> dict` com as chaves `kind`, `transaction_ids`, `explanation` e `rule_version`.

Regras:
- `duplicate_payment`: mesma `bank_account_id`, as duas `outflow`, mesmo `amount`, `|Δdias| <= duplicate_payment_window_days` e descrição parecida. Parecida quer dizer `normalize_description` igual, ou ao menos 2 palavras de 3 ou mais letras em comum.
- `own_transfer`: `bank_account_id` diferentes, mesma `legal_entity_id`, uma `outflow` e outra `inflow`, mesmo `amount` e `|Δdias| <= own_transfer_window_days`.
- Um alerta por par, sem par repetido.
- Explicações fixas:
  - "Pagamento de R$ {valor} repetido em {n} dia(s) com histórico parecido. Confira se não é duplicidade."
  - "Saída e entrada de R$ {valor} entre contas da mesma empresa. Parece transferência entre contas próprias."

- [ ] **Passo 1: Testes que falham:**
  - `test_duplicate_payment_within_window` (dia 0 e dia 3 → 1 alerta);
  - `test_duplicate_payment_outside_window` (dia 0 e dia 4 → nenhum);
  - `test_duplicate_requires_same_amount_and_outflow`;
  - `test_duplicate_requires_similar_description`;
  - `test_own_transfer_between_entity_accounts`;
  - `test_own_transfer_ignores_other_entity`;
  - `test_alert_carries_rule_version` (`== "2026.11-provisorio"`).
- [ ] **Passo 2:** `pytest tests/unit/test_statement_alerts.py -q` deve FALHAR.
- [ ] **Passo 3:** implementar. Ordenar por data e varrer a janela, sem produto cartesiano.
- [ ] **Passo 4:** o mesmo comando deve PASSAR.
- [ ] **Passo 5: Commit** "Calcula alertas de pagamento em duplicidade e de transferência entre contas próprias."

### Tarefa A2: alertas nas rotas e contagem da competência

**Arquivos:**
- Alterar: `reconciliation/alerts.py` (carregador) e `reconciliation/service.py` (`case_dict`, `list_cases`, `get_case`, `bank_account_summary`).
- Teste: `apps/api/tests/integration/test_statement_alerts.py`.

**Interfaces produzidas:**
- `alerts_for_transactions(session, tenant_id: str, legal_entity_id: str, transactions: Sequence[BankTransaction]) -> dict[str, list[dict]]`. Busca as transações de todas as contas bancárias da empresa em `[min_data - maior_janela, max_data + maior_janela]`, chama `statement_alerts` e devolve os alertas por `transaction_id`, só para os ids pedidos.
- `period_alert_count(session, tenant_id: str, legal_entity_id: str, period: AccountingPeriod) -> int`: número de alertas distintos com alguma transação dentro da competência. A integração usa no checklist.
- `case_dict(session, case, *, alerts: list[dict] | None = None)`: a chave nova `"alerts"` vale `alerts or []`. `list_cases` calcula uma vez para a página; `get_case` calcula para o caso.
- O resumo da conta bancária ganha `"alert_count"`.

- [ ] **Passo 1: Testes que falham** (reusar `_upload`/`_relay` de `test_phase_b` e o fluxo de extrato de `test_phase_c`):
  - `test_case_lists_duplicate_alert`: CSV com duas saídas iguais a 2 dias → os dois casos trazem `alerts[0]["kind"] == "duplicate_payment"`.
  - `test_own_transfer_alert_across_accounts`.
  - `test_alerts_never_cross_entities`: a mesma situação com a outra conta numa segunda empresa (`add_entity`) → `alerts == []`.
  - `test_bank_summary_alert_count`.
- [ ] **Passo 2:** rodar e ver FALHAR.
- [ ] **Passo 3:** implementar.
- [ ] **Passo 4:** rodar o arquivo, `tests/integration/test_phase_c.py` e `pytest tests/unit -q`. Deve PASSAR.
- [ ] **Passo 5: Commit** "Mostra os alertas do extrato nos casos de conciliação e no resumo da conta."

### Tarefa A3: tela e ADR 013

**Arquivos:** alterar `apps/web/src/pages/ReconciliationPage.tsx` e `docs/adr/013-conciliacao-por-casos.md`.

- [ ] **Passo 1:** o tipo do caso ganha `alerts: { kind: string; transaction_ids: string[]; explanation: string; rule_version: string }[]`. Cada caso com alerta mostra a etiqueta "Atenção" e a `explanation`, sem botão novo. No resumo da conta aparece "{n} ponto(s) de atenção".
- [ ] **Passo 2:** na ADR 013, uma seção "Alertas do extrato (14/11/2026)":
  - calculados na leitura, sem tabela;
  - não bloqueiam o fechamento;
  - limiares em `configs/conferencias.yaml`;
  - cartão e empréstimo fora, com o motivo.
- [ ] **Passo 3:** `npm run typecheck && npm run lint` em `apps/web` deve PASSAR.
- [ ] **Passo 4: Commit** "Exibe os alertas do extrato na conciliação e registra a regra na ADR 013."

---

## Frente B — Conferências do balancete

### Tarefa B1: `trial_balance_checks` e a rota

**Arquivos:**
- Criar: `apps/api/src/contabil/closing/checks.py`.
- Alterar: `apps/api/src/contabil/closing/router.py`.
- Testes: `apps/api/tests/unit/test_trial_balance_checks.py` e `apps/api/tests/integration/test_trial_balance_checks.py`.

**Interfaces produzidas:**
- `CheckRow` (dataclass frozen): `account_id`, `code`, `name`, `account_type`, `closing_balance: Decimal` (débito − crédito), `last_movement: date | None`.
- `Check` (dataclass frozen): `kind: Literal["inverted_balance", "idle_balance"]`, `account_id`, `code`, `name`, `amount: Decimal`, `explanation: str`, `rule_version: str`.
- `evaluate_checks(rows: Sequence[CheckRow], period_start: date, period_end: date, thresholds: Thresholds) -> list[Check]`. Função pura, ordenada por `kind` e `code`.
- `trial_balance_checks(session, principal, period_id: str) -> dict`. Monta as linhas a partir de `ledger.service.trial_balance` (o `closing_balance` dos itens, convertido para `Decimal`), de `Account.account_type` e da maior `JournalEntry.entry_date` efetiva (`EFFECTIVE_JOURNAL_STATUSES`) por conta até `period_end`. Devolve `{"period_id", "rule_version", "items": [check_dict...]}`, com `amount` formatado por `format_signed`.
- Rota `GET /v1/periods/{period_id}/trial-balance-checks` em `closing/router.py`, aberta a qualquer papel do escritório (o router já monta com `require_office`).

Regras:
- `inverted_balance`: `asset`/`expense` com saldo < 0, ou `liability`/`equity`/`revenue` com saldo > 0. Texto: "Saldo {credor|devedor} numa conta de natureza {devedora|credora}. Se for conta redutora (depreciação, prejuízo acumulado), ignore."
- `idle_balance`: saldo ≠ 0 e nenhum movimento desde o 1º dia do mês `idle_balance_months − 1` meses antes do mês da competência. Com 3 e competência novembro, conta movimento a partir de 1º de setembro. Texto: "Saldo parado há {n} meses ou mais. Confira se ainda é devido."

- [ ] **Passo 1: Testes unitários que falham:**
  - `test_asset_with_credit_balance_is_inverted`;
  - `test_revenue_with_debit_balance_is_inverted`;
  - `test_normal_balances_have_no_check`;
  - `test_idle_balance_uses_month_window` (movimento em 31/08 numa competência de novembro → aparece; em 01/09 → não aparece);
  - `test_zero_balance_never_idle`.
- [ ] **Passo 2:** `pytest tests/unit/test_trial_balance_checks.py -q` deve FALHAR.
- [ ] **Passo 3:** implementar `evaluate_checks`.
- [ ] **Passo 4:** os testes unitários devem PASSAR.
- [ ] **Passo 5: Testes de integração que falham:**
  - `test_checks_route_flags_inverted_asset`: lançamento publicado deixando uma conta de ativo credora → `items[0]["kind"] == "inverted_balance"`;
  - `test_checks_route_other_tenant_404`;
  - `test_checks_route_client_forbidden` (403).
- [ ] **Passo 6:** implementar `trial_balance_checks` e a rota. Rodar o arquivo de integração: deve PASSAR.
- [ ] **Passo 7: Commit** "Aponta saldo invertido e saldo parado no balancete da competência."

### Tarefa B2: tela e ADR 020

**Arquivos:** alterar `apps/web/src/pages/TrialBalancePage.tsx` e `docs/adr/020-*.md` (a ADR do checklist de fechamento).

- [ ] **Passo 1:** o bloco "Pontos de atenção" fica acima da tabela, com uma linha por item (código e nome da conta, valor e explicação) e link para a conta, no mesmo padrão de link que a página já usa. Some quando a lista vem vazia.
- [ ] **Passo 2:** na ADR 020, registrar que as conferências do balancete são informativas e não bloqueiam. O item entra no checklist na versão `2026.11-1`. A pergunta sobre o campo de natureza da conta vai ao caderno.
- [ ] **Passo 3:** `npm run typecheck && npm run lint` deve PASSAR.
- [ ] **Passo 4: Commit** "Mostra os pontos de atenção do balancete e registra a conferência na ADR 020."

---

## Frente C — Resumo do mês para o empresário

### Tarefa C1: tabela `client_summaries`

**Arquivos:**
- Criar: `apps/api/alembic/versions/0022_client_summaries.py` (`down_revision = "0021_journal_line_guards"`).
- Alterar: `apps/api/src/contabil/tables.py` (classe `ClientSummary`, no fim do arquivo).

Colunas, conforme o desenho:
- `status` com CHECK em (`draft`, `published`, `withdrawn`);
- `payload` JSONB;
- `withdrawn_reason` `String(500)` nulo.

Restrições:
- índice único parcial `uq_client_summaries_period` em (`tenant_id`, `period_id`) `WHERE status <> 'withdrawn'`;
- RLS forçada, policy `tenant_isolation`, `GRANT SELECT, INSERT, UPDATE ON client_summaries TO contabil_app`;
- trigger `guard_client_summary`, que recusa `UPDATE` que mude `payload` quando `OLD.status <> 'draft'` e recusa `DELETE`.

- [ ] **Passo 1: Teste que falha** em `tests/integration/test_client_summaries.py`: `test_published_payload_is_immutable`. Pelo engine admin, inserir publicado, tentar `UPDATE payload` e esperar `DBAPIError`.
- [ ] **Passo 2:** implementar a migração e o modelo. O teste deve PASSAR.
- [ ] **Passo 3: Commit** "Cria a tabela do resumo do mês com RLS e payload imutável depois de publicado."

### Tarefa C2: cálculo, rotas do escritório e retirada na reabertura

**Arquivos:**
- Criar: `apps/api/src/contabil/client_summaries/{__init__,compose,service,router}.py`.
- Alterar: `main.py` (`include_router(client_summaries_router, prefix="/v1", dependencies=office)`) e `closing/service.py` (`reopen_closed_run`).
- Testes: `tests/unit/test_client_summary_compose.py` e `tests/integration/test_client_summaries.py`.

**Interfaces produzidas:**
- `compose_summary(*, revenue: Decimal, expense: Decimal, cash: Decimal, fiscal_year: int, month: int) -> dict`. Função pura. Devolve:
  - `schema_version: "1.0.0"`, `competence: "AAAA-MM"`;
  - `revenue`, `expense`, `result` e `cash` como string, via `format_signed`;
  - `margin_percent`: string com uma casa (`"29.0"`), ou `None` quando a receita é 0;
  - `sentences: list[str]`.
- Frases fixas, nesta ordem:
  1. "Em {mês por extenso}/{ano}, a empresa faturou R$ {revenue} e gastou R$ {expense}."
  2. Com resultado ≥ 0: "O resultado foi lucro de R$ {result}." Com resultado < 0: "O resultado foi prejuízo de R$ {abs}."
  3. Com margem: "De cada R$ 100 faturados, sobraram R$ {round(margem)}." ou, com margem negativa, "faltaram R$ {abs}". Sem receita: "Não houve faturamento na competência."
  4. "No fim do mês, havia R$ {cash} nas contas bancárias."
  - Valores no formato brasileiro (`1.234,56`) só dentro das frases.
- `generate_summary(session, principal, period_id) -> dict`:
  - papéis `preparer`, `approver` e `admin`;
  - competência com `status == "closed"`, senão 409 "Competência aberta";
  - o rascunho existente é recalculado; o publicado gera 409 "Resumo já publicado".
  - receita e despesa vêm de `income_statement(...)["sections"]`, coluna `month`;
  - o caixa vem de `account_sums(..., AccountingPeriod.end_date <= period.end_date)`, somado nas `BankAccount.account_id` da empresa.
- `get_summary(session, principal, period_id) -> dict`: devolve o não retirado mais recente, ou 404.
- `publish_summary(session, principal, period_id) -> dict`:
  - papéis `approver` e `admin`;
  - `principal.username == created_by` recebe 409 "Quem gerou não publica";
  - grava `published_by` e `published_at` e chama `append_event`.
- `withdraw_summary(session, principal, period_id, reason: str) -> dict`: papéis `approver` e `admin`, motivo com 10 caracteres ou mais.
- `withdraw_on_reopen(session, tenant_id, period_id) -> None`: o publicado passa a `withdrawn` com motivo "Competência reaberta". É chamada dentro de `reopen_closed_run`, antes do `return` antecipado, para valer mesmo sem execução de fechamento.
- `summary_dict(row) -> dict`: `summary_id`, `period_id`, `legal_entity_id`, `status`, `payload`, `created_by`, `published_by`, `published_at` e `withdrawn_reason`.
- Rotas:
  - `POST /v1/periods/{period_id}/client-summary` (201 ao criar, 200 ao recalcular);
  - `GET` no mesmo caminho;
  - `POST .../client-summary/publish`;
  - `POST .../client-summary/withdraw` com `ReasonBody`.

- [ ] **Passo 1: Testes unitários que falham:**
  - `test_compose_profit_sentences` (receita 1000, despesa 710, caixa 500 → margem `"29.0"` e frase "sobraram R$ 29");
  - `test_compose_loss_sentences`;
  - `test_compose_without_revenue` (`margin_percent is None`).
- [ ] **Passo 2:** ver FALHAR, implementar `compose.py` e ver PASSAR.
- [ ] **Passo 3: Testes de integração que falham:**
  - `test_generate_requires_closed_period` (409);
  - `test_generate_and_publish_by_other_person`;
  - `test_creator_cannot_publish` (409);
  - `test_regenerate_draft_recalculates`;
  - `test_reopen_withdraws_published`: fechar, gerar, publicar, pedir e aprovar a reabertura pelo fluxo de `periods` → `status == "withdrawn"`, `withdrawn_reason == "Competência reaberta"`.
- [ ] **Passo 4:** implementar o serviço, o router e o gancho. Rodar os testes de integração e `tests/integration/test_close_runs.py`: devem PASSAR.
- [ ] **Passo 5: Commit** "Gera, publica e retira o resumo do mês para o empresário."

### Tarefa C3: rotas do portal

**Arquivos:**
- Alterar: `apps/api/src/contabil/portal/router.py` e `client_summaries/service.py`.
- Teste: `tests/integration/test_client_summaries.py`.

**Interfaces produzidas:**
- `list_client_summaries(session, principal) -> dict` (`{"items": [...]}`, por `published_at` decrescente).
- `client_summary(session, principal, summary_id) -> dict`.
- As duas chamam `ensure_client` e filtram por `principal.legal_entity_id` e `status == "published"`. Fora disso, 404.
- Rotas `GET /v1/portal/summaries` e `GET /v1/portal/summaries/{summary_id}`.

- [ ] **Passo 1: Testes que falham:**
  - `test_client_sees_only_published_own_entity`: o rascunho não aparece; o resumo publicado de outra empresa dá 404 por id;
  - `test_client_loses_summary_after_reopen`;
  - `test_office_user_cannot_use_portal_route` (403).
- [ ] **Passo 2:** implementar. Os testes devem PASSAR.
- [ ] **Passo 3: Commit** "Mostra no portal só o resumo publicado da empresa do cliente."

### Tarefa C4: telas, ADR 025 e ADR 034

**Arquivos:**
- Alterar: `apps/web/src/pages/CloseRunPage.tsx` (ou `PeriodsPage.tsx`, onde estiver a competência fechada) e `apps/web/src/pages/PortalPage.tsx`.
- Criar: `docs/adr/034-resumo-do-mes-para-o-cliente.md`.
- Alterar: `docs/adr/025-portal-do-cliente.md`.

- [ ] **Passo 1: Painel "Resumo para o cliente"**, só com a competência fechada.
  - Botões "Gerar resumo", "Publicar" e "Retirar" (este pede motivo), cada um visível conforme o papel e o estado.
  - Mostra as frases e o estado: rascunho, publicado ou retirado com o motivo.
- [ ] **Passo 2: Cartão "Resumo do mês" no portal**, com as frases do resumo publicado mais recente e a lista dos anteriores.
- [ ] **Passo 3: ADR 034 (`accepted`)**:
  - sem IA;
  - frases fixas;
  - quatro olhos (quem gera não publica);
  - retirada na reabertura;
  - payload imutável.
  - Na ADR 025, uma linha: o cliente lê o resumo publicado da própria empresa.
- [ ] **Passo 4:** `npm run typecheck && npm run lint` deve PASSAR.
- [ ] **Passo 5: Commit** "Leva o resumo do mês ao fechamento e ao portal e registra a ADR 034."

---

## Frente D+E — Sugestão de contrapartida

### Tarefa E1: tipos e sugestão pelo histórico

**Arquivos:**
- Criar: `apps/api/src/contabil/suggestions/{__init__,types,history}.py`.
- Testes: `tests/unit/test_history_suggestions.py` e `tests/integration/test_suggestions.py`.

**Interfaces produzidas:**
- `Suggestion` (dataclass frozen): `account_id`, `code`, `name`, `confidence: Literal["alta", "média", "baixa"]`, `justification: str`, `source: Literal["history", "model"]`, `provider_version: str`.
- `suggestion_dict(s) -> dict`.
- `rank_history(tx_description: str, past: Sequence[tuple[str, str]], accounts: Mapping[str, tuple[str, str]]) -> list[Suggestion]`. Função pura. `past` traz (descrição normalizada, `account_id` da contrapartida); `accounts` leva o id a (código, nome).
  - Descrição igual: 3 ou mais usos da mesma conta dão `alta`, 1 ou 2 dão `média`.
  - Só 2 palavras ou mais em comum: `baixa`.
  - No máximo 3, ordenado por confiança e depois por uso.
  - `provider_version = "history-1"`.
  - Justificativa: "Usada {n} vez(es) para '{descrição}'".
- `history_suggestions(session, tenant_id: str, case: ReconciliationCase, transaction: BankTransaction, bank: BankAccount) -> list[Suggestion]`.
  - Busca os casos da mesma `legal_entity_id`, por `BankAccount`, com `journal_id` de um `JournalEntry` com `source_type == "bank"` e status em `EFFECTIVE_JOURNAL_STATUSES`, cuja transação tenha a mesma `direction`.
  - A contrapartida é a linha do journal com `account_id != bank.account_id`.
  - O próprio caso fica fora. Só entram contas ativas e lançáveis.

- [ ] **Passo 1: Testes unitários que falham:**
  - `test_three_equal_uses_is_high`;
  - `test_one_use_is_medium`;
  - `test_partial_tokens_is_low`;
  - `test_at_most_three_suggestions`.
- [ ] **Passo 2:** ver FALHAR, implementar `rank_history` e ver PASSAR.
- [ ] **Passo 3: Testes de integração que falham:**
  - `test_history_suggests_previous_counterpart`: um caso resolvido por `POST .../journal` com a conta X e um segundo extrato com a mesma descrição → `history_suggestions` devolve X;
  - `test_history_ignores_other_entity`.
- [ ] **Passo 4:** implementar `history_suggestions`. Os testes devem PASSAR.
- [ ] **Passo 5: Commit** "Sugere a contrapartida pelo histórico de casos da mesma empresa."

### Tarefa E2: pseudonimização

**Arquivos:** criar `suggestions/pseudonymize.py`. Teste: `tests/unit/test_pseudonymize.py`.

**Interfaces produzidas:** `pseudonymize(text: str) -> str`.
- Por regra, nesta ordem:
  - e-mail → `[EMAIL]`;
  - CNPJ (com ou sem máscara, inclusive alfanumérico) → `[CNPJ]`;
  - CPF → `[CPF]`;
  - telefone → `[TELEFONE]`;
  - qualquer sequência de 6 dígitos ou mais que sobrar → `[NUMERO]`.
- Por heurística: depois de `PIX`, `TED`, `DOC`, `TRANSF`, `TRANSFERENCIA`, `TRANSFERÊNCIA`, `RECEBIDO DE` ou `ENVIADO PARA`, cada palavra seguinte vira `[PESSOA]`, até a primeira que esteja em `_KNOWN_TERMS`. `_KNOWN_TERMS` é um frozenset em maiúsculas com termos bancários e comerciais: LTDA, ME, EIRELI, SA, PAGAMENTO, BOLETO, TARIFA, ALUGUEL, ENERGIA, etc. Palavras seguidas de `[PESSOA]` viram um só marcador.
- Não loga nada.

- [ ] **Passo 1: Testes que falham:**
  - `test_masks_cpf_cnpj_email_phone`, com CPF e CNPJ gerados pelo próprio teste (válidos e fictícios);
  - `test_masks_long_numbers`;
  - `test_masks_person_after_pix` ("PIX RECEBIDO JOAO DA SILVA" → sem "JOAO");
  - `test_keeps_known_terms` ("PAGAMENTO BOLETO ENERGIA" não muda);
  - `test_heuristic_gap_documented`: um nome solto sem prefixo ("MARIA SOUZA ALUGUEL") **passa**. Assim o teste registra a lacuna que a ADR 035 cita.
- [ ] **Passo 2:** ver FALHAR, implementar e ver PASSAR.
- [ ] **Passo 3: Commit** "Pseudonimiza a descrição da transação antes de qualquer envio ao modelo."

### Tarefa E3: tabelas `account_suggestions` e `suggestion_runs`

**Arquivos:**
- Criar: `alembic/versions/0023_account_suggestions.py`. Na frente, usar `down_revision = "0021_journal_line_guards"` e `revision = "0023_account_suggestions"`.
- Alterar: `tables.py` (classes `AccountSuggestion` e `SuggestionRun`, no fim).

Colunas conforme o desenho.
- `confidence` com CHECK em (`alta`, `média`, `baixa`) e `source` com CHECK em (`model`).
- Índice `ix_account_suggestions_case` em (`tenant_id`, `case_id`, `created_at`) e índice `ix_suggestion_runs_day` em (`tenant_id`, `created_at`).
- RLS forçada nas duas tabelas. `GRANT SELECT, INSERT` apenas.

- [ ] **Passo 1: Teste que falha** `test_suggestion_tables_are_insert_only`: com o papel `contabil_app`, `UPDATE account_suggestions` falha por permissão.
- [ ] **Passo 2:** implementar. O teste deve PASSAR.
- [ ] **Passo 3: Commit** "Cria as tabelas de sugestão por IA e de custo por lote, só de inserção."

### Tarefa E4: cliente do modelo, validação e handler do worker

**Arquivos:**
- Criar: `suggestions/model.py` e `suggestions/worker.py`.
- Alterar: `worker.py` (`HANDLERS["CounterpartSuggestionRequested"]`).
- Testes: `tests/unit/test_model_suggestions.py` e `tests/integration/test_suggestions.py`.

**Interfaces produzidas:**
- `PROMPT_VERSION = "contrapartida-1"`. `BATCH_SIZE = 40`.
- Modelos Pydantic de saída:
  - `ModelPick`: `transaction_ref: str`, `account_code: str`, `confidence: str`, `justification: str`.
  - `ModelAnswer`: `picks: list[ModelPick]`.
- `ModelResult` (dataclass): `answer: ModelAnswer | None`, `stop_reason: str`, `input_tokens: int`, `output_tokens: int`.
- `ModelClient` (Protocol): `suggest(*, system: str, user: str) -> ModelResult`.
- `AnthropicModelClient(api_key: str, model: str)`. Usa `anthropic.Anthropic(api_key=..., timeout=30, max_retries=2)` e `client.messages.parse(model=model, max_tokens=4096, output_config={"effort": "low"}, system=system, messages=[{"role": "user", "content": user}], output_format=ModelAnswer)`.
  - Com `stop_reason` em (`refusal`, `max_tokens`), `answer=None`.
  - Sem `temperature`/`top_p` e sem prefill.
- `FakeModelClient(picks_by_ref: dict[str, tuple[str, str]])`: determinístico, só para teste.
- `build_prompt(chart: Sequence[tuple[str, str, str]], txs: Sequence[tuple[str, str, str, str]]) -> tuple[str, str]`.
  - O plano vai como (código, nome, tipo).
  - Cada transação vai como (ref `t1`…, direção, faixa de valor, descrição pseudonimizada).
  - Faixas de valor: `até 100`, `100 a 1.000`, `1.000 a 10.000` e `acima de 10.000`.
  - O sistema diz em português que é uma sugestão para conferência humana, que a resposta só pode usar códigos do plano dado e que a confiança é `alta`, `média` ou `baixa`.
- `validate_picks(answer: ModelAnswer, refs: Mapping[str, str], accounts_by_code: Mapping[str, Account]) -> list[tuple[str, Account, str, str]]`. Devolve (case_id, conta, confiança, justificativa).
  - Descarta ref desconhecido e conta ausente, inativa ou não lançável. Contas de outra empresa nunca estão no mapa.
  - Confiança inválida vira `baixa`. Justificativa é cortada em 300 caracteres.
- `used_today(session, tenant_id: str) -> int`: soma de `transactions_sent` desde 00:00 de Brasília (`platform/clock`).
- `run_counterpart_suggestions(session, tenant_id: str, payload: dict, client: ModelClient | None = None) -> None`. É o handler. O payload traz `bank_account_id`, `period_id`, `operation_id` e `legal_entity_id`.
  - Chama `mark_operation_running`.
  - Junta os casos `open`, `suggested` ou `reversed` da conta e da competência sem sugestão `alta` do histórico.
  - Para cada lote de até 40: se `used_today + len(lote) > suggestion_daily_limit`, para. Senão, chama o cliente, grava `SuggestionRun` (com `model`, `prompt_version`, tokens e `stop_reason`) e grava `AccountSuggestion` dos picks válidos.
  - Log só com ids, contagens e `stop_reason`.
  - Sem cliente injetado, usa `AnthropicModelClient(settings.claude_api_key, settings.suggestion_model)`.

- [ ] **Passo 1: Testes unitários que falham:**
  - `test_validate_discards_unknown_and_inactive`;
  - `test_validate_coerces_confidence_and_truncates`;
  - `test_prompt_has_no_raw_digits_or_names` (o `user` montado não contém o CPF nem o nome do fixture);
  - `test_value_bands`;
  - `test_refusal_yields_no_answer`, com um objeto falso no lugar do SDK.
- [ ] **Passo 2:** ver FALHAR, implementar `model.py` e ver PASSAR.
- [ ] **Passo 3: Testes de integração que falham** (`FakeModelClient` injetado e handler chamado direto):
  - `test_worker_saves_valid_suggestions`;
  - `test_worker_discards_other_entity_account`;
  - `test_worker_stops_at_daily_limit`: com o limite em 1 via `monkeypatch`/`get_settings.cache_clear()`, não chama o cliente e não grava run;
  - `test_worker_batches_of_40`: 45 casos → 2 chamadas.
- [ ] **Passo 4:** implementar `suggestions/worker.py` e registrar o handler. Os testes devem PASSAR. `tests/unit/test_worker.py` deve seguir verde.
- [ ] **Passo 5: Commit** "Pede ao Claude Haiku 5.5 a contrapartida em lotes, valida a resposta e registra o custo."

### Tarefa E5: rota de pedido, sugestões no caso e auditoria da escolha

**Arquivos:**
- Criar: `suggestions/router.py` e `suggestions/service.py`.
- Alterar: `main.py` (`include_router(suggestions_router, prefix="/v1", dependencies=office)`), `reconciliation/service.py` (`case_dict`, `create_journal_from_case`) e `reconciliation/router.py` (`JournalFromCase`).
- Teste: `tests/integration/test_suggestions.py`.

**Interfaces produzidas:**
- `request_counterpart_suggestions(session, principal, bank_account_id: str, period_id: str) -> dict`:
  - papéis `preparer`, `approver` e `admin`;
  - chave vazia → 503 "Sugestão por IA indisponível";
  - conta pendente para enviar mais `used_today` acima do limite → 429 "Limite diário de sugestões por IA atingido";
  - caso contrário, cria `Operation(kind="counterpart_suggestions", status="accepted")` e `enqueue(... "CounterpartSuggestionRequested" ...)` e devolve `operation_dict`.
- Rota `POST /v1/bank-accounts/{bank_account_id}/counterpart-suggestions`, com corpo `{"period_id"}`, `replay_guard`/`persist` e 202.
- `counterpart_suggestions(session, tenant_id, case, transaction, bank) -> list[dict]`: as do histórico primeiro, depois a mais recente do modelo por caso, sem repetir `account_id`.
- `case_dict` ganha `"counterpart_suggestions"` e `"model_suggestions_enabled": bool(get_settings().claude_api_key)`.
- `JournalFromCase` ganha `suggestion_source: Literal["history", "model", "manual"] = "manual"` e `suggestion_rank: int | None = Field(default=None, ge=1, le=3)`. `create_journal_from_case` chama `append_event` com a ação `reconciliation_counterpart_chosen` e os dados `{case_id, journal_id, suggestion_source, suggestion_rank}`.

- [ ] **Passo 1: Testes que falham:**
  - `test_request_without_key_is_503`;
  - `test_request_over_limit_is_429_and_creates_no_operation`;
  - `test_request_creates_operation_and_event`;
  - `test_case_shows_history_then_model_without_duplicates`;
  - `test_journal_records_suggestion_source`;
  - `test_client_cannot_request` (403).
- [ ] **Passo 2:** implementar. Os testes devem PASSAR, junto com `tests/integration/test_phase_c.py`.
- [ ] **Passo 3: Commit** "Expõe o pedido de sugestão por IA, junta histórico e modelo no caso e audita a escolha."

### Tarefa E6: smoke manual, tela, ADR 004 e ADR 035

**Arquivos:**
- Criar: `suggestions/smoke.py` e `docs/adr/035-sugestao-de-conta-por-modelo.md`.
- Alterar: `apps/web/src/pages/ReconciliationPage.tsx` e `docs/adr/004-*.md` (a ADR de IA sugere e humano aprova).

- [ ] **Passo 1: `python -m contabil.suggestions.smoke`.**
  - Monta 3 transações fictícias fixas e um plano fictício de 6 contas.
  - Chama `AnthropicModelClient` e imprime só refs, códigos, confiança, `stop_reason` e tokens.
  - Recusa rodar sem `CLAUDE_API_KEY`.
  - **Não executar** sem autorização do usuário.
- [ ] **Passo 2: Tela.**
  - O campo de contrapartida pré-seleciona `counterpart_suggestions[0]`, com o rótulo "Sugerido pelo histórico: {código} {nome} (confiança {c})" ou "Sugerido pela IA: … — confira".
  - O botão "Pedir sugestão à IA" só aparece com `model_suggestions_enabled`. Ele faz `POST` com Idempotency-Key, mostra "Pedindo sugestões…" e, quando a operação termina, invalida os casos.
  - Ao criar o journal, envia `suggestion_source` e `suggestion_rank` (`manual` se a pessoa trocou a conta).
- [ ] **Passo 3: ADRs.**
  - ADR 035 `accepted` para dados fictícios do piloto. Registra:
    - o que sai: plano, direção, faixa de valor e descrição pseudonimizada;
    - o que não sai;
    - a lacuna da heurística de nomes;
    - o teto diário e o registro em `suggestion_runs`;
    - as condições para dado real: retenção e não uso para treino conferidos, cláusula no contrato e aprovação do contador.
  - ADR 004: a fonte `model` entra, sempre como sugestão.
- [ ] **Passo 4:** `npm run typecheck && npm run lint` deve PASSAR.
- [ ] **Passo 5: Commit** "Leva a sugestão de contrapartida à tela e registra a ADR 035."

---

## Integração (sequencial, no branch `conferencias-e-sugestoes`)

### Tarefa I1: juntar as frentes

- [ ] **Passo 1:** fazer o merge de `frente-a`, `frente-b`, `frente-c` e `frente-de`, nesta ordem. Depois de cada uma, `pytest tests/unit -q`.
  - Conflitos esperados: `case_dict` (A e E acrescentam chaves diferentes), `tables.py` e `main.py` (só linhas acrescentadas) e `ReconciliationPage.tsx`. Resolva mantendo os dois lados.
- [ ] **Passo 2:** em `0023_account_suggestions.py`, `down_revision = "0022_client_summaries"`. Confirmar que `alembic heads` mostra uma cabeça só.
- [ ] **Passo 3:** suíte de integração inteira com o compose no ar. Deve PASSAR.
- [ ] **Passo 4: Commit** "Junta as quatro frentes e religa a migração da sugestão depois do resumo do mês."

### Tarefa I2: checklist `2026.11-1`

**Arquivos:**
- Alterar: `closing/checklist.py` e `closing/service.py` (`_gather`).
- Teste: `tests/unit/test_close_checklist.py`.

- [ ] **Passo 1: Testes que falham:**
  - `CHECKLIST_VERSION == "2026.11-1"`;
  - os itens `statement_alerts` e `trial_balance_checks`, não bloqueantes, com status `pending` quando a contagem é > 0 e `completed` quando é 0.
- [ ] **Passo 2:** acrescentar os dois `ItemSpec`:
  - `"statement_alerts"`, categoria `bank`, "Pontos de atenção do extrato", `blocking=False`, `kind="count"`, href `/app/rastro/conciliacao`, referência "ITG 2000 (R1), item 14", `count_key="statement_alerts"`;
  - `"trial_balance_checks"`, categoria `reports`, "Conferências do balancete", `blocking=False`, `kind="count"`, href `/app/rastro/balancete`, referência "ITG 2000 (R1), item 12", `count_key="trial_balance_checks"`.
  - Em `_gather`, as contagens vêm de `period_alert_count` e `len(trial_balance_checks(...)["items"])`.
- [ ] **Passo 3:** os testes unitários e `test_close_runs.py` devem PASSAR.
- [ ] **Passo 4: Commit** "Leva os alertas do extrato e as conferências do balancete ao checklist 2026.11-1."

### Tarefa I3: documentos comuns

- [ ] **Passo 1: SPEC do Rastro 0.12.0**, com entrada no changelog: alertas, pontos de atenção, resumo do cliente e sugestões com os rótulos exatos.
- [ ] **Passo 2: OpenAPI.** Entram as rotas novas e os campos `alerts`, `alert_count`, `counterpart_suggestions`, `model_suggestions_enabled`, `suggestion_source` e `suggestion_rank`, além dos schemas `StatementAlert`, `TrialBalanceCheck`, `ClientSummary` e `CounterpartSuggestion`. Descrição com vírgula dentro de `{ }` vai entre aspas.
- [ ] **Passo 3: Mapa do código.**
  - módulos `client_summaries` e `suggestions`;
  - evento `CounterpartSuggestionRequested`;
  - estados do resumo;
  - tabelas novas;
  - armadilha: os alertas são calculados na leitura.
- [ ] **Passo 4: README e caderno do contador.** Perguntas novas:
  - os três limiares;
  - o papel de conta para cartão, empréstimo e taxa;
  - o campo de natureza e as contas redutoras;
  - quem publica o resumo;
  - a aprovação do uso de IA com dado real.
  - `configs/conferencias.yaml` passa a citar os números reais das perguntas.
- [ ] **Passo 5: Roteiro do piloto** (`deploy/pilot/README.md`): as variáveis novas e um passo do roteiro para cada frente.
- [ ] **Passo 6:** `python scripts/validate_specs.py`, `python scripts/check_internal_links.py` e `openapi-spec-validator schemas/openapi.yaml`. Devem PASSAR.
- [ ] **Passo 7: Commit** "Atualiza SPEC 0.12.0, OpenAPI, mapa, README, caderno e roteiro do piloto."

### Tarefa I4: verificação final

- [ ] **Passo 1:** a lista completa do `AGENTS.md`:
  - `pytest tests/unit` e `python -m pyflakes src`;
  - `npm run typecheck` e `npm run lint`;
  - os três validadores;
  - a suíte de integração.
  
  Tudo verde. Se algo não rodar, dizer o quê.
- [ ] **Passo 2:** abrir o PR só com o ok do usuário. O smoke real do modelo também só com a autorização do gasto.
