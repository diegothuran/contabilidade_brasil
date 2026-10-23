# ADR 002 — Regulatório como registry versionado

**Status:** proposed · **Data:** 11 de outubro de 2026

## Contexto

Leiautes, XSDs, tabelas, regras, prazos e órgãos mudam por vigência e jurisdição. Colocar a lógica diretamente em telas ou no ledger torna atualização e auditoria arriscadas.

## Decisão

O registry regulatório será um módulo próprio, com versões, vigência, jurisdição, fonte, changelog, testes de regressão e matriz de cobertura. Conectores usam adaptadores.

## Consequências

É possível atualizar regra sem migrar o ledger. O produto precisa de governança, revisão fiscal e testes por versão.
