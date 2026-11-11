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
   > **Resposta (contador 1, questionário de 05/11/2026):** "Determinadas rotinas só podem ser feitas por contadores com CRC ativo." A segregação continua, e passa a depender também do registro profissional. Quais rotinas, na pergunta 50.
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
   > **Resposta (contador 1, questionário de 05/11/2026):** "Não deveria haver" diferença de data. A tolerância de 3 dias deixa de valer como decisão provisória; o ajuste é a configuração `RECONCILIATION_DATE_TOLERANCE_DAYS`. Exceções como compensação no dia seguinte, na pergunta 51.
12. Diferença pequena de tarifa, juros ou IOF vira conciliação 1:N, N:1 ou parcial? Qual regra separa o que pode ser ligado do que precisa de lançamento?
   > **Resposta (contador 1, questionário de 05/11/2026):** "Depende da origem, mas quase sempre é despesa financeira." O caso pede um lançamento na conta de despesa financeira, não um vínculo parcial. Qual conta e quais exceções, na pergunta 52.
13. Quem aprova a conciliação quando o escritório tem uma pessoa só? Nesta fase, quem cria o caso não é impedido de aprová-lo; a barreira é o papel `approver`.
14. Qual é a diferença operacional entre rejeitar e ignorar? Os dois preservam a transação e tiram o caso da pendência de match. Rejeitar foi tratado como "não é este candidato" e ignorar como "não vou conciliar este movimento".
15. Quais bancos e quais versões reais de OFX o escritório recebe? O leitor aceita SGML 1.x e XML 2.x, com cp1252 quando o cabeçalho pede, mas layout de banco ainda não foi homologado.
16. Publicar o lançamento nascido do caso pode resolver o caso sem uma segunda aprovação de conciliação? A fundação assume que sim: a publicação é a aprovação humana, e o caso registra essa decisão.

## Decisões provisórias do piloto hospedado

17. Quem é o primeiro usuário administrador do escritório no ambiente hospedado, e esse usuário aceita MFA por aplicativo? O piloto usa um dyno para a API e outro para a interface, e não guarda documento de cliente real.
18. Qual plano de contas substitui o modelo mínimo de teste, e a empresa deve nascer com o ano corrente? O cadastro atual cria 12 contas sintéticas, incluindo `3.2.01 Lucros ou prejuízos acumulados`, e os 12 períodos do ano informado. Nenhuma delas é referencial.
19. Quais itens do checklist mudam por porte ou regime? A versão `2026.10-2` é a mesma para toda empresa.
20. A revisão do balancete pode ser feita por quem também publica, ou o escritório exige outra pessoa? Nesta fase, `approver` ou `admin` registra a revisão.
21. Qual é a retenção por tipo de documento, além da guarda até prescrição ou decadência (Código Civil, art. 1.194; CTN, art. 195, parágrafo único; Lei 9.430/1996, art. 37)?
22. O pacote precisa de outros relatórios além do balancete, dos lançamentos, da conciliação, dos lotes e dos documentos? Em que formato o escritório entrega hoje o balancete e o razão (PDF, Excel, papel), para quem, e quais demonstrações (DRE, Balanço) ele emite todo mês? Hoje o sistema imprime o balancete, o razão, a DRE e o Balanço pelo navegador e baixa CSV para o Excel, com o aviso de relatório gerencial. DRE e Balanço são gerenciais: os grupos são as contas raiz do plano, sem o layout oficial, que depende das perguntas 18 e 53 ([ADR 029](adr/029-encerramento-e-demonstracoes.md)).
   > **Resposta (contador 1, questionário de 05/11/2026):** "O ideal é ter todas as demonstrações contábeis sempre atualizadas conforme o regime de competência." DRE e Balanço Patrimonial entram como necessidade, além do balancete e do razão. Quando e para quais regimes, na pergunta 53.
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
   > **Resposta (contador 1, questionário de 05/11/2026):** "São zeradas e lançadas ao BP com prejuízo ou lucros acumulados." As contas de resultado zeram por um lançamento de encerramento, que leva o resultado ao patrimônio líquido. O balancete já mostra isso quando esse lançamento existe, porque soma os lançamentos publicados; falta a rotina de encerramento do exercício, que prepara o lançamento para alguém aprovar.
   >
   > **Implementado ([ADR 029](adr/029-encerramento-e-demonstracoes.md)):** no balancete de dezembro, o preparador gera o rascunho do encerramento, que zera receitas e despesas contra a conta do PL escolhida. Outro usuário aprova e publica. A forma do lançamento e o que bloqueia o encerramento continuam nas perguntas 55 e 56.

## Respostas recebidas

