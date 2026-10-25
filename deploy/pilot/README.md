# Piloto hospedado

Um dyno Heroku Basic atende a interface, a API e o ciclo do outbox. O banco é Postgres Essential-0. O dado fica nos Estados Unidos. Documento de cliente real continua fora deste ambiente, como no [ADR 015](../../docs/adr/015-piloto-barato-heroku.md).

O `build.config` em [heroku.yml](../../heroku.yml) aponta para o grupo Cognito em Ohio e para o client público `contabil-web`. A interface grava esses valores na hora do build. Trocar o grupo ou o client exige um build novo.

## App e banco

```bash
heroku create NOME --stack container
heroku addons:create heroku-postgresql:essential-0 --app NOME
git push heroku main
```

`DATABASE_URL` vem do add-on. A aplicação aceita o formato `postgres://` e usa essa mesma credencial para a API e para o outbox.

## Login

No Cognito, região do dyno (por exemplo `us-east-1`):

1. Crie um user pool com o atributo customizado `tenant_id` (texto).
2. Crie um app client público, com authorization code e PKCE, sem client secret.
3. Callback e sign-out: `https://NOME.herokuapp.com/`.
4. O client precisa ler `custom:tenant_id`, `email` e `profile`. O ID token é o que a API valida; o audience dele é o próprio client id.
5. Crie o usuário administrador com `custom:tenant_id` igual ao `--tenant-id` do bootstrap e exija MFA por aplicativo (TOTP).

## Arquivos

Crie um bucket S3 privado na mesma região, com versionamento e bloqueio de acesso público. O usuário IAM só precisa de `s3:PutObject`, `s3:GetObject` e `s3:HeadObject` nesse bucket. A aplicação não cria o bucket.

## Configuração

```bash
heroku config:set --app NOME \
  OUTBOX_IN_PROCESS=1 \
  STATIC_DIR=/app/static \
  OIDC_ISSUER=https://cognito-idp.us-east-1.amazonaws.com/POOL_ID \
  OIDC_AUDIENCE=CLIENT_ID \
  OIDC_JWKS_URL=https://cognito-idp.us-east-1.amazonaws.com/POOL_ID/.well-known/jwks.json \
  OIDC_USERNAME_CLAIM=cognito:username \
  OIDC_TENANT_CLAIM=custom:tenant_id \
  OBJECT_STORAGE_ENDPOINT=https://s3.us-east-1.amazonaws.com \
  OBJECT_STORAGE_BUCKET=NOME-DO-BUCKET \
  OBJECT_STORAGE_ACCESS_KEY=CHAVE \
  OBJECT_STORAGE_SECRET_KEY=SEGREDO \
  OBJECT_STORAGE_REGION=us-east-1 \
  CORS_ORIGINS=https://NOME.herokuapp.com
```

Não defina `SEED_DEMO` nem `OBJECT_STORAGE_CREATE_BUCKETS`.

## Primeiro escritório

O `--user-id` é o `cognito:username` (em geral o e-mail ou o `sub`, o que o token trouxer nesse claim).

```bash
heroku run --app NOME python -m contabil.bootstrap \
  --tenant-id escritorio \
  --tenant-name "Escritório piloto" \
  --user-id USUARIO \
  --display-name "Administrador" \
  --roles admin,preparer,approver,viewer
```

Para provar o isolamento, repita com outro `--tenant-id` e outro usuário. Esse segundo usuário não vê o dado do primeiro.

## Conferência

- `GET /readyz` responde `ready`.
- O administrador entra, envia um OFX em Conciliação e vê um caso Sugerido.
- O usuário do outro escritório recebe 404 ao abrir um caso do primeiro.
- O seed de demonstração não aparece.
