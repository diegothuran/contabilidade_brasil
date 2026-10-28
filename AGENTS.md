# AGENTS.md — plataforma contábil brasileira

## Ordem de leitura

Leia `README.md`, `docs/benchmark-synthesis.md`, `docs/domain-model.md`, `docs/architecture.md`, o caderno do contador, os cinco anchors em `docs/specs/` e as ADRs antes de alterar qualquer contrato. Antes de mexer na interface, leia também `docs/rastro/SPEC.md`, que é a fonte de verdade da tela.

## Regras de domínio

- Nunca publicar journal desequilibrado. Débitos e créditos devem reconciliar na moeda aplicável.
- Journal publicado é imutável. Correção usa reversão, ajuste ou retificação vinculada ao original.
- Período fechado não aceita postagem normal. Reabertura exige papel, motivo, aprovação e auditoria.
- Subledger, razão, documento e obrigação precisam manter origem e vínculo de reconciliação.
- Regra fiscal, XSD, tabela, prazo e versão são dados versionados. Não esconda legislação em condicionais sem referência.
- Não trate “não comprovado no benchmark” como “não existe”. Registre como hipótese ou lacuna de evidência.
- Não permita que IA publique lançamento, pague título, altere certificado ou transmita obrigação sem aprovação humana explícita.
- Não use float para valores monetários; use decimal armazenado como string nos contratos ou tipo decimal no banco.
- Isole escritório, empresa, filial e estabelecimento. Tenant não é apenas um filtro aplicado pelo frontend.
- O cliente da empresa (papel `client`) é exclusivo e fica preso à empresa da membership. Ele não abre rota do escritório, não troca de escritório e não confirma pedido ([ADR 025](docs/adr/025-portal-do-cliente.md)). A troca de escritório só vale para quem é admin no escritório do login ([ADR 022](docs/adr/022-troca-de-escritorio.md)).
- Preserve documento original, hash, versão derivada, protocolo, recibo e cadeia de eventos.
- Toda integração externa deve ter idempotência, retry limitado, dead-letter e reconciliação.
- Não grave certificados, senhas, tokens, CPF desnecessário, XML completo ou dados bancários em logs, prompts ou fixtures.

## Regras de implementação

Comece com um monólito modular e interfaces de adaptador. Não extraia microserviços só por preferência. Primeiro prove ledger, migração, conciliação e fechamento com testes de contrato e dados sintéticos.

O monorepo tem dois serviços implantáveis ([ADR 016](docs/adr/016-frontend-separado.md)). `apps/web` é a interface: não acessa banco, não guarda segredo e não decide regra de tenant. `apps/api` é o domínio e o único serviço que toca o banco, o object storage e o outbox. Mudança de contrato publica a API antes da interface.

O motor regulatório deve ser separado do ledger. Um adaptador fiscal pode falhar sem corromper o livro. Operações assíncronas, como importação, extrato e exportação, passam pelo outbox e retornam status, `operation_id` e `correlation_id`. A API deve ter idempotency key, paginação, limites e versionamento.

Router novo do escritório entra em `main.py` com `dependencies=[Depends(require_office)]`, ou chama `ensure_office` na rota. Rota do cliente fica em `portal/` e valida a empresa da membership. Tabela nova de negócio leva `tenant_id`, RLS forçada e grant para `contabil_app` na migração.

O `.gitignore` ignora pastas e extensões de dados, como `exports/`, `*.csv`, `*.xml`, `*.sql` e `*.pdf`. Ao criar módulo ou fixture com um desses nomes, confira com `git status --short --ignored` se o arquivo entra no commit; se não entrar, abra uma exceção específica no `.gitignore`.

## Definition of Done

Uma alteração está pronta quando atualiza a spec correspondente, mantém o contrato agnóstico, adiciona fixture e teste, passa validação estrutural e semântica, registra ADR quando muda segurança ou invariantes e informa impacto no trabalho do contador.

Se a tela precisa entender a mudança (estado, papel, rota, texto, contexto ou campo novo), o mesmo commit atualiza as decisões de projeto: `docs/rastro/SPEC.md` com entrada no changelog, a ADR afetada, o `README.md`, o caderno do contador, `schemas/openapi.yaml` e `deploy/pilot/README.md`.

Antes de concluir, rode os testes unitários em `apps/api` (`pytest tests/unit`), `npm run typecheck` e `npm run lint` em `apps/web`, `python scripts/validate_specs.py` e `python scripts/check_internal_links.py`. Os testes de integração precisam do compose no ar; quando não rodarem, diga isso.
