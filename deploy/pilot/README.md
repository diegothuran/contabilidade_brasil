# Piloto hospedado

O piloto roda em dois apps Heroku Basic, como no [ADR 016](../../docs/adr/016-frontend-separado.md).

| App | Pasta | Endereço atual |
| --- | --- | --- |
| `contabilidade-brasil-web` | `apps/web` | `https://contabilidade-brasil-web-e81b4d6d4b02.herokuapp.com/` |
| `contabilidade-brasil` | `apps/api` | `https://contabilidade-brasil-9b3a64403fb1.herokuapp.com/` |

O app da API atende `/v1`, `/healthz` e `/readyz` e roda o ciclo do outbox. O banco é Postgres Essential-0. O dado fica nos Estados Unidos. Documento de cliente real continua fora deste ambiente, como no [ADR 015](../../docs/adr/015-piloto-barato-heroku.md).

O `build.config` em [apps/web/heroku.yml](../../apps/web/heroku.yml) aponta para o grupo Cognito em Ohio, para o client público `contabil-web` e para a URL da API. A interface grava esses valores na hora do build. Trocar o grupo, o client ou a URL da API exige um build novo da interface.

## Apps e banco

```bash
heroku create NOME-API --stack container --region us --remote heroku
heroku addons:create heroku-postgresql:essential-0 --app NOME-API
heroku create NOME-WEB --stack container --region us --remote heroku-web
```

`DATABASE_URL` vem do add-on. A aplicação aceita o formato `postgres://` e usa essa mesma credencial para a API e para o outbox.

Confira o tipo de dyno nos dois apps depois do primeiro deploy. Eco dorme e para o outbox.

```bash
heroku ps:type web=basic --app NOME-API
heroku ps:type web=basic --app NOME-WEB
```

## Publicar

A API sai pelo [heroku.yml](../../heroku.yml) da raiz. O release roda `python -m contabil.migrate`.

```bash
git push heroku main
```

A interface sai só com a pasta `apps/web`. A Heroku monta a imagem; não é preciso Docker local.

```bash
git subtree push --prefix apps/web heroku-web main
```

Quando o contrato da API mudar, publique a API primeiro.

Se o release não mostrar as migrações do Alembic no log, rode a migração à mão:

```bash
heroku run --no-tty --exit-code --app NOME-API -- python -m contabil.migrate
```

## Login

No Cognito, região do dyno (o piloto atual usa `us-east-2`):

1. Crie um user pool com o atributo customizado `tenant_id` (texto).
2. Crie um app client público, com authorization code e PKCE, sem client secret.
3. Callback e sign-out: `https://NOME-WEB.herokuapp.com/`, com a barra no final. O endereço da API não entra.
4. O client precisa ler `custom:tenant_id`, `email` e `profile`. O ID token é o que a API valida; o audience dele é o próprio client id.
5. Em **Autenticação › Fazer login › Autenticação multifator**, deixe o MFA opcional, só por aplicativo autenticador.
6. Crie o usuário administrador com `custom:tenant_id` igual ao `--tenant-id` do bootstrap e cadastre nele o aplicativo autenticador (TOTP).

## Arquivos

Crie um bucket S3 privado na mesma região, com versionamento e bloqueio de acesso público. O usuário IAM só precisa de `s3:PutObject`, `s3:GetObject` e `s3:HeadObject` nesse bucket. A aplicação não cria o bucket.

## Configuração da API

```bash
heroku config:set --app NOME-API \
  OUTBOX_IN_PROCESS=1 \
  OIDC_ISSUER=https://cognito-idp.us-east-2.amazonaws.com/POOL_ID \
  OIDC_AUDIENCE=CLIENT_ID \
  OIDC_JWKS_URL=https://cognito-idp.us-east-2.amazonaws.com/POOL_ID/.well-known/jwks.json \
  OIDC_USERNAME_CLAIM=cognito:username \
  OIDC_TENANT_CLAIM=custom:tenant_id \
  OBJECT_STORAGE_ENDPOINT=https://s3.us-east-2.amazonaws.com \
  OBJECT_STORAGE_BUCKET=NOME-DO-BUCKET \
  OBJECT_STORAGE_ACCESS_KEY=CHAVE \
  OBJECT_STORAGE_SECRET_KEY=SEGREDO \
  OBJECT_STORAGE_REGION=us-east-2 \
  CORS_ORIGINS=https://NOME-WEB.herokuapp.com
```

