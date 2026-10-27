# Modelo de domínio contábil

## Limites de contexto

O produto deve começar como monólito modular, mas com fronteiras claras. O contexto de identidade e tenancy controla escritório, usuários, empresas, filiais, estabelecimentos e permissões. Master data mantém plano de contas, referencial, pessoas, bancos, produtos, serviços, dimensões e códigos fiscais.

O subledger financeiro trata contas a pagar, contas a receber, bancos, caixa, cobranças, pagamentos e competência/caixa. O ledger geral publica journals, partidas, saldos, períodos, rateios, livros e demonstrações. O motor fiscal trata regras e cálculos. Conectores governamentais transmitem documentos e obrigações. Documents & Evidence preserva arquivos e retornos. Close & Compliance Workflow orquestra calendário, pendências, aprovação, fechamento, reabertura e retificação.

Portal, tarefas e solicitações ligam contador e cliente. A plataforma de integração expõe API, webhooks, importadores, exportadores e jobs. Analytics e observabilidade apresentam relatórios semânticos, saúde das filas, rejeições, certificados e trilhas.

## Entidades essenciais

`AccountingOffice`, `Tenant`, `User`, `Role`, `LegalEntity`, `Branch`, `Establishment`, `AccountingPeriod`, `FiscalYear`, `ChartOfAccounts`, `Account`, `ReferentialMapping`, `Dimension`, `CostCenter`, `Journal`, `JournalEntry`, `JournalLine`, `SourceDocument`, `ImportBatch`, `Receivable`, `Payable`, `BankTransaction`, `ReconciliationCase`, `FixedAsset`, `TaxContext`, `TaxRule`, `FiscalDocument`, `FiscalEvent`, `RegulatoryObligation`, `Transmission`, `Protocol`, `Receipt`, `Certificate`, `PowerOfAttorney`, `CloseRun`, `Approval`, `AuditEvent`, `RetentionPolicy` e `ExportPackage` são o vocabulário inicial. O schema físico ainda deve ser validado com o contador e com os dados de migração.

No piloto, o admin cadastra a `LegalEntity` com CNPJ único no escritório. Ela nasce com matriz, um modelo mínimo de contas que não é referencial e os períodos abertos do ano informado ([ADR 017](adr/017-cadastro-de-empresa.md)).

## Estados importantes

### Journal

```text
draft -> pending_approval -> approved -> published -> reversed
                         \-> rejected
```

A transição para `published` exige balanço, período aberto, conta postável, entidade válida, origem e autorização. `reversed` cria novo journal vinculado; não apaga o original.

### Período

```text
open -> closed -> reopened -> closed
```

O valor `closing` existe na restrição do banco e não é usado: a competência continua aceitando lançamento enquanto o checklist está aberto. Reabertura exige papel, motivo, aprovação e `AuditEvent`, e preserva o snapshot da execução anterior. O fechamento grava o snapshot. O pacote de evidências é gerado no download.

### Obrigação

```text
planned -> collecting -> ready -> validating -> transmitting
         -> accepted | rejected | pending_correction | rectified
```

Uma retificação não substitui silenciosamente a versão original. Ela referencia o arquivo, motivo, competência, regra e protocolo anteriores.

## Invariantes

1. Toda publicação de journal tem soma de débitos igual à soma de créditos.
2. Journal publicado é imutável; ajustes são novos journals relacionados.
3. Toda linha publicada tem entidade, período, conta, moeda, valor, origem e autor ou serviço.
4. Conta não postável não recebe lançamento.
5. Período fechado rejeita postagem normal.
6. Subledger e razão reconciliam por entidade, competência, moeda e lote.
7. Documento fiscal e evento externo são idempotentes por chave, CNPJ, ambiente e versão.
8. O arquivo original é preservado; normalizações são versões derivadas.
9. Credencial só opera no tenant, CNPJ, ambiente e procuração autorizados.
10. Exportação, reabertura, cancelamento, baixa, transmissão e alteração de permissão geram auditoria.

## Valores e identificadores

Valores monetários usam decimal, nunca float. Identificadores externos são preservados junto ao sistema de origem. Datas de competência e datas de transmissão são distintas. O fuso e o calendário devem ser configuráveis por entidade, com padrão brasileiro apenas quando aprovado.

## Papel do contador

O contador deve confirmar o significado operacional de “lançamento pronto”, “conciliação aceita”, “fechamento concluído”, “obrigação entregue” e “documento suficiente”. Esses termos não devem ser definidos apenas pela equipe técnica.
