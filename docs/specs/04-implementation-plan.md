# Anchor 4 — Implementation Plan

## Fase A — domínio e dados sintéticos

Implementar contratos, tenancy, entidades, plano de contas, períodos, journals, validação de balanço e auditoria. Criar dados sintéticos de uma empresa e uma competência.

**Pronto quando:** o sistema publica journals equilibrados, rejeita desequilíbrio, consulta drill-down e reverte sem editar o original.

A fundação de software desta fase está executável em localhost: API, worker de outbox, PostgreSQL, Keycloak de desenvolvimento e UI mínima. O comando está no [README](../../README.md). Isso não substitui a confirmação do contador sobre fechamento, segregação em escritório pequeno, dimensões obrigatórias e conta postável.

## Fase B — migração e documentos

Implementar arquivos, hash, import batch, dry-run, erros por linha, preservação de IDs externos, object storage e relatório de diferença.

**Pronto quando:** o mesmo lote pode ser reprocessado sem duplicidade e o contador entende cada diferença.

A fundação local desta fase guarda o original no MinIO, simula o CSV, lista o erro por linha e só publica com um aprovador diferente de quem criou o lote. Rollback de lote, OCR e conciliação bancária ficam fora. As perguntas novas estão no caderno de descoberta.

## Fase C — financeiro, conciliação e fechamento

Implementar contas a pagar/receber, OFX/CSV, casos de conciliação, candidatos explicáveis, aprovação, checklist, lock, reabertura e pacote de evidências.

**Pronto quando:** uma competência completa pode fechar com pendências visíveis e auditoria exportável.

O corte C1 está na fundação local. Um extrato CSV ou OFX reimportado não duplica transação. Cada transação nova vira um caso com candidatos do razão, score e explicação, e só um aprovador cria o vínculo. A conta banco mostra o que ainda está pendente. O corte de fechamento grava checklist, snapshot e pacote sob demanda ([ADR 020](../adr/020-fechamento-com-evidencia.md)). O primeiro corte do portal pede um documento na competência, guarda o arquivo e bloqueia o fechamento enquanto o pedido está aberto ou só recebido ([ADR 021](../adr/021-pedido-de-documento.md)). O login do cliente, limitado ao próprio pedido, entra na Fase D ([ADR 025](../adr/025-portal-do-cliente.md)). Contas a pagar e receber, match 1:N, N:1 e parcial e comentário continuam fora. As perguntas estão no caderno de descoberta.

## Fase D — portal e API

Implementar solicitações ao cliente, tarefas, upload, comentários, permissões, API versionada, idempotency key, status de jobs e exportação.

**Pronto quando:** cinco clientes de teste resolvem uma lista de pendências sem depender de planilha paralela.

O primeiro corte está publicado no piloto, em quatro partes. A fila do escritório e Hoje mostram o pedido que bloqueia ([ADR 024](../adr/024-fila-de-pendencias.md)). A exportação da competência sai em Evidências, e a lista de operações fica na API ([ADR 023](../adr/023-exportacao-operacional.md)). O cliente envia o arquivo do próprio pedido e o escritório confirma ([ADR 025](../adr/025-portal-do-cliente.md)). Cada escritório fictício tem cinco clientes de teste, um por empresa; o admin cria o login deles em Administração. Comentário, e-mail, lembrete, vários arquivos no mesmo pedido e webhook continuam fora.

Falta para fechar a fase: os cinco clientes resolverem as pendências com o contador, e o contador dizer se o fluxo dispensa a planilha paralela. O roteiro dessa rodada, o critério de decisão e as perguntas 27 a 32 estão no [caderno do contador](../accountant-discovery-workbook.md#rodada-da-fase-d). O comando `contabil.pilot_report` mostra o ciclo de cada pedido para a conversa. Os testes de integração, inclusive os da Fase D, passaram com o compose no ar em 27 de outubro de 2026.

## Fase E — obrigação fiscal piloto

Escolher obrigação e localidades. Implementar registry, validação, homologação, adapter, transmissão assíncrona, polling, rejeição, protocolo, retificação e reconciliação.

**Pronto quando:** o fluxo funciona em homologação, apresenta cobertura explicitamente e não duplica envio.

## Fase F — assistência de IA

Adicionar sugestões de classificação, conciliação e explicação. A aplicação valida schema e evidências; usuário autorizado aprova.

**Pronto quando:** o contador consegue aceitar, rejeitar e corrigir uma sugestão, e nenhuma sugestão produz efeito sem aprovação.

## Primeiro ambiente hospedado

O primeiro ambiente hospedado testa plano, razão, documentos, conciliação bancária 1:1, fechamento, pedidos de documento, exportação e o portal do cliente no plano mais barato, como no [ADR 015](../adr/015-piloto-barato-heroku.md). A API e o outbox dividem um dyno. A interface, com a sala de fechamento como entrada, ocupa outro, como no [ADR 016](../adr/016-frontend-separado.md). A credencial única do banco obedece ao RLS por `FORCE ROW LEVEL SECURITY`. O dado desse ambiente fica nos Estados Unidos, num bucket S3 privado em `us-east-2`. A obrigação fiscal continua na Fase E. A forma AWS do [ADR 014](../adr/014-deploy-piloto-aws-sa-east-1.md) entra com documento de cliente real ou quando o escritório depender do sistema no dia a dia.

## Dependências críticas

A definição do contador sobre fechamento e reconciliação precede o ledger final. A escolha de estados e obrigações precede o adapter fiscal. A política de certificados precede transmissão de produção. A política de retenção precede storage definitivo. O volume de documentos precede decisões de escala.
