# Schemas — plataforma contábil

| Arquivo | Contrato |
| --- | --- |
| `journal-entry.schema.json` | Journal, linhas, origem, estado e publicação. |
| `import-batch.schema.json` | Dry-run, arquivos, linhas, totais e diferença. |
| `reconciliation-case.schema.json` | Transação bancária, candidatos, score e aprovação. |
| `close-run.schema.json` | Competência, checklist, bloqueios, snapshot e evidência. |
| `source-document.schema.json` | Documento original, hash, proveniência e retenção. |
| `document-request.schema.json` | Pedido de documento da competência, arquivo ligado e confirmação. |
| `export-package.schema.json` | Pacote `operational_v1` da competência, com listas limitadas e SHA-256. |
| `regulatory-obligation.schema.json` | Obrigação, jurisdição, competência, versão, transmissão e cobertura. |
| `audit-event.schema.json` | Ações sensíveis, ator, alvo, motivo e integridade. |
| `ai-review.schema.json` | Revisão do mês por IA: estado, modelo, pontos com evidência e a decisão vigente de cada ponto ([ADR 036](../docs/adr/036-revisao-do-mes-por-ia.md)). |
| `openapi.yaml` | API inicial do produto. |

Os schemas descrevem contratos canônicos, não o schema físico do banco. Mudanças incompatíveis exigem nova versão e migração documentada.
