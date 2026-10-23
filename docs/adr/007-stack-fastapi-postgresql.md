# ADR 007 — Stack Python, FastAPI e PostgreSQL na fundação local

**Status:** proposed · **Data:** 11 de outubro de 2026

## Contexto

A Fase A precisa de um monólito testável em localhost, com decimal, transação e testes de contrato. O repositório já valida schemas em Python.

## Decisão

A fundação usa Python 3.12, FastAPI, SQLAlchemy, Alembic e PostgreSQL 16. Valores monetários são `NUMERIC(20,6)` e saem na API como string. O primeiro piloto hospedado está no [ADR 015](015-piloto-barato-heroku.md). A forma AWS, para quando o escritório depender do sistema no dia a dia, está no [ADR 014](014-deploy-piloto-aws-sa-east-1.md). Esta decisão não muda a stack.

## Consequências

O time desenvolve e testa o razão sem escolher a nuvem. Trocar o banco depois exige manter os contratos JSON e repetir as invariantes fora do dialeto PostgreSQL.
