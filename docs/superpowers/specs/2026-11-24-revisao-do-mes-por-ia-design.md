# Revisão do mês por IA — desenho

**Data:** 24/11/2026 · **Pedido:** "a IA avaliando os clientes", opção (a): a IA revisa o mês de cada empresa para o contador. O usuário aprovou o plano e pediu para começar sem mais perguntas (24/11/2026).

## Intenção

No fim do mês, o contador pede à IA uma revisão de uma empresa numa competência. A IA lê o que o sistema já calcula e devolve pontos de atenção, cada um com explicação e referência à evidência. O contador marca cada ponto como **procede** ou **não procede**, com nota opcional. Nada muda no razão e nada vai ao cliente.

A tela **Revisões de IA** já existe no menu como `PlannedPage` ("não há contrato"). Esta entrega dá o contrato e a tela. É o segundo corte da Fase F do [plano](../../specs/04-implementation-plan.md): o contador aceita, rejeita e corrige (nota) uma sugestão, e nenhuma sugestão produz efeito.

## Objetivos

- Pedido explícito por empresa e competência, assíncrono pelo outbox, como a sugestão de contrapartida ([ADR 035](../../adr/035-sugestao-de-conta-por-modelo.md)).
- Pacote do mês montado pela aplicação, só com agregados: balancete, DRE do mês e dos três meses anteriores, conferências, contagem de alertas e de pendências.
- A IA acrescenta o que regra fixa não pega: variação estranha entre meses, conta que não combina com o resto, resultado que não bate com o caixa, e explica por quê. Os avisos que o sistema já calcula entram no pacote para a IA não repeti-los sem acrescentar nada.
- Cada ponto cita pelo menos uma evidência que existe no pacote; ponto sem evidência válida é descartado.
- Decisão do contador por ponto, só de inserção, com auditoria. A taxa de "procede" por versão de prompt mede se a revisão vale o custo.
- Aviso de revisão desatualizada quando o pacote mudou desde a revisão (hash).

## Não objetivos

- Efeito contábil: nenhuma revisão cria, corrige ou aprova lançamento, decide item do checklist ou bloqueia fechamento.
- Texto da IA para o cliente. O resumo do mês continua em frases fixas ([ADR 034](../../adr/034-resumo-do-mes-para-o-cliente.md)).
- Avaliar comportamento do cliente (atrasos, devoluções) — opção (c), outro pedido.
- Mandar descrição de transação, histórico de lançamento, documento, nome ou CNPJ da empresa.
- Usar com dado real de cliente. Vale só para os dados fictícios do piloto, como a ADR 035, até a resposta da pergunta 87 e a ida para São Paulo ([ADR 014](../../adr/014-deploy-piloto-aws-sa-east-1.md)).
- Item novo no checklist de fechamento (vira pergunta ao contador).

## Anti-objetivos

- Ponto apresentado como fato ("a IA encontrou erro"). A tela diz "Sugerido pela IA — confira".
- Ponto sem evidência clicável.
- Revisão que repete as conferências com outras palavras e chama isso de análise.
- Custo sem teto ou chamada ao abrir a tela.

## Restrições

`AGENTS.md`: tenant isolado e RLS forçada em tabela nova, dinheiro em `Decimal` e string no contrato, idempotência em POST que muda estado, nada de CPF, CNPJ ou nome em log ou prompt. ADR 004: IA sugere, pessoa aprova. Mudança de tela atualiza no mesmo commit SPEC do Rastro, ADR, README, caderno, OpenAPI, README do piloto e mapa do código.

## Abordagens consideradas

1. **Pacote de agregados, uma chamada por revisão (escolhida).** A aplicação calcula os números; o modelo julga e explica. Expõe menos dado que a ADR 035 (não sai descrição de PIX), cabe numa chamada e é verificável: toda evidência aponta para algo que o pacote tem.
2. Mandar as transações do mês. Mais poder de análise, mas manda descrição bancária (o ponto mais sensível da ADR 035), multiplica tokens e o modelo passa a refazer a conciliação.
3. Só regras novas, sem IA. Barato e previsível, mas não é o que foi pedido; as regras que dependem do contador (papéis de conta, natureza) estão em aberto.

## Desenho

### Pacote do mês (`ai_reviews/packet.py`, versão `pacote-1`)

Montado da competência pedida e das três anteriores da mesma empresa, quando existem:

- `competencia`: `AAAA-MM`. `status_competencia`: aberta ou fechada.
- `contas`: cada conta do balancete com saldo ou movimento — código, nome, tipo, saldo anterior, débito, crédito, saldo atual — e `movimento_meses_anteriores`: o movimento líquido (débito menos crédito) de cada uma das três competências anteriores, do mais antigo ao mais recente, `null` quando a competência não existe.
- `indicadores`: receita, despesa e resultado do mês e das três anteriores, dinheiro em conta no fim do mês.
- `conferencias`: as conferências do balancete (`c1`, `c2`…) com tipo, código da conta e valor.
- `pendencias`: lançamentos em rascunho, pendentes e aprovados não publicados, casos de conciliação pendentes, pedidos de documento abertos ou recebidos, alertas do extrato.

