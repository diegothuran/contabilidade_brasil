# Plano de implementação e POCs

Este é o plano de descoberta original, com os cards de avaliação. O andamento das fases construídas está no [Anchor 4](specs/04-implementation-plan.md). Ledger, migração, conciliação, fechamento e o primeiro corte do portal (CARD-POC-004) já rodam no piloto com dados fictícios.

## Fase 0 — descoberta e avaliação de ferramentas

Definir ICP, dois ou três estados, competências de teste, papéis, fontes de dados e obrigações. Avaliar banco relacional, object storage, fila, identidade, observabilidade, OCR, provedor de documentos e alternativas de conector fiscal. A avaliação deve considerar contrato, versionamento, limites, custo, exportação, SLA e capacidade de teste, não apenas demonstração comercial.

## Fase 1 — fundação contábil

Implementar tenancy, legal entities, plano de contas, períodos, journals, linhas, balanço, aprovação, publicação, reversão, relatórios básicos e auditoria. Os dados devem ser sintéticos ou anonimizados.

## Fase 2 — migração, documentos e conciliação

Adicionar import batch com dry-run, idempotência e relatório de diferença. Adicionar object storage, documentos originais, hash, contas a pagar/receber, OFX/CSV e reconciliação manual e assistida com aprovação.

## Fase 3 — fechamento e portal

Implementar calendário, checklist, pendências, tarefas, solicitações ao cliente, lock, reabertura, snapshot e pacote de evidências. O portal deve mostrar impacto da pendência na competência.

## Fase 4 — piloto fiscal limitado

Escolher uma matriz pequena de NF-e, XML recebido e uma obrigação contábil em localidades definidas. Implementar registry de regras, validação, fila, protocolo, rejeição, polling, idempotência e exportação. Só ampliar cobertura depois de medir manutenção e suporte.

## Fase 5 — API e escala controlada

Publicar API versionada, OAuth/OIDC quando a identidade estiver decidida, webhooks assinados, sandbox, quotas, idempotency key, OpenAPI, logs de integração e exportação completa. Executar restore, teste de carga e exercícios de contingência.

## Cards de levantamento e avaliação

### CARD-TOOL-001 — avaliar banco e storage

**Problema:** ledger e evidências precisam de transação, retenção, busca e exportação. **Ação:** comparar PostgreSQL gerenciado, AlloyDB quando GCP for confirmado, object storage e política de backup. **Pronto:** decisão registra latência, custo, restore, retenção, isolamento e exportação. **Impacto:** backend, segurança, DevOps e suporte.

### CARD-TOOL-002 — avaliar fila e workflow

**Problema:** importação, fechamento e transmissão são assíncronos. **Ação:** comparar fila gerenciada, scheduler, DLQ e mecanismo de workflow. **Pronto:** uma operação pode pausar, retomar, deduplicar e ser reconciliada. **Impacto:** integrações, SRE e produto.

### CARD-TOOL-003 — avaliar documentos e OCR

**Problema:** PDFs, XML e anexos chegam em formatos diferentes. **Ação:** comparar storage, parser, OCR e classificação. **Pronto:** documento original preservado, hash calculado, classificação explicável e erro revisável. **Impacto:** fiscal, portal, privacidade e custo.

### CARD-TOOL-004 — avaliar conector fiscal piloto

**Problema:** nenhum fornecedor deve ser aceito como “cobertura nacional” sem matriz verificável. **Ação:** avaliar um provedor e um adaptador próprio em duas UFs. **Pronto:** contrato documenta versões, órgãos, certificado, status, retry, protocolo, limites, SLA e saída. **Impacto:** fiscal, compliance, suporte e vendas.

### CARD-POC-001 — ledger e fechamento

**Problema:** validar o núcleo contábil antes de construir ERP amplo. **Ação:** publicar journals sintéticos, fechar período, tentar alteração, reabrir com aprovação e gerar pacote de evidências. **Pronto:** invariantes passam, versão original permanece e o contador reconhece o fluxo. **Impacto:** produto, QA e contábil.

### CARD-POC-002 — migração round-trip

**Problema:** troca de sistema é risco de negócio. **Ação:** importar plano, saldos e lançamentos anonimizados, reconciliar e exportar. **Pronto:** diferenças explicadas, reprocessamento idempotente e exportação sem perda dos IDs externos. **Impacto:** onboarding, suporte e vendas.

### CARD-POC-003 — conciliação explicável

**Problema:** matching automático pode gerar erro silencioso. **Ação:** testar 1:1, 1:N, N:1, parcial, taxa, juros, estorno e exceção. **Pronto:** cada sugestão mostra regra e candidato; publicação exige aprovação. **Impacto:** financeiro, IA e QA.

### CARD-POC-004 — portal de pendências

**Problema:** documentos faltantes interrompem fechamento. **Ação:** criar solicitação, prazo, responsável, upload, comentário, confirmação e impacto na competência. **Pronto:** cinco clientes conseguem resolver uma competência sem planilha paralela. **Impacto:** portal, suporte e experiência do cliente.

### CARD-POC-005 — obrigação fiscal limitada

**Problema:** transmissão fiscal envolve versões, órgãos e rejeições. **Ação:** implementar um fluxo em homologação com arquivo, validação, assinatura aprovada, envio, retorno, retry e protocolo. **Pronto:** rejeição e retificação têm estados e evidências; nenhum envio duplica. **Impacto:** fiscal, segurança e SRE.

### CARD-POC-006 — assistência de IA

**Problema:** classificação e explicação consomem tempo, mas automação pode gerar risco. **Ação:** sugerir categoria ou match usando dados autorizados e evidências. **Pronto:** contador vê fonte, confiança, versão e aprova; sugestão não altera livro sozinha. **Impacto:** IA, contábil, privacidade e auditoria.

## Go/no-go do MVP

Avançar para piloto somente se o contador aprovar o fluxo de fechamento, a migração produzir reconciliação, o ledger preservar invariantes, a operação tiver isolamento por tenant, a exportação for testada e a cobertura fiscal estiver explicitamente limitada. Não avançar apenas porque a interface parece completa.
