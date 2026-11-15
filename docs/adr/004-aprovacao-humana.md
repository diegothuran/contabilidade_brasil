# ADR 004 — Efeitos contábeis e fiscais exigem aprovação

**Status:** proposed · **Data:** 11 de outubro de 2026

## Contexto

Sugestões de IA e automações podem errar classificação, match, cálculo ou transmissão. O impacto de um erro contábil ou fiscal é maior que o benefício de remover toda revisão.

## Decisão

IA pode sugerir, explicar e preparar. Publicação de journal, aprovação de conciliação, reabertura, uso de certificado e transmissão exigem workflow e ator autorizado.

**Atualização de 15/11/2026 ([ADR 035](035-sugestao-de-conta-por-modelo.md)):** a contrapartida de um caso de conciliação passa a ter duas fontes de sugestão: `history` (contas usadas antes na mesma empresa) e `model` (Claude Haiku 5.5, com descrição pseudonimizada e só para dados fictícios do piloto). As duas são sempre sugestão. A tela pré-seleciona a conta e diz "sugerido". A pessoa confirma com o botão que já existe, e o journal segue envio, aprovação e publicação. A resposta do modelo é validada contra o plano da empresa e nunca cria journal, aprova caso ou muda conta. A auditoria registra a origem da conta escolhida (`history`, `model` ou `manual`).

## Consequências

O sistema precisa mostrar evidências e pendências. O MVP não mede sucesso por automação total, mas por redução de tempo sem perda de controle.
