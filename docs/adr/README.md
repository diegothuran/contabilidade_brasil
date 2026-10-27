# ADRs — plataforma contábil

| ADR | Decisão |
| --- | --- |
| [001](001-ledger-immutavel.md) | Journal publicado é imutável. |
| [002](002-registry-regulatorio-versionado.md) | Regulatório é registry versionado e separado. |
| [003](003-monolito-modular.md) | MVP começa em monólito modular. |
| [004](004-aprovacao-humana.md) | Efeitos contábeis e fiscais exigem aprovação. |
| [005](005-isolamento-de-tenant.md) | Isolamento forte por escritório e entidade. |
| [006](006-adaptadores-e-idempotencia.md) | Integrações usam adaptadores idempotentes. |
| [007](007-stack-fastapi-postgresql.md) | Fundação local em Python, FastAPI e PostgreSQL. |
| [008](008-outbox-postgresql.md) | Fila inicial é outbox no PostgreSQL. |
| [009](009-oidc-keycloak-dev.md) | Keycloak só no ambiente local; validação OIDC é agnóstica. |
| [010](010-rls-e-triggers.md) | RLS e triggers reforçam tenant e invariantes do ledger. |
| [011](011-object-storage-s3.md) | Object storage S3-compatível; MinIO só em localhost. |
| [012](012-jobs-outbox.md) | Jobs de importação usam o outbox, com retry e dead-letter. |
| [013](013-conciliacao-por-casos.md) | Conciliação liga extrato e razão só com aprovação humana. |
| [014](014-deploy-piloto-aws-sa-east-1.md) | AWS São Paulo quando o escritório depender do sistema no dia a dia. |
| [015](015-piloto-barato-heroku.md) | Primeiro piloto no Heroku, dyno Basic e Postgres Essential-0. |
| [016](016-frontend-separado.md) | A interface é um serviço próprio; o domínio continua num processo. |
| [017](017-cadastro-de-empresa.md) | Só o admin cadastra empresa, com CNPJ único no escritório e modelo mínimo de teste. |
| [018](018-uma-casca-visual.md) | A interface tem uma casca só. O contexto é a empresa do escritório. |
| [019](019-convite-de-usuario.md) | Só o admin convida. O Cognito envia a senha por e-mail. |
| [020](020-fechamento-com-evidencia.md) | Fechar exige checklist. O snapshot é imutável e o pacote sai no download. |
