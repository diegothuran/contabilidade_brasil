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

A API sai pelo [heroku.yml](../../heroku.yml) da raiz. O release chama `/app/bin/migrate.sh`, um único executável, porque a Heroku não repassa `python -m contabil.migrate` inteiro. A imagem inclui `curl` para essa fase registrar o log.

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

O `--user-id` é o `cognito:username` (em geral o e-mail ou o `sub`, o que o token trouxer nesse claim). O bootstrap e o convite gravam esse nome em minúsculas, como o user pool do piloto devolve no token.

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

O primeiro admin continua no bootstrap acima. As pessoas seguintes nascem em **Administração**, com o admin logado. O cliente de uma empresa também nasce aqui, com o papel Cliente sozinho e a empresa escolhida. O Cognito envia a senha temporária para o e-mail informado. No primeiro acesso a pessoa troca essa senha. O MFA segue opcional.

Isso só envia e-mail depois de um usuário IAM restrito ao user pool, com `cognito-idp:AdminCreateUser` e `cognito-idp:AdminGetUser`. O client público da tela não recebe essa permissão. As chaves ficam só na API:

```bash
heroku config:set --app NOME-API \
  COGNITO_ADMIN_ACCESS_KEY=CHAVE \
  COGNITO_ADMIN_SECRET_KEY=SEGREDO
```

Sem essas variáveis, a tela diz que o diretório de usuários não está configurado. O remetente é o padrão do Cognito, com o limite desse remetente. O bootstrap não altera uma membership que já existe e continua útil para o primeiro admin.

## Aviso ao cliente

O aviso ao cliente usa o SES na mesma região ([ADR 028](../../docs/adr/028-aviso-por-email.md)). Sem `MAIL_FROM`, `SES_ACCESS_KEY` e `SES_SECRET_KEY`, o pedido segue, nenhum e-mail sai e o log da API registra `notice skipped`. Nada avisa na tela, então confira as variáveis antes de uma rodada com clientes. `PORTAL_BASE_URL` é o endereço da interface, o único link que o aviso carrega. O banco não guarda o e-mail: ele é lido no Cognito na hora do envio, com a mesma chave do convite. O cliente desliga o aviso no próprio portal.

Para ligar:

1. No SES em `us-east-2`, verifique o remetente, um endereço ou um domínio.
2. Enquanto a conta estiver em sandbox, verifique também o e-mail de cada cliente de teste. Endereço não verificado não recebe.
3. Crie um usuário IAM só com `ses:SendEmail` e `ses:SendRawEmail`, restrito à identidade do remetente, e gere a chave de acesso.
4. Grave as variáveis na API. Os valores não entram no repositório nem no chat.

```bash
heroku config:set --app NOME-API   MAIL_FROM=REMETENTE   SES_ACCESS_KEY=CHAVE   SES_SECRET_KEY=SEGREDO   PORTAL_BASE_URL=URL-DA-INTERFACE
```

O pedido novo e a devolução saem pelo outbox logo depois. O lembrete de três dias antes e o de depois do vencimento saem no ciclo de hora em hora do worker, na data de Brasília. Cada aviso fica uma vez em `notification_log`; se essa tabela fica vazia depois de um pedido novo para um cliente verificado, o envio falhou.

## Primeira empresa

O admin entra na sala, abre **Rotinas do razão** e depois **Nova empresa**. A barra de contexto, no topo, é o seletor da empresa. O cadastro pede nome, CNPJ e ano. A empresa nasce com matriz, o modelo mínimo de teste e 12 períodos abertos. Use CNPJ fictício: o dado fica nos Estados Unidos. Os lançamentos ficam em **Dados e ledger**. A caminhada da Orbe fica em **Demonstração** e não grava nada.

## Empresas de teste

Este comando não é o seed de demonstração. Pode ser repetido: o que já existe é preservado.

```bash
heroku run --no-tty --exit-code --app NOME-API -- python -m contabil.pilot_samples --tenant-id escritorio
```

Ele deixa cinco empresas fictícias, cada uma com um caso diferente:

- Padaria Aurora: lançamentos publicados da padaria, um estorno, um rascunho, um pendente e um aprovado ainda não publicado. O checklist fica bloqueado.
- Studio Norte: competência do mês anterior fechada, com snapshot, e um pedido de reabertura feito por outra pessoa. Os outros meses abertos têm o movimento do estúdio.
- Comercial Vale Azul: livros da loja e conta bancária.
- Ateliê Brisa: plano, períodos e encomendas publicadas em alguns meses do ano.
- Transportes Rio Claro: fretes publicados, mais um rascunho e um lançamento pendente no mês corrente.

