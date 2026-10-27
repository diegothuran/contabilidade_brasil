# ADR 022 — Troca de escritório só entre memberships

**Status:** proposed · **Data:** 27 de outubro de 2026

## Contexto

O token traz um escritório em `custom:tenant_id`. Para testar a carteira de outro escritório, a mesma pessoa precisava de outro usuário. O isolamento por tenant continua obrigatório.

## Decisão

O header `X-Tenant-Id` escolhe o escritório ativo. Sem o header, vale o escritório do token. Com o header, a API só aceita um escritório em que o usuário do token já tem membership. A policy `membership_own_select` deixa a pessoa ler as próprias memberships, para montar a lista. A interface mostra o seletor na barra lateral quando há mais de um escritório e, ao trocar, esquece a empresa e a competência da sessão.

## Consequências

Um header com escritório alheio recebe 403 e não revela se o escritório existe. Convite continua criando membership num escritório só. O piloto ganha o escritório fictício `litoral`, com outra carteira, e o administrador do escritório `escritorio` também entra nele.
