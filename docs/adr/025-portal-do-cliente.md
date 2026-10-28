# ADR 025 — Portal do cliente da empresa

**Status:** proposed · **Data:** 27 de outubro de 2026

## Contexto

O pedido de documento nasceu dentro do escritório ([ADR 021](021-pedido-de-documento.md)). A Fase D pede que o cliente resolva a pendência sem planilha. Comentário, e-mail, lembrete e mais de um arquivo no mesmo pedido continuam sem regra do contador.

## Decisão

O papel `client` é exclusivo. Não combina com `preparer`, `approver`, `admin` ou `viewer`. A membership guarda a empresa. Sem empresa, o papel não existe.

O login do cliente:

- permanece no escritório do token. O header `X-Tenant-Id` é ignorado. Não há seletor de escritório nem troca de empresa ([ADR 022](022-troca-de-escritorio.md));
- não abre a sala do escritório. Razão, balancete, fechamento, conciliação, importação, auditoria, convite e exportação respondem 403;
- vê o nome do escritório e a razão social e o CNPJ da própria empresa, sem seletor;
- lista só pedidos `open` e `received` dessa empresa;
- envia um arquivo no pedido aberto. O original segue o armazenamento das evidências, com hash;
- pode baixar só o arquivo ligado a um pedido seu;
- não confirma e não cancela. Confirmar continua com `approver` ou `admin`.

A interface do cliente é uma casca própria, sem o menu do escritório. O vocabulário na tela é pedido, prazo e arquivo. Não aparece journal, competência contábil nem papéis do escritório.

O convite é do admin, na Administração, com o papel Cliente e a empresa. A senha temporária continua saindo por e-mail e não aparece na tela. Se o nome de usuário já tem acesso de cliente à mesma empresa, mas ainda não tem login (o caso das amostras do piloto), o convite só cria o login, sem duplicar o acesso, e grava `client_login_completed` na auditoria. Qualquer outro acesso que já exista com esse nome continua recebendo 409.

## Consequências

Cinco empresas de teste podem ter um cliente cada. Resolver a pendência é enviar o arquivo. O fechamento só desbloqueia quando o escritório confirma. Comentário, e-mail, lembrete e vários arquivos no mesmo pedido continuam fora.