O movimento copiado igual em todas as empresas é estornado quando o período ainda está aberto, e no lugar entra o lançamento do ramo. Com o bucket configurado, cada empresa ganha recibo, nota, contrato, um arquivo com o nome do ramo, um lote de diário em simulação e um extrato OFX. A Padaria Aurora também fica com um pedido de recibo já confirmado em outubro de 2026. O Ateliê Brisa fica com um pedido de contrato aberto nessa competência, com prazo em 31/10, e o fechamento de outubro permanece bloqueado até confirmar ou cancelar. O Studio Norte (extrato), o Comercial Vale Azul (nota) e a Transportes Rio Claro (recibo de frete) ficam com pedidos abertos com prazo em 20/10, para a fila ter itens vencidos. Sem o bucket, o comando imprime `extrato=skipped` e não grava arquivo; os pedidos abertos ainda são criados.

O segundo escritório fictício é o Litoral. O comando cria o escritório, copia os administradores do escritório de origem e carrega outra carteira: Pousada Maré Alta, Oficina Serra Dourada, Mercado Bom Preço, Clínica Verde Vale e Gráfica Norte Sul.

```bash
heroku run --no-tty --exit-code --app NOME-API -- python -m contabil.pilot_samples --tenant-id litoral --catalog litoral --copy-admins-from escritorio
```

O seletor da barra lateral só aparece para o administrador geral, que tem o papel admin no escritório do login e acesso a outro escritório. Um login ligado a um escritório só vê esse escritório. O cliente da empresa não vê o seletor. A troca não muda o atributo do login; ela só vale enquanto a sessão do navegador guarda o escritório escolhido.

Hoje mostra a fila de pedidos que bloqueiam o fechamento. Abrir um item troca a empresa e a competência da barra. Em Evidências, quem prepara gera a exportação da competência e baixa o JSON quando o estado fica pronto. A lista de operações fica na API, em `GET /v1/operations`.

Cada empresa de teste ganha um usuário `cliente-` seguido do nome interno da história (`andamento`, `fechada`, `banco`, `vazia` e `rascunhos`; no Litoral, `pousada`, `oficina`, `mercado`, `clinica` e `grafica`). Esse usuário existe no banco, ligado só àquela empresa, mas ainda não tem login. Para criar o login, o administrador convida o mesmo nome de usuário em Administração, com o papel Cliente, a mesma empresa e um e-mail de teste. A API reconhece o cliente que já existe, não duplica o acesso e manda o e-mail com a senha temporária. Convidar esse nome com outro papel ou outra empresa continua sendo recusado. O cliente envia o arquivo. Quem confirma continua sendo o escritório. Os cinco casos do escritório piloto são o recibo confirmado da Padaria, o extrato aberto do Studio, a nota aberta do Vale, o contrato aberto do Ateliê e o recibo de frete aberto da Transportes.

Depois da rodada com os clientes, o relatório abaixo mostra o ciclo de cada pedido: quem enviou o arquivo, os dias até receber e até confirmar, se chegou no prazo, e um resumo. Ele só lê o banco e imprime no terminal, sem gravar arquivo. `--since AAAA-MM-DD` limita aos pedidos abertos a partir dessa data. O roteiro da rodada está no [caderno do contador](../../docs/accountant-discovery-workbook.md#rodada-da-fase-d).

```bash
heroku run --no-tty --exit-code --app NOME-API -- python -m contabil.pilot_report --tenant-id escritorio
```


## Conferência

- `GET /readyz` da API responde `ready`.
- A URL da interface abre a tela de entrada. Depois do Cognito, cai em `/app/rastro`.
- O navegador não mostra erro de CORS em `/v1/me`.
- O administrador cadastra uma empresa fictícia e ela aparece no seletor, com plano e períodos.
- Hoje lista a pendência que bloqueia o fechamento. Abrir o item troca a empresa e a competência.
- Em Evidências, a exportação da competência passa por em fila, gerando e pronto, e o JSON confere o SHA-256.
- Um cliente convidado para uma empresa vê o resumo, os pedidos em aberto, o histórico e a conversa. Envia arquivo, manda um documento sem pedido e não abre o razão. O escritório devolve, classifica ou confirma. A Transportes Rio Claro e a Gráfica Norte Sul ficam com uma nota devolvida e uma mensagem.
- O administrador entra, envia um OFX em Conciliação e vê um caso Sugerido. Sem bucket, esse passo fica para depois do storage.
- O usuário do outro escritório recebe 404 ao abrir um caso do primeiro.
- O seed de demonstração não aparece.
