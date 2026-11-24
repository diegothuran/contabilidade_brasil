# Conferências e sugestões inspiradas na aula "Claude para contadores" — desenho

**Data:** 14/11/2026 · **Origem:** aula gravada em 07/11/2026 (fora do Git), analisada nesta sessão.

## Intenção

Na aula, o contador entregava extrato, plano de contas e balancete a um modelo de linguagem e recebia três coisas: a conta sugerida para cada transação com confiança e justificativa, avisos de conferência (pagamento em duplicidade, transferência entre contas próprias, repasse de cartão sem taxa, empréstimo sem juros) e um relatório do mês em linguagem de empresário. O usuário pediu para trazer as cinco ideias para o sistema, em paralelo, atualizando as ADRs necessárias.

O sistema já guarda o dado que a aula precisava montar à mão: extrato importado (OFX/CSV), casos de conciliação, razão, balancete, DRE, Balanço e portal do cliente. Falta a camada de **conferência** e **sugestão**. Ela deve ajudar o preparador e o contador sem nunca produzir efeito contábil sozinha.

## Objetivos

- **A — Alertas do extrato.** Na conciliação, marcar transações que parecem pagamento em duplicidade ou transferência entre contas da mesma empresa.
- **B — Conferências do balancete.** No checklist de fechamento, itens de atenção (não bloqueiam) que apontam saldo invertido pela natureza da conta e conta com saldo parado.
- **C — Resumo do mês para o empresário.** O contador gera, revisa e publica um resumo da competência fechada (faturamento, despesas, resultado, margem, dinheiro em conta) com frases fixas em linguagem simples. O cliente da empresa lê no portal.
- **D — Sugestão de conta pelo histórico.** No caso de conciliação sem par, sugerir a contrapartida usada antes para transações parecidas da mesma empresa, com confiança e justificativa. A tela pré-seleciona; a pessoa confirma.
- **E — Sugestão por modelo de linguagem.** Para a transação que o histórico não resolve, pedir a sugestão ao Claude Haiku 5.5 pela API da Anthropic, com a chave `CLAUDE_API_KEY` do ambiente (pedido do usuário em 14/11/2026). O texto vai pseudonimizado, a resposta é validada contra o plano da empresa e fica guardada como sugestão. ADR nova.

## Não objetivos

- Mandar ao modelo CPF, CNPJ, e-mail, telefone ou número de documento (garantido por regra). Nome de pessoa sai por heurística, com vazamento possível; por isso o uso fica restrito a dados fictícios até existir uma garantia forte (ver ADR nova).
- Gravar a chave no repositório ou em log.
- Classificar automaticamente, criar journal, aprovar caso ou publicar resumo sem ação humana.
- Detectar repasse de cartão sem taxa, empréstimo sem juros e adiantamento parado: dependem de saber qual conta é "cartão a receber", "empréstimo" ou "taxa", e o plano não tem esse papel (pergunta 18 do caderno). Viram pergunta ao contador.
- Exportar lançamentos no layout de Domínio, Alterdata ou SCI.
- Texto livre gerado por IA no resumo do empresário.

## Anti-objetivos

- Sugestão apresentada como fato ("a IA conciliou"). A SPEC §7 manda dizer `sugerido`.
- Limiar contábil escondido em `if` sem referência. Janela de dias e tolerâncias são dado versionado com pergunta ao contador.
- Cliente da empresa vendo resumo não publicado ou de outra empresa.
- Alerta que bloqueia o fechamento sem decisão do contador.

## Restrições

- Regras de `AGENTS.md`: tenant e empresa isolados, RLS forçada em tabela nova, dinheiro em `Decimal`, idempotência em POST que muda estado, nada de CPF/CNPJ/nome em log ou prompt.
- ADR 004: IA sugere; pessoa autorizada aprova. ADR 013: conciliação por casos. ADR 020: checklist versionado. ADR 025: cliente preso à empresa.
- `CLAUDE.md`: incerteza vira pergunta de decisão, não código permanente.

## Abordagens consideradas