Não defina `STATIC_DIR`, `SEED_DEMO` nem `OBJECT_STORAGE_CREATE_BUCKETS`. O app da interface não tem config: tudo o que ele usa está no build.

## Primeiro escritório

O `--user-id` é o `cognito:username` (em geral o e-mail ou o `sub`, o que o token trouxer nesse claim).

```bash
heroku run --app NOME-API python -m contabil.bootstrap \
  --tenant-id escritorio \
  --tenant-name "Escritório piloto" \
  --user-id USUARIO \
  --display-name "Administrador" \
  --roles admin,preparer,approver,viewer
```

Para provar o isolamento, repita com outro `--tenant-id` e outro usuário. Esse segundo usuário não vê o dado do primeiro.

## Convite pela sala

O primeiro admin continua no bootstrap acima. As pessoas seguintes nascem em **Administração**, com o admin logado. O Cognito envia a senha temporária para o e-mail informado. No primeiro acesso a pessoa troca essa senha. O MFA segue opcional.

Isso só envia e-mail depois de um usuário IAM restrito ao user pool, com `cognito-idp:AdminCreateUser` e `cognito-idp:AdminGetUser`. O client público da tela não recebe essa permissão. As chaves ficam só na API:

```bash
heroku config:set --app NOME-API \
  COGNITO_ADMIN_ACCESS_KEY=CHAVE \
  COGNITO_ADMIN_SECRET_KEY=SEGREDO
```

Sem essas variáveis, a tela diz que o diretório de usuários não está configurado. O remetente é o padrão do Cognito, com o limite desse remetente. O bootstrap não altera uma membership que já existe e continua útil para o primeiro admin.

## Primeira empresa

O admin entra na sala, abre **Rotinas do razão** e depois **Nova empresa**. A barra de contexto, no topo, é o seletor da empresa. O cadastro pede nome, CNPJ e ano. A empresa nasce com matriz, o modelo mínimo de teste e 12 períodos abertos. Use CNPJ fictício: o dado fica nos Estados Unidos. Os lançamentos ficam em **Dados e ledger**. A caminhada da Orbe fica em **Demonstração** e não grava nada.

## Empresas de teste

Este comando não é o seed de demonstração. Pode ser repetido: o que já existe é preservado.

```bash
heroku run --no-tty --exit-code --app NOME-API -- python -m contabil.pilot_samples --tenant-id escritorio
```

Ele deixa cinco empresas fictícias, cada uma com um caso diferente:

- Padaria Aurora: lançamentos publicados, um estorno, um rascunho, um pendente e um aprovado ainda não publicado. O checklist fica bloqueado.
- Studio Norte: competência do mês anterior fechada, com snapshot, e um pedido de reabertura feito por outra pessoa.
- Comercial Vale Azul: livros publicados e conta bancária.
- Ateliê Brisa: plano, períodos e lançamentos publicados em alguns meses do ano, para o balancete ter saldo.
- Transportes Rio Claro: rascunho e lançamento pendente no mês corrente.

Com o bucket configurado, cada empresa ganha recibo, nota, contrato, um lote de diário em simulação e um extrato OFX. Sem o bucket, o comando imprime `extrato=skipped` e não grava arquivo.

## Conferência

- `GET /readyz` da API responde `ready`.
- A URL da interface abre a tela de entrada. Depois do Cognito, cai em `/app/rastro`.
- O navegador não mostra erro de CORS em `/v1/me`.
- O administrador cadastra uma empresa fictícia e ela aparece no seletor, com plano e períodos.
- O administrador entra, envia um OFX em Conciliação e vê um caso Sugerido. Sem bucket, esse passo fica para depois do storage.
- O usuário do outro escritório recebe 404 ao abrir um caso do primeiro.
- O seed de demonstração não aparece.
