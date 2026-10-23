# ADR 014 — Piloto do cliente em AWS São Paulo

**Status:** proposed · **Data:** 12 de outubro de 2026

O ambiente hospedado de agora é o [ADR 015](015-piloto-barato-heroku.md), nos Estados Unidos, no plano mais barato. Esta decisão vale quando houver documento de cliente real ou quando o escritório depender do sistema no dia a dia.

## Contexto

O compose local sobe API, worker, PostgreSQL, MinIO e Keycloak de desenvolvimento para o time. Um cliente que testa o MVP envia documento, extrato e dado de empresa. Esse material fica no Brasil, com backup e sem segredo de exemplo.

O sistema cabe em um monólito, um worker, um PostgreSQL e um bucket. A fila continua no outbox. O contrato de arquivo já é S3. O login já é OIDC, com o provedor fora do código. Render, em outubro de 2026, oferece Oregon, Ohio, Virginia, Frankfurt e Singapura, e não tem região em São Paulo.

## Decisão

Quando o piloto do ADR 015 ficar pequeno, ou quando o documento for de cliente real, o escritório roda na região `sa-east-1` (São Paulo), em quatro peças:

- **API e worker.** A mesma imagem vira dois serviços ECS Fargate em subnet privada. A API recebe HTTPS público. O worker não tem porta pública, fica com uma tarefa sempre ligada e continua lendo o outbox. Não há Kubernetes nem broker.
- **Banco.** RDS PostgreSQL 16, sem IP público, com backup automático. O papel `contabil_app` e as migrações Alembic seguem iguais. O seed de demonstração não roda neste ambiente.
- **Arquivos.** Bucket S3 privado na mesma região, com versionamento e bloqueio de acesso público. O módulo de documentos só troca endpoint e credencial. MinIO não entra.
- **Interface e login.** A interface estática sai por CloudFront. O login do piloto é Cognito na mesma região, com MFA para quem administra. A API continua validando issuer, JWKS e audience. Keycloak não sobe. Se o escritório já usar outro OIDC com MFA, a troca é configuração.

Segredo fica no Secrets Manager. Há um ambiente de piloto, separado do localhost. Transmissão fiscal de produção continua fora até existir política de certificado.

## Consequências

O dado do teste fica em São Paulo, e o preço da região é o custo dessa escolha. O worker segue com conexão administrativa, sem RLS; a rede é quem impede acesso casual ao banco. Backup do RDS e versão do objeto são o restore que precisa ser ensaiado antes de chamar o ambiente de piloto.

Trocar de nuvem depois preserva o contrato S3 e o OIDC. Retenção definitiva continua em aberto: o bucket do piloto não apaga objeto. Um teste só com dado sintético pode usar outra região; cliente com documento real usa este desenho.