1. **Quatro frentes paralelas em worktrees, arquivos comuns integrados no fim (escolhida).** A, B, C e D+E tocam módulos diferentes (`reconciliation/`, `closing/`, `ledger/statements` + `portal/`, novo `suggestions/`). O checklist, a SPEC, o OpenAPI, o mapa do código, o README, o caderno e o roteiro do piloto ficam para a integração, um de cada vez, para não gerar conflito.
2. Uma frente só, em sequência. Mais simples de juntar, mas o usuário pediu paralelo e as frentes são independentes.
3. Quatro frentes que editam também os arquivos comuns. Mais rápido por frente, mas quatro edições no mesmo trecho da SPEC e do OpenAPI geram conflito garantido.

D e E ficam juntas porque a tela e a resposta do caso juntam as duas fontes.

## Desenho por frente

### Limiares versionados (comum a A e B)

Arquivo `configs/conferencias.yaml`, versão `2026.11-provisorio`, lido por `contabil/platform/conferences.py` (criado pela frente A; B importa). Valores provisórios até o contador responder:

- `duplicate_payment_window_days: 3` — mesma conta bancária, saída, mesmo valor, descrições parecidas (mesmo `normalize_description` ou ao menos dois tokens em comum), datas a até 3 dias.
- `own_transfer_window_days: 2` — saída numa conta bancária e entrada de mesmo valor em outra conta bancária da mesma empresa, a até 2 dias.
- `idle_balance_months: 3` — conta com saldo diferente de zero e sem movimento nos últimos 3 meses até o fim da competência.

O arquivo cita a pergunta do caderno que vai decidir cada valor.

### A — Alertas do extrato (`reconciliation/`)

- Função pura `statement_alerts(transactions, bank_accounts, thresholds) -> list[Alert]` em `reconciliation/alerts.py`; `Alert` tem `kind` (`duplicate_payment` ou `own_transfer`), `transaction_ids`, `explanation` em português e `rule_version`.
- Calculado na leitura, sem tabela: `GET /v1/reconciliation-cases` e `GET /v1/reconciliation-cases/{id}` passam a trazer `alerts` por caso; `GET /v1/bank-accounts/{id}/summary` traz a contagem da competência.
- Função `period_alert_count(session, tenant_id, legal_entity_id, period)` para a integração usar no checklist.
- Web: `ReconciliationPage` mostra o alerta como etiqueta "Atenção" com a explicação, sem botão de ação nova.
- Testes: unitários da função pura (casos de borda: janela, valor, direção, outra empresa) e integração da rota.
- ADR 013 atualizada.

### B — Conferências do balancete (`closing/`)

- Função `trial_balance_checks(session, tenant_id, legal_entity_id, period, thresholds) -> list[Check]` em `closing/checks.py`: `inverted_balance` (ativo e despesa com saldo credor; passivo, patrimônio líquido e receita com saldo devedor; o plano não marca conta redutora, então depreciação acumulada e prejuízo acumulado aparecem como atenção, e a pergunta sobre um campo de natureza vai ao caderno) e `idle_balance` (limiar acima). Cada check traz conta (código e nome), valor, explicação e `rule_version`.
- Rota `GET /v1/periods/{period_id}/trial-balance-checks` (qualquer papel do escritório).
- Web: o balancete mostra "Pontos de atenção" acima da tabela, com link para a conta.
- **Não** edita `closing/checklist.py`: a integração acrescenta os itens.
- Testes unitários e de integração. ADR 020 atualizada.

### C — Resumo do mês para o empresário (`ledger/` + `portal/`)

- Tabela `client_summaries` (migração `0022_client_summaries`): `id`, `tenant_id`, `legal_entity_id`, `period_id`, `status` (`draft`, `published`, `withdrawn`), `payload` JSONB, `created_by`, `published_by`, `published_at`, `withdrawn_reason`, `created_at`. Única por (`tenant_id`, `period_id`) entre os não retirados. RLS forçada, grant para `contabil_app`, trigger que impede mudar `payload` depois de publicado.
- Números calculados da DRE e do Balanço que já existem: faturamento (receitas), despesas, resultado, margem (resultado ÷ receitas, uma casa), dinheiro em conta (saldo no fim da competência das contas contábeis ligadas a `bank_accounts`). Frases fixas, por exemplo "De cada R$ 100 faturados, sobraram R$ 29". Sem IA.
- Rotas do escritório: `POST /v1/periods/{period_id}/client-summary` (preparer, approver, admin; só competência fechada; cria ou recalcula o rascunho), `GET` do mesmo caminho, `POST .../publish` (approver ou admin, que não pode ser quem criou), `POST .../withdraw` com motivo.
- Reabertura: quando a competência é reaberta, o resumo publicado passa a `withdrawn` com motivo "Competência reaberta" na mesma transação da reabertura (gancho em `closing.reopen_closed_run`). O cliente deixa de vê-lo; o contador gera e publica outro depois do novo fechamento.
- Rota do cliente: `GET /v1/portal/summaries` e `GET /v1/portal/summaries/{id}`, só publicados e só da empresa da membership.
- Web: painel "Resumo para o cliente" na tela de Fechamentos (competência fechada) e cartão "Resumo do mês" no portal.
- ADR 025 atualizada e ADR nova para o resumo publicado.

