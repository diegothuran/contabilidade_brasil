# Arquitetura inicial

## Decisão de partida

Começar com um **monólito modular** e workers assíncronos. O objetivo é provar o modelo contábil e o fechamento sem espalhar invariantes entre muitos serviços. Os módulos terão interfaces estáveis para permitir extração posterior quando volume, equipe ou isolamento justificarem.

## Componentes

```text
Web/API
  -> Identity & Tenancy
  -> Application Services
       -> Master Data
       -> Subledger Finance
       -> General Ledger
       -> Reconciliation
       -> Close & Compliance
       -> Documents & Evidence
       -> Regulatory Registry
       -> Integrations
  -> Audit/Event Outbox

Workers
  -> importação/migração
  -> conciliação
  -> cálculo/validação fiscal
  -> transmissão e polling
  -> notificações
  -> geração de export packages

Storage
  -> banco relacional transacional
  -> object storage para XML, PDFs, arquivos e evidências
  -> fila para jobs e DLQ
  -> analytics separado quando houver volume
```

PostgreSQL compatível é a escolha inicial natural para o ledger transacional. AlloyDB pode ser uma opção quando o ambiente GCP, a operação e a conectividade forem confirmados. A decisão do banco não deve alterar os contratos de domínio.

## Serviços implantáveis

O repositório é um monorepo com dois serviços, como no [ADR 016](adr/016-frontend-separado.md).

| Serviço | Pasta | Responsabilidade |
| --- | --- | --- |
| Interface | `apps/web` | Sala de fechamento e rotinas do razão. Build estático em nginx. Fala com a API por HTTPS com o token do usuário. |
| Domínio | `apps/api` | API, módulos de domínio, auditoria e ciclo do outbox. Único serviço que acessa o banco e o object storage. |

Schemas, configs e scripts de validação ficam na raiz e servem aos dois. A extração seguinte, se houver, continua sendo o pipeline de conectores e jobs fiscais.

## Regras de fronteira

O frontend nunca escreve diretamente no banco. Conectores nunca publicam journals sem passar por serviço de aplicação, validação e idempotência. O motor regulatório não altera dados contábeis sem uma operação versionada. Workers retomam jobs por `operation_id` e não repetem transmissão não idempotente sem reconciliação.

O object storage mantém o arquivo original, hash, tipo, versão, origem e política de retenção. O banco guarda metadados e referências. XML e certificados não devem circular em logs.

## Eventos e jobs

Toda operação longa retorna `operation_id`, status e `correlation_id`. O outbox publica eventos depois da transação. Consumidores são idempotentes. Cada conector possui retry com backoff, circuit breaker, deadline e dead-letter queue. Um job de reconciliação busca divergências entre o status local e o órgão ou parceiro.

## Segurança

O isolamento começa no backend por tenant, escritório, empresa e estabelecimento. RBAC define papéis. ABAC adiciona escopo de entidade, período, obrigação e operação. Preparar, revisar, aprovar e transmitir podem ser papéis diferentes. MFA é obrigatório para administradores e operações sensíveis quando o provedor de identidade estiver escolhido.

Auditoria registra antes/depois quando aplicável, ator, serviço, timestamp, motivo, aprovação, regra, versão, hash, protocolo e resultado. Logs técnicos usam referências pseudonimizadas e nunca devem registrar tokens, chaves, senhas ou payloads completos por padrão.

## IA como módulo de assistência

A IA recebe contexto mínimo e dados já autorizados. Pode sugerir classificação, correspondência, explicação, resumo de pendências e consulta. Toda sugestão inclui evidência, confiança, versão do prompt/modelo e estado de aprovação. A aplicação valida a sugestão. A IA não publica journal, paga título, altera regra, manipula certificado nem transmite obrigação de forma autônoma.

## Escala posterior

O primeiro candidato à extração é o pipeline de conectores e jobs fiscais. O ledger e o serviço de fechamento só devem ser separados quando houver necessidade comprovada de escala ou isolamento. A API, os eventos de domínio e os schemas são as fronteiras de evolução.
