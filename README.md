# contabilidade_brasil

Esta pasta define a base para construir uma plataforma contábil e de operação de escritórios no Brasil. Ela foi derivada do benchmark recebido e não tenta copiar literalmente nenhum concorrente.

## Tese inicial

O produto deve competir por **confiança operacional mensurável**. Cada saldo precisa ser explicado até a origem. Cada obrigação precisa ter versão, status, protocolo e responsável. Cada migração precisa ser reconciliável. Cada cliente deve conseguir sair com seus dados em formato útil.

O primeiro foco recomendado é um escritório contábil com aproximadamente **20–200 CNPJs**, em dois ou três estados e com um conjunto fiscal controlado. O produto deve coexistir com o legado durante a entrada, em vez de exigir uma troca completa no primeiro dia.

## Escopo da fundação

A base contempla:

- ledger de partidas dobradas, plano de contas, dimensões e períodos;
- importação e migração com dry-run e reconciliação;
- contas a pagar/receber e conciliação bancária explicável;
- fechamento com checklist, aprovação, lock e reabertura auditável;
- documentos, evidências, portal e tarefas entre contador e cliente;
- motor regulatório versionado e matriz pública de cobertura;
- adaptadores para documentos fiscais e obrigações;
- RBAC/ABAC, segregação de funções, auditoria e exportação;
- API versionada, webhooks idempotentes e observabilidade;
- IA apenas como assistência explicável, sem publicar lançamentos ou transmitir obrigações sozinha.

Folha completa, cobertura nacional de NFS-e, banking próprio, crédito, manufatura profunda, marketplace amplo e IA autônoma ficam fora do primeiro ciclo.

## Como usar com o contador

Comece por [caderno de descoberta](docs/accountant-discovery-workbook.md). Ele transforma a experiência do contador em decisões testáveis: como o escritório fecha hoje, onde ocorrem retrabalho e risco, quais arquivos realmente chegam, quais obrigações são prioritárias e que evidência precisa ser preservada.

Depois leia:

1. [síntese do benchmark e hipóteses de oportunidade](docs/benchmark-synthesis.md);
2. [modelo de domínio](docs/domain-model.md);
3. [contratos contábeis em linguagem humana](docs/data-contracts.md);
4. [arquitetura](docs/architecture.md);
5. [Product Spec](docs/specs/01-product-spec.md) até [Agent Configuration](docs/specs/05-agent-configuration.md);
6. [backlog de discovery e POCs](docs/specs/06-discovery-and-poc-backlog.md);
7. [schemas e exemplos](schemas/README.md).

## Estrutura

| Caminho | Finalidade |
| --- | --- |
| `docs/references/` | Benchmark recebido e fontes de contexto preservadas. |
| `docs/specs/` | Cinco anchors spec-driven e backlog de POCs. |
| `docs/adr/` | Decisões arquiteturais com consequências explícitas. |
| `docs/` | Modelo de domínio, arquitetura, síntese e caderno do contador. |
| `schemas/` | Contratos JSON e OpenAPI. |
| `examples/` | Fixtures para validar os contratos. |
| `prompts/` | Prompt de assistência contábil com guardrails. |
| `configs/` | Configuração sem segredos e sem regras fiscais escondidas. |
| `scripts/` | Validações estruturais e semânticas. |
| `tests/contract/` | Testes de contrato e invariantes contábeis. |

## Rodar em localhost

A fundação local sobe API, worker, PostgreSQL, MinIO, Keycloak e a interface. Os segredos do exemplo são falsos e servem só para esta máquina.

```bash
cp .env.example .env
docker compose up --build
```

- Interface: `http://localhost:5173`
- API e OpenAPI gerada: `http://localhost:8000/docs`
- Keycloak: `http://localhost:8080` (realm `contabil`). Se essa porta já estiver em uso, defina `KEYCLOAK_PORT` no `.env` antes do build; a interface e o emissor do token usam essa porta.
- MinIO: API em `http://localhost:9000` e console em `http://localhost:9001`. Usuário e senha vêm de `MINIO_ROOT_USER` e `MINIO_ROOT_PASSWORD` no `.env`. A imagem local é a do Chainguard, porque `minio/minio` não está mais no Docker Hub; o contrato da aplicação continua S3.

Para importar um lote: entre como `preparer`, envie o CSV em Importação e espere o estado Pronto. Entre como `approver` e publique. O mesmo arquivo, no mesmo sistema de origem, não gera lançamento de novo; a linha fica como já importada e o relatório explica a diferença. O cabeçalho de cada tipo está em `GET /v1/import-batches/templates/{kind}`.

Para conciliar: em Bancos, ligue um ativo postável à conta e informe só os quatro últimos dígitos. Em Conciliação, envie um CSV (`date;description;amount;external_id`) ou um OFX. O mesmo movimento não entra duas vezes. Um caso sugerido mostra a linha do razão, o score e o motivo. Só `approver` aprova. Se não houver linha, o preparador pode criar um rascunho; publicá-lo, por outra pessoa, resolve o caso.
- Usuários `preparer`, `approver`, `admin`, `viewer` e `outsider`, senha `dev-only-password`
- Adminer, se quiser inspecionar o banco: `docker compose --profile tools up adminer` em `http://localhost:8081`

O primeiro boot do Keycloak pode levar cerca de um minuto. Para repetir a carga inicial, apague o volume com `docker compose down -v`.

O piloto hospedado, num dyno só, está em [deploy/pilot/README.md](deploy/pilot/README.md). Ele não substitui este compose.

```bash
docker compose exec api pytest
```

O build da interface executa `tsc`. Na máquina, com Node, use `npm run typecheck` e `npm run lint` dentro de `apps/web`. O smoke de ponta a ponta é `npm run e2e` em `apps/web`, com o compose no ar.

## Validação

```bash
python3 -m pip install -r requirements-dev.txt
python3 scripts/validate_specs.py
python3 scripts/check_internal_links.py
python3 -m pytest tests/contract -q
openapi-spec-validator schemas/openapi.yaml
```

## Decisões que ainda não devem ser inventadas

A equipe ainda precisa decidir nome do produto, ICP final, estados e municípios do piloto, regime tributário, provedores fiscais, política de certificados, retenção, RPO/RTO, cloud, banco, modelo de pricing, critérios de migração e o que o contador considera “fechamento pronto”.

O benchmark é um insumo de decisão. Uma ausência pública de feature não prova que o concorrente não a possui, e uma feature anunciada não prova cobertura universal. A fonte preservada está em [benchmark-software-contabil.md](docs/references/benchmark-software-contabil.md).
