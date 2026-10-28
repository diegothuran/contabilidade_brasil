# ADR 024 — Fila de pendências do escritório

**Status:** proposed · **Data:** 27 de outubro de 2026

## Contexto

O pedido de documento já bloqueia o fechamento da competência ([ADR 021](021-pedido-de-documento.md)), mas a lista só aparece quando a barra está naquela empresa e naquela competência. Hoje mostra lançamentos recentes e não responde o que bloqueia o mês.

## Decisão

`GET /v1/document-requests/queue` lista os pedidos do escritório ativo, não de outro escritório. O escritório ativo continua o do token, ou o escolhido pelo administrador geral ([ADR 022](022-troca-de-escritorio.md)).

- Quem consulta é qualquer papel do escritório: `preparer`, `approver`, `admin` e `viewer`. O cliente da empresa não usa esta fila.
- O padrão é `open` e `received`. Os dois bloqueiam o fechamento. `confirmed` e `cancelled` não entram no padrão e não bloqueiam.
- A ordem é o prazo, do mais próximo para o mais distante. No mesmo prazo, `open` vem antes de `received`.
- Cada item traz empresa, CNPJ, competência em mês e ano, prazo, estado e `blocks_close`.
- Há filtro por estado, por prazo até uma data (inclusive) e por ano e mês juntos. A página usa cursor.
- Hoje mostra os primeiros itens desta fila e o próximo passo: abrir a pendência. O clique troca a empresa e a competência da sessão, e a barra passa a mostrar esse contexto. Não é uma troca silenciosa.
- Pendências mantém a lista da competência da barra e ganha a fila do escritório.

Não há responsável designado, comentário, e-mail nem lembrete. Isso continua fora até o contador decidir.

## Consequências

A home deixa de ser só uma lista de lançamentos. Um pedido confirmado ou cancelado some do padrão da fila e deixa de bloquear. A fila não atravessa escritório.
