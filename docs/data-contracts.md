# Contratos de dados contábeis

Os JSON Schemas definem forma e limites. Este documento define o significado operacional que o contador deve validar.

## JournalEntry

Um journal representa um conjunto de linhas que será publicado no ledger. Antes da publicação pode ser corrigido no estado draft. Depois da publicação, a correção cria um novo journal de reversão ou ajuste.

Campos essenciais são tenant, empresa, período, moeda, linhas, origem e ator. Cada linha possui conta, lado, valor e descrição. Centro de custo e dimensões são opcionais no contrato, mas podem ser obrigatórios por plano de contas ou regra do contador.

O schema não consegue sozinho provar que débitos e créditos somam o mesmo valor. Essa é uma regra de domínio e está coberta pelo validador e pelos testes.

## ImportBatch

Um lote registra a entrada de um arquivo ou conjunto de arquivos. `dry_run` significa que nenhum efeito foi publicado. O lote deve preservar hash, nome, sistema de origem, IDs externos, erros por linha, totais e relatório de diferença.

Uma nova tentativa com a mesma chave de idempotência deve produzir o mesmo resultado lógico. Se o arquivo mudar, seu hash muda e o sistema deve tratar isso como nova entrada ou conflito explícito.

O CSV desta fase é UTF-8, com cabeçalho obrigatório. O separador é `;` quando ele aparece no cabeçalho; caso contrário é `,`. O decimal usa ponto.

| Tipo | Colunas |
| --- | --- |
| `chart_of_accounts` | `external_id;code;name;account_type;postable;parent_code` |
| `opening_balance` | `external_account_id;account_code;debit;credit` |
| `journal` | `external_journal_id;entry_date;description;account_code;side;amount;line_description;cost_center_code` |

Erros por linha: `MISSING_COLUMN`, `INVALID_AMOUNT`, `ACCOUNT_NOT_FOUND`, `ACCOUNT_NOT_POSTABLE`, `PERIOD_MISMATCH`, `JOURNAL_UNBALANCED`, `DUPLICATE_EXTERNAL_ID_IN_FILE`, `PARENT_NOT_FOUND`, `ALREADY_IMPORTED`. `ALREADY_IMPORTED` não conta como linha inválida. O saldo de abertura que não fecha sozinho usa `BATCH_UNBALANCED` e o lote falha. O modelo de cada tipo sai de `GET /v1/import-batches/templates/{kind}`.

## DocumentRequest

Um pedido pede um arquivo para uma empresa e uma competência aberta ou reaberta. O estado começa em `open`. O envio grava o original com hash e passa o pedido para `received`. A confirmação, feita por quem aprova, passa para `confirmed` e exige o arquivo. O cancelamento exige motivo de pelo menos 10 caracteres e passa para `cancelled`.

`open` e `received` bloqueiam o fechamento da competência. `confirmed` e `cancelled` não bloqueiam. O checklist que conta esses pedidos é `2026.10-2`.

O cliente da empresa vê só os pedidos `open` e `received` da própria empresa e pode enviar o arquivo. Ele não confirma nem cancela. A fila do escritório lista os pedidos de todas as empresas do escritório ativo, por prazo, com `open` antes de `received` no mesmo prazo, e marca `blocks_close` em cada item ([ADR 024](adr/024-fila-de-pendencias.md)).

## ExportPackage

O pacote `operational_v1` exporta uma competência de uma empresa: o cabeçalho dos lançamentos publicados ou revertidos (data, histórico e estado, sem as linhas), os documentos com hash, os pedidos de documento com `blocks_close`, os eventos de auditoria e os totais de débito e crédito do balancete. O contrato está em `schemas/export-package.schema.json`. Cada lista tem teto de 200 itens. O campo `sha256` é o hash do pacote calculado sem ele mesmo. O pedido é assíncrono: responde com `operation_id` e `correlation_id`, e o pacote fica disponível quando o estado chega a pronto. O pedido e a conclusão geram o evento `document_exported` na auditoria ([ADR 023](adr/023-exportacao-operacional.md)).

O pacote não é SPED, ECD nem arquivo de obrigação. Ele serve para outro sistema ou outro ambiente ler a competência.

## Extrato bancário

O CSV deste corte usa o cabeçalho `date;description;amount;external_id`. O separador é `;` quando ele aparece na primeira linha e `,` nos demais casos. `amount` é decimal com ponto e sinal: negativo é saída. `external_id` pode vir vazio. A data aceita `AAAA-MM-DD` ou `DD/MM/AAAA`.

