# ADR 009 — OIDC agnóstico e Keycloak apenas local

**Status:** proposed · **Data:** 11 de outubro de 2026

## Contexto

A fundação precisa de login, papéis e um segundo escritório para o teste negativo. O provedor de identidade de produção não foi escolhido.

## Decisão

A API valida JWT pelo issuer, JWKS e audience configurados. O Keycloak em `start-dev` existe só no compose local, com usuários sintéticos e senha falsa. Papel e escritório efetivos vêm da membership no banco; o token prova a identidade e declara o `tenant_id`.

## Consequências

Dá para exercitar aprovação e isolamento sem fixar o IdP. Produção continua exigindo decisão de identidade, MFA e ciclo de vida de usuário. O realm local não é configuração de produção. O piloto do [ADR 015](015-piloto-barato-heroku.md) configura os nomes das claims e valida o ID token do Cognito.
