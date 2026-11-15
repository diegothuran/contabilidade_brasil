# ADR 034 — Resumo do mês publicado para o cliente

**Status:** accepted · **Data:** 15 de novembro de 2026

O empresário que entra no portal ([ADR 025](025-portal-do-cliente.md)) não lê balancete. O escritório precisa de uma forma de mostrar, depois do fechamento, o que aconteceu no mês em poucas frases, sem abrir o razão e sem prometer mais do que o fechamento garante.

## Decisão

**Sem IA.** O resumo é calculado do razão fechado por uma função pura (`client_summaries/compose.py`). Nenhum modelo de linguagem escreve ou reescreve o texto.

**Frases fixas.** São quatro, nesta ordem: o que a empresa faturou e gastou; lucro ou prejuízo; quanto sobrou ou faltou de cada R$ 100 faturados (ou a frase de que não houve faturamento); e o saldo das contas bancárias no fim do mês. Receita e despesa vêm da DRE do mês; o caixa soma as contas bancárias cadastradas da empresa até o fim da competência. Os valores em formato brasileiro só aparecem dentro das frases; o payload guarda strings decimais.

**Quatro olhos.** `preparer`, `approver` e `admin` geram o rascunho; só `approver` e `admin` publicam, e quem gerou não publica (409). Retirar exige `approver` ou `admin` e um motivo de 10 caracteres ou mais. Gerar, publicar e retirar entram na auditoria.

**Só competência fechada.** Gerar numa competência aberta responde 409. Um rascunho pode ser recalculado; um resumo publicado precisa ser retirado antes de gerar outro. Há no máximo um resumo não retirado por competência (`uq_client_summaries_period`).

**Retirada na reabertura.** Quando a reabertura é aprovada, o resumo publicado vira `withdrawn` com o motivo "Competência reaberta", na mesma transação, mesmo se a competência fechada não tiver execução de fechamento. O portal deixa de mostrá-lo.

**Payload imutável.** A tabela `client_summaries` (migração `0022_client_summaries`, RLS forçada) tem um trigger que recusa mudar o `payload` quando o resumo já não é rascunho e recusa `DELETE`.

**Portal.** O cliente lê só resumos `published` da própria empresa (`GET /v1/portal/summaries` e `/{summary_id}`). Rascunho, retirado ou de outra empresa responde 404. O cliente não gera, não publica e não retira.

## Consequências

- O texto do resumo é previsível e auditável, mas não explica causas. Isso fica com o contador.
- O caixa depende de a empresa ter conta bancária cadastrada; sem ela, o resumo mostra R$ 0,00.
- Corrigir um número exige reabrir a competência, o que retira o resumo e obriga a gerar e publicar de novo.
