# Anchor 5 — Agent Configuration

## Contexto obrigatório

A implementação é uma plataforma contábil brasileira em construção, com primeiro foco em escritórios de 20–200 CNPJs. O banco, provedor fiscal, estados e regras de negócio finais são decisões abertas.

## Ordem de execução

A IA implementadora deve seguir: contratos; domínio e invariantes; dados sintéticos; ledger; migração; conciliação; fechamento; portal/API; obrigação piloto; assistência. Não deve começar pela tela mais chamativa nem por uma lista de features concorrentes.

## Regras de parada

Parar e abrir uma decisão quando faltar: definição contábil do contador, jurisdição, vigência regulatória, papel de aprovação, política de retenção, limite de dados, contrato de parceiro, identidade ou critério de reconciliação.

## Proibições

Não usar float para dinheiro. Não editar journal publicado. Não apagar documento original. Não afirmar obrigação aceita sem protocolo. Não liberar SQL direto para usuário. Não colocar regra fiscal somente no prompt. Não permitir IA autônoma para publicar, pagar ou transmitir. Não registrar PII ou segredos em fixtures.

## Checklist de release

Contratos versionados; invariantes testadas; cross-tenant negado; migração idempotente; exportação executada; restore testado; cobertura fiscal publicada; adaptadores com retry e DLQ; auditoria íntegra; logs redigidos; contador aprovou o fluxo; e rollback documentado.
