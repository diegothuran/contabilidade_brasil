# Roteiro de entrevista com o contador

Este roteiro é para quem conduz a conversa. O contador não precisa lê-lo. Ele organiza as perguntas abertas do [caderno do contador](accountant-discovery-workbook.md) pelo que cada resposta destrava e divide a conversa em três sessões. O texto completo de cada pergunta fica no caderno; aqui está só a forma de perguntar e a ordem.

O produto não decide regra contábil nem fiscal sozinho. Tudo o que depende do contador está como pergunta. Resposta "não sei" vira POC ou pergunta para outra pessoa, nunca código.

## Como perguntar

- **Peça um caso, não uma opinião.** "A última vez que um cliente mandou o extrato errado, o que você fez?" rende mais que "como deveria funcionar?".
- **Use uma competência já fechada.** Peça que ele abra o que fez naquele mês, com os dados anonimizados.
- **Mostre a tela.** Abra o piloto e faça o caminho junto. Ele reage melhor ao que vê do que a uma descrição.
- **Apresente a decisão provisória e peça um veredito.** Leia o que o piloto faz hoje e pergunte: confirma, muda ou retira? Quando mudar, pergunte o que ele faria no lugar e por quê.
- **Não sugira a resposta.** Evite "você concorda que...". Se ele hesitar, espere.
- **Anote a frase dele.** Quando o contador definir uma regra, anote as palavras que ele usou. A frase literal vira o texto da decisão no caderno.
- **Pergunte o tamanho.** Para cada dor, pergunte com que frequência acontece e quanto custa (tempo, multa, retrabalho).
- **Não peça nem aceite** XML real, certificado, senha, CPF de cliente ou planilha com dado real. Se ele quiser mostrar, peça que mostre na tela dele, sem enviar.

## Mapa do que depende dele

**Destrava** diz o que a resposta libera:
- **D**: fechar a Fase D;
- **E**: começar a Fase E;
- **Depois**: melhoria que pode esperar.

**Hoje** resume a decisão provisória que o piloto já usa ("—" quando não há nenhuma).

