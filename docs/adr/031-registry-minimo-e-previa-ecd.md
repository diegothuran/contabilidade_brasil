# ADR 031 — Registry mínimo e prévia da ECD

**Status:** proposed (POC) · **Data:** 8 de novembro de 2026

Prova de conceito. Ela não transmite, não assina, não lê certificado, não preenche o I051 e não monta a ECF. Depende da [ADR 002](002-registry-regulatorio-versionado.md) (regulatório como registry versionado), da [ADR 029](029-encerramento-e-demonstracoes.md) (encerramento e demonstrações) e da [ADR 030](030-signatarios-das-demonstracoes.md) (signatários).

## Contexto

A ECD é a próxima entrega fiscal de valor para o escritório. Os sistemas do mercado (Alterdata, Omie, Domínio, TOTVS) geram o .txt do leiaute, e o contador importa esse arquivo no PVA da Receita, que valida, assina e transmite. Nenhum deles transmite sozinho.

O repositório proíbe leiaute fiscal escondido no código antes da decisão do contador. Por isso a ECD entra como **prévia não transmissível**, e o leiaute fica como dado versionado.

A ECD é federal; não há leiaute estadual. O que muda por estado é o cadastro. Em Pernambuco, a UF é PE e o código IBGE do município começa com 26 (Recife é 2611606). O NIRE da JUCEPE também começa com 26. Clínicas e escritórios registrados em cartório de pessoas jurídicas não têm NIRE.

## Fonte normativa (B0)