### D + E — Sugestão de conta (`suggestions/`)

- Módulo `contabil/suggestions/`. `Suggestion` tem `account_id`, `confidence` (`alta`, `média`, `baixa`), `justification`, `source` (`history` ou `model`) e `provider_version`.
- `HistorySuggester` (D): procura, na mesma empresa, casos resolvidos com journal de origem `bank` cuja transação tenha a mesma direção e descrição parecida; conta a contrapartida usada. Três ou mais usos iguais: `alta`; um ou dois: `média`; só por tokens parciais: `baixa`. No máximo três sugestões.
- `ModelSuggester` (E), assíncrono porque a chamada custa e demora:
  - Pedido explícito: `POST /v1/bank-accounts/{id}/counterpart-suggestions` com `period_id` (preparer, approver, admin; `Idempotency-Key`) cria uma `operation` e um evento `CounterpartSuggestionRequested` no outbox. Nada é chamado na leitura de uma tela.
  - O worker junta os casos abertos sem par da conta e competência que não têm sugestão `alta` do histórico, em lotes de até 40 transações por chamada, e chama o modelo uma vez por lote.
  - Entrada do modelo: plano da empresa (código, nome, tipo, só contas lançáveis e ativas) e, por transação, um id local (`t1`, `t2`…), direção, faixa de valor e descrição pseudonimizada por `suggestions/pseudonymize.py` (CPF, CNPJ, e-mail, telefone e sequências de 6+ dígitos viram marcadores como `[CNPJ]` por regra; nome de pessoa vira `[PESSOA]` por heurística: depois dos prefixos de PIX, TED, DOC e transferência, as palavras seguintes que não estão numa lista de termos bancários e comerciais conhecidos. Os testes documentam o que a heurística não pega). O mapeamento fica só na memória do worker.
  - Chamada: SDK oficial `anthropic` (dependência nova em `apps/api`), `anthropic.Anthropic(api_key=settings.claude_api_key, timeout=30, max_retries=2)`, `client.messages.parse(model=settings.suggestion_model, max_tokens=4096, output_config={"effort": "low"}, system=..., messages=..., output_format=<modelo Pydantic>)`. Modelo padrão `claude-haiku-5-5`. Checar `stop_reason`: `refusal` ou `max_tokens` não gera sugestão e marca a operação como concluída com aviso.
  - Validação da saída: conta inexistente, inativa, não lançável ou de outra empresa é descartada; confiança fora de `alta|média|baixa` vira `baixa`; justificativa cortada em 300 caracteres.
  - Gravação: tabela `account_suggestions` (migração `0023_account_suggestions` depois da integração; na frente ela nasce sobre a 0021): `id`, `tenant_id`, `legal_entity_id`, `case_id`, `account_id`, `confidence`, `justification`, `source` (`model`), `provider_version` (modelo + versão do prompt), `operation_id`, `created_at`. RLS forçada, grant para `contabil_app`, só `INSERT` e `SELECT`. Na leitura vale a mais recente por caso.
  - Custo e registro: tabela `suggestion_runs` na mesma migração (`id`, `tenant_id`, `operation_id`, `model`, `prompt_version`, `transactions_sent`, `input_tokens`, `output_tokens`, `stop_reason`, `created_at`; RLS forçada). `operations` não muda; refusal ou `max_tokens` aparecem como `stop_reason` do lote. O log não leva prompt nem resposta, só ids, contagens e `stop_reason`.
  - Teto diário por escritório: `SUGGESTION_DAILY_LIMIT` (padrão 500 transações enviadas por escritório por dia de Brasília), contado em `suggestion_runs.transactions_sent`. A rota recusa com 429 "Limite diário de sugestões por IA atingido" quando o pedido passaria do teto; o worker também confere antes de cada lote e para sem chamar o modelo.
  - Sem chave (`CLAUDE_API_KEY` vazia), a rota responde 503 "Sugestão por IA indisponível" e a tela esconde o botão (a resposta do caso informa `model_suggestions_enabled`).
  - Testes: `ModelClient` injetado; os testes usam um cliente falso determinístico e nunca a rede. Um script manual `python -m contabil.suggestions.smoke` faz uma chamada real com dados fictícios, só quando o usuário autorizar o gasto.
