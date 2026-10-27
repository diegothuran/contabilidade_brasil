# ADR 021 — Pedido de documento bloqueia o fechamento

**Status:** proposed · **Data:** 27 de outubro de 2026

## Contexto

O checklist `2026.10-1` conta os documentos da competência, mas não impede o fechamento quando falta um arquivo pedido ao cliente. O corte do portal, nesta versão, acontece dentro do escritório: quem pede, envia e confirma já tem papel no sistema. Não há login de cliente, e-mail nem lembrete.

## Decisão

Um pedido de documento pertence a uma empresa e a um período aberto ou reaberto.

- `preparer` ou `admin` abre o pedido, com tipo, título e prazo.
- `preparer`, `approver` ou `admin` envia um arquivo. O original segue o armazenamento já usado pelas evidências, com hash.
- `approver` ou `admin` confirma. Sem arquivo, a confirmação não acontece.
- Cancelar exige motivo de pelo menos 10 caracteres. `preparer`, `approver` ou `admin` podem cancelar.
- Os estados `open` e `received` bloqueiam o fechamento. `confirmed` e `cancelled` não bloqueiam. O checklist vigente passa a ser `2026.10-2`.
- Execução aberta mostra a versão vigente. Snapshot de execução fechada ou reaberta permanece como foi gravado.
- Cada transição grava auditoria. Não há fila nova.

## Consequências

Outubro do Ateliê Brisa de teste fica bloqueado por um pedido aberto até alguém confirmar ou cancelar. A Padaria Aurora de teste tem um pedido já confirmado. Comentário, vários arquivos no mesmo pedido e acesso do cliente ficam fora.
