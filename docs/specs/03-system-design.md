# Anchor 3 — System Design

## Fluxo de origem a evidência

```text
Documento/arquivo
  -> ingestão e hash
  -> classificação e vínculo
  -> subledger ou importação
  -> journal draft
  -> validação e aprovação
  -> ledger publicado
  -> conciliação e fechamento
  -> obrigação/relatório
  -> protocolo/recibo
  -> pacote de evidências/exportação
```

## Módulos

Identity & Tenancy; Master Data; Import & Migration; Documents & Evidence; Subledger Finance; General Ledger; Reconciliation; Close & Compliance; Regulatory Registry; Government Adapters; Collaboration Portal; Integration Platform; Audit & Observability; Accounting Assistance.

## Fronteiras de confiança

O documento recebido é conteúdo não confiável. O modelo de IA não decide permissão. O conector externo não decide que uma transmissão foi aceita sem retorno verificável. O banco não é interface de negócio. O frontend não é boundary de tenant.

## Transações e jobs

Publicação de journal, aprovação e lock são transacionais. Importação, conciliação assistida, validação regulatória, transmissão, polling e geração de export package são jobs. O outbox publica eventos depois da transação. Workers devem ser idempotentes e retomar por operação.

## Dados

O banco relacional mantém entidades, journals, estados, metadados e auditoria. Object storage mantém arquivos originais e derivados. Uma fila sustenta jobs e DLQ. Analytics pode ser separado depois do primeiro volume comprovado.

## Motor regulatório

O registry guarda órgão, obrigação, jurisdição, versão, XSD, tabela, regra, vigência, fonte, cobertura e changelog. Adaptadores traduzem contratos canônicos para endpoints e arquivos externos. Um conector não pode mudar a regra do ledger silenciosamente.

## APIs e eventos

A API usa versionamento, idempotency key, paginação e operação assíncrona. Webhooks têm assinatura, event ID, timestamp, replay e retry. Eventos de domínio incluem `JournalPublished`, `PeriodClosed`, `DocumentReceived`, `ReconciliationApproved`, `ObligationRejected` e `TransmissionAccepted`.

## Segurança

RBAC define papel e ABAC limita escritório, entidade, estabelecimento, competência, obrigação e operação. MFA e segregação de funções aplicam-se a administradores e efeitos sensíveis. Certificados ficam em cofre e nunca no prompt, log ou fixture.

## Fundação local da Fase A

O compose em [docker-compose.yml](../../docker-compose.yml) sobe PostgreSQL, MinIO, migração com seed sintético, API, worker, Keycloak de desenvolvimento e a UI em `http://localhost:5173`. O papel `contabil_app` aplica RLS. O worker administrativo valida e publica lote, lê extrato e resolve o caso nascido de um journal publicado, com retry e dead-letter. O corte bancário é 1:1 e exige aprovação humana. Contas a pagar e receber, match parcial, obrigação e IA não entram neste deploy. O fechamento com checklist, snapshot e pacote sob demanda entra ([ADR 020](../adr/020-fechamento-com-evidencia.md)). A fila de pendências, a exportação da competência e o portal do cliente entram na Fase D ([ADR 024](../adr/024-fila-de-pendencias.md), [ADR 023](../adr/023-exportacao-operacional.md), [ADR 025](../adr/025-portal-do-cliente.md)). O primeiro ambiente hospedado, separado deste compose, sobe a API e o outbox num processo só, como no [ADR 015](../adr/015-piloto-barato-heroku.md), e a interface num app próprio, como no [ADR 016](../adr/016-frontend-separado.md). Nesse ambiente o cliente testa plano, razão, documentos, conciliação bancária 1:1, o fechamento da competência, a fila de pendências e a exportação. O cliente da empresa testa o envio do arquivo do próprio pedido.
