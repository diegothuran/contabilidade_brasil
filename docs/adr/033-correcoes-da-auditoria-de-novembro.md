# ADR 033 — Correções P0 da auditoria de novembro de 2026

**Status:** accepted · **Data:** 14 de novembro de 2026

A auditoria de código de 14/11/2026 (cartographer, relatório fora do Git em `.cartographer/`) achou oito defeitos P0 e sete perguntas de decisão. Esta ADR registra as correções que mudam segurança ou invariantes e a decisão D3, respondida pelo usuário no mesmo dia.

## Decisão

**Convite (fix-1).** O nome de usuário é global. Um nome que já existe em `app_users` sem vínculo no escritório de quem convida pertence a outro escritório: o convite responde 409 "Nome indisponível" antes de chamar o Cognito e não grava `AppUser` nem `Membership`. Antes, o admin do escritório B podia criar o login de um nome que tinha vínculo em A e, como admin em casa, trocar para A pela [ADR 022](022-troca-de-escritorio.md). Completar o login de um cliente da mesma empresa ([ADR 025](025-portal-do-cliente.md)) continua igual.

**Memória de importação por empresa (fix-2).** `external_refs` ganha `legal_entity_id` (migração `0019_external_refs_entity`, preenchida a partir do lote) e a empresa entra na chave única. A segunda empresa do escritório que migra do mesmo sistema não tem mais as linhas marcadas como "já importado".

**Mesmo arquivo em empresas diferentes (D3, fix-d3).** Decisão do usuário: o mesmo arquivo pode estar em empresas diferentes, principalmente quando o cliente troca de contador. A chave `uq_documents_tenant_sha` sai (migração `0020_documents_entity_sha`) e entram dois índices parciais: `(tenant_id, legal_entity_id, sha256)` para documento de empresa e `(tenant_id, sha256)` para documento sem empresa. O reenvio do mesmo arquivo na mesma empresa continua devolvendo o documento existente (200). Antes, o envio na empresa B devolvia o documento da empresa A, inclusive ao cliente da empresa B. O objeto no storage é endereçado pelo hash dentro do escritório e é compartilhado; a API não regrava um objeto que já existe. Entre escritórios nada muda: cada um tem o seu documento.

**Origem do lançamento (fix-3).** `POST /v1/journals` aceita só `source_type` `manual` ou `adjustment`. As outras origens (importação, banco, documento fiscal, encerramento, reversão) nascem no módulo de origem, que chama `create_journal` com `system_source=True`. Antes, um preparador declarava origem `import` ou `bank` com qualquer `source_id`.

**Linhas e TRUNCATE (fix-5).** Migração `0021_journal_line_guards`: uma linha não muda de `journal_id` e o trigger confere o journal de origem e o de destino. `audit_events`, `journal_entries` e `journal_lines` recusam `TRUNCATE`. A limpeza dos testes de integração liga `app.allow_truncate` na própria transação; fora disso, nem o dono das tabelas apaga o livro sem desligar o trigger, o que fica visível.

**Worker (fix-4).** Outbox, lembretes e verificação da cadeia de auditoria rodam cada um com sessão, commit e rollback próprios. Uma falha nos lembretes não desfaz mais o lote do outbox nem a contagem de tentativas.

**Configuração (fix-8).** `ENVIRONMENT` aceita `development`, `pilot` e `production`. Fora de `development`, a API recusa a subida quando URL de banco, valores OIDC ou chaves de storage têm cara de desenvolvimento (`dev-only`, `localhost`), quando `OIDC_USERNAME_CLAIM` ou `OIDC_TENANT_CLAIM` não foram definidos, ou quando `SEED_DEMO` está ligado. A imagem do piloto (`Dockerfile` da raiz) fixa `ENVIRONMENT=pilot`; o compose e os testes continuam em `development`. As variáveis do piloto estão em `deploy/pilot/env.example`.

**Interface (fix-6 e fix-7).** As rotas vivas remontam ao trocar de empresa, para que nenhum id da empresa anterior entre numa escrita. A tela de fechamento só lê; a execução nasce pelo botão "Abrir checklist", visível para preparer, approver e admin.

## Consequências

- O piloto precisa de `OIDC_USERNAME_CLAIM` e `OIDC_TENANT_CLAIM` explícitos, como o README já mandava. Se faltar, a API não sobe e o log diz qual variável.
- Um nome de usuário não é reaproveitado entre escritórios. Quem precisa de acesso a dois escritórios segue o caminho da [ADR 022](022-troca-de-escritorio.md), pelo administrador geral.
- Quem lê a tela de fechamento sem papel de escrita não cria mais execução por acidente.
- Continuam abertas as perguntas D1, D2 e D4 a D7 da auditoria.
