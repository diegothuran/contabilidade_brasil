# ADR 006 — Integrações por adaptadores idempotentes

**Status:** proposed · **Data:** 11 de outubro de 2026

## Contexto

Órgãos, bancos e parceiros possuem APIs, arquivos, versões e erros diferentes. Uma falha de rede não pode gerar duplicidade ou afirmar entrega sem protocolo.

## Decisão

Cada integração implementa contrato de adapter, idempotency key, estados, retry limitado, dead-letter, polling e reconciliação. O core não depende da forma técnica do fornecedor.

## Consequências

Trocar provedor é possível e o estado fica observável. Cada adaptador exige manutenção, homologação e documentação de cobertura.
