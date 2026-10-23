# ADR 008 — Outbox no PostgreSQL como fila provisória

**Status:** proposed · **Data:** 11 de outubro de 2026

## Contexto

Publicação, reversão, fechamento e reabertura precisam emitir eventos na mesma transação do efeito. A fila de produção ainda está pendente.

## Decisão

A fundação grava `outbox_events` na mesma transação do ledger. Um worker no monólito consome com `FOR UPDATE SKIP LOCKED`, registra o tipo e marca `dispatched_at`. Não há broker externo nesta fase.

## Consequências

O efeito e o evento confirmam juntos. A escolha de fila gerenciada continua aberta e não vaza para o domínio. O worker usa conexão administrativa só para o relay; a API continua sob o papel da aplicação.
