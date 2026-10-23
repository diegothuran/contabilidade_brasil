# ADR 010 — RLS e triggers como defesa das invariantes

**Status:** proposed · **Data:** 11 de outubro de 2026

## Contexto

Filtro só na aplicação não impede acesso cruzado nem edição de journal publicado por uma sessão SQL. O papel da aplicação não deve ser dono das tabelas.

## Decisão

A API conecta como `contabil_app`, sem `BYPASSRLS`. Cada tabela de negócio tem `tenant_id` e policy de RLS usando `app.tenant_id` definido na transação. Triggers bloqueiam alteração de journal publicado, exigem balanço na publicação e tornam a auditoria append-only. A auditoria encadeia o hash do evento anterior por escritório.

## Consequências

Um erro de filtro na aplicação não devolve linha de outro escritório. Migração e seed usam o papel dono, que ignora RLS e continua sujeito aos triggers. Grants novos precisam ser explícitos nas próximas migrações. No piloto do [ADR 015](015-piloto-barato-heroku.md) a credencial é dona das tabelas; `FORCE ROW LEVEL SECURITY` faz essa credencial obedecer às policies, exceto em `outbox_events`.
