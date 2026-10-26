# Caderno de descoberta com o contador

Este documento transforma a experiência do contador em decisões de produto. A conversa deve usar exemplos reais anonimizados, arquivos sem dados pessoais e uma competência já encerrada quando possível.

## Sessão 1 — escritório e carteira

Registrar quantidade de CNPJs, regimes, estados, municípios, setores, volume de documentos, equipe por função e sistemas atuais. Identificar quais clientes exigem mais horas e quais processos ficam fora do sistema.

Perguntar: “Qual é o primeiro sinal de que uma competência não vai fechar no prazo?”. “Quais tarefas dependem de planilha, WhatsApp, e-mail ou memória?”. “Qual dado você nunca confiaria a uma automação sem revisar?”. “O que precisa ser provado para o cliente ou para uma fiscalização?”.

## Sessão 2 — um fechamento completo

Escolher uma empresa e uma competência. Desenhar a sequência desde a chegada dos documentos até o envio das obrigações. Para cada etapa, registrar entrada, responsável, sistema, decisão, saída, exceções, prazo e evidência guardada.

O resultado esperado é um mapa com os estados `pendente`, `em análise`, `aguardando cliente`, `aprovado`, `transmitido`, `rejeitado`, `corrigido` e `fechado`, adaptados ao vocabulário do escritório.

## Sessão 3 — migração e conciliação

Coletar exemplos anonimizados de plano de contas, saldos, lançamentos, OFX/CSV, XML, contas a pagar/receber e relatórios. Perguntar como o contador verifica uma importação, como identifica duplicidade e como explica uma diferença.

O aceite da conversa é definir quais reconciliações precisam zerar, quais diferenças são aceitáveis e quem aprova a publicação do lote.

## Sessão 4 — fiscal e obrigações

Para o piloto, escolher duas ou três UFs e um conjunto pequeno de obrigações. Registrar órgão, documento, regime, competência, versão do leiaute, prazo, pré-requisitos, certificado, assinatura, protocolo, rejeições, contingência, retificação e retenção.

O contador deve classificar cada capacidade como: indispensável no piloto, útil depois, dependente de parceiro ou fora do produto.

## Sessão 5 — portal e colaboração

Listar os documentos e respostas que o cliente precisa entregar. Registrar quem pede, quem recebe, prazo, confirmação, lembrete, comentário, aprovação e impacto no fechamento. O objetivo é diferenciar um portal de evidência de um simples armazenamento de arquivos.

## Cartões de cenário para validar

### Cenário A — saldo de abertura

Dado um saldo importado do sistema legado, o contador consegue ver arquivo, conta, competência, lote, regra de transformação, saldo de origem, saldo de destino e diferença?

### Cenário B — lançamento incorreto em período fechado

O sistema bloqueia a edição, mostra como solicitar reabertura, exige motivo e aprovação, cria o ajuste e preserva a versão original?

### Cenário C — extrato bancário

A sugestão de match mostra valor, data, documento, regra, candidatos e confiança? É possível rejeitar, ajustar, desfazer e auditar?

### Cenário D — documento fiscal rejeitado

O usuário entende órgão, versão, código, mensagem, documento de origem, próxima ação, responsável, retry e efeito no fechamento?

### Cenário E — exportação e saída

O escritório consegue exportar ledger, documentos, XML, recibos, configurações, permissões e auditoria de forma suficiente para trocar de sistema ou atender auditoria?

## Saída obrigatória do workshop

Ao final, produzir um documento com: ICP escolhido; primeira competência-alvo; dois ou três estados/municípios; lista de arquivos de entrada; definição de fechamento pronto; invariantes de reconciliação; obrigações do piloto; papéis de aprovação; evidências exigidas; funcionalidades fora do MVP; e três dores cuja frequência e impacto foram observados.

Uma feature só entra no MVP quando o contador fornecer um exemplo, explicar o risco, descrever o resultado esperado e aceitar o critério de teste. Opinião de uma pessoa é sinal de investigação, não validação de mercado.

## Decisões provisórias da Fase A

A fundação local adotou estas regras para poder ser testada. Elas não fecham o desenho contábil:

1. Quem cria um lançamento não o aprova nem o publica. Escritório de uma pessoa ainda não tem exceção.
2. Dimensões são opcionais no contrato. O contador ainda define quais são obrigatórias por plano ou empresa.
3. Conta sintética não recebe lançamento. O contador confirma quando uma conta pode ser postável.
4. Fechar período nesta fase só trava a competência. Checklist, snapshot e pacote de evidências continuam na fase de fechamento.
5. Reverter um lançamento de período fechado exige reabrir antes. O contador confirma se esse é o fluxo desejado.

## Decisões provisórias da Fase B

A importação local também adotou regras para poder ser testada. Elas esperam confirmação:

6. Quais são os layouts reais dos sistemas de origem que o escritório precisa migrar, além dos três CSVs desta fase?
7. Qual é a política de retenção padrão de um documento recebido? Hoje ele fica com `retention_pending`, sem prazo e sem legal hold.
8. Um journal importado dispensa aprovação individual quando o lote inteiro já foi aprovado por outra pessoa? A fundação assume que sim: o criador do lote não é quem publica, e o lançamento nasce publicado.
9. O que é uma diferença aceitável entre o arquivo e o razão? O relatório explica linha inválida, item já importado e conta não mapeada, mas não define tolerância.
10. Qual é a semântica desejada de rollback de um lote? O estado existe no contrato e, nesta fase, a operação responde que não é suportada.

## Decisões provisórias da Fase C

A conciliação bancária deste corte também adotou regras para poder ser testada. Elas esperam confirmação:

11. A tolerância de data entre o extrato e a linha do razão é de 3 dias. Esse prazo serve para o escritório?
12. Diferença pequena de tarifa, juros ou IOF vira conciliação 1:N, N:1 ou parcial? Qual regra separa o que pode ser ligado do que precisa de lançamento?
13. Quem aprova a conciliação quando o escritório tem uma pessoa só? Nesta fase, quem cria o caso não é impedido de aprová-lo; a barreira é o papel `approver`.
14. Qual é a diferença operacional entre rejeitar e ignorar? Os dois preservam a transação e tiram o caso da pendência de match. Rejeitar foi tratado como "não é este candidato" e ignorar como "não vou conciliar este movimento".
15. Quais bancos e quais versões reais de OFX o escritório recebe? O leitor aceita SGML 1.x e XML 2.x, com cp1252 quando o cabeçalho pede, mas layout de banco ainda não foi homologado.
16. Publicar o lançamento nascido do caso pode resolver o caso sem uma segunda aprovação de conciliação? A fundação assume que sim: a publicação é a aprovação humana, e o caso registra essa decisão.

## Decisões provisórias do piloto hospedado

17. Quem é o primeiro usuário administrador do escritório no ambiente hospedado, e esse usuário aceita MFA por aplicativo? O piloto usa um dyno para a API e outro para a interface, e não guarda documento de cliente real.
18. Qual plano de contas substitui o modelo mínimo de teste, e a empresa deve nascer com o ano corrente? O cadastro atual cria 11 contas sintéticas e os 12 períodos do ano informado. Nenhuma delas é referencial.