- Configuração: `CLAUDE_API_KEY` (vazia por padrão), `SUGGESTION_MODEL` (padrão `claude-haiku-5-5`) e `SUGGESTION_DAILY_LIMIT` (padrão 500). Valem em `development` e `pilot`; o piloto só usa dados fictícios. A chave nunca vai para o `env.example` com valor.
- `GET /v1/reconciliation-cases/{id}` traz `counterpart_suggestions`: primeiro as do histórico (calculadas na leitura), depois a mais recente do modelo (lida da tabela), sem repetir conta. Web: a `ReconciliationPage` pré-seleciona a primeira no campo de contrapartida, mostra "Sugerido pelo histórico: … (confiança média)" e a pessoa confirma com o botão que já existe.
- Web: botão "Pedir sugestão à IA" na conciliação (some sem chave), estado "Pedindo sugestões…" enquanto a operação roda, e a sugestão aparece como "Sugerido pela IA: … (confiança baixa) — confira".
- A criação do journal grava em auditoria a origem da conta escolhida (`history`, `model` ou `manual`) e se era a primeira sugestão, para medir acerto depois.
- ADR 004 atualizada e ADR nova "Sugestão de conta por modelo de linguagem" (`accepted` para dados fictícios do piloto): o que sai para a Anthropic, a pseudonimização, o que não sai, o registro de custo e as condições para usar com dado real de cliente (termos de retenção e de não uso para treino conferidos, cláusula no contrato do escritório, aprovação do contador).

## Integração (feita no fim, em sequência)

1. Juntar as quatro frentes num branch de integração, uma de cada vez, rodando os testes após cada uma. C e D+E criam migração em paralelo: cada frente escreve a sua com `down_revision = "0021_journal_line_guards"`; na integração a de D+E é renomeada para `0023_account_suggestions` e passa a apontar para `0022_client_summaries`, para a cadeia ter uma só cabeça.
2. `closing/checklist.py`: versão `2026.11-1`, itens não bloqueantes "Pontos de atenção do extrato" (A) e "Conferências do balancete" (B).
3. SPEC do Rastro (0.12.0), OpenAPI, mapa do código, README, caderno do contador (perguntas novas: limiares, papéis de conta para cartão e empréstimo, quem publica o resumo) e roteiro do piloto.
4. Todos os validadores do `AGENTS.md` e a suíte inteira no compose.

## Decidido pelo usuário

- Fazer as cinco ideias, em paralelo, com o processo do superpowers.
- Atualizar as ADRs necessárias.
- E chama o Claude Haiku 5.5 de verdade, com a chave `CLAUDE_API_KEY` do `.env` (mensagem do usuário em 14/11/2026).
- Teto diário de gasto por escritório, 500 transações por padrão, configurável (resposta do usuário em 14/11/2026).

## Escolhas minhas, para conferir

- Limiares provisórios (3, 2 e 3) em arquivo versionado.
- Cartão sem taxa e empréstimo sem juros fora desta entrega.
- Resumo só para competência fechada, publicado por approver ou admin diferente de quem gerou.
- Sugestão pré-selecionada, nunca enviada sozinha.
- IA só por pedido explícito, em lote, pelo worker, com esforço `low` no Haiku 5.5.
- Pseudonimização de nome por heurística, aceitável só com dados fictícios.
- Resumo retirado sozinho na reabertura.
- Saldo invertido avisa também conta redutora, até existir campo de natureza.
- Custo em `suggestion_runs`, sem mexer em `operations`.

## Para quem constrói

Nomes internos de funções, forma exata do JSON de alerta e de sugestão (registrar no OpenAPI na integração), texto das frases do resumo e layout das etiquetas na tela.
