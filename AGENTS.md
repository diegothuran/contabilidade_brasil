# AGENTS.md — plataforma contábil brasileira

## Ordem de leitura

Leia `README.md`, `docs/benchmark-synthesis.md`, `docs/domain-model.md`, `docs/architecture.md`, o caderno do contador, os cinco anchors em `docs/specs/` e as ADRs antes de alterar qualquer contrato.

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
- Preserve documento original, hash, versão derivada, protocolo, recibo e cadeia de eventos.
- Toda integração externa deve ter idempotência, retry limitado, dead-letter e reconciliação.
- Não grave certificados, senhas, tokens, CPF desnecessário, XML completo ou dados bancários em logs, prompts ou fixtures.

## Regras de implementação

Comece com um monólito modular e interfaces de adaptador. Não extraia microserviços só por preferência. Primeiro prove ledger, migração, conciliação e fechamento com testes de contrato e dados sintéticos.

O motor regulatório deve ser separado do ledger. Um adaptador fiscal pode falhar sem corromper o livro. Operações assíncronas devem retornar status e correlation ID. A API deve ter idempotency key, paginação, limites e versionamento.

## Definition of Done

Uma alteração está pronta quando atualiza a spec correspondente, mantém o contrato agnóstico, adiciona fixture e teste, passa validação estrutural e semântica, registra ADR quando muda segurança ou invariantes e informa impacto no trabalho do contador.
