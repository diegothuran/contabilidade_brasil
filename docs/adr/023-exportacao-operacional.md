# ADR 023 — Exportação operacional da competência

**Status:** proposed · **Data:** 27 de outubro de 2026

## Contexto

O pacote baixado no fechamento é o snapshot da execução. Não há uma exportação da competência enquanto ela ainda está aberta, nem um formato estável para levar lançamentos, documentos, pedidos e auditoria para outro ambiente. A lista de jobs assíncronos só existia pedido a pedido.

## Decisão

`preparer`, `approver` ou `admin` pede a exportação da empresa e da competência da barra, em Evidências. `viewer` consulta o resultado, mas não dispara outra exportação. O cliente da empresa não exporta o razão.

O pedido cria uma operação `operational_export` e um evento no outbox. O worker monta o pacote `operational_v1` e grava o JSON com SHA-256. A tela acompanha só essa operação e mostra os estados em texto: em fila, gerando, pronto, falhou. Não há uma tela de lista de operações.

`GET /v1/operations` lista as operações do escritório, com filtro por tipo, estado e correlation id. Isso fica na API. A interface não presume essa lista.

O pacote reúne, com teto de volume do piloto:

- lançamentos publicados ou revertidos da competência, como referência;
- documentos da competência, com nome, tipo e hash, sem o arquivo e sem a referência interna de armazenamento;
- pedidos de documento da competência;
- eventos de auditoria ligados a esses objetos ou à competência;
- totais do balancete.

O manifesto declara a versão, a data, o hash e o aviso de que o pacote não é livro autenticado e não tem assinatura ICP-Brasil. Não entram certificado, senha, configuração de identidade, recibo fiscal nem arquivo transmitido a órgão. A mesma Idempotency-Key devolve o mesmo pedido. Outra chave gera outra exportação.

A API permanece em `/v1`. Webhook fica fora até haver decisão própria de assinatura, replay e retry.

## Consequências

Evidências deixa de tratar exportação como ação demonstrativa. O hash permite conferir o JSON sem abrir o storage. Um escritório não lê a exportação de outro.
