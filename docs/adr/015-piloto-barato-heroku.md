# ADR 015 — Primeiro piloto no plano mais barato

**Status:** proposed · **Data:** 12 de outubro de 2026

## Contexto

O [ADR 014](014-deploy-piloto-aws-sa-east-1.md) deixa o dado em São Paulo e custa cerca de US$ 230 a 320 por mês. Uma Machine na Fly.io em São Paulo com Postgres gerenciado fica em cerca de US$ 55 a 70, porque o plano Basic do banco custa US$ 38.

Por enquanto o ambiente hospedado é o mais barato que permanece ligado. O recorte é o que já existe: escritório, plano de contas, razão, documentos e conciliação bancária 1:1. Portal, fechamento e obrigação fiscal continuam nas fases D e E. Transmissão fiscal continua fora até existir política de certificado.

Em outubro de 2026, o Heroku cobra US$ 7 por um dyno Basic (512 MB, sempre ligado) e US$ 5 pelo Postgres Essential-0 (1 GB, 20 conexões, até 4.000 tabelas, PostgreSQL 16). O dyno Eco custa US$ 5 e dorme depois de 30 minutos. O runtime comum fica nos Estados Unidos ou na Europa. O Essential não cria credencial extra, não oferece fork e não tem o rollback do Standard-0 (US$ 50).

## Decisão

O ambiente hospedado atual é um app Heroku no runtime comum dos Estados Unidos, no menor plano sempre ligado.

- **Um processo para o domínio.** Um dyno Basic atende a API em HTTPS e roda o ciclo do outbox no mesmo processo. Não há NAT, balanceador dedicado nem CloudFront. A interface estática saía por esse processo; desde o [ADR 016](016-frontend-separado.md) ela é um app próprio, também Basic. O passo a passo está em [deploy/pilot/README.md](../../deploy/pilot/README.md).
- **Banco.** Heroku Postgres `essential-0`. O Alembic segue igual. O seed de demonstração não roda. A credencial única é dona das tabelas e não pode criar outro papel. `FORCE ROW LEVEL SECURITY` faz essa credencial obedecer às policies. `outbox_events` fica sem `FORCE`: o ciclo do outbox lê todos os escritórios e, em seguida, fixa `app.tenant_id` antes de mexer no restante.
- **Arquivos.** Bucket S3 privado na mesma região do dyno, com versionamento e bloqueio de acesso público. O módulo de documentos só troca endpoint e credencial. MinIO não entra. A aplicação não cria o bucket.
- **Login.** Cognito na mesma região do dyno, com MFA por aplicativo para quem administra. A interface envia o ID token. A API continua validando issuer, JWKS e audience, e lê o usuário e o escritório pelos claims configurados (`cognito:username` e `custom:tenant_id`). Keycloak não sobe.

Segredo fica na config do Heroku. Há um ambiente, separado do localhost. Documento de cliente real espera o [ADR 014](014-deploy-piloto-aws-sa-east-1.md), em São Paulo.

## Consequências

A conta prevista, em preço público de outubro de 2026, fica em torno de **US$ 12 por mês**: US$ 7 do dyno e US$ 5 do banco. Com o app da interface do [ADR 016](016-frontend-separado.md), passa a cerca de US$ 19. Cognito para dezenas de usuários e um bucket pequeno ficam na faixa gratuita. Imposto e um segundo ambiente ficam de fora.

O dado deste ambiente fica nos Estados Unidos. O plano aceita até cerca de 4 horas de indisponibilidade no mês, manutenção sem aviso e um disco de 1 GB. O papel separado de aplicação volta a ter credencial própria quando o ambiente for o de São Paulo. Até lá, `FORCE ROW LEVEL SECURITY` é o que faz o RLS valer para a credencial dona.

Juntar o ciclo do outbox ao processo da API é configuração deste piloto. A fila continua no PostgreSQL. Se 512 MB não couberem o processo, o passo seguinte é um dyno Standard-1X (US$ 25), ainda um processo só. O desenho de São Paulo entra quando houver documento de cliente real ou quando o escritório depender do sistema no dia a dia.
