# SPEC — Contrato de interface v0.3.0

> Fonte de verdade da experiência do front-end. Atualizações de comportamento, estado, linguagem visual ou estrutura precisam atualizar este arquivo antes do código.

## 1. Tese

O produto ajuda escritórios de contabilidade a **fechar e entregar com evidência**. A tela começa pelo trabalho e pelas exceções, não pelo catálogo de módulos. Toda decisão material deve permitir voltar à fonte, explicar o motivo e identificar quem aprovou.

## 2. Vocabulário canônico

- **Escritório:** organização/tenant que opera a carteira.
- **Cliente/CNPJ:** entidade empresarial atendida pelo escritório; sempre exibir razão social e identificador suficiente.
- **Competência:** período contábil/fiscal em análise, por exemplo `01/2025`.
- **Fonte:** documento, arquivo, integração, usuário ou modelo que originou um dado.
- **Lote:** conjunto importado/processado com hash, origem, estado e idempotência.
- **Evidência:** documento, evento, regra, aprovação, protocolo, recibo, timestamp ou pacote que sustenta uma decisão.
- **Sugestão:** proposta de regra/IA que ainda não tem efeito material aprovado.
- **Aprovação:** decisão humana registrada com ator, horário e justificativa quando exigida.
- **Protocolo:** retorno identificável de transmissão; tentativa de envio não é protocolo.
- **Recibo:** confirmação disponibilizada pelo órgão/parceiro; protocolo sem recibo não é aceite.
- **Pacote de fechamento:** snapshot/exportação que reúne checklist, ledger, reconciliações, obrigações, aprovações e manifesto.

## 3. Estados canônicos

### Entrada
`recebido` · `incompleto` · `duplicado` · `inválido` · `aguardando documento`

### Processamento
`em fila` · `processando` · `requer revisão` · `falhou` · `pronto para aprovar`

### Reconciliação
`não iniciado` · `parcialmente reconciliado` · `reconciliado` · `divergência aceita` · `bloqueado`

### Fechamento
`aberto` · `pré-fechamento` · `aguardando aprovação` · `fechado` · `entregue` · `reaberto com motivo`

### Entrega
`preparada` · `validada` · `transmitida` · `protocolo recebido` · `cliente notificado` · `leitura confirmada` · `contestada`

### IA
`sugerido` · `revisado` · `aprovado` · `aplicado` · `rejeitado` · `revertido`

### Integração
`saudável` · `sincronizando` · `atenção` · `degradada` · `sem conexão`

## 4. Invariantes visíveis

1. Nenhum journal publicado é editado silenciosamente; correção é reversão/ajuste com nova versão.
2. Nenhuma fonte original é apagada; versões derivadas apontam para a origem.
3. Dry-run não publica efeito.
4. Score/candidato de conciliação é sugestão, não aprovação.
5. IA nunca publica journal, paga título ou transmite obrigação sozinha.
6. “Enviado” não é “aceito”; aceite requer retorno identificável, protocolo e recibo quando aplicável.
7. Fechamento só avança com bloqueios resolvidos ou não aplicáveis com motivo.
8. Reprocessamento é idempotente e mostra escopo/resultado.
9. Verde significa verificado/concluído e sempre vem acompanhado de texto, fonte ou critério.
10. Todo contexto de ação material mostra escritório, cliente/CNPJ, competência, origem, responsável e impacto.

## 5. Contexto global obrigatório

A barra de contexto deve exibir, nesta ordem: `Escritório > Cliente/CNPJ > Competência > Regime/UF > Estado do fechamento`. No aplicativo, o escritório fica na barra lateral e a barra de contexto lista as empresas e as competências do escritório. Regime e UF só entram quando o cadastro os tiver. Trocas de empresa ou competência não podem ser silenciosas quando há ação selecionada ou aprovação pendente. A caminhada sintética usa dados fictícios e não comunica efeitos reais.

## 6. Regras de interação

- A home responde: o que aconteceu, onde, qual o risco, quem é responsável, qual evidência existe e qual é o próximo passo.
- Ação primária resolve/encaminha; “abrir detalhes” é secundária.
- Aprovação em massa exige prévia de escopo, contagens, impacto agregado e confirmação contextual.
- Rejeição pede motivo quando muda o estado operacional.
- Toda tela crítica possui estado vazio, carregando, erro e sem permissão planejável.
- Painel de evidência abre em camada lateral sem retirar o usuário do contexto.
- Filtros nunca alteram o contexto global.

