# Anchor 2 — Requirements

## Requisitos funcionais

**REQ-001 — Tenancy.** O sistema deve separar escritório, usuário, empresa, filial e estabelecimento em toda operação sensível.

**REQ-002 — Importação.** O sistema deve receber arquivos, preservar origem e hash, executar dry-run, apontar erros e duplicidades e publicar somente após reconciliação aprovada.

**REQ-003 — Ledger.** O sistema deve criar, aprovar, publicar, consultar e reverter journals de partidas dobradas, com conta, entidade, período, moeda, dimensões e documento de origem.

**REQ-004 — Período.** O sistema deve controlar período aberto, em fechamento, fechado e reaberto. A reabertura exige motivo, papel, aprovação e auditoria.

**REQ-005 — Subledger.** O sistema deve representar contas a pagar/receber e movimentações bancárias com vínculo ao ledger.

**REQ-006 — Conciliação.** O sistema deve importar OFX/CSV, sugerir candidatos, explicar a sugestão, suportar parcial e reversão e exigir aprovação humana.

**REQ-007 — Fechamento.** O sistema deve executar checklist, pendências, aprovação, snapshot e pacote de evidências.

**REQ-008 — Documentos.** O sistema deve guardar o original, hash, proveniência, versões derivadas, retenção e vínculo com competência e entidade.

**REQ-009 — Regulatório.** O sistema deve manter obrigação, versão, jurisdição, vigência, status, dependências, arquivo, protocolo e recibo.

**REQ-010 — Integrações.** O sistema deve suportar idempotência, operações assíncronas, retry limitado, dead-letter e reconciliação de status.

**REQ-011 — Auditoria.** Ações contábeis, exportação, permissão, reabertura, baixa, certificado e transmissão devem produzir evento auditável.

**REQ-012 — Assistência.** A IA pode sugerir classificação, match, explicação e resumo, sempre com evidência e aprovação; não publica nem transmite sozinha.

## Requisitos não funcionais

**NFR-001 — Decimal.** Valores monetários não usam float.

**NFR-002 — Isolamento.** Testes negativos cross-tenant são obrigatórios.

**NFR-003 — Portabilidade.** O cliente deve exportar dados operacionais, documentos, configurações, recibos e auditoria em formato documentado.

**NFR-004 — Privacidade.** Logs e prompts minimizam dados pessoais e não registram segredos.

**NFR-005 — Reprodutibilidade.** Regras regulatórias, schemas, prompts, versões e arquivos de transmissão são identificáveis.

**NFR-006 — Resiliência.** Uma indisponibilidade externa não corrompe o ledger nem afirma aceite sem protocolo.

**NFR-007 — Operação.** Cada operação assíncrona possui `operation_id` e `correlation_id`.

## Cenários de aceitação

### Journal desequilibrado

**Dado** um journal com débitos e créditos diferentes, **quando** o usuário tenta publicar, **então** o sistema rejeita e não altera o saldo.

### Reabertura

**Dado** um período fechado, **quando** um usuário sem aprovação tenta editar, **então** a operação é negada; com aprovação, cria evento, motivo e novo fluxo.

### Importação

**Dado** um lote com duplicidade e diferença de saldo, **quando** roda o dry-run, **então** o lote permanece não publicado e mostra erros por linha e reconciliação.

### Conciliação

**Dado** uma transação bancária e candidatos, **quando** o sistema sugere um match, **então** exibe campos, regra, score e exige aprovação para gerar efeito.

### Obrigação rejeitada

**Dado** um retorno de rejeição, **quando** o órgão responde, **então** a obrigação permanece rejeitada, mantém arquivo/protocolo/retorno e mostra próxima ação.

### Tenant inválido

**Dado** um usuário de um escritório, **quando** tenta acessar documento de outro, **então** o backend nega sem revelar sua existência.
