# ADR 035 — Sugestão de conta por modelo de linguagem

**Status:** accepted para dados fictícios do piloto · **Data:** 15 de novembro de 2026

Depende da [ADR 004](004-aprovacao-humana.md) (IA sugere, pessoa autorizada aprova), da [ADR 005](005-isolamento-de-tenant.md) (isolamento de tenant), da [ADR 012](012-jobs-outbox.md) (operações pelo outbox) e da [ADR 013](013-conciliacao-por-casos.md) (conciliação por casos).

## Contexto

Na aula "Claude para contadores", o contador entregava extrato e plano de contas a um modelo de linguagem e recebia a conta sugerida para cada transação, com confiança e justificativa. O sistema já guarda o extrato importado, os casos de conciliação e o plano de cada empresa. O usuário pediu, em 14/11/2026, que a sugestão use o Claude Haiku 5.5 pela API da Anthropic, com a chave `CLAUDE_API_KEY` do ambiente.

Mandar descrição bancária a um terceiro expõe dado de cliente. A descrição de um PIX costuma trazer nome, CPF ou CNPJ de quem pagou ou recebeu. O escritório ainda não conferiu os termos de retenção e de uso para treino, nem tem cláusula no contrato com o cliente.

## Decisão

**Primeiro o histórico, depois o modelo**
- A leitura do caso (`GET /v1/reconciliation-cases/{id}`) traz `counterpart_suggestions`. Primeiro vêm até três contas do histórico da **mesma empresa** (`suggestions/history.py`, versão `history-1`), calculadas na leitura: descrição igual com 3 ou mais usos dá `alta`, com 1 ou 2 dá `média`, e só 2 palavras em comum dá `baixa`. Depois vem a sugestão mais recente do modelo para o caso, sem repetir conta.
- O modelo só é chamado por pedido explícito: `POST /v1/bank-accounts/{id}/counterpart-suggestions` com `period_id` (preparer, approver ou admin, com `Idempotency-Key`). A rota cria uma `operation` (`counterpart_suggestions`) e o evento `CounterpartSuggestionRequested` no outbox. Nenhuma tela chama o modelo ao abrir.
- O worker junta os casos `open`, `suggested` ou `reversed` da conta na competência que não têm sugestão `alta` do histórico. Ele manda lotes de até 40 transações, uma chamada por lote.

**O que sai para a Anthropic**
- O plano da empresa: código, nome e tipo das contas ativas e lançáveis, menos a própria conta banco. **Os nomes das contas saem como estão no plano, sem pseudonimização.** Um plano pode ter conta com nome de sócio ("Empréstimo de João Silva"), de fornecedor ou de cliente, e esse nome vai para a Anthropic.
- Por transação: um id local (`t1`, `t2`…), a direção (entrada ou saída), a faixa de valor (`até 100`, `100 a 1.000`, `1.000 a 10.000`, `acima de 10.000`) e a descrição pseudonimizada.
- A pseudonimização (`suggestions/pseudonymize.py`) troca, por regra, e-mail por `[EMAIL]`, CNPJ (com ou sem máscara, inclusive alfanumérico) por `[CNPJ]`, CPF por `[CPF]`, telefone por `[TELEFONE]` e qualquer sequência de 6 dígitos ou mais por `[NUMERO]`. Por heurística, troca por `[PESSOA]` as palavras que vêm depois de `PIX`, `TED`, `DOC`, `TRANSF`, `TRANSFERÊNCIA`, `RECEBIDO DE` ou `ENVIADO PARA`, até o primeiro termo bancário ou comercial conhecido (`LTDA`, `PAGAMENTO`, `BOLETO`, `TARIFA`…).
- `build_prompt` aplica a faixa e a pseudonimização. Não existe outro caminho de montagem do texto enviado.

**O que não sai**
- Valor exato, data, nome e CNPJ da empresa, nome do escritório, ids internos de caso, conta, transação ou tenant, documentos anexados e linhas do razão. O mapa `t1 → caso` fica só na memória do worker.

**Lacuna conhecida da heurística de nomes**
- Nome de pessoa sem um dos prefixos passa sem máscara. "MARIA SOUZA ALUGUEL" sai como está. O teste `test_heuristic_gap_documented` registra essa lacuna e também estas: CPF já mascarado pelo banco (`***.273.650-**`, os dígitos do meio passam), CPF escrito com espaços e prefixo colado por hífen (`PIX-JOAO`). Por isso o uso fica restrito a dados fictícios.

