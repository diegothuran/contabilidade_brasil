# SPEC — Contrato de interface v0.6.3

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

A barra de contexto deve exibir, nesta ordem: `Escritório > Cliente/CNPJ > Competência > Regime/UF > Estado do fechamento`. No aplicativo, o escritório fica na barra lateral. O seletor só aparece para o administrador geral que já tem acesso a mais de um escritório. Quem tem o login ligado a um escritório só vê o nome desse escritório. A troca limpa a empresa e a competência escolhidas. A empresa escolhida fica marcada no topo, com razão social e CNPJ, ao lado de uma busca que permanece visível. A busca responde enquanto a pessoa digita, por nome ou CNPJ, inclusive por aproximação, e ignora maiúsculas, acentos e pontuação. A competência aparece uma vez, na barra, como mês e ano. O balancete, as pendências da competência, o lançamento novo, a importação, a conciliação e a exportação usam essa competência e não repetem o seletor. Regime e UF só entram quando o cadastro os tiver. Trocas de empresa ou competência não podem ser silenciosas quando há ação selecionada ou aprovação pendente. Abrir uma pendência da fila do escritório troca a empresa e a competência, e a barra passa a mostrar esse contexto. A caminhada sintética usa dados fictícios e não comunica efeitos reais. O cliente da empresa não usa esta barra: vê o escritório e a própria empresa, sem seletor.

## 6. Regras de interação

- A home responde: o que bloqueia o fechamento, em qual empresa, qual o prazo e qual é o próximo passo. O próximo passo abre a pendência e a barra acompanha a empresa e a competência. Os lançamentos recentes continuam na mesma tela.
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

Nome definitivo e identidade; estados/municípios do piloto; obrigações iniciais; política de retenção; materialidade; conectores; métricas de sucesso; SLA/RPO/RTO; requisitos jurídicos de protocolo/assinatura; quem devolve o arquivo, se dez arquivos bastam, se a conversa entra no pacote, se o envio sem pedido vira pendência sozinho e qual a antecedência do lembrete.

## 12. Montagem no aplicativo

A sala fica em `/app/rastro` e é a primeira tela depois do login. Ela é a única casca do serviço de interface `apps/web` ([ADR 016](../adr/016-frontend-separado.md), [ADR 018](../adr/018-uma-casca-visual.md)). Não há segundo menu nem segundo fundo.

| Menu | O que abre |
| --- | --- |
| Hoje | Pendências que bloqueiam o fechamento no escritório, com empresa, prazo e o próximo passo, e os lançamentos recentes da empresa selecionada. Mostra a contagem de documentos enviados pelo cliente sem pedido. |
| Fechamentos | Checklist da competência, fechamento, hash do snapshot e download do pacote. Reabertura continua na lista. |
| Pendências | Pedidos da competência da barra, a fila do escritório ou os documentos enviados pelo cliente sem pedido. O arquivo entra nas evidências e a confirmação tira o bloqueio do fechamento. Abrir um item da fila troca a empresa e a competência na barra. O pedido recebido pode ser devolvido ao cliente, com motivo. A conversa fica no pedido. Classificar um envio cria um pedido já recebido na competência da barra. |
| Balancete | Saldos da competência da barra. O cartão em Rotinas do razão e a rota antiga continuam. |
| Conciliação | Casos de conciliação. |
| Migrações | Lotes de importação. |
| Dados e ledger | Lançamentos. |
| Revisões de IA | Estado vazio: não há contrato de sugestão nesta versão. |
| Obrigações e entregas | Estado vazio: não há obrigação versionada nesta versão. |
| Evidências | Documentos da empresa e a exportação da competência da barra. Os estados aparecem em texto: em fila, gerando, pronto, falhou. Não há lista de operações nesta tela. |
| Integrações | Estado vazio: nenhum conector externo. As contas bancárias ficam nas rotinas. |
| Rotinas do razão | Novo lançamento, balancete, plano, bancos, auditoria e, para o admin, nova empresa. |
| Administração | O admin convida uma pessoa do escritório ou um cliente ligado a uma empresa. Convidar um cliente que já existe para a mesma empresa, mas ainda sem login, só cria o login. A senha temporária vai por e-mail e não aparece na tela. Quem não é admin vê que só o admin convida. |
| Demonstração | Caminhada sintética da Orbe, só com `VITE_RASTRO_DEMO` diferente de `false`. |

