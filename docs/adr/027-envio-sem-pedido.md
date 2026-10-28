# ADR 027 — Envio de documento sem pedido

**Status:** proposed · **Data:** 27 de outubro de 2026

Decisão provisória. O contador ainda não confirmou se o envio sem pedido pode virar pendência sozinho. A pergunta está no caderno.

## Contexto

O cliente só envia arquivo quando o escritório já abriu um pedido. Um documento que chega antes do pedido fica fora do sistema.

## Decisão

O cliente envia um arquivo com uma nota opcional de até 500 caracteres, sem pedido. Isso não bloqueia o fechamento. O original segue as evidências, com hash.

O escritório vê os envios novos. `preparer`, `approver` ou `admin` classifica: escolhe competência aberta, tipo, título e prazo. Nasce um pedido já `received`, com o arquivo ativo. Confirmar continua com `approver` ou `admin`. Descartar exige motivo de pelo menos 10 caracteres e preserva o original.

## Consequências

Hoje mostra quantos envios novos existem. O envio não vira pedido sozinho.
