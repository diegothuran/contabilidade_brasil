# ADR 016 — Interface como serviço próprio

**Status:** proposed · **Data:** 25 de outubro de 2026

## Contexto

A sala de fechamento (`apps/web/src/rastro/`) passou a ser a entrada do produto. No piloto do [ADR 015](015-piloto-barato-heroku.md), um dyno só servia a interface, a API e o ciclo do outbox. Cada mudança visual reconstruía a imagem da API e reiniciava o processo que publica eventos.

A Heroku publica HTTP apenas no processo `web` de cada app. Uma interface com endereço próprio exige um segundo app.

## Decisão

O repositório é um monorepo com dois serviços implantáveis.

| Serviço | Pasta | App no piloto | Conteúdo |
| --- | --- | --- | --- |
| Interface | `apps/web` | `contabilidade-brasil-web` | Build do Vite servido por nginx sem root. Não guarda segredo nem dado. |
| Domínio | `apps/api` | `contabilidade-brasil` | API, razão, conciliação, documentos, auditoria e ciclo do outbox, num processo só. |

- A interface é o único serviço extraído. Razão, conciliação, documentos e outbox continuam no monólito modular do [ADR 003](003-monolito-modular.md), porque separá-los criaria transação distribuída em volta de journal publicado.
- O navegador fala com duas origens. O login volta para a origem da interface. A interface manda o ID token do Cognito direto para a API. A API aceita só a origem da interface em `CORS_ORIGINS` e continua validando issuer, JWKS e audience.
- A URL da API, o grupo e o client do Cognito entram no build da interface por `apps/web/heroku.yml`. São valores públicos. Trocar qualquer um exige um build novo da interface.
- A API sobe pelo `heroku.yml` da raiz, com `git push heroku main`, e mantém a migração no release. A interface sobe com `git subtree push --prefix apps/web heroku-web main`: a Heroku recebe só essa pasta e monta a imagem. Não é preciso Docker na máquina de quem publica.
- `STATIC_DIR` deixa de existir no app da API. O suporte a ele continua no código, para quem quiser um processo só.
- O dyno da interface é Basic. Eco continua recusado.

## Consequências

Em preço público de outubro de 2026, a conta do piloto vai de cerca de US$ 12 para cerca de US$ 19 por mês: dois dynos Basic de US$ 7 e o Postgres Essential-0 de US$ 5.

Uma mudança só de tela não reinicia a API nem o outbox. Uma mudança de contrato exige publicar os dois apps, a API primeiro. O Cognito precisa ter o callback e o logout da origem da interface, com barra no final. O endereço da API deixa de mostrar tela.

A sala segue em demonstração enquanto `VITE_RASTRO_DEMO` não for `false`. As rotinas do razão em `/app/journals` e nas rotas vizinhas continuam no mesmo serviço de interface.

No compose local nada muda de forma: a interface já era um contêiner separado, agora construído só com a pasta `apps/web`.
