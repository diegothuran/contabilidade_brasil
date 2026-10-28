# Anchor 6 — Discovery e POC backlog

## P0 — provar o núcleo

**DISC-001 — Definir “fechamento pronto”.** Levantar passos, responsáveis, pendências, relatórios e evidências de uma competência. Dependência: contador parceiro. Pronto: mapa assinado pelo contador.

**POC-001 — Ledger.** Publicar, consultar, reverter e fechar dados sintéticos. Pronto: invariantes e drill-down passam.

**POC-002 — Migração.** Importar arquivos anonimizados, executar dry-run e reconciliar. Pronto: diferença explicada e reprocessamento idempotente.

**POC-003 — Conciliação.** Testar casos 1:1, 1:N, N:1, parcial e estorno. Pronto: score e explicação revisáveis.

## P1 — provar a operação do escritório

**DISC-002 — Selecionar estados e obrigações.** Escolher recorte de piloto e responsabilidade por homologação. Pronto: matriz com obrigação, localidade, regime, versão e cobertura. A conversa segue a Sessão 2 do [roteiro de entrevista](../roteiro-entrevista-contador.md), com as perguntas 34 a 48 do [caderno do contador](../accountant-discovery-workbook.md#perguntas-da-fase-e). A matriz tem uma linha por obrigação citada:

| Obrigação | Órgão | Localidade | Regimes | Versão do leiaute | Ambiente de teste | Parceiro | Classificação |
|---|---|---|---|---|---|---|---|
| a preencher com o contador | | | | | | | indispensável / útil depois / parceiro / fora |

A linha marcada como obrigação do piloto (pergunta 38) abre o card do POC-007.

**POC-004 — Portal de pendências.** Enviar, receber e aprovar documentos por competência. O cliente da empresa envia o arquivo do próprio pedido; o escritório confirma ([ADR 025](../adr/025-portal-do-cliente.md)). Pronto: cliente e contador resolvem cinco casos.

**POC-006 — Exportação.** Exportar ledger, documentos, configurações, recibos e auditoria. O corte atual exporta a competência em JSON com hash ([ADR 023](../adr/023-exportacao-operacional.md)). Pronto: outro ambiente consegue ler o pacote.

**POC-005 — Fechamento.** Executar checklist, lock, reabertura e pacote de evidências. Pronto: auditoria e snapshot são reproduzíveis.

## P2 — provar o regulatório

**POC-007 — Adapter fiscal homologado.** Escolher um fluxo e um parceiro ou integração direta. Pronto: validação, fila, retorno, rejeição, protocolo e retificação.

**POC-008 — Certificado e procuração.** Testar cofre, escopo, uso e revogação sem expor segredo. Pronto: operação é auditável e limitada.

## P3 — provar diferenciação

**POC-009 — IA assistiva.** Sugerir classificação, match ou resumo com evidências. Pronto: aprovação humana e taxa de correção medida.

**POC-010 — Matriz de cobertura.** Publicar capacidade por UF, município, versão, edição e parceiro. Pronto: contador encontra cobertura e limitação rapidamente.

## Card template

Cada card precisa conter: problema observado; evidência ou hipótese; usuário afetado; entrada; comportamento esperado; critérios de aceite; dados de teste; risco; dependências; impacto em outras squads; e decisão após a POC.

## Go/no-go

Não avançar para um ERP amplo porque uma POC de tela funcionou. Avançar quando o contador confirmar que o fluxo reduz tempo ou risco, a contabilidade permanece reconciliável, o cliente consegue fornecer dados e a operação suporta falha externa sem perder evidência.
