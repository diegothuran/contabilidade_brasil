# ADR 036 — Revisão do mês por IA

**Status:** accepted para dados fictícios do piloto · **Data:** 24 de novembro de 2026

Depende da [ADR 004](004-aprovacao-humana.md) (IA sugere, pessoa autorizada aprova), da [ADR 005](005-isolamento-de-tenant.md) (isolamento de tenant), da [ADR 012](012-jobs-outbox.md) (operações pelo outbox), da [ADR 020](020-fechamento-com-evidencia.md) (fechamento com evidência) e da [ADR 035](035-sugestao-de-conta-por-modelo.md) (primeiro uso de modelo de linguagem).

## Contexto

O usuário pediu, em 24/11/2026, "a IA avaliando os clientes": a IA revisa o mês de cada empresa para o contador. As conferências que o sistema já tem usam regra fixa: duplicidade, transferência entre contas próprias, saldo invertido e saldo parado. Elas não pegam variação fora do padrão entre meses, conta que não combina com o resto nem resultado que não conversa com o caixa, e não explicam o porquê. A tela Revisões de IA estava no menu sem contrato ([ADR 018](018-uma-casca-visual.md)).

A sugestão de contrapartida ([ADR 035](035-sugestao-de-conta-por-modelo.md)) manda descrição bancária pseudonimizada, e a heurística de nomes tem lacuna conhecida. Uma revisão que lesse as transações herdaria o mesmo risco e multiplicaria os tokens.

## Decisão

**O que a revisão é**
- Um pedido explícito por empresa e competência: `POST /v1/periods/{period_id}/ai-reviews` (preparer, approver ou admin, com `Idempotency-Key`). A rota cria uma `operation` (`month_review`), uma linha em `ai_reviews` (`requested`) e o evento `MonthReviewRequested` no outbox. Nenhuma tela chama o modelo ao abrir.
- Vale para competência aberta ou fechada. Serve para achar problema antes de fechar.
- O resultado é uma lista de até 10 pontos de atenção. Cada ponto tem relevância (`alta`, `média`, `baixa`), categoria (`variacao`, `classificacao`, `saldo`, `coerencia`, `pendencia`, `outro`), título, explicação e evidências.
- Nenhum ponto cria, corrige ou aprova lançamento, decide item do checklist, bloqueia fechamento ou chega ao cliente.

**O que sai para a Anthropic: o pacote do mês (`ai_reviews/packet.py`, `pacote-1`)**
- Competência (`AAAA-MM`) e se está aberta ou fechada.
- Contas do balancete com saldo ou movimento: código, nome e tipo como estão no plano, mais saldo anterior, débito, crédito, saldo atual e o movimento líquido (débito menos crédito) das três competências anteriores. Uma competência que não existe vai como `null`. **Os valores saem exatos, com duas casas**, porque a revisão compara números. **O nome da conta sai como está**, com a mesma lacuna da ADR 035: conta com nome de sócio, fornecedor ou cliente leva esse nome.
- Indicadores do mês e das três competências anteriores: receita, despesa, resultado (sem o encerramento do exercício) e dinheiro em conta no fim do mês.
- As conferências do balancete (`c1`, `c2`…), com tipo, conta e valor.
- Contagens de pendência: lançamentos em rascunho, pendentes e aprovados não publicados, casos de conciliação pendentes, pedidos de documento abertos ou recebidos e alertas do extrato.

**O que não sai**
- Nome e CNPJ da empresa, nome do escritório, ids internos, descrição de transação, histórico de lançamento, documento, nome de pessoa do escritório ou do cliente e datas além da competência.

