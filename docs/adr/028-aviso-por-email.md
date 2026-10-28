# ADR 028 — Aviso por e-mail ao cliente

**Status:** proposed · **Data:** 27 de outubro de 2026

Decisão provisória. A antecedência de três dias ainda é pergunta do contador.

## Contexto

O cliente só fica sabendo de um pedido se entrar no portal. O escritório não tem lembrete.

## Decisão

O aviso sai pelo Amazon SES em `us-east-2`, por um adaptador. Sem remetente ou sem chave, o adaptador registra que o e-mail não está configurado e a operação de negócio segue.

O destinatário é lido no Cognito na hora do envio. O banco não guarda e-mail. O texto leva o título, o prazo e o link do portal. Não leva CNPJ, nome de arquivo nem texto de comentário.

O pedido novo e a devolução entram no outbox. O ciclo do worker também avisa três dias antes do prazo e uma vez depois do vencimento. A tabela `notification_log`, com chave única por pedido, tipo e data, impede o aviso duplicado. Há retry limitado e dead-letter.

O cliente desliga os avisos no portal. A escolha fica em `memberships.notify_client`.

## Consequências

No SES em sandbox, cada endereço de destino precisa estar verificado. As variáveis `MAIL_FROM`, `SES_ACCESS_KEY`, `SES_SECRET_KEY` e `PORTAL_BASE_URL` ficam só na API.
