# Caderno de descoberta com o contador

Este documento transforma a experiência do contador em decisões de produto. A conversa deve usar exemplos reais anonimizados, arquivos sem dados pessoais e uma competência já encerrada quando possível. A ordem da conversa, a forma de perguntar e a folha de anotação estão no [roteiro de entrevista](roteiro-entrevista-contador.md).

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

O contador deve classificar cada capacidade como: indispensável no piloto, útil depois, dependente de parceiro ou fora do produto. As perguntas estão em [Perguntas da Fase E](#perguntas-da-fase-e), e a sessão segue a Sessão 2 do [roteiro de entrevista](roteiro-entrevista-contador.md#sessão-2--escolher-a-obrigação-do-piloto-90-minutos).

## Sessão 5 — portal e colaboração

Listar os documentos e respostas que o cliente precisa entregar. Registrar quem pede, quem recebe, prazo, confirmação, lembrete, comentário, aprovação e impacto no fechamento. O objetivo é diferenciar um portal de evidência de um simples armazenamento de arquivos.

### Rodada da Fase D

A Fase D fecha quando cinco clientes de teste resolvem as pendências com o contador e ele diz se o fluxo dispensa a planilha paralela.

**Preparar.** Carregar as empresas de teste no escritório e convidar em Administração o cliente de cada uma, como no [roteiro do piloto](../deploy/pilot/README.md#empresas-de-teste). Cada empresa fica com um pedido aberto, com prazo e tipo de documento. Os dados são fictícios. Para o lembrete chegar, o e-mail de cada cliente precisa estar verificado no SES enquanto a conta estiver em sandbox ([aviso ao cliente](../deploy/pilot/README.md#aviso-ao-cliente)).

**Observar.** Durante a rodada, anotar onde o cliente travou, o que foi pedido ou respondido por fora (WhatsApp, e-mail, telefone, planilha) e por quê. Cada contato por fora é um candidato a regra do portal, não uma falha do cliente.

**Medir.** No fim, rodar `python -m contabil.pilot_report --tenant-id ESCRITORIO`. Para cada pedido, ele mostra quem enviou o primeiro arquivo (cliente ou escritório), se chegou no prazo, os dias até receber, até confirmar e da abertura até a confirmação, quantas vezes o arquivo voltou e quantas mensagens cada lado escreveu. O resumo conta também os documentos enviados sem pedido e quantos o escritório classificou. Os horários e as contagens vêm da trilha de auditoria; o texto das mensagens não é lido.

**Decidir.** O fluxo dispensa a planilha quando os cinco pedidos chegam pelo próprio cliente, o escritório confirma sem contato por fora e nenhum pedido precisa ser controlado em outro lugar. O contador pode trocar esse critério; a troca entra aqui. Como critério de apoio, nenhum arquivo deve voltar mais de uma vez sem uma mensagem no pedido explicando o motivo. As respostas das perguntas 27 a 33 confirmam ou mudam o portal e decidem o próximo corte.

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
22. O pacote precisa de outros relatórios além do balancete, dos lançamentos, da conciliação, dos lotes e dos documentos? Em que formato o escritório entrega hoje o balancete e o razão (PDF, Excel, papel), para quem, e quais demonstrações (DRE, Balanço) ele emite todo mês? Hoje o sistema imprime o balancete e o razão pelo navegador e baixa CSV para o Excel, com o aviso de relatório gerencial; DRE e Balanço não existem.
23. O fechamento precisa de assinatura ICP-Brasil neste corte? A fundação não assina e não trata o pacote como livro autenticado da ECD (IN RFB 2.003/2021, art. 8º).

## Decisões provisórias do portal

24. O cliente da empresa envia arquivo no próprio pedido, vê o histórico e pode mandar um documento sem pedido. O papel `client` não combina com papel do escritório e não abre a sala. O admin convida o cliente em Administração. Se o cliente já existe para a mesma empresa e ainda não tem login, o convite só cria o login. Confirmar continua com o escritório. Pedido aberto ou com arquivo ainda não confirmado bloqueia o fechamento (`2026.10-2`). Devolução, vários arquivos, conversa, envio sem pedido e aviso por e-mail estão nas perguntas 27 a 33, como validação do que o piloto já faz.
25. Hoje mostra a fila do escritório ordenada pelo prazo, do mais próximo para o mais distante, e no mesmo prazo o pedido ainda sem arquivo vem primeiro. Abrir o item troca a empresa e a competência na barra. Não há responsável designado no pedido.
26. A exportação da competência leva o cabeçalho dos lançamentos, sem as linhas, e no máximo 200 itens por lista ([ADR 023](adr/023-exportacao-operacional.md)). Isso basta para levar a competência a outro sistema, ou o escritório precisa das linhas, das contas e de mais volume?

## Perguntas da rodada da Fase D

O piloto já tem conversa, vários arquivos, devolução, envio sem pedido e lembrete por e-mail. Isso foi feito como decisão provisória, antes desta rodada ([ADR 026](adr/026-devolucao-e-conversa.md), [ADR 027](adr/027-envio-sem-pedido.md), [ADR 028](adr/028-aviso-por-email.md)). Por isso a maior parte das perguntas abaixo valida o que existe, em vez de perguntar se deveria existir. A resposta pode confirmar, mudar ou retirar a regra; as três ADRs continuam `proposed` até lá.

27. **Conversa.** Hoje cliente e escritório escrevem no pedido enquanto ele está aberto ou recebido, com até 1000 caracteres por mensagem, e a conversa fica fora do pacote de fechamento e da exportação. A conversa basta para dispensar o WhatsApp e o e-mail? Ela é prova e deve entrar no pacote?
28. **Lembrete.** Hoje o cliente recebe e-mail quando o pedido é aberto ou devolvido, três dias antes do prazo e uma vez depois do vencimento, na data de Brasília. O cliente pode desligar o aviso no portal. A antecedência e a frequência servem? O e-mail basta como canal, e alguém do escritório precisa poder disparar um lembrete à mão?
29. **Vários arquivos e devolução.** Hoje o pedido aceita até 10 arquivos ativos, e o escritório confirma o pedido inteiro. Só quem aprova devolve, com motivo de pelo menos 10 caracteres, e a devolução vale para todos os arquivos ativos. Dez arquivos bastam? O escritório precisa confirmar ou devolver um arquivo só?
30. O pedido precisa de responsável designado no escritório, além de quem abriu? Isso ainda não existe.
31. **Pedido vencido.** Hoje ele continua aberto, gera um aviso por e-mail, conta como vencido no resumo do portal e segue na fila do escritório pela ordem do prazo. Ele precisa mudar de estado, avisar alguém do escritório ou ir para uma fila separada?
32. O cliente precisa ver o pedido já confirmado ou cancelado, e o motivo do cancelamento? Neste corte, sim: o histórico mostra os dois e o motivo do cancelamento.
33. **Envio sem pedido.** Hoje o documento que o cliente manda sem pedido espera o escritório, que o liga a um pedido novo ou o descarta com motivo. Ele não vira pendência sozinho. Esse fluxo serve, ou o envio deve abrir um pedido automaticamente?

## Perguntas da Fase E

A Fase E começa por estas respostas ([DISC-002](specs/06-discovery-and-poc-backlog.md)). Nenhuma tem decisão provisória: o piloto ainda não tem obrigação fiscal, e nenhuma regra, prazo ou leiaute entra no código antes delas.

34. **Carteira por regime.** Quantos CNPJs o escritório atende em cada regime de tributação, aproximadamente? Quais regimes dão mais trabalho por cliente?
35. **Localidade.** Em quais UFs e municípios estão os clientes? Quais concentram a maior parte da carteira?
36. **Obrigações de hoje.** Quais obrigações o escritório entrega hoje, com que periodicidade e para quantos clientes? Para cada uma: quem prepara, quem transmite, em que software e quanto tempo leva por cliente.
37. **Classificação.** Cada obrigação citada na 36 é indispensável no piloto, útil depois, dependente de parceiro ou fora do produto?
38. **Obrigação do piloto.** Qual obrigação o piloto deve cobrir primeiro, e por quê? Critérios possíveis, sem ordem definida: volume, custo de um erro, existência de ambiente de teste, dependência de município e quanto da informação já está no razão.
39. **Entradas e pré-requisitos.** De onde vêm os dados dessa obrigação? O que precisa estar fechado ou entregue antes, como a competência, outra obrigação ou um documento do cliente?
40. **Conferência.** O que o escritório confere antes de transmitir, e com que validador ou programa?
41. **Prazos.** Qual é o prazo legal e qual é o prazo interno do escritório? Quem controla os dois hoje, e como fica sabendo de uma mudança de prazo ou de leiaute?
42. **Rejeição e retificação.** Quais rejeições são mais comuns e como são corrigidas? Quando uma entrega precisa de retificação, o que liga a retificação à entrega original?
43. **Prova.** O que o escritório guarda de cada entrega (arquivo transmitido, recibo, protocolo, relatório do validador), onde e por quanto tempo?
44. **Contingência.** O que o escritório faz quando o serviço do órgão está fora do ar perto do prazo?
45. **Certificado e procuração.** A transmissão usa certificado da empresa ou do escritório, com procuração? O certificado é A1 ou A3, quem guarda e quem renova?
46. **Homologação ou parceiro.** Existe ambiente de teste para essa obrigação, e o escritório já usou? Ou ele prefere que um parceiro transmita?
47. **Quem transmite.** Quem no escritório pode transmitir? O escritório aceitaria que o sistema só transmitisse depois da aprovação de uma segunda pessoa ([ADR 004](adr/004-aprovacao-humana.md))?
48. **Cobertura.** Como o contador quer ver o que o sistema cobre e o que não cobre: por obrigação, por UF, por município ou por cliente?

## Decisões provisórias dos relatórios

49. **Saldo anterior.** Hoje o saldo anterior do balancete e do razão soma todos os lançamentos publicados das competências anteriores, desde o primeiro, sem zerar as contas de resultado na virada do exercício. O saldo das contas de resultado deve voltar a zero no início do exercício? Se sim, o zeramento é um lançamento de encerramento que alguém aprova, ou só uma regra de exibição? O CSV usa ponto e vírgula, vírgula decimal e duas casas, e o arquivo diz que não é livro contábil oficial. Esse formato abre direto no Excel do escritório?
