# ADR 026 — Devolução, vários arquivos e conversa no pedido

**Status:** proposed · **Data:** 27 de outubro de 2026

Decisão provisória. O contador ainda não confirmou quem pode devolver, se dez arquivos bastam e se a conversa entra no pacote. As perguntas estão no caderno.

## Contexto

O pedido aceita um arquivo e, depois de recebido, só segue para confirmado ou cancelado ([ADR 021](021-pedido-de-documento.md)). O cliente não tem como corrigir um arquivo que o escritório não aceitou, nem explicar o que enviou.

## Decisão

`approver` ou `admin` devolve o pedido recebido, com motivo de pelo menos 10 caracteres. O pedido volta para `open`. Os arquivos ativos passam a `returned` e guardam o motivo. Nada é apagado. A auditoria registra `document_request_returned`.

O envio vale em `open`, que passa a `received`, e em `received`, que continua `received`. O teto é de 10 arquivos ativos. Confirmar exige ao menos um arquivo ativo. `document_id` continua apontando para o último arquivo, para o checklist e a exportação atuais.

O cliente e o escritório comentam no pedido aberto ou recebido. O texto tem até 1000 caracteres, não se edita e não se apaga. A auditoria guarda o identificador do comentário, não o texto. O texto não entra em log.

O pacote `operational_v1` não muda neste corte.

## Consequências

O cliente vê o arquivo devolvido riscado, com o motivo, e envia outro. O escritório confirma só quando há arquivo ativo. Quem devolve, o teto de arquivos e a presença da conversa no pacote continuam perguntas do contador.
