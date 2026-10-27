# ADR 020 — Fechamento com checklist, snapshot e pacote de evidências

**Status:** proposed · **Data:** 27 de outubro de 2026

## Contexto

Fechar a competência só travava o período. O contrato de `CloseRun` já pedia checklist, bloqueios, snapshot e pacote, mas não havia tabela nem rota. A ITG 2000 (R1), itens 31 a 36, só admite correção por estorno, transferência ou complementação, com histórico do motivo, da data e do lançamento original. O art. 1.194 do Código Civil, o art. 195, parágrafo único, do CTN e o art. 37 da Lei 9.430/1996 exigem guardar a escrituração e os comprovantes até a prescrição ou a decadência. O Decreto 10.278/2020, arts. 10 e 11, pede integridade e preservação, mas trata de digitalização. A ECD autenticada só é substituída quando o erro não cabe em lançamento extemporâneo (IN RFB 2.003/2021, art. 8º).

## Decisão

A competência fecha por uma execução de fechamento.

- O checklist v1 é fixo, versão `2026.10-1`. Itens calculados são reavaliados na leitura e de novo ao fechar. Bloqueio pendente responde 409. Não aplicável exige motivo de pelo menos 10 caracteres, decidido por `approver` ou `admin`.
- A revisão do balancete é o único item manual bloqueante. Rascunho e documentos não bloqueiam.
- O período continua aberto a lançamentos enquanto a execução está aberta. O estado `closing` permanece no banco e não é usado.
- Ao fechar, a API grava um snapshot JSON no Postgres com SHA-256. Trigger impede UPDATE e DELETE. A reabertura não altera o snapshot: a execução fechada passa a `reopened` e a seguinte nasce com outro número.
- O pacote é JSON gerado no download, com manifesto, hash e o snapshot. Ele não declara livro autenticado nem assinatura ICP-Brasil. O download registra `document_exported`.
- `POST /v1/periods/{id}/close` usa a mesma regra e exige execução aberta sem bloqueio.

## Consequências

Fechamentos mostra o checklist, o hash e o download. Contas a pagar, checklist editável, obrigações e assinatura digital ficam fora. O prazo de guarda por tipo de documento continua pergunta para o contador.