| Nº | Pergunta curta | Destrava | Onde a resposta entra | Hoje |
|---|---|---|---|---|
| 24 | Portal do cliente como está | D | [ADR 025](adr/025-portal-do-cliente.md) | cliente envia, escritório confirma |
| 25 | Ordem da fila de pendências | D | [ADR 024](adr/024-fila-de-pendencias.md) | por prazo, sem arquivo primeiro |
| 27 | Conversa no pedido | D | [ADR 026](adr/026-devolucao-e-conversa.md) | fora do pacote |
| 28 | Lembrete por e-mail | D | [ADR 028](adr/028-aviso-por-email.md) | 3 dias antes e depois do vencimento |
| 29 | Vários arquivos e devolução | D | [ADR 026](adr/026-devolucao-e-conversa.md) | até 10 arquivos, só aprovador devolve |
| 30 | Responsável designado no pedido | D | ADR nova | — |
| 31 | Pedido vencido | D | [ADR 024](adr/024-fila-de-pendencias.md) | segue aberto, gera aviso |
| 32 | Histórico de pedidos encerrados | D | [ADR 025](adr/025-portal-do-cliente.md) | cliente vê os dois e o motivo |
| 33 | Envio sem pedido | D | [ADR 027](adr/027-envio-sem-pedido.md) | escritório classifica |
| 34 | Carteira por regime | E | matriz do DISC-002 | — |
| 35 | UFs e municípios da carteira | E | matriz do DISC-002 | — |
| 36 | Obrigações entregues hoje | E | matriz do DISC-002 | — |
| 37 | Classificação de cada obrigação | E | matriz do DISC-002 | — |
| 38 | Obrigação do piloto | E | POC-007 | — |
| 39 | Entradas e pré-requisitos | E | POC-007 | — |
| 40 | Conferência antes de transmitir | E | POC-007 | — |
| 41 | Prazo legal e prazo interno | E | registry ([ADR 002](adr/002-registry-regulatorio-versionado.md)) | — |
| 42 | Rejeição e retificação | E | POC-007 | — |
| 43 | Prova guardada | E | POC-007 e retenção | — |
| 44 | Contingência | E | POC-007 | — |
| 45 | Certificado e procuração | E | POC-008 | — |
| 46 | Homologação ou parceiro | E | POC-007 | — |
| 47 | Quem transmite e quem aprova | E | [ADR 004](adr/004-aprovacao-humana.md) | — |
| 48 | Como ver a cobertura | E | POC-010 | — |
| 1 | Quem cria não aprova | Depois | [ADR 004](adr/004-aprovacao-humana.md) | sem exceção para escritório de uma pessoa |
| 2 | Dimensões obrigatórias | Depois | contrato do lançamento | opcionais |
| 3 | Conta sintética | Depois | plano de contas | não recebe lançamento |
| 4 | Fechamento com checklist | Depois | [ADR 020](adr/020-fechamento-com-evidencia.md) | checklist `2026.10-2` |
| 5 | Reverter em período fechado | Depois | [ADR 001](adr/001-ledger-immutavel.md) | reabre antes |
| 8 | Lote aprovado dispensa aprovar cada lançamento | Depois | importação | dispensa |
| 11 | Tolerância de data na conciliação | Depois | [ADR 013](adr/013-conciliacao-por-casos.md) | 3 dias |
| 13 | Conciliação com uma pessoa só | Depois | [ADR 013](adr/013-conciliacao-por-casos.md) | papel `approver` basta |
| 14 | Rejeitar e ignorar | Depois | [ADR 013](adr/013-conciliacao-por-casos.md) | dois sentidos distintos |
| 16 | Publicar resolve o caso | Depois | [ADR 013](adr/013-conciliacao-por-casos.md) | resolve |
| 19 | Checklist por porte ou regime | Depois | [ADR 020](adr/020-fechamento-com-evidencia.md) | um só |
| 20 | Revisão do balancete | Depois | [ADR 020](adr/020-fechamento-com-evidencia.md) | `approver` ou `admin` |
| 26 | Exportação basta | Depois | [ADR 023](adr/023-exportacao-operacional.md) | cabeçalho, até 200 itens |
| 6 | Layouts de migração | Depois | POC-002 | — |
| 7 | Retenção padrão | Depois | [ADR 011](adr/011-object-storage-s3.md) | `retention_pending` |
| 9 | Diferença aceitável na importação | Depois | POC-002 | — |
| 10 | Rollback de lote | Depois | POC-002 | não suportado |
| 12 | Tarifa, juros e IOF | Depois | POC-003 | — |
| 15 | Bancos e versões de OFX | Depois | POC-003 | — |
| 17 | Primeiro admin e MFA | Depois | piloto | — |
| 18 | Plano de contas real | Depois | [ADR 017](adr/017-cadastro-de-empresa.md) | modelo de 11 contas |
| 21 | Retenção por tipo de documento | Depois | [ADR 011](adr/011-object-storage-s3.md) | — |
| 22 | Relatórios do pacote e formato | Depois | [ADR 020](adr/020-fechamento-com-evidencia.md) | cinco relatórios; balancete e razão em impressão e CSV |
| 49 | Saldo anterior e zeramento no exercício | Depois | caderno, relatórios | acumula desde o primeiro lançamento |
| 23 | Assinatura ICP-Brasil | Depois | [ADR 020](adr/020-fechamento-com-evidencia.md) | não assina |

## Sessão 1 — validar o que o piloto já faz (60 minutos)