**Chamada e validação (`ai_reviews/model.py`, prompt `revisao-1`)**
- SDK oficial `anthropic`, `beta.messages.create` com `model = REVIEW_MODEL`, por padrão `claude-opus-5-5`, o modelo padrão atual, porque a revisão pede julgamento. Esforço `high`, `max_tokens` 16000, saída em JSON Schema, sem `temperature` e sem prefill. Em caso de recusa, o fallback fica do lado do servidor (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`). `timeout` de 120 s e `max_retries` 2.
- Só `end_turn` com JSON válido vira resposta. `refusal`, `max_tokens` ou JSON inválido (`invalid_output`) concluem a revisão como `incomplete`, sem pontos, com os tokens reais e com `error_code = resposta_incompleta` na operação.
- Erro de API ou de conexão marca a revisão `failed` (`stop_reason = error`) numa transação própria e relança. O outbox tenta o despacho três vezes. Revisão `completed` ou `incomplete` não chama o modelo de novo numa reentrega.
- A aplicação descarta a evidência que não está no pacote e o ponto que fica sem evidência válida. Relevância ou categoria fora da lista vira `baixa` ou `outro`. O título é cortado em 120 caracteres e a explicação em 600. Título repetido sai, e passam no máximo 10 pontos. Nada disso gera erro.

**Registro (migração `0024_ai_reviews`)**
- `ai_reviews`: empresa, competência, operação, estado, modelo, versão do prompt e do pacote, `input_sha256` do pacote enviado, tokens, `stop_reason`, quem pediu e datas. O `contabil_app` tem `SELECT`, `INSERT` e `UPDATE`, porque o worker muda o estado. Não tem `DELETE`.
- `ai_review_findings`: um registro por ponto, só `SELECT` e `INSERT`.
- `ai_review_decisions`: `procede` ou `nao_procede`, nota opcional até 500 caracteres e quem decidiu. Só `SELECT` e `INSERT`. Vale a decisão mais recente; a anterior fica.
- As três tabelas têm `tenant_id` e RLS forçada.
- A auditoria registra `ai_review_requested` e `ai_review_finding_decided` com a decisão, sem a nota.
- O log leva ids, contagens e `stop_reason`. O pacote, a resposta e o nome de conta ficam fora.

**Leitura e decisão**
- `GET /v1/periods/{period_id}/ai-reviews` (qualquer papel do escritório) traz `ai_reviews_enabled` e as revisões, a mais recente primeiro, com pontos e decisão vigente.
- A revisão concluída mais recente traz `stale`. A leitura recalcula o pacote, e `stale` é verdadeiro quando o hash difere do enviado. As revisões mais antigas não são recalculadas.
- `POST /v1/ai-review-findings/{finding_id}/decisions` (preparer, approver ou admin, com `Idempotency-Key`). O cliente da empresa não acessa nenhuma rota ([ADR 025](025-portal-do-cliente.md)).
- Sem `CLAUDE_API_KEY`, o pedido responde 503 "Revisão por IA indisponível", e a tela esconde o botão.

**Teto**
- `REVIEW_DAILY_LIMIT` (padrão 20) revisões pedidas por escritório desde 00:00 de Brasília, em qualquer estado. Acima do teto, o pedido responde 429 "Limite diário de revisões por IA atingido" e não cria nada.
- O teto conta pedidos, não chamadas. Com chave inválida, uma revisão faz até três chamadas antes de virar `failed`.
- Conferir e gravar não é atômico: dois pedidos simultâneos podem passar do teto em um. O risco é aceito no piloto.

**Smoke**
- `python -m contabil.ai_reviews.smoke` faz uma chamada real com um pacote fictício fixo, que fecha e traz dois problemas plantados: a despesa de serviços triplicou, e boa parte do lucro não chegou ao banco porque ficou a prazo. Ele só roda à mão, com autorização do usuário para o gasto. Os testes usam um cliente falso e nunca a rede.

## Condições para usar com dado real de cliente

As mesmas quatro da [ADR 035](035-sugestao-de-conta-por-modelo.md): termos de retenção e de não uso para treino conferidos, cláusula no contrato com o cliente, aprovação do contador e decisão sobre os nomes de conta. Também é preciso levar o ambiente para São Paulo ([ADR 014](014-deploy-piloto-aws-sa-east-1.md)), porque o piloto guarda o dado nos Estados Unidos ([ADR 015](015-piloto-barato-heroku.md)). A decisão está na pergunta 87 do [caderno do contador](../accountant-discovery-workbook.md).

## Consequências

- O contador ganha uma segunda leitura do mês, com o porquê e a evidência, sem sair do sistema.
- A taxa de "procede" por versão de prompt mede se a revisão vale o custo. Trocar o modelo ou o prompt muda `model` ou `prompt_version` e não exige migração.
- O escritório passa a ter um segundo custo variável, limitado pelo teto e visível em `ai_reviews` (tokens).
- Com `timeout` de 120 s, a chamada segura o relay do outbox por até dois minutos por revisão. No piloto isso é aceito; com volume, a chamada sai do relay.
- O que a revisão deve priorizar, se ponto sem decisão entra no checklist e quem pode decidir esperam o contador (perguntas 89 a 91 do caderno).