**Chamada e validação**
- SDK oficial `anthropic`: `Anthropic(api_key=..., timeout=30, max_retries=2)` e `messages.create(model=SUGGESTION_MODEL, max_tokens=4096, output_config={"effort": "low", "format": {"type": "json_schema", "schema": <schema de ModelAnswer>}})`. O modelo padrão é `claude-haiku-5-5` e a versão do prompt é `contrapartida-1`. A chamada não usa `temperature`, `top_p` nem prefill.
- A aplicação valida o JSON por conta própria (`ModelAnswer.model_validate_json`) e só quando o `stop_reason` é `end_turn`. O `messages.parse` não é usado: com JSON truncado ou texto de recusa, ele levanta uma exceção que leva a saída do modelo e perde os tokens.
- Com `refusal`, `max_tokens` ou JSON inválido (`invalid_output`), o lote não gera sugestão e fica registrado com esse `stop_reason` e os tokens reais. A operação termina `completed` com `error_code = resposta_incompleta`, e a tela mostra o aviso.
- Erro de API ou de conexão falha a operação pelo caminho do worker (3 tentativas e depois `failed`). A mensagem leva só o tipo do erro, nunca o texto enviado.
- A resposta é validada contra o plano da empresa. Um ref que não foi enviado é descartado, e uma conta ausente, inativa ou não lançável também. A conta de outra empresa nunca está no mapa. Confiança fora de `alta`, `média` ou `baixa` vira `baixa`, e a justificativa é cortada em 300 caracteres. Nada disso gera erro.

**Registro e custo**
- `account_suggestions` (migração `0023_account_suggestions`) guarda empresa, caso, conta, confiança, justificativa, `source = model`, `provider_version` (modelo e versão do prompt) e a operação. As duas tabelas têm `tenant_id` e RLS forçada, e o `contabil_app` só tem `SELECT` e `INSERT`.
- `suggestion_runs` recebe duas linhas por lote, sempre por INSERT e numa transação própria do worker, que sobrevive ao rollback do handler. Antes da chamada entra a **reserva**: `transactions_sent` igual ao tamanho do lote, tokens 0 e `stop_reason = reserved`. Depois entra o **resultado**: `transactions_sent = 0`, tokens e o `stop_reason` real, ou `error` quando a chamada falha. As sugestões válidas do lote entram na mesma transação do resultado.
- Reentrega: quando um lote falha, o outbox tenta de novo e pula os casos que já têm sugestão da mesma operação. Assim os lotes anteriores não são pagos de novo. Caso de uma operação anterior pode ser reenviado num pedido novo.
- O log leva ids, contagens e `stop_reason`. Prompt, resposta, descrição e nome ficam fora do log.
- **Teto diário:** `SUGGESTION_DAILY_LIMIT` (padrão 500) transações enviadas por escritório desde 00:00 de Brasília, somadas em `suggestion_runs.transactions_sent`. A soma conta as reservas, inclusive as de chamada que falhou. A rota responde 429 "Limite diário de sugestões por IA atingido" quando o pedido passaria do teto, sem criar operação. O worker confere de novo antes de cada lote e para sem chamar o modelo. Nesse caso, a operação termina `completed` com `error_code = limite_diario`, e a tela mostra o aviso.
- Sem chave (`CLAUDE_API_KEY` vazia), a rota responde 503 "Sugestão por IA indisponível". O caso informa `model_suggestions_enabled: false`, e a tela esconde o botão.

**Sempre sugestão**
- A tela pré-seleciona a primeira sugestão no campo de contrapartida, com "Sugerido pelo histórico: …" ou "Sugerido pela IA: … — confira". A pessoa confirma com o botão "Criar lançamento", e o journal segue o fluxo normal de envio, aprovação e publicação ([ADR 004](004-aprovacao-humana.md)).
- A criação do journal grava em auditoria `reconciliation_counterpart_chosen` com `suggestion_source` (`history`, `model` ou `manual`) e `suggestion_rank`, para medir o acerto depois. Só a primeira sugestão aceita conta como acerto: ela leva a origem dela e `suggestion_rank = 1`. Qualquer outra conta vai como `manual`, sem rank. A API recusa com 422 a combinação incoerente.
- `python -m contabil.suggestions.smoke` faz uma chamada real com 3 transações e 6 contas fictícias. Ele só roda à mão, com autorização do usuário para o gasto. Os testes usam um cliente falso e nunca a rede.

## Condições para usar com dado real de cliente

Todas precisam estar cumpridas, e cada uma pede registro próprio:

1. Termos de retenção e de não uso para treino da API conferidos para a conta do escritório, com data e versão.
2. Cláusula no contrato do escritório com o cliente autorizando o envio pseudonimizado a um processador de IA.
3. Aprovação do contador responsável, registrada.
4. Revisão da lacuna da heurística de nomes: uma garantia mais forte ou a aceitação explícita do risco.

Até lá, a ADR vale só para os dados fictícios do piloto.

## Consequências

- O preparador ganha uma sugestão de contrapartida sem sair da conciliação. Nenhum lançamento nasce sem uma pessoa.
- O escritório passa a ter custo variável por chamada, limitado pelo teto diário e visível em `suggestion_runs`.
- A medição de acerto (`suggestion_source` e `suggestion_rank` na auditoria) permite decidir depois se o modelo vale o custo.
- A troca de modelo ou de prompt muda `provider_version` e não exige migração.