A barra de contexto marca a empresa escolhida e mantém a busca ao lado. A competência dessa empresa vale para o balancete, o lançamento novo, a importação, a conciliação, as pendências da competência e a exportação. A caminhada sintética tem o próprio seletor e não altera a empresa do sistema. As rotas `/app/journals`, `/app/accounts` e vizinhas permanecem e renderizam na mesma casca.

## 13. Portal do cliente

O cliente não entra na sala do escritório. A casca mostra o nome do escritório e a razão social e o CNPJ da empresa do login. Não há seletor de escritório, de empresa nem de competência, e não há menu de razão, fechamento, conciliação ou administração.

O vocabulário da tela é pedido, prazo, estado e arquivo. O topo mostra abertos, recebidos, vencidos e o próximo prazo. Há duas listas: em aberto (pedido aberto e arquivo recebido) e histórico (pedido confirmado e pedido cancelado). O cancelado mostra o motivo. Cada pedido mostra o mês de referência. O cliente abre o pedido e vê os arquivos. O devolvido aparece riscado, com o motivo, e não some. No pedido aberto ou com arquivo recebido, o cliente envia outro arquivo, até dez ativos, e escreve uma mensagem. A conversa mostra Cliente ou Escritório. Confirmar, cancelar e devolver não aparecem. O download usa o nome original do arquivo. O cliente também envia um documento sem pedido, com uma nota. Esse envio não bloqueia o fechamento. O cliente liga ou desliga os avisos por e-mail. O aviso traz o título, o prazo e o link. Não mostra CNPJ, nome de arquivo nem a conversa.

Nada nesta tela fala em journal, balancete, papéis do escritório, exportação ou outro cliente.

## 14. Changelog

- `0.6.3` — O cliente liga ou desliga o aviso por e-mail. O texto leva título, prazo e link.
- `0.6.2` — O cliente envia um documento sem pedido. O escritório classifica ou descarta. Hoje mostra a contagem.
- `0.6.1` — O escritório devolve o arquivo com motivo. O pedido aceita até dez arquivos ativos e uma conversa.
- `0.6.0` — O portal do cliente mostra o resumo, o mês de referência e o histórico, com o motivo do cancelamento. O download usa o nome original do arquivo.
- `0.5.0` — O cliente da empresa vê só os próprios pedidos, envia o arquivo e não abre a sala do escritório. O convite completa o login de um cliente que já existe para a mesma empresa.
- `0.4.9` — A lista de operações fica na API. Evidências não ganha essa lista.
- `0.4.8` — Evidências gera a exportação da competência e mostra em fila, gerando, pronto ou falhou.
- `0.4.7` — Hoje mostra a fila de pendências do escritório. Abrir um item troca a empresa e a competência na barra.
- `0.4.6` — O seletor de escritório fica só para o administrador geral. Um login ligado a um escritório permanece nesse escritório.
- `0.4.5` — Quem pertence a mais de um escritório troca o escritório na barra lateral. A empresa e a competência da sessão são limpas.
- `0.4.4` — Pendências e Balancete entram no menu de Operação. O pedido em aberto bloqueia o fechamento.
- `0.4.3` — O balancete abre os lançamentos da conta pelo nome dela, em vez de “Drill-down”.
- `0.4.2` — A competência fica só na barra, em mês e ano. As telas não repetem o identificador do período.
- `0.4.1` — A empresa escolhida fica marcada no topo e a busca por nome ou CNPJ permanece visível.
- `0.4.0` — Fechamentos percorre o checklist, grava o snapshot e baixa o pacote.
- `0.3.1` — Administração convida para o escritório; a senha temporária sai por e-mail.
- `0.3.0` — uma casca só; o contexto passa a ser a empresa do escritório; a Orbe fica na demonstração.
- `0.2.1` — a tela de login usa a marca e os tokens da sala.
- `0.2.0` — sala vira a entrada do produto, no serviço de interface separado da API.
- `0.1.1` — sala montada em `/app/rastro`, com demonstração explícita e rollback pelas rotas antigas.
- `0.1.0` — contrato inicial aprovado junto ao plano “Sala de fechamento”.
