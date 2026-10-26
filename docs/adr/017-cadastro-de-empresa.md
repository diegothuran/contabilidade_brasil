# ADR 017 — Cadastro de empresa pelo admin

**Status:** proposed · **Data:** 25 de outubro de 2026

## Contexto

O piloto do [ADR 015](015-piloto-barato-heroku.md) sobe sem seed. O escritório existia, mas a API só listava empresas. Sem cadastro, a interface caía na sala de demonstração e o razão, os documentos e a conciliação ficavam sem empresa.

O plano de contas real ainda é decisão do contador. Um modelo mínimo já existe no seed local e basta para lançar, ver balancete e conciliar.

## Decisão

Só o papel `admin` cadastra empresa, por `POST /v1/legal-entities`, com idempotency key.

- O corpo traz nome, CNPJ e ano. A moeda é BRL. O CNPJ é normalizado para 14 dígitos, com os dois dígitos verificadores conferidos. O par escritório e CNPJ é único.
- A mesma transação cria a matriz, o plano "Modelo mínimo de teste (não referencial)" com as 11 contas do seed e os 12 períodos abertos do ano informado. A auditoria registra `legal_entity_created`.
- O papel `contabil_app` passa a poder inserir em `legal_entities`, `establishments` e `charts_of_accounts`. No piloto a credencial dona continua sujeita ao RLS.
- Empresas fictícias de teste nascem do comando `python -m contabil.pilot_samples`, que não é o seed de demonstração. Ele pode ser repetido. Sem `OBJECT_STORAGE_BUCKET`, o comando não grava extrato.

## Consequências

O admin cadastra pela tela e o seletor passa a ter empresa. Quem não é admin pede o cadastro. O modelo mínimo não é plano referencial e não substitui a decisão do contador. Documento de cliente real continua fora deste ambiente.
