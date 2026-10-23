# ADR 012 — Jobs pelo outbox, com retry e dead-letter

**Status:** proposed · **Data:** 12 de outubro de 2026

## Contexto

Validar e publicar um lote é trabalho assíncrono. A fila de produção continua pendente. O worker da Fase A só marcava o evento como despachado.

## Decisão

`ImportBatchReceived` valida o lote e `ImportBatchPublishRequested` publica. Cada evento tratado corre num savepoint, com `app.tenant_id` definido. Sucesso grava `dispatched_at` e completa a operação. Falha incrementa `attempts` e guarda só o nome da exceção. Na terceira falha o evento recebe `dead_at` e a operação fica `failed`. Evento sem handler continua apenas sendo marcado como despachado. Revalidar um lote já pronto ou republicar um lote já publicado não gera efeito.

## Consequências

O worker segue com a conexão administrativa, então a RLS não se aplica a ele. O serviço filtra `tenant_id` e os triggers de imutabilidade continuam valendo. Lote de até 100.000 linhas numa transação é aceitável em localhost e precisa ser medido antes de produção. Não há broker externo.
