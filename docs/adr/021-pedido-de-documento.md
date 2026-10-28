# ADR 021 — Pedido de documento bloqueia o fechamento

**Status:** proposed · **Data:** 27 de outubro de 2026

## Contexto

O checklist `2026.10-1` conta os documentos da competência, mas não impede o fechamento quando falta um arquivo pedido ao cliente. O primeiro corte aconteceu dentro do escritório. O login do cliente, limitado aos pedidos da própria empresa, entra no [ADR 025](025-portal-do-cliente.md). A devolução, os vários arquivos e a conversa entram no [ADR 026](026-devolucao-e-conversa.md). E-mail e lembrete continuam fora.

## Decisão

Um pedido de documento pertence a uma empresa e a um período aberto ou reaberto.

- `preparer` ou `admin` abre o pedido, com tipo, título e prazo.
- `preparer`, `approver` ou `admin` envia um arquivo. O original segue o armazenamento já usado pelas evidências, com hash.
- `approver` ou `admin` confirma. Sem arquivo ativo, a confirmação não acontece.
- `approver` ou `admin` devolve o pedido recebido, com motivo. O pedido volta a aberto e o arquivo fica marcado como devolvido ([ADR 026](026-devolucao-e-conversa.md)).
- Cancelar exige motivo de pelo menos 10 caracteres. `preparer`, `approver` ou `admin` podem cancelar.
- Os estados `open` e `received` bloqueiam o fechamento. `confirmed` e `cancelled` não bloqueiam. O checklist vigente passa a ser `2026.10-2`.
- Execução aberta mostra a versão vigente. Snapshot de execução fechada ou reaberta permanece como foi gravado.
- Cada transição grava auditoria. Não há fila nova.

## Consequências

Outubro do Ateliê Brisa de teste fica bloqueado por um pedido aberto até alguém confirmar ou cancelar. A Padaria Aurora de teste tem um pedido já confirmado. O acesso do cliente está no [ADR 025](025-portal-do-cliente.md). E-mail e lembrete ficam fora.
