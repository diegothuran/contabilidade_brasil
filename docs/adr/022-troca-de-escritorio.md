# ADR 022 — Troca de escritório só entre memberships

**Status:** proposed · **Data:** 27 de outubro de 2026

## Contexto

O token traz um escritório em `custom:tenant_id`. Para testar a carteira de outro escritório, a mesma pessoa precisava de outro usuário. O isolamento por tenant continua obrigatório.

## Decisão

O header `X-Tenant-Id` escolhe o escritório ativo. Sem o header, vale o escritório do token. Com o header, a API só aceita a troca quando a pessoa é administradora no escritório do login e já tem membership no escritório pedido. Quem não é administrador geral permanece no escritório do login, mesmo que exista outra membership. A policy `membership_own_select` deixa a pessoa ler as próprias memberships. `GET /v1/me` só devolve os outros escritórios para o administrador geral. A interface mostra o seletor na barra lateral só nesse caso e, ao trocar, esquece a empresa e a competência da sessão.

## Consequências

Um header com escritório alheio, ou enviado por quem não é administrador no escritório do login, recebe 403 e não revela se o escritório existe. O login de cliente ignora `X-Tenant-Id` e permanece no escritório do token. Ele não vê o seletor e não troca de empresa ([ADR 025](025-portal-do-cliente.md)). Convite continua criando membership num escritório só. O piloto ganha o escritório fictício `litoral`, com outra carteira, e o administrador geral do escritório `escritorio` também entra nele.