O leiaute foi transcrito do **Manual de Orientação do Leiaute 9 da ECD**, anexo ao ADE Cofis nº 01/2026, atualização de maio de 2026, baixado do portal SPED em 8/11/2026 ([pasta](http://sped.rfb.gov.br/pasta/show/1569), [item](http://sped.rfb.gov.br/item/show/7990)). O portal recusou HTTPS no dia; o download foi por HTTP, e o SHA-256 do PDF está no dado. As tabelas vieram do arquivo Word da mesma versão e foram conferidas por amostragem contra o PDF.

**Conferido no manual oficial**
- `I010.COD_VER_LC = 9.00`. O valor 10.00 só aparece nos exemplos do I012, por erro do próprio manual. Isso explica a divergência entre as fontes secundárias.
- Arquivo em ISO-8859-1 (Latin-1). Cada linha começa com `|`, cada campo termina com `|` e a linha termina em CR+LF.
- Número com vírgula decimal, sem separador de milhar e sem sinal; data em ddmmaaaa. O manual cita a troca de vírgula por ponto entre o sistema contábil e o PVA como causa típica de ECD substituta. O escritor grava os valores com duas casas e vírgula (1234567,80), e o saldo credor sai sem sinal, com o indicador C; o teste `test_ecd_preview_fields.py` confere os dois casos.
- Sem NIRE (sociedade simples em cartório), o 0000 sai com `IND_NIRE = 0` e o I030 com o NIRE vazio; NIRE preenchido com `IND_NIRE = 0`, ou vazio com `IND_NIRE = 1`, é erro no PVA. Os dois primeiros dígitos do NIRE são os da UF do 0000.
- O `I030.DT_ARQ` de empresa sem NIRE é a **data de abertura** da empresa, não uma data de arquivamento na Junta. O escritório usa a data de abertura do CNPJ, não a do registro no cartório (resposta de 11/11/2026), e a dica da tela diz isso. O `DT_ARQ_CONV` é a data em que a Junta arquivou a conversão de sociedade simples em empresária. O escritório confirmou em 11/11/2026 que já teve cliente nessa situação, e o cadastro passou a guardar a data (`conversion_date`, migração `0017_ecd_conversion_date`).
- Campos, ordem, tipo, tamanho, decimais e obrigatoriedade de 0000, 0001, 0007, 0990, I001, I010, I030, I050, I052, I150, I155, I200, I250, I350, I355, I990, J001, J005, J100, J150, J900, J930, J990, 9001, 9900, 9990 e 9999.
- J930: pelo menos um signatário com código 900 e um diferente de 900; um só com `IND_RESP_LEGAL = S`, e nunca o 900. Com 900, `IND_CRC`, `EMAIL`, `FONE` e `UF_CRC` vazios são erro; `NUM_SEQ_CRC` e `DT_CRC` vazios são advertência.
- O 0007 é obrigatório no Diário completo (G); o código 00 diz "nenhuma inscrição em outras entidades".
- J100 e J150 com linha de detalhe exigem I052 com o mesmo código de aglutinação numa conta analítica. O J100 tem exatamente duas linhas de nível 1 (A e P); o J150 tem uma só, totalizadora.
- O bloco C não é importado: o PVA o preenche a partir da ECD anterior.
- O manual de janeiro de 2026 já aceita o CNPJ alfanumérico da IN RFB nº 2.229/2024: 12 caracteres em [0-9A-Z] e 2 dígitos verificadores numéricos, pelo módulo 11 com valor = código ASCII − 48. O `CNPJ` do 0000 e do I030 é tipo C de 14 posições no dado, então o escritor não muda.

**Não conferido (`unverified` no dado)**
- A importação no PVA (abaixo).
- Se o 9999 entra no `QTD_LIN_9`. O manual diz só "linhas do bloco 9"; a prévia conta o 9999.
- O formato do `IND_CRC`. O manual só traz o exemplo `1SP123456`; a prévia grava a UF e o número do registro, sem o prefixo `CRC-`.
- A correspondência entre o cargo do representante e o `COD_ASSIN`, e a natureza das contas por tipo. São decisões do produto, não do manual.
- A tabela das 27 UFs ([ufs.json](../../apps/api/src/contabil/regulatory/data/ufs.json)) não foi conferida na página do IBGE nesta POC.

## Decisão

**Registry mínimo**
- O leiaute fica em [`regulatory/data/ecd/leiaute-9.json`](../../apps/api/src/contabil/regulatory/data/ecd/leiaute-9.json). Ele traz a fonte, a data de consulta, a vigência (`valid_from_year = 2020`), as constantes, a estrutura dos blocos, as tabelas de código e as obrigatoriedades condicionais.
- `regulatory/registry.py` carrega as versões e escolhe a do ano-calendário pela vigência. Se duas cobrem o ano, vale a mais recente.
- `regulatory/writer.py` serializa os registros a partir do dado, sem `if` por campo fiscal. O que não cabe no leiaute vira `Violation`: campo obrigatório vazio, tamanho, casas decimais, caractere proibido e as regras condicionais do J930.

**Dados da escrituração**
- A tabela `ecd_registrations` (migração `0016_ecd_registration`) guarda, por empresa: UF, município IBGE, `registry_kind` (`junta` ou `cartorio`), NIRE, a data do I030.DT_ARQ (`registry_date`), a data do I030.DT_ARQ_CONV (`conversion_date`, opcional), situação especial e número do livro.
- `registry_date` é uma coluna só, com sentido que depende do registro (ADE Cofis nº 01/2026): na Junta é a **data do arquivamento** dos atos constitutivos; no cartório, sem NIRE, é a **data de abertura** do CNPJ. A tela troca o rótulo pelo registro escolhido e, no cartório, explica que a ECD usa a data de abertura quando não há NIRE. A recusa de data futura usa o mesmo nome. Não houve migração.
- `conversion_date` só existe na Junta: a sociedade simples que virou empresária passou a ter NIRE. No cartório a API recusa a data, e a tela só mostra o campo quando o registro é Junta. Data futura também é recusada. A ordem entre `registry_date` e `conversion_date` não é conferida, porque o manual não fixa essa regra.
- As validações seguem as regras do manual:
  - os dois primeiros dígitos do município são os da UF (`REGRA_COD_MUN_INV_UF`);
  - os do NIRE também (`REGRA_NIRE_UF`);
  - Junta exige NIRE de 11 dígitos e cartório não tem NIRE (`REGRA_CAMPO_OBRIGATORIO_NIRE`).
- `GET` e `PUT /v1/legal-entities/{id}/ecd-registration`. Qualquer papel do escritório lê; só o admin grava. Cada gravação gera um evento de auditoria (`ecd_registration_created` ou `ecd_registration_updated`).

**Prévia**
- `regulatory/ecd_preview.py` monta o ano a partir do razão:
  - **0000, 0007, I010 e I030** vêm do cadastro e da empresa, com `COD_PLAN_REF` vazio. Sem o plano referencial, o I051 não é exigido.
  - **I050 e I052** vêm do plano de contas. A natureza vem do tipo da conta, o nível vem do `parent_id`, e a conta lançável é analítica (A) com o próprio código como código de aglutinação.
  - **I150 e I155** trazem os saldos mensais, com o cálculo do balancete.
  - **I200 e I250** trazem os lançamentos publicados e revertidos. O encerramento (`source_type = closing`) vira tipo **E**; o resto, **N**.
  - **I350 e I355** trazem os saldos de resultado antes do encerramento, iguais aos da DRE.
  - **J100 e J150** reaproveitam o Balanço e a DRE gerenciais. Os grupos são as contas raiz.
  - **J930** usa os signatários da ADR 030.
- O arquivo sai marcado como prévia no nome (`ECD-PREVIA-<cnpj>-<ano>.txt`, com o CNPJ como está gravado, numérico ou alfanumérico) e na natureza do livro (`DIARIO GERAL - PREVIA NAO TRANSMITIR`, no I030 e no J900). A tela e a resposta trazem o aviso fixo "Prévia para conferência no PVA. Não transmitir."
- `issues` lista o que falta, com severidade (`blocker`, `warning`, `assumption`, `out_of_scope`) e onde corrigir:
  - cadastro ausente, contador ou representante ausente;
  - cadastro gravado que fura a regra do NIRE: Junta sem NIRE, cartório com NIRE ou NIRE que não começa com o código da UF do 0000 (`REGRA_NIRE_UF`). A gravação já recusa esses casos; a prévia confere de novo porque não confia em dado gravado por seed, migração ou SQL. O `IND_NIRE` sai da presença do NIRE, então o par `IND_NIRE`/`NIRE` é sempre coerente no arquivo;
  - conta sem natureza, ano sem encerramento publicado e lançamento pendente no ano;
  - as violações do leiaute;
  - o que fica fora: I051, I012/I015, bloco K, DLPA/DMPL e bloco C;
  - os valores assumidos. O 0000 assume situação inicial normal, escrituração original, não grande porte, sem SCP, moeda funcional N, não consolidada e centralizada; o 0007 sai 00.
- Antes de devolver, a prévia confere o próprio texto:
  - cada I200 fecha com os seus I250;
  - no I155, inicial + débitos − créditos = final;
  - o I355 soma o resultado da DRE;
  - no J100, ativo = passivo + PL no início e no fim;
  - o 9900, os encerramentos de bloco e o 9999 batem com as linhas.
- Se uma conferência falha, entra uma pendência `blocker`.

**Geração assíncrona**
- `POST /v1/legal-entities/{id}/exports` com `kind: ecd_preview_v1` e `fiscal_year` cria a exportação e o evento `EcdPreviewRequested` no outbox. A exportação guarda a última competência do ano como referência.
- O worker chama `run_ecd_preview`. Ele guarda o .txt no storage como documento (`document_type = other`, `source_type = generated`) e grava na exportação `{file_name, sha256, document_id, issues, checks, counts, result}`.
- `GET /v1/exports/{id}` devolve esse resumo, e `GET /v1/exports/{id}/file` baixa o arquivo.
- Pedem a prévia preparer, approver ou admin; o viewer recebe 403.

**CNPJ alfanumérico**
- A validação central (`tenancy/service.py`, `valid_cnpj`, com o cálculo em `seed/cnpj.py`) aceita o CNPJ alfanumérico pelo algoritmo oficial: tira a máscara, passa letras para maiúscula e exige 12 caracteres em [0-9A-Z] seguidos de 2 dígitos. O CNPJ numérico tem o mesmo resultado de antes. O exemplo `12.ABC.345/01DE-35` foi conferido com essa implementação; ele está nos testes `test_cnpj.py` e `test_ecd_preview_fields.py`, que também levam o CNPJ ao 0000, ao I030 e ao nome do arquivo.
- A coluna `legal_entities.cnpj` já é `String(14)`; não houve migração. Fica para depois: a máscara da tela (`formatCnpj`) e do CSV (`cnpj_br`) só formata CNPJ de dígitos e mostra o alfanumérico sem máscara; a busca de empresa da barra compara só os dígitos.

## Validação no PVA

**Pendente.** O PVA da ECD não estava instalado no ambiente da POC. Por isso a importação **não** foi feita, e a prévia **não** está aprovada.

O critério de sucesso continua o do plano: gerar a prévia da Empresa Alfa de 2026, importar o .txt no PVA e anotar aqui cada erro como esperado (falta conhecida) ou defeito (corrigir).

Erros esperados, pelo que a prévia já lista:
- `EMAIL` e `FONE` do contador vazios (`REGRA_OBRIGATORIO_CONTADOR`), porque o cadastro da ADR 030 não tem esses campos;
- o J930 sem o representante, quando a empresa não tem signatários;
- o I350/I355 ausentes, quando o ano não tem encerramento publicado.

## Consequências

- **Uma regra nova do leiaute** vira um arquivo novo em `data/ecd/`, com outra vigência, sem mudar o escritor.
- **O que o contador ainda precisa decidir:**
  - perguntas 58 a 61 do [caderno](../accountant-discovery-workbook.md);
  - o plano referencial e o I051, na pergunta 18;
  - o layout da Lei 6.404 nas demonstrações, na pergunta 53.
- **Fora da POC:** transmissão, assinatura, certificado e ECF. A `configs/product.yaml` mantém `production_transmission: false`, e o validador do repositório recusa outro valor.
- **CORS:** a API passa a aceitar `PUT`, que a rota do cadastro usa.