## 7. IA e automação

A IA só aparece como `sugerido`, `revisado`, `aprovado`, `aplicado`, `rejeitado` ou `revertido`. Uma sugestão sempre informa: objeto/escopo, ação proposta, evidências, confiança, impacto, versão/regra, responsável e como desfazer. Não usar “a IA conciliou” quando houve somente sugestão.

## 8. Design tokens v0.1.0

- Assinatura: `--ink-900: #162536` e `--blue-rastro: #1f5c86`.
- Superfícies: `--paper: #f5f8fb`, `--surface: #ffffff`, `--line: #dfe7ee`.
- Semântica: `--info: #2f80ed`, `--attention: #b7791f`, `--danger: #b84048`, `--success: #2f855a`.
- Tipografia de interface: `Inter, ui-sans-serif, system-ui, sans-serif`; títulos de pacote: `Newsreader, Georgia, serif`.
- Raios: 10px em cards, 8px em controles, 999px em badges.
- Elevação: sombra discreta; evitar gradientes decorativos e glassmorphism.
- Motion: 140–180ms; respeitar `prefers-reduced-motion`.

## 9. Definition of done de tela

A tela está pronta quando contém: contexto visível; estado textual além de cor; fonte/frescor quando houver dado; ação com próximo passo; detalhe/evidência navegável; estados vazio/carregando/erro; foco e teclado; layout de desktop e colapso coerente em telas menores; nenhum claim de cobertura fiscal, aceite, assinatura ou segurança sem contrato/evidência.

## 10. Dados sintéticos

Usar somente organizações e empresas fictícias, sem CPF, certificados, documentos reais, segredos, URLs privadas ou dados bancários reais. O front inicial é demonstrativo; ações de aprovar/rejeitar atualizam apenas estado local.

## 11. Decisões abertas

Nome definitivo e identidade; estados/municípios do piloto; obrigações iniciais; política de retenção; materialidade; conectores; modelo de permissões; métricas de sucesso; SLA/RPO/RTO; requisitos jurídicos de protocolo/assinatura; endpoints de fila do dia, close run, sugestão de IA, obrigação, saúde de conector e pacote de fechamento.

## 12. Montagem no aplicativo

A sala fica em `/app/rastro` e é a primeira tela depois do login. Ela é a única casca do serviço de interface `apps/web` ([ADR 016](../adr/016-frontend-separado.md), [ADR 018](../adr/018-uma-casca-visual.md)). Não há segundo menu nem segundo fundo.

| Menu | O que abre |
| --- | --- |
| Hoje | Lançamentos recentes da empresa selecionada. |
| Fechamentos | Períodos dessa empresa. |
| Conciliação | Casos de conciliação. |
| Migrações | Lotes de importação. |
| Dados e ledger | Lançamentos. |
| Revisões de IA | Estado vazio: não há contrato de sugestão nesta versão. |
| Obrigações e entregas | Estado vazio: não há obrigação versionada nesta versão. |
| Evidências | Documentos da empresa. |
| Integrações | Estado vazio: nenhum conector externo. As contas bancárias ficam nas rotinas. |
| Rotinas do razão | Novo lançamento, balancete, plano, bancos, auditoria e, para o admin, nova empresa. |
| Administração | Estado vazio: papéis continuam no provedor de identidade. |
| Demonstração | Caminhada sintética da Orbe, só com `VITE_RASTRO_DEMO` diferente de `false`. |

A barra de contexto é o seletor da empresa e da competência do escritório. A caminhada sintética tem o próprio seletor e não altera a empresa do sistema. As rotas `/app/journals`, `/app/accounts` e vizinhas permanecem e renderizam na mesma casca.

## 13. Changelog

- `0.3.0` — uma casca só; o contexto passa a ser a empresa do escritório; a Orbe fica na demonstração.
- `0.2.1` — a tela de login usa a marca e os tokens da sala.
- `0.2.0` — sala vira a entrada do produto, no serviço de interface separado da API.
- `0.1.1` — sala montada em `/app/rastro`, com demonstração explícita e rollback pelas rotas antigas.
- `0.1.0` — contrato inicial aprovado junto ao plano “Sala de fechamento”.
