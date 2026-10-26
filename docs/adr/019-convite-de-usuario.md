# ADR 019 — Convite de usuário pelo admin

**Status:** proposed · **Data:** 26 de outubro de 2026

## Contexto

O login exige o usuário no provedor de identidade e a membership no banco. O token traz `cognito:username` e `custom:tenant_id`. Os papéis saem da membership ([ADR 009](009-oidc-keycloak-dev.md)). O primeiro admin nasce no `contabil.bootstrap`. Cada pessoa seguinte passava pelo console do Cognito e por outro comando.

## Decisão

Só o papel `admin` convida, por `POST /v1/users`, com idempotency key. O escritório é o do token.

- O corpo traz nome de usuário, nome de exibição, e-mail e ao menos um papel entre `preparer`, `approver`, `admin` e `viewer`.
- A API cria o usuário no Cognito com `AdminCreateUser`, atributo `custom:tenant_id` do escritório e envio da senha temporária por e-mail. A senha não volta na resposta, na auditoria nem em log.
- A mesma operação grava `app_users`, se faltar, e a membership. A auditoria registra `user_invited` com os papéis.
- Se o nome já existe no Cognito com outro escritório, a API responde 409 e não cria membership. Se o escritório é o mesmo e a membership falta, ela é completada.
- Sem `COGNITO_ADMIN_ACCESS_KEY` e `COGNITO_ADMIN_SECRET_KEY`, o convite responde 503. Essas chaves ficam só na API. O client público da interface não as recebe.
- O papel `contabil_app` passa a poder inserir em `app_users` e `memberships`.
- O primeiro admin continua no bootstrap. Trocar papel e desativar usuário ficam fora desta decisão.

## Consequências

O admin convida em Administração. A pessoa troca a senha no primeiro login. O pool usa o remetente padrão do Cognito até o volume pedir SES. No compose local, sem essas chaves, a tela informa que o diretório não está configurado.