Valores como string decimal. O nome das contas sai como está no plano (a mesma lacuna da ADR 035). O pacote é serializado com chaves ordenadas; o SHA-256 dele fica na revisão.

### Chamada (`ai_reviews/model.py`, prompt `revisao-1`)

- `REVIEW_MODEL`, padrão `claude-opus-5-5` (o modelo padrão atual; a revisão é trabalho de julgamento). Esforço `high`, `max_tokens` 16000, saída em JSON Schema, sem `temperature` e sem prefill. Fallback do lado do servidor para recusa (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`). `timeout` de 120 s, `max_retries` 2.
- Mesmo cuidado da ADR 035: `create` e validação própria, só `end_turn` com JSON válido vira resposta; `refusal`, `max_tokens` ou JSON inválido concluem a revisão como `incomplete` com os tokens reais.
- Resposta: `pontos[]` com `relevancia` (`alta`, `média`, `baixa`), `categoria` (`variacao`, `classificacao`, `saldo`, `coerencia`, `pendencia`, `outro`), `titulo` (até 120), `explicacao` (até 600) e `evidencias` (`conta:<código>`, `conferencia:<cN>`, `indicador:<chave>`, `pendencia:<chave>`).
- Validação: evidência que não está no pacote sai; ponto sem evidência válida sai; enum fora da lista vira `baixa`/`outro`; texto cortado; no máximo 10 pontos, na ordem da resposta.

### Registro (migração `0024_ai_reviews`)

- `ai_reviews`: empresa, competência, operação, `status` (`requested`, `completed`, `incomplete`, `failed`), modelo, versão do prompt e do pacote, `input_sha256`, tokens, `stop_reason`, quem pediu, datas. `contabil_app` com `SELECT`, `INSERT` e `UPDATE` (o worker muda o estado).
- `ai_review_findings`: um por ponto, só `SELECT` e `INSERT`.
- `ai_review_decisions`: `procede` ou `nao_procede`, nota até 500, quem decidiu. Só inserção; vale a mais recente por ponto (a pessoa pode mudar de ideia, e a trilha fica).
- As três com `tenant_id` e RLS forçada.

### Rotas (todas do escritório)

- `POST /v1/periods/{period_id}/ai-reviews` (preparer, approver, admin; `Idempotency-Key`) → 202 com a operação e o id da revisão. 503 sem `CLAUDE_API_KEY`; 429 quando o escritório já pediu `REVIEW_DAILY_LIMIT` revisões no dia de Brasília (padrão 20).
- `GET /v1/periods/{period_id}/ai-reviews` → `ai_reviews_enabled` e as revisões da competência, a mais recente primeiro, com pontos e a decisão vigente; a mais recente traz `stale` (hash do pacote atual diferente).
- `POST /v1/ai-review-findings/{finding_id}/decisions` (preparer, approver, admin; `Idempotency-Key`) com `decision` e `note`.
- Auditoria: `ai_review_requested` e `ai_review_finding_decided`.

### Worker

Evento `MonthReviewRequested`, uma chamada por despacho. Sucesso grava pontos e estado na transação do handler. Falha de API grava `failed` com `stop_reason = error` numa transação própria e relança; o outbox tenta três vezes. O teto conta revisões pedidas, não chamadas: uma revisão pode custar até três chamadas com chave inválida. O log leva ids, contagens e `stop_reason`, nunca pacote ou resposta.

### Tela

Revisões de IA usa a empresa e a competência da barra. Botão "Pedir revisão à IA" (some sem chave), "Revisando…" enquanto a operação roda, aviso de revisão incompleta, falha, teto e revisão desatualizada. Cada ponto mostra relevância, categoria, título, explicação, as evidências (conta e conferência abrem o balancete, indicador abre a DRE, pendência abre Fechamentos) e os botões **Procede** e **Não procede** com nota. Aviso fixo: "Sugestão da IA para conferência. Não altera o razão e não vai ao cliente."

### Smoke

`python -m contabil.ai_reviews.smoke` chama o modelo de verdade com um pacote fictício montado no código. Só roda à mão, com autorização do gasto.

## Escolhas minhas, para conferir

- Opus 5.5 com esforço alto, configurável. Custo estimado por revisão de uma empresa pequena: centavos de dólar.
- Teto de 20 revisões por escritório por dia.
- Revisão em competência aberta ou fechada: serve para achar problema antes de fechar.
- Três competências anteriores na comparação.
- Decisão muda por nova inserção, sem apagar a anterior.
- Sem item no checklist e sem bloqueio.

## Perguntas ao contador (caderno)

- O que a revisão deve olhar primeiro, e o que é ruído (liga com a pergunta 54, "Explicar").
- Ponto sem decisão deve aparecer no checklist de fechamento, sem bloquear?
- Quem pode pedir e decidir: só quem tem CRC, ou também o preparador?

## Para quem constrói

Nomes internos, forma exata do JSON no OpenAPI, texto do prompt e layout dos cartões.
