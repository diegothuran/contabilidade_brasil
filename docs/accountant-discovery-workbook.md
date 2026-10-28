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

### Rodada da Fase D

A Fase D fecha quando cinco clientes de teste resolvem as pendências com o contador e ele diz se o fluxo dispensa a planilha paralela.

**Preparar.** Carregar as empresas de teste no escritório e convidar em Administração o cliente de cada uma, como no [roteiro do piloto](../deploy/pilot/README.md#empresas-de-teste). Cada empresa fica com um pedido aberto, com prazo e tipo de documento. Os dados são fictícios.

**Observar.** Durante a rodada, anotar onde o cliente travou, o que foi pedido ou respondido por fora (WhatsApp, e-mail, telefone, planilha) e por quê. Cada contato por fora é um candidato a regra do portal, não uma falha do cliente.

**Medir.** No fim, rodar `python -m contabil.pilot_report --tenant-id ESCRITORIO`. Para cada pedido, ele mostra quem enviou o primeiro arquivo (cliente ou escritório), se chegou no prazo, os dias até receber, até confirmar e da abertura até a confirmação, quantas vezes o arquivo voltou e quantas mensagens cada lado escreveu. O resumo conta também os documentos enviados sem pedido e quantos o escritório classificou. Os horários e as contagens vêm da trilha de auditoria; o texto das mensagens não é lido.

**Decidir.** O fluxo dispensa a planilha quando os cinco pedidos chegam pelo próprio cliente, o escritório confirma sem contato por fora e nenhum pedido precisa ser controlado em outro lugar. O contador pode trocar esse critério; a troca entra aqui. As respostas das perguntas 27 a 32 decidem o próximo corte do portal.

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
4. Fechar a competência exige a execução de fechamento. O checklist vigente é `2026.10-2`. Bloqueio pendente impede o fechamento, inclusive pedido de documento em aberto ou só recebido. Não aplicável exige motivo. O snapshot JSON fica no banco, com SHA-256, e não é editado. O pacote sai no download. O estado `closing` não é usado. Correção depois do fechamento segue a ITG 2000 (R1), itens 31 a 36: reabrir e lançar estorno, transferência ou complementação.
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
19. Quais itens do checklist mudam por porte ou regime? A versão `2026.10-2` é a mesma para toda empresa.
20. A revisão do balancete pode ser feita por quem também publica, ou o escritório exige outra pessoa? Nesta fase, `approver` ou `admin` registra a revisão.
21. Qual é a retenção por tipo de documento, além da guarda até prescrição ou decadência (Código Civil, art. 1.194; CTN, art. 195, parágrafo único; Lei 9.430/1996, art. 37)?
22. O pacote precisa de outros relatórios além do balancete, dos lançamentos, da conciliação, dos lotes e dos documentos?
23. O fechamento precisa de assinatura ICP-Brasil neste corte? A fundação não assina e não trata o pacote como livro autenticado da ECD (IN RFB 2.003/2021, art. 8º).

## Decisões provisórias do portal

24. O cliente da empresa envia arquivo no próprio pedido, vê o histórico e pode mandar um documento sem pedido. O papel `client` não combina com papel do escritório e não abre a sala. O admin convida o cliente em Administração. Se o cliente já existe para a mesma empresa e ainda não tem login, o convite só cria o login. Confirmar continua com o escritório. Pedido aberto ou com arquivo ainda não confirmado bloqueia o fechamento (`2026.10-2`). Devolução, vários arquivos, conversa, envio sem pedido e aviso por e-mail estão nas respostas provisórias 33 a 37.
25. Hoje mostra a fila do escritório ordenada pelo prazo, do mais próximo para o mais distante, e no mesmo prazo o pedido ainda sem arquivo vem primeiro. Abrir o item troca a empresa e a competência na barra. Não há responsável designado no pedido.
26. A exportação da competência leva o cabeçalho dos lançamentos, sem as linhas, e no máximo 200 itens por lista ([ADR 023](adr/023-exportacao-operacional.md)). Isso basta para levar a competência a outro sistema, ou o escritório precisa das linhas, das contas e de mais volume?

## Perguntas da rodada da Fase D

27. O pedido precisa de comentário? Se sim, quem escreve para quem (cliente para escritório, escritório para cliente, os dois) e o comentário entra no pacote de fechamento?
28. O cliente precisa de lembrete? Quando (antes do prazo, no prazo, depois), por qual canal (e-mail, WhatsApp, só na tela) e quem dispara (o sistema ou uma pessoa do escritório)?
29. Um pedido aceita mais de um arquivo? Se sim, o escritório confirma o pedido inteiro ou cada arquivo, e um arquivo errado volta para o cliente com motivo?
30. O pedido precisa de responsável designado no escritório, além de quem abriu?
31. O que acontece com o pedido vencido: continua aberto, muda de estado, avisa alguém ou entra numa fila separada?
32. O cliente precisa ver o pedido já confirmado ou cancelado, e o motivo do cancelamento? Neste corte, sim: o histórico mostra os dois e o motivo do cancelamento.

## Respostas provisórias do portal ampliado

33. Quem pode devolver um arquivo ao cliente? Nesta fase, só quem aprova, com motivo de pelo menos 10 caracteres ([ADR 026](adr/026-devolucao-e-conversa.md)).
34. Dez arquivos ativos no mesmo pedido bastam?
35. A conversa do pedido é prova e deve entrar no pacote de exportação? Neste corte ela fica fora do pacote.
36. O documento enviado sem pedido vira pendência sozinho, ou o escritório classifica antes? Neste corte o escritório classifica ([ADR 027](adr/027-envio-sem-pedido.md)).
37. O lembrete por e-mail sai três dias antes do prazo. Essa antecedência serve ao escritório? ([ADR 028](adr/028-aviso-por-email.md))
