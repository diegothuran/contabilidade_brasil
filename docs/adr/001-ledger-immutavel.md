# ADR 001 — Ledger publicado é imutável

**Status:** proposed · **Data:** 11 de outubro de 2026

## Contexto

A confiança do contador depende de explicar como um saldo mudou. Alterar uma linha publicada destrói a cadeia de evidência e dificulta auditoria.

## Decisão

Journal publicado não é editado nem excluído. Correção usa reversão, ajuste ou retificação como novo journal relacionado. O período fechado bloqueia postagem normal.

## Consequências

A auditoria e a reprodução ficam mais fortes. O produto precisa ensinar reversão e lidar com o custo de mais registros.