O OFX 1.x é lido como SGML, com tags sem fechamento e cabeçalho `OFXHEADER`. O OFX 2.x é XML. Os campos lidos são `BANKACCTFROM` (só contexto), `DTSTART`, `DTEND`, `STMTTRN` (`DTPOSTED`, `TRNAMT`, `FITID`, `MEMO` ou `NAME`) e `LEDGERBAL`/`BALAMT`. `DTPOSTED` usa os oito primeiros dígitos, então um fuso no final não muda o dia. `CHARSET:1252` decodifica em cp1252. Sem esse pedido, o arquivo precisa ser UTF-8.

O fingerprint é sha256 de `conta banco|FITID` quando há identificador externo. Sem ele, a chave é `conta banco|data|valor canônico|direção|descrição normalizada`. Duas linhas iguais no mesmo dia, sem FITID, contam como duplicata em `transactions_duplicate` e não são descartadas em silêncio. Erros de lote: `INVALID_ENCODING`, `MISSING_COLUMN`, `UNSUPPORTED_FORMAT`, `INVALID_AMOUNT`, `INVALID_DATE`.

O score deste corte, só para linha do razão com o mesmo valor e o lado coerente (`inflow` é débito na conta banco, `outflow` é crédito), soma 0,6 pelo valor, 0,3 se a data é a mesma ou 0,2 se cai na tolerância, e 0,1 se alguma palavra do histórico coincide. A explicação nomeia esses fatos: "Valor idêntico", "Data igual", "Data a N dias", "Histórico compatível". Sem candidato o caso fica `open`. A tolerância padrão é 3 dias, em `configs/product.yaml`.

## ReconciliationCase

O caso de conciliação representa uma transação bancária ou outro item externo que precisa ser relacionado a uma origem interna. A lista de candidatos não é uma decisão. O score é uma sugestão, não uma autorização.

A explicação deve indicar quais campos coincidiram e quais regras foram usadas. A aprovação cria o vínculo e o evento `reconciliation_approved`. Rejeitar ou ignorar não apaga a transação. Rejeitado e ignorado saem da pendência de match; aberto, sugerido e revertido continuam nela. Reverter só desativa o vínculo.

## CloseRun

A execução de fechamento é uma instância de uma competência. O checklist v1 é fixo e versionado. Itens bloqueantes e não bloqueantes convivem. Fechar exige que todos os itens bloqueantes estejam concluídos ou explicitamente não aplicáveis, com motivo.

O snapshot é JSON no Postgres, com SHA-256, e não aceita alteração. O pacote de evidências não fica gravado como arquivo: o download monta o JSON a partir do snapshot. O estado `closing` do período existe no banco e não é usado, para a competência continuar aceitando lançamento enquanto o checklist está aberto.

## SourceDocument

O original é imutável e identificado por hash. Classificação, OCR, normalização ou assinatura criam versões derivadas. A proveniência registra como o documento chegou e quem ou qual serviço o recebeu.

Retenção combina política do produto, obrigação legal, auditoria e legal hold. O sistema não deve apagar automaticamente um documento em hold nem prometer um prazo universal sem consultar a política aplicável.

## RegulatoryObligation

A obrigação representa uma exigência para uma entidade, estabelecimento, competência e jurisdição. `rule_version` e `layout_version` precisam ser registrados para que uma transmissão seja reproduzível.

`coverage` indica a natureza do suporte. `native` não deve ser usado apenas porque um parceiro diz que o produto suporta uma obrigação. A cobertura precisa ter matriz de jurisdição, versão, regime, dependências e estado de homologação.

Uma obrigação `accepted` precisa apontar transmissão aceita, protocolo e recibo. Um arquivo enviado sem retorno não é aceite.

## AuditEvent

O evento de auditoria registra ações relevantes. O alvo indica o agregado afetado. O motivo é obrigatório nos fluxos que alteram controle, como reabertura, reversão, exportação sensível e mudança de permissão.

A integridade do evento pode usar hash encadeado ou mecanismo equivalente. O produto deve definir retenção, acesso e exportação da auditoria antes do primeiro cliente.

## Relações mínimas

```text
SourceDocument -> ImportBatch ou SubledgerDocument
SubledgerDocument -> JournalEntry -> JournalLine
BankTransaction -> ReconciliationCase -> aprovação -> JournalEntry
CloseRun -> checklist -> snapshot no Postgres; pacote gerado no download
DocumentRequest -> SourceDocument
Membership client -> LegalEntity -> DocumentRequest
ExportPackage -> competência -> cabeçalho de JournalEntry, SourceDocument, DocumentRequest, AuditEvent
RegulatoryObligation -> arquivos -> Transmission -> Protocol/Receipt
AuditEvent -> todos os efeitos sensíveis
```

## Decisões para o contador

O contador ainda precisa confirmar se o plano referencial é versionado por competência, quando uma conta pode receber lançamento, quais dimensões são obrigatórias, como ocorre baixa parcial, quais diferenças de conciliação exigem aprovação adicional, quais relatórios entram no pacote de fechamento e quais documentos precisam de retenção legal por tipo.
