# ADR 003 — Monólito modular no MVP

**Status:** proposed · **Data:** 11 de outubro de 2026

## Contexto

Ledger, subledgers, fechamento e auditoria têm invariantes relacionadas. Separar serviços antes de validar o domínio aumenta transações distribuídas e dificulta testes.

## Decisão

Começar com monólito modular, workers assíncronos e interfaces de adaptador. Extrair serviços apenas diante de escala, isolamento ou ownership comprovados.

## Consequências

O primeiro deploy é mais simples e consistente. O time precisa manter fronteiras de módulo e evitar acesso direto ao banco entre módulos.
