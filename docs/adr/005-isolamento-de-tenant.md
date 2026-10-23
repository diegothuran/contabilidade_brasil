# ADR 005 — Isolamento forte de tenant e entidade

**Status:** proposed · **Data:** 11 de outubro de 2026

## Contexto

Um escritório acessa várias empresas, mas dados, certificados, obrigações e permissões não podem misturar-se. Filtro somente no frontend é insuficiente.

## Decisão

Toda entidade sensível carrega escopo de tenant e, quando aplicável, legal entity, branch e establishment. Autorização ocorre no backend e é testada com casos cross-tenant negativos.

## Consequências

Consultas e jobs exigem contexto explícito. Migração, exportação e logs precisam preservar o mesmo isolamento.