**Quando:** durante a [rodada da Fase D](accountant-discovery-workbook.md#rodada-da-fase-d) ou logo depois, com o piloto aberto.

**Bloco 1 — portal e pendências (25 min).** Perguntas 24, 25 e 27 a 33. Faça junto com ele o caminho de um pedido:
1. abrir;
2. o cliente envia;
3. devolver com motivo;
4. conversar;
5. o cliente reenvia;
6. confirmar.

Em cada passo, leia a decisão provisória e peça confirma, muda ou retira. Na 30, pergunte quem na equipe dele cuida de cada cliente hoje.

**Bloco 2 — a pergunta que fecha a Fase D (10 min).** Rode `python -m contabil.pilot_report` (comando no [roteiro do piloto](../deploy/pilot/README.md#empresas-de-teste)) e mostre o resultado: quem enviou, quantas devoluções, quantas mensagens. Pergunte, nesta ordem:
1. "Nesta rodada, alguma coisa foi pedida ou respondida fora do sistema?"
2. "O que você ainda anotaria numa planilha?"
3. "Com isso, você deixaria de usar a planilha de pendências?"

A resposta da terceira é o critério de saída da Fase D.

**Bloco 3 — razão, conciliação e fechamento (25 min).** Perguntas 1 a 5, 8, 11, 13, 14, 16, 19, 20, 26 e 49. Na 49, abra o Balancete e razão numa competência com saldo anterior, baixe o CSV na frente dele e peça que abra no Excel e imprima. Abra um lançamento, uma conciliação e um fechamento já feitos no piloto. Para cada regra, a pergunta é a mesma: "hoje o sistema faz assim; no seu escritório é assim?". Se o tempo acabar, as que sobrarem passam para a Sessão 3.

## Sessão 2 — escolher a obrigação do piloto (90 minutos)

**Quando:** depois da Sessão 1. Esta sessão é o card DISC-002 do [backlog de discovery](specs/06-discovery-and-poc-backlog.md). O objetivo é sair com uma obrigação escolhida e o fluxo dela descrito. O roteiro não sugere obrigação: quem nomeia é o contador.

**Bloco 1 — carteira (15 min).** Perguntas 34 a 36. Peça os números aproximados, não a lista de clientes. Para cada obrigação que ele citar, anote quem prepara, quem transmite, em que software e quanto tempo leva por cliente.

**Bloco 2 — classificar e escolher (20 min).** Perguntas 37 e 38. Escreva numa folha as obrigações que ele citou e peça que classifique cada uma em:
- indispensável no piloto;
- útil depois;
- dependente de parceiro;
- fora do produto.

Depois peça que escolha uma para o piloto. Se ele travar, ofereça critérios, e não respostas:
- volume por mês;
- custo de um erro (multa, retrabalho);
- existência de ambiente de teste;
- dependência de município;
- quanto da informação já está no razão.

**Bloco 3 — o fluxo da obrigação escolhida (35 min).** Perguntas 39 a 44. Peça que ele conte a última entrega dessa obrigação, do começo ao fim:
1. de onde vieram os dados;
2. o que precisava estar fechado antes;
3. o que conferiu;
4. quando transmitiu e o que voltou;
5. o que guardou.

Depois pergunte pela última vez em que deu errado: rejeição, retificação ou sistema do órgão fora do ar.

**Bloco 4 — acesso e segurança (20 min).** Perguntas 45 a 48. Fale de certificado e procuração sem pedir para ver nenhum. Pergunte quem no escritório pode transmitir e se ele aceitaria que o sistema transmitisse só depois da aprovação de uma segunda pessoa. Termine mostrando a ideia da matriz de cobertura e perguntando como ele gostaria de ver o que o sistema cobre e o que não cobre.

## Sessão 3 — o que pode esperar (30 minutos, opcional)

Perguntas 6, 7, 9, 10, 12, 15, 17, 18 e 21 a 23, mais as da Sessão 1 que não couberam. Nenhuma delas bloqueia a Fase D nem a Fase E. Vale fazer quando o contador tiver um exemplo à mão: um arquivo de migração, um OFX de banco, uma política de guarda.

## Folha de anotação

Use uma linha por pergunta. É esta folha que volta para o repositório.

| Nº | Resposta nas palavras dele | Veredito | Exemplo que ele citou | Pendência |
|---|---|---|---|---|
| | | confirma / muda / retira / não sabe | | |

Em **Veredito**, "muda" sempre leva a nova regra. "Não sabe" leva quem saberia responder. A folha não leva nome de cliente, CNPJ real nem valor.

## Depois da conversa

Com a folha preenchida:

1. A resposta de cada pergunta entra no [caderno](accountant-discovery-workbook.md), no lugar da decisão provisória.
2. A ADR afetada muda de `proposed` para `accepted` quando ele confirma. Quando ele muda a regra, a ADR ganha a nova decisão, e o código só muda depois, num PR próprio.
3. A matriz do DISC-002 é preenchida com as respostas 34 a 38, e a Fase E do [plano de implementação](specs/04-implementation-plan.md) passa a citar a obrigação escolhida.
4. Com a obrigação escolhida, o POC-007 ganha um card com o fluxo das perguntas 39 a 46, e o POC-008 com a resposta 45.
5. Toda resposta "não sei" vira pergunta na próxima sessão ou um card de POC. Nenhuma vira código.