O [questionário anônimo](https://claude.ai/artifact/3QCemad8tRtHsfKse7f4W3) junta as respostas de mais de um contador. Cada resposta entra junto da pergunta, com a origem e a data. Uma resposta só é sinal de investigação: a ADR afetada continua `proposed` até a confirmação, e o código muda num PR próprio.

**Contador 1, 05/11/2026.** Respondeu às perguntas 1, 11, 12, 22 e 49, acima, e a duas perguntas de rotina:
- Sobre o regime que dá mais trabalho, disse que a pergunta é desnecessária: Lucro Real e Presumido dão trabalho de qualquer jeito. Ela saiu do questionário.
- Sobre o que precisa ficar provado para o cliente ou numa fiscalização, respondeu "Explicar". O detalhe vai na pergunta 54.

## Perguntas de seguimento

50. **CRC ativo.** Quais rotinas só um contador com CRC ativo pode fazer: aprovar lançamento, revisar o balancete, fechar a competência, assinar as demonstrações? O sistema deve guardar o número e a situação do CRC de cada usuário, e quem confere essa situação?
   > **Implementado em parte ([ADR 030](adr/030-signatarios-das-demonstracoes.md)):** cada pessoa do escritório cadastra no Perfil o CPF, a UF, o número e a categoria do CRC, e, se quiser, a certidão de regularidade e a validade. O admin escolhe, por empresa, o contador responsável e o representante legal. A DRE e o Balanço saem com as duas linhas de assinatura, na impressão e no CSV. O sistema não consulta o CRC e não bloqueia nada por falta de certidão (pergunta 57). Continua aberto se alguma rotina, além de assinar, fica reservada a quem tem CRC ativo.
51. **Data na conciliação.** A diferença de data zero vale também para cheque compensado, boleto ou transferência que cai no dia seguinte e venda no cartão? Quando a data difere, o caso fica sem sugestão ou recebe sugestão com aviso?
52. **Despesa financeira.** Que conta do plano recebe tarifa, juros e IOF? Quando não é despesa financeira (juros recebidos, IOF de uma operação específica)?
53. **Demonstrações atualizadas.** A DRE e o Balanço precisam estar disponíveis a qualquer momento do mês ou só depois do fechamento? Valem para todos os regimes, inclusive o Simples Nacional?
54. **Explicar.** O que precisa ser explicado, e para quem: cada lançamento até o documento de origem, as diferenças de conciliação, a variação de um saldo entre dois meses?
55. **Apuração do resultado.** O encerramento passa por uma conta de apuração do resultado (ARE) antes de chegar a lucros ou prejuízos acumulados, ou vai direto? Hoje o rascunho vai direto para a conta do PL escolhida. O saldo final é o mesmo; muda o que o razão mostra.
56. **O que bloqueia o encerramento.** Hoje qualquer lançamento do ano em rascunho, pendente ou aprovado impede gerar o encerramento, e dezembro precisa estar aberto. Basta isso, ou o fechamento de dezembro e a provisão de IRPJ e CSLL precisam estar concluídos antes? Resultado lançado depois do encerramento publicado gera um encerramento complementar, como na complementação da ITG 2000; isso serve ao escritório?
57. **Certidão de regularidade.** Hoje a DRE e o Balanço saem com o nome e o CRC do contador mesmo sem certidão de regularidade (a Certidão de Habilitação Profissional, CHP, da Resolução CFC 1.637/2021) informada ou com ela vencida, e a tela só mostra a validade no perfil e na tela de assinaturas. O escritório quer bloquear a impressão quando a certidão do responsável técnico não estiver válida, só avisar, ou deixar como está? Quem confere a certidão no site do CRC, e com que frequência?
58. **ECD hoje.** O manual da ECD já responde o leiaute, o prazo e o que impede a transmissão ([item 58 da pesquisa](#o-que-a-pesquisa-pública-já-responde-pesquisa-de-11112026)). Falta o que é do escritório. Em qual sistema ele gera a ECD hoje? Ele aceita importar a prévia ([ADR 031](adr/031-registry-minimo-e-previa-ecd.md)) numa base do PVA separada da base de produção e comparar os saldos do I155 e do J100/J150 com o arquivo do sistema atual? A prévia não é transmitida nem assinada.
   > **Resposta (escritório, arquivo de perguntas da ECD, 11/11/2026):** Domínio, Prosoft e Alterdata são os mais usados. O contador corrige o que o PVA aponta, ou um estagiário ou funcionário corrige e o contador revisa. Para comparar, o escritório importa os dois arquivos no PVA.
59. **Junta ou cartório.** O manual já diz como preencher a empresa sem NIRE e que a transmissão autentica o livro também para quem é registrado em cartório ([item 59 da pesquisa](#o-que-a-pesquisa-pública-já-responde-pesquisa-de-11112026)). Quantos clientes são sociedade empresária na JUCEPE e quantos são sociedade simples no cartório de pessoas jurídicas? Para a sociedade simples, que data de abertura vai em `I030.DT_ARQ`: a do registro no cartório ou a do CNPJ?
   > **Implementado ([ADR 031](adr/031-registry-minimo-e-previa-ecd.md)):** na tela da ECD, a empresa registrada em cartório vê o campo "Data de abertura" no lugar de "Data do arquivamento", e a data vai para o `I030.DT_ARQ`. A prévia aponta como bloqueio o NIRE que não começa pelo código da UF e aceita o CNPJ alfanumérico.
   >
   > **Resposta (escritório, arquivo de perguntas da ECD, 11/11/2026):** para empresa sem NIRE, o `I030.DT_ARQ` recebe a data de abertura do CNPJ, e a dica da tela passou a dizer isso. Quando a sociedade simples vira empresária, o `DT_ARQ_CONV` recebe a data em que a Junta arquivou a conversão. O escritório já teve cliente nessa situação, e a tela da ECD ganhou o campo opcional "Data da conversão" na Junta ([ADR 031](adr/031-registry-minimo-e-previa-ecd.md)). O escritório ainda não tem carteira de clientes para dizer quantos são de cada registro.
60. **Livros na JUCEPE.** A taxa de R$ 68,00 vale só para livro enviado direto à Junta, não para a ECD ([item 60 da pesquisa](#o-que-a-pesquisa-pública-já-responde-pesquisa-de-11112026)). Algum cliente autentica livros sociais ou o Diário na JUCEPE? Para os clientes do Simples que querem o Diário autenticado, o escritório prefere oferecer a ECD facultativa?
   > **Resposta (escritório, arquivo de perguntas da ECD, 11/11/2026):** hoje nenhum cliente autentica livro na JUCEPE. Para o cliente do Simples que precisar do Diário autenticado, o escritório prefere a JUCEPE, com a ECD facultativa como alternativa. O escritório confirma que o "Livro Digital" custa R$ 68,00 em 2026, que a JUCEPE cobra de novo quando o livro autenticado é retificado ou substituído e que o livro auxiliar fora do SPED paga o mesmo valor. Se um cartório de Recife ainda autentica o Diário de sociedade simples que não entrega ECD continua sem confirmação.
61. **Plano referencial.** O mapeamento é facultativo, e a prévia sem `COD_PLAN_REF` e sem I051 é válida ([item 61 da pesquisa](#o-que-a-pesquisa-pública-já-responde-pesquisa-de-11112026)). O custo de não mapear aparece na ECF. O escritório mapeia na ECD ou na ECF? Se mapeia na ECD, o vínculo fica num modelo de plano compartilhado ou em cada empresa, e quem o mantém?
   > **Resposta (escritório, arquivo de perguntas da ECD, 11/11/2026):** o escritório deixa o plano referencial em branco na ECD e mapeia só na ECF, como a prévia já faz. Quando mapear, o vínculo fica num modelo compartilhado entre as empresas, e qualquer pessoa com acesso de contador ou acima pode alterá-lo. Quem assina a ECD como responsável pela empresa é o sócio-administrador ou um procurador, com e-CPF, não o e-CNPJ.

## Perguntas da pesquisa de 11/11/2026

A [pesquisa de 11/11/2026](references/pesquisa-perguntas-contador-2026-11.md) respondeu a parte normativa de várias perguntas abertas. O que sobrou é carteira e política do escritório, e só o contador responde. As perguntas abaixo estreitam as que já existem; a pergunta de origem vai entre parênteses.

62. **Retenções na carteira** (34 e 38). Quantos clientes retêm IR, CSLL, PIS ou Cofins de terceiros por mês? Quem lança essas retenções hoje? O volume decide se a EFD-Reinf R-4000 serve ao piloto.
   > **Resposta (escritório, 11/11/2026):** o escritório ainda não tem carteira de clientes. Esta pergunta e a obrigatoriedade da ECD por cliente (regime, livro caixa no Presumido, lucro distribuído acima da base, investidor-anjo no Simples, inatividade) voltam quando houver carteira. Até lá, a escolha da obrigação do piloto (63) não tem o critério de volume.
63. **R-4000 ou outra obrigação** (38). A pesquisa pôs a EFD-Reinf R-4000 em primeiro lugar: o dado já está no razão, não depende de município e tem produção restrita oficial. Em segundo, uma prévia da ECF, sem transmissão. Diante da matriz rascunho, a R-4000 é a obrigação certa, ou o volume da carteira aponta para outra?
   > **Decisão provisória (usuário, 11/11/2026):** sem carteira para medir volume (62), a Fase E começou pela R-4000 como **prévia sem assinatura e sem envio** ([ADR 032](adr/032-previa-efd-reinf-r4000.md)). O escritório informa os pagamentos com retenção da competência; a prévia monta R-4010, R-4020 e R-4099, valida no XSD oficial e entrega um zip para conferência. O sistema não calcula imposto: guarda o que o escritório informa. A escolha continua aberta até o contador responder esta pergunta; se ele apontar outra obrigação, a POC fica como está e a Fase E segue pela escolhida. As dúvidas que a POC levantou estão na pergunta 77.
64. **Folga e prova de indisponibilidade** (41 e 44). A Receita não prorroga o prazo sozinha quando o sistema cai. Quantos dias antes do prazo legal o escritório transmite? O que ele guarda para provar que o serviço estava fora do ar?
65. **A1 em servidor ou A3 em nuvem** (45). O escritório usa certificado A1 guardado num servidor ou A3 em nuvem, com confirmação a cada assinatura? Quem renova, e com quanto tempo de antecedência?
   > **Resposta (escritório, arquivo de perguntas da ECD, 11/11/2026):** os certificados são A1 e A3 e ficam com o contador ou num bucket criptografado. O escritório quer manter o piloto sem assinar: o sistema não guarda certificado, não assina e não transmite. Guardar certificado no sistema seria decisão de segurança, com ADR própria. Quem renova continua sem resposta.
66. **Segunda aprovação** (47). Nenhuma norma exige que uma segunda pessoa aprove a transmissão. O escritório quer a segunda aprovação sempre, ou só acima de um valor? Que valor?
67. **Linha da DRE da despesa financeira** (52). Nenhuma norma fixa a linha. Em que linha da DRE ficam tarifa bancária, IOF sobre empréstimo, IOF sobre câmbio e multa sobre tributo?
68. **Subcontas por natureza fiscal** (52). A dedutibilidade não depende da linha da DRE. O escritório aceita subcontas que separem juros de mora sobre IRPJ e CSLL dos juros sobre outros tributos, e multa de mora de multa de ofício?
69. **CPC 51** (52). O CPC 51 substitui o CPC 26 (R1) a partir de 01/01/2027 e pede reapresentar 2026. O escritório quer adotar antes ou só em 2027? Que clientes ele atinge?
70. **CHP em pacote para terceiros** (57). Nenhuma norma obriga bloquear a demonstração por falta de CHP. Basta avisar quando a CHP do responsável técnico estiver vencida ao gerar o pacote para banco ou licitação? O escritório quer guardar também a CND do CRC?
71. **Registro ativo no CRC-PE** (50 e 57). O controle com base na ITG 2000 é o registro ativo de quem assina. Quem confere o registro na consulta do CFC, e com que frequência? O sistema não consulta o CRC sozinho.
72. **Histórico sugerido pela IA** (54). O histórico faz parte do lançamento (ITG 2000, item 6). Se a IA sugerir o texto, o escritório aceita que quem aprova o lançamento revise e aprove também o histórico, ou quer o histórico sempre escrito por uma pessoa?
73. **Responder no portal o que chega pelo WhatsApp** (27 e 28). Os concorrentes mandam o pedido também pelo WhatsApp. O escritório aceita conduzir a conversa do pedido no portal e responder lá o que chegar pelo WhatsApp? Se precisar de WhatsApp como canal, isso vira POC de integração, não código.
74. **Cadência por escritório** (28). Hoje a cadência dos lembretes é fixa. O escritório precisa escolher a própria cadência, por exemplo as datas de envio de cada pedido recorrente?
75. **"Não tenho este mês"** (24 e 31). O cliente pode avisar que não tem o documento naquele mês? O cliente não confirma nem encerra o próprio pedido, então o aviso só sinaliza: quem decide é o escritório, que cancela com motivo ou mantém aberto. Esse sinal serve?
76. **Fechamento travado por pedido** (24). Hoje um pedido aberto ou só recebido impede fechar a competência. Os concorrentes pesquisados só marcam a tarefa e não travam o fechamento. O escritório quer mesmo esse bloqueio?
77. **Prévia da EFD-Reinf: fato gerador, Simples e CSRF** (63). A prévia da R-4000 ([ADR 032](adr/032-previa-efd-reinf-r4000.md)) supôs três coisas, que aparecem como "Suposição" na tela:
    - **Data do fato gerador.** A prévia usa a data do pagamento como `dtFG`. Para o IR pago a pessoa jurídica, o fato gerador é o pagamento ou o crédito, o que vier primeiro; para a CSRF, é o pagamento (Manual do Usuário 2.1.2.1, p. 108). O escritório lança a despesa (o crédito) antes de pagar? Se sim, a prévia deve guardar a data do crédito à parte e usar a anterior das duas para o IR?
    - **Beneficiário do Simples Nacional.** A Lei 10.833/2003, art. 32, dispensa a retenção da CSRF no pagamento a optante do Simples. A pesquisa não confirmou em fonte primária a dispensa do IR na fonte para esse beneficiário. Como o escritório trata hoje o IR retido de prestador do Simples, e com base em que norma?
    - **CSRF agregada ou separada.** A prévia informa a CSRF agregada (`vlrBaseAgreg` e `vlrAgreg`, 4,65%). O leiaute também aceita CSLL, Cofins e PIS/Pasep em separado. Qual forma o escritório usa, e algum cliente retém só parte dos três tributos?

## O que as normas já respondem (pesquisa de 06/11/2026)

As regras abaixo são nacionais. O CRC-PE aplica as resoluções do CFC, e a pesquisa não achou regra própria de Pernambuco para estes pontos. Cada item diz o que a norma decide e o que continua sendo escolha do escritório. A pergunta continua aberta até o contador confirmar.

- **50, CRC ativo.**
  - **O que a norma diz:** as atribuições privativas do contador estão no Decreto-Lei 9.295/1946 (arts. 25 e 26) e na Resolução CFC 1.640/2021, que substituiu a 560/1983 ([CFC, prerrogativas](https://cfc.org.br/fiscalizacao-etica-e-disciplina/perguntas-frequentes/prerrogativas-de-contadores-e-tecnicos-em-contabilidade/)).
  - **CHP:** a Certidão de Habilitação Profissional comprova que o profissional está habilitado no CRC. Ela vale 90 dias, sai só pelo site do CRC de registro e tem código de segurança conferido no próprio site do CRC ([Resolução CFC 1.637/2021](https://www.normasbrasil.com.br/norma/resolucao-1637-2021_423756.html), em vigor desde 03/01/2022). Ela substituiu a Certidão de Regularidade Profissional (Resolução CFC 1.402/2012), que já tinha substituído a DHP (Resoluções CFC 871/2000 e 1.363/2011). A CND do CRC é outra certidão: prova que não há débito, não a habilitação. *Correção de 11/11/2026: a versão anterior deste item tratava a DHP como vigente.*
  - **Anexar à demonstração:** a pesquisa de 11/11/2026 não achou norma que obrigue a anexar a CHP à DRE ou ao Balanço. O CFC mantém uma [consulta cadastral pública](https://www3.cfc.org.br/SPW/ConsultaNacionalCFC/cfc), sem API documentada.
  - **O que falta decidir:** o sistema guarda o nome, a categoria e o número do CRC (por exemplo, CRC-PE) de quem assina? Quais rotinas internas, além de assinar as demonstrações, o escritório reserva ao contador?
- **51, data na conciliação.** Nenhuma norma contábil fixa tolerância de data entre o extrato e o lançamento. Compensação em D+1 de cheque, boleto ou cartão é prática bancária. A resposta é do escritório; a tolerância segue configurável.
- **53, demonstrações.**
  - **Microempresa e pequeno porte:** a ITG 1000 (Resolução CFC 1.418/2012, revista em 2022) exige balanço, DRE e notas explicativas ao fim de cada exercício, e intermediárias quando necessário ([CFC, ITG 1000](https://cfc.org.br/wp-content/uploads/2023/01/ITG-1000.pdf)).
  - **ECD no Simples Nacional:** o optante é dispensado de entregar a ECD (IN RFB 2.003/2021), salvo se recebeu aporte de investidor-anjo ou distribuiu lucro isento acima da base de cálculo ([Contábeis](https://www.contabeis.com.br/noticias/57172/ecd-veja-quem-esta-dispensado-da-entrega/)). A dispensa é da entrega, não da escrituração.
  - **O que falta decidir:** se o escritório quer DRE e Balanço todo mês ou só no fechamento anual.
- **55, apuração do resultado.**
  - **O que a norma diz:** nada obriga a conta transitória de Apuração do Resultado do Exercício (ARE). Ela é prática comum de ensino e de sistemas como Domínio, Omie e Senior. As receitas e despesas são zeradas contra a ARE, e o saldo dela vai para lucros ou prejuízos acumulados.
  - **ECD:** a ECD exige que o lançamento de encerramento seja marcado como tipo **E** no registro I200 e que os saldos das contas de resultado antes do encerramento estejam no registro I355 ([Vri, I200](https://vriconsulting.com.br/guias/guiasIndex.php?idGuia=678); [Alterdata, I355](https://ajuda.alterdata.com.br/x/DlzKAw)). Os dois caminhos atendem a isso.
  - **No sistema:** o encerramento vai direto para a conta do PL escolhida, tem origem `closing` (que corresponde ao tipo E), e a DRE sem o encerramento traz os saldos do I355.
  - **O que falta decidir:** se o escritório quer ver a ARE no razão.
- **56, o que bloqueia o encerramento.**
  - **O que a norma diz:** a ITG 2000 (R1) corrige lançamentos por estorno, transferência ou complementação. Lançamento extemporâneo, depois de transmitida a ECD, não pode ir para conta de resultado e precisa citar no histórico o motivo, a data e o lançamento de origem (itens 31 a 36) ([Alterdata, extemporâneos](https://ajuda.alterdata.com.br/bdcc/sped-ecd-tudo-o-que-voce-precisa-saber-sobre-lancamentos-extemporaneos-95068789.html)).
  - **Implementado:** um resultado lançado no ano depois do encerramento publicado gera um **encerramento complementar** ([ADR 029](adr/029-encerramento-e-demonstracoes.md)). Refazer continua possível por reversão.
  - **O que falta decidir:** o fechamento de dezembro deve estar concluído antes do encerramento? A provisão de IRPJ e CSLL precisa existir antes dele?
- **18, plano de contas.** A ECD liga cada conta analítica ao plano referencial da Receita Federal. A ITG 1000 de 2022 traz modelo de plano de contas para micro e pequenas. O modelo do contador continua sendo a referência; a pergunta segue aberta.

## O que a pesquisa pública já responde (pesquisa de 11/11/2026)

Os itens abaixo resumem a [pesquisa de 11/11/2026](references/pesquisa-perguntas-contador-2026-11.md), feita em fontes públicas, sem o contador. Fonte primária é norma, manual oficial ou página do órgão. Fonte secundária é blog de fornecedor, portal contábil ou fórum, e vai marcada. Dado que depende só de fonte secundária não vira regra no produto sem conferência no texto oficial. A pergunta continua aberta até o contador confirmar.

- **52, despesa financeira.**
  - **O que a norma diz:** nenhuma norma vigente fixa a linha da DRE de tarifa bancária, IOF ou multa sobre tributo. CPC 26 (R1), NBC TG 1000 e ITG 1000 não tratam disso. Tarifa como despesa financeira é opinião de fórum, não norma ([Fórum Contábeis](https://www.contabeis.com.br/forum/contabilidade/177783/taxa-aluguel-da-administradora-de-cartao/), secundária).
  - **CPC 51:** o CPC 51 (IFRS 18) substitui o CPC 26 (R1) a partir de 01/01/2027, cria a categoria "financiamento" e pede reapresentar os comparativos de 2026 ([Moore, set/2026](https://www.moore-global.com/wp-content/uploads/2026/09/Moore-IFRS-18-Guidance_160926_PORT.pdf); [ESN](https://escolasuperioresn.com.br/?p=11846)). *Secundária: o texto oficial do CPC 51 não foi lido.*
  - **Dedutibilidade:** a SD Cosit 1/2022 declara indedutíveis os juros de mora sobre IRPJ e CSLL, manda os juros seguirem a dedutibilidade do principal e trata multa fiscal como indedutível, salvo a de natureza compensatória ([Normas Legais](https://www.normaslegais.com.br/legislacao/solucao-de-divergencia-cosit-1-2022.htm)). Isso vale qualquer que seja a linha da DRE.
  - **No produto:** o vínculo conta → linha da DRE deve ser tabela versionada por exercício no registry, não constante do ledger.
  - **O que falta decidir:** perguntas 67 a 69.
- **54, explicar.**
  - **O que a norma diz:** a ITG 2000 (R1) vale para toda entidade, de qualquer porte. Ela exige histórico com a essência econômica e um identificador que ligue as partidas (item 6), referência ao documento probante no Diário (item 14) e documentação hábil (item 27). Correção só por estorno, transferência ou complementação, com motivo, data e lançamento de origem no histórico (itens 31 a 36) ([Normas Legais, ITG 2000](https://www.normaslegais.com.br/legislacao/itg-2000-r1-escrituracao-contabil.htm)). A cadeia linha da DRE → conta → lançamento → documento tem base normativa.
  - **Guarda:** o CTN, art. 195, parágrafo único, manda guardar livros e documentos até a prescrição dos créditos tributários ([Planalto, CTN](https://www.planalto.gov.br/ccivil_03/leis/l5172compilado.htm)). O Código Civil, art. 1.194, manda guardar enquanto não houver prescrição ou decadência, sem prazo em anos ([Jus.com.br](https://jus.com.br/artigos/87995/conservacao-da-escrituracao), secundária; o texto do Planalto não foi lido).
  - **O que falta decidir:** se a explicação vai além do piso da norma (variação de saldo, diferença de conciliação), para quem se explica (auditor, fiscal ou cliente) e a pergunta 72.
- **58, ECD hoje.**
  - **O que a norma diz:** o ano-calendário 2025 foi entregue no Leiaute 9 (`COD_VER_LC = 9.00`), pelo Manual de Orientação anexo ao ADE Cofis nº 01/2026, que vale "enquanto não editado e publicado novo leiaute" ([Manual ECD Leiaute 9, jan/2026](https://www.gov.br/sped/pt-br/assuntos/escrituracoes-digitais/ecd/manuais-e-documentos-tecnicos/manual_de_orientacao_da_ecd_leiaute_9_janeiro_2026.pdf/@@display-file/file)). O prazo é o último dia útil de junho do ano seguinte. Erro do PGE impede a transmissão; advertência não. A atualização de 2026 trouxe o CNPJ alfanumérico.
  - **Assinaturas:** toda ECD leva duas assinaturas ICP-Brasil, a do contador (código 900) e a de um responsável da empresa, que não pode ser o contador.
  - **O que falta decidir:** o software atual e a forma da comparação no PVA (pergunta 58). Nenhuma fonte oficial descreve comparar dois arquivos no PVA.
- **59, Junta ou cartório.**
  - **O que a norma diz:** sem registro na Junta, `0000.IND_NIRE = 0` e `I030.NIRE` em branco; o par diferente é erro do PGE. Sem NIRE, `I030.DT_ARQ` recebe a data de abertura da empresa, não uma data de arquivamento na Junta. Pelo item 1.26 do manual e pelo Decreto 9.555/2018, a ECD de quem não está no Registro do Comércio é autenticada pela transmissão, e o recibo dispensa outra autenticação, inclusive em cartório ([Manual ECD 2026](https://www.gov.br/sped/pt-br/assuntos/escrituracoes-digitais/ecd/manuais-e-documentos-tecnicos/manual_de_orientacao_da_ecd_leiaute_9_janeiro_2026.pdf/@@display-file/file); [Decreto 9.555/2018](https://www.contabeis.com.br/legislacao/4852235/decreto-9555-2018/)).
  - **O que falta decidir:** quantos clientes são de cada tipo e qual data de abertura usar, porque o manual não diz se é a do cartório ou a do CNPJ (pergunta 59).
- **60, livros na JUCEPE.**
  - **O que a norma diz:** pelo Decreto 8.683/2016 e pela IN DREI 82/2021, a ECD transmitida é a própria autenticação, e o recibo é o termo ([IN DREI 82 compilada](https://www.gov.br/empresas-e-negocios/pt-br/drei/legislacao/arquivos/legislacoes-federais/indrei822023_compilada.pdf/@@download/file)). Os R$ 68,00 do item 16.2 da JUCEPE valem só para livro enviado direto à Junta, como livros sociais e o Diário de quem não entrega ECD ([JUCEPE, tabela de preços](https://portal.jucepe.pe.gov.br/tabela-precos)). O valor vem da Portaria JUCEPE 017/2022, e não foi achado reajuste depois. *A confirmar num DAE atual.*
  - **ECD facultativa:** para o Simples, a ECD facultativa (IN RFB 2.003/2021, art. 3º, § 6º) autentica o Diário sem custo na Junta.
  - **O que falta decidir:** pergunta 60.
- **61, plano referencial.**
  - **O que a norma diz:** o mapeamento é facultativo (item 1.17 do manual). Sem mapeamento, `0000.COD_PLAN_REF` fica em branco e o I051 não é exigido. Com `COD_PLAN_REF` preenchido, o I051 vira obrigatório para todas as contas (`REGRA_I051_OBRIGATORIO`), e cada conta e centro de custo só tem uma conta referencial. Os códigos vão de 1 a 10; na carteira pequena, 1 (Lucro Real) ou 2 (Lucro Presumido) ([Manual ECD 2026](https://www.gov.br/sped/pt-br/assuntos/escrituracoes-digitais/ecd/manuais-e-documentos-tecnicos/manual_de_orientacao_da_ecd_leiaute_9_janeiro_2026.pdf/@@display-file/file)). A prévia atual está correta.
  - **Custo na ECF:** sem I051, a ECF recupera a ECD sem mapeamento, e o vínculo é feito no J051 ou a ECD é substituída ([Ajuda Alterdata/Prosoft](https://ajuda.alterdata.com.br/prosoftcontabil/c48-sped-ecf-como-corrigir-a-mensagem-nao-foi-encontrada-nenhuma-conta-referencial-j051-para-esta-conta-contabil-148472759.html)). Confirmado na fonte oficial: o [Manual da ECF, Leiaute 12](http://sped.rfb.gov.br/estatico/8E/318140FF63B0A8FA6F2392D85A0FF1D6973A81/Manual_ECF_Leiaute_12_28_04_2026_AC_2025_SIT_ESP_2026.pdf) (ADE Cofis 02/2026) diz no item 1.3 que a recuperação da ECD é obrigatória no Lucro Real, e também no Presumido e nas imunes ou isentas obrigadas à ECD. No item 1.6, diz que, sem mapeamento, a ECF traz os saldos mas não calcula o Balanço nem a DRE. O plano referencial é tabela versionada da Receita e pertence ao registry.
  - **O que falta decidir:** pergunta 61.
- **34 a 48, Fase E.** A pesquisa não conhece a carteira do escritório. Ela traz a mecânica de cada obrigação, para o contador confirmar em vez de montar do zero.
  - **Ranking do piloto:** a EFD-Reinf série R-4000, com a DCTFWeb só como conferência, é a única candidata com dado já no razão, sem dependência de município, com ambiente de teste sem efeito jurídico e com ciclo mensal. A produção restrita da Reinf recebe por webservice ([Manual do Desenvolvedor Reinf v2.8](https://www.gov.br/sped/pt-br/assuntos/escrituracoes-digitais/efd-reinf/manuais-e-documentos-tecnicos/manualorientacaodesenvolvedor-reinf-v2-8.pdf/@@display-file/file)). Em segundo lugar vem uma prévia da ECF, sem transmissão. PGDAS-D e NFS-e ficam atrás pelas mudanças de 2027. Não foi achado ambiente oficial de teste para PGDAS-D, DEFIS nem DCTFWeb. O ranking é insumo, não decisão: o volume depende das perguntas 62 e 63.
  - **Prazo da DCTFWeb:** último dia útil do mês seguinte ao fato gerador, pela IN RFB 2.248/2025 ([Jornal Contábil](https://jornalcontabil.com.br/noticia/contabilidade-e-prazos-dctfweb-dme-doi-e-ecd-sao-as-ultimas-obrigacoes-de-junho/), secundária; o texto da IN não foi lido). O prazo da R-4000 (dia 15) e os da EFD-Contribuições, da EFD ICMS/IPI e da DeSTDA em Pernambuco também vêm só de fontes secundárias.
  - **Recife:** a cidade adotou o Emissor Nacional da NFS-e pela Portaria SEFIN 42/2025 ([LegisWeb](https://www.legisweb.com.br/legislacao/?id=484107)) e consolidou as regras na Portaria 12/2026 ([Recife em Dia](https://recifeemdia.recife.pe.gov.br/sites/default/files/Portaria%20N%2012%2C%20de%2029%20de%20abril%20de%202026.pdf)). O ISS continua pago por DAM municipal.
  - **Contingência (44):** não há prorrogação automática quando o sistema cai. A Receita prorrogou em maio de 2025 ([RFB](https://www.gov.br/receitafederal/pt-br/assuntos/noticias/2025/maio/comunicado-receita-federal-informa-indisponibilidade-momentanea-no-sistema-de-emissao-de-documentos-de-arrecadacao)) e negou o pedido da Fenacon em fevereiro de 2026 ([Contábeis](https://www.contabeis.com.br/noticias/75331/receita-nao-prorroga-prazos-apos-instabilidade-no-e-cac/), secundária).
  - **Retificação (42):** na Reinf e no eSocial, a retificação usa `indRetif=2` e o `nrRecibo` do evento original. Sem o recibo guardado, a correção sai do sistema e vai para o e-CAC ([CAGE-RS](https://cage.fazenda.rs.gov.br/upload/arquivos/202605/18162359-orientac-a-o-retificac-a-o-de-eventos-ja-transmitidos-ao-ambiente-nacional-mas-que-na-o-possuem-a-informac-a-o-do-recibo-de-entrega-no-sistema-da-techne.pdf)). Guardar o recibo é requisito.
  - **Prova (43):** a Lei 8.218/1991, art. 11, manda manter arquivos digitais e sistemas pelo prazo decadencial, e o art. 12 traz multas de até 1% da receita bruta ([Planalto](https://www.planalto.gov.br/ccivil_03/leis/l8218.htm)). Um padrão defensável é no mínimo 5 anos a partir de 1º de janeiro do exercício seguinte, mais enquanto houver processo, parcelamento ou prejuízo a compensar. A extensão é do contador e do jurídico (pergunta 21).
  - **Quem transmite (47):** não foi achada exigência legal de CRC para transmitir obrigação federal, salvo a assinatura do contador na ECD e na ECF. A segunda aprovação da [ADR 004](adr/004-aprovacao-humana.md) é escolha do produto, não obrigação.
  - **Certificado e acesso (45):** o Integra Contador aceita A1 ou A3, de e-CPF ou e-CNPJ. A software house usa o próprio e-CNPJ e um Termo de Autorização em XML assinado pelo procurador, que gera um token válido até a meia-noite do dia seguinte ([SERPRO](https://apicenter.estaleiro.serpro.gov.br/documentacao/api-integra-contador/pt/solucoes/integra-contador-gerenciador/autenticaprocurador/)). Toda chamada é de produção e cobrada; o preço citado vem de fornecedores, e a tabela oficial do SERPRO não foi lida. ECD, ECF e EFD não passam pelo Integra Contador. *Não verificado:* a troca da procuração eletrônica pela "autorização de acesso" no e-CAC desde 05/12/2025 vem só de blogs.
  - **No produto:** `production_transmission` continua `false`. A POC da R-4000 em produção restrita, com dados fictícios, só começa depois da resposta à pergunta 62.
  - **O que falta decidir:** perguntas 34 a 48 e 62 a 66.
- **27 a 33, portal.** Nenhuma norma decide o portal. A pesquisa olhou só Omie.G-Click, Domínio/Onvio com Gestta e o site da Acessórias, e não achar um recurso não quer dizer que ele não existe.
  - **Mercado:** o pedido é cobrado por e-mail com link de upload. O G-Click deixa o cliente marcar "Não tenho este mês" e mantém pendências antigas visíveis ([Ajuda Omie](https://ajuda.omie.com.br/pt-BR/articles/15209365-omie-g-click-obrigacao-conhecendo-a-solicitacao-e-cobranca-automatica-de-documentos)). O Gestta deixa o escritório configurar as datas de envio dos e-mails ([TR FAQ Gestta, 2021](https://images.engage.es-pt.thomsonreuters.com/Web/LALEYSAEIMPRESORA/%7Bfa3be1a4-eadc-479b-a994-f9e425ce049d%7D_TAX_PROF_BR_PDF_PERGUNTAS_E_RESPOSTAS_Base.pdf), secundária). A Domínio e a Omie mandam arquivos pelo WhatsApp ([Domínio](https://suporte.dominioatendimento.com/central/faces/solucao.html?codigo=8693); [Ajuda Omie, Digisac](https://ajuda.omie.com.br/pt-BR/articles/15209592-omie-g-click-integrando-com-a-digisac-envie-arquivos-via-whatsapp)). Nenhum concorrente pesquisado limita a quantidade de arquivos nem trava o fechamento por pedido pendente.
  - **O que falta decidir:** perguntas 27 a 33 e 73 a 76. O limite de 10 arquivos da pergunta 29 é escolha própria, sem paralelo no mercado.

## Aditivo visual v0.7.0 — 06/11/2026

A renovação visual foi aplicada sem mudar o ciclo de fechamento, os dados sintéticos, os papéis ou os contratos. Na rodada com contador, observar especificamente: leitura da fila e dos estados loading/erro/vazio; localização do cliente/CNPJ e competência; leitura de D/C, saldos e diferença sem animação; foco por teclado na sidebar móvel e no painel de evidências; e legibilidade do portal sem menu do escritório. O verde continua acompanhado de texto/critério, e recebido, protocolo e aceite continuam distintos.

Este aditivo não cria rotina fiscal, relatório novo, endpoint, aprovação ou regra de negócio. API, RLS, segregação de funções, upload OIDC, impressão do balancete/razão e rastreabilidade permanecem os mesmos.
