# ADR 013 — Conciliação por casos, com aprovação humana

**Status:** proposed · **Data:** 12 de outubro de 2026

## Contexto

O extrato bancário precisa entrar como evidência e aparecer ao lado do razão, sem a aplicação decidir sozinha o que está conciliado. Contas a pagar, receber, match parcial e o checklist de fechamento ainda não têm regra do contador.

## Decisão

Cada transação nova de um extrato CSV ou OFX vira um caso. O matcher só sugere linhas publicadas da conta banco no razão, com score e explicação. Aprovar, por um usuário `approver` ou `admin`, cria `reconciliation_matches`. Reverter desativa o vínculo e não apaga a transação. O extrato é evidência: a transação bancária não aceita `UPDATE` nem `DELETE`.

Reimportar o mesmo movimento não cria outra transação. A identidade é o fingerprint: `bank_account_id` mais FITID, ou data, valor, direção e descrição normalizada quando não há FITID. A colisão sem FITID conta em `transactions_duplicate`.

Um lançamento criado a partir do caso nasce rascunho, com `source_type=bank`. Publicá-lo resolve o caso. A aprovação humana, neste corte, é a publicação. Journals de outra origem não mudam caso nenhum: o handler de `JournalPublished` só age quando a origem é `bank`.

O modo deste corte é 1:1. Tolerância de data, diferenças pequenas e quem aprova num escritório de uma pessoa continuam perguntas ao contador.

## Consequências

O worker segue com a conexão administrativa, então a RLS não se aplica a ele. O serviço filtra `tenant_id` e o trigger da transação continua valendo. Candidato fora da lista só entra se a linha for da mesma conta, no lado coerente, com o mesmo valor, publicada e sem vínculo ativo. Não há contas a pagar nem receber neste corte.
