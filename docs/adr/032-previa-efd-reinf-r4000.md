# ADR 032 — Prévia da EFD-Reinf R-4000

**Status:** proposed (POC) · **Data:** 11 de novembro de 2026

Prova de conceito. Ela não assina, não lê certificado, não monta lote e não transmite, nem à produção restrita. Depende da [ADR 002](002-registry-regulatorio-versionado.md) (regulatório como registry versionado), da [ADR 030](030-signatarios-das-demonstracoes.md) (signatários) e da [ADR 031](031-registry-minimo-e-previa-ecd.md) (registry mínimo e prévia assíncrona).

## Contexto

A Fase E pede uma obrigação fiscal piloto. A pesquisa de 11/11/2026 pôs a EFD-Reinf série R-4000 em primeiro lugar: o dado já existe no escritório, não depende de município e a Receita mantém um ambiente de produção restrita. O contador ainda não respondeu a [pergunta 63](../accountant-discovery-workbook.md) (R-4000 ou outra obrigação), e o escritório não tem carteira para medir volume (pergunta 62).

**Decisão provisória do usuário (11/11/2026):** a Fase E começa pela R-4000 como **prévia sem assinatura e sem envio**, até o contador responder a pergunta 63. O critério de pronto da Fase E muda para "os eventos da competência validam contra o XSD oficial, a cobertura aparece explícita e nada é assinado ou transmitido" ([plano](../specs/04-implementation-plan.md)).

Mesmo a produção restrita exige o certificado ICP-Brasil **do próprio CNPJ** declarado; o ambiente recusa certificado do representante legal e do procurador (Manual do Desenvolvedor 2.7, §8.1). Guardar ou usar certificado de cliente é decisão de segurança e fica para uma ADR futura. Por isso a prévia para na validação local.

Fonte técnica: nota de pesquisa `research_notes/EFD-Reinf R-4000/reinf_r4000.md` (fora do Git), com URL para cada afirmação.

## Decisão

**Pagamentos com retenção**
- A tabela `withholding_payments` (migração `0018_withholding_payments`) guarda, por empresa e competência: data do pagamento, tipo do beneficiário (`pj` ou `pf`), CNPJ ou CPF sem máscara, nome, natureza do rendimento (Tabela 01), valor bruto, base e valor do IR, base e valor da CSRF agregada (só `pj`) e descrição. Tem `tenant_id`, `FORCE ROW LEVEL SECURITY` e grant de `SELECT, INSERT, DELETE` para `contabil_app`. Os checks do banco repetem as regras simples.
- **O sistema não calcula imposto.** Guarda o que o escritório informa e confere a coerência em `withholdings/validators.py`:
  - CNPJ com `valid_cnpj` (aceita o alfanumérico) para `pj`; CPF com 11 dígitos e verificadores para `pf`;
  - natureza com 5 dígitos, presente no recorte da Tabela 01 e do mesmo tipo de beneficiário;
  - data do pagamento dentro da competência;
  - valores decimais em string, com até 2 casas, maiores que zero; valor retido ≤ base; valor sem base é recusado;
  - IR dispensado (até R$ 10,00) é base preenchida e valor vazio, como manda o Manual do Usuário 2.1.2.1, p. 87;
  - CSRF só em `pj` e só em natureza com AGREGADO na Tabela 01; no R-4010, base do IR ≤ bruto (regra do `vlrRendBruto`).
  - Nenhuma alíquota entra no código.
- Rotas: `GET /v1/legal-entities/{id}/withholding-payments?period_id=...` (qualquer papel do escritório), `POST` e `DELETE /v1/legal-entities/{id}/withholding-payments/{payment_id}` (preparer, approver e admin, com `Idempotency-Key`). Erro de campo responde 400 com `errors[].loc`. Competência fechada responde 409. O cliente da empresa recebe 403.
- A exclusão é física e responde 204 sem corpo; a idempotência grava e repete o 204 (`stored_response`). O CORS passa a aceitar `DELETE`.
- Auditoria: `withholding_payment_created` e `withholding_payment_deleted`, com tipo, natureza e valor bruto, **sem** CPF, CNPJ ou nome do beneficiário.

**Tabela 01 no registry**
- [`regulatory/data/reinf/natureza-rendimentos.json`](../../apps/api/src/contabil/regulatory/data/reinf/natureza-rendimentos.json) traz versão (`2026-01-15+NT04-2026`), fonte (zip de tabelas de 15/01/2026 e NT 04/2026) e só os códigos citados na pesquisa: PJ 15014, 15015, 15043, 15044, 15045, 15046 e 15099; PF 10002 e 13002. Cada item tem o tipo de beneficiário e a coluna Tributo, sem alíquota.
- `GET /v1/regulatory/reinf/natures?beneficiary_kind=pj|pf` devolve `{version, items: [{code, description, beneficiary_kind}]}` para o select da tela.

**XSD oficial sem modificação (CC BY-ND 3.0)**
- Os XSDs do R-4010, do R-4020 e do R-4099 foram copiados **byte a byte** do pacote oficial "XSD EFD-Reinf v2.1.2 - 23092026" (zip de 57.951 bytes, SHA-256 `ff878035d2b80fe435bb5bb48a8e863d44685aff7ffc9d88b7ba11bc207c2559`, conferido antes da extração) para [`regulatory/data/reinf/v2_01_02/`](../../apps/api/src/contabil/regulatory/data/reinf/README.md). O README da pasta traz a atribuição, a URL, o hash do zip e o hash de cada arquivo. O `.gitattributes` desliga a conversão de fim de linha desses arquivos, e um teste unitário confere os hashes.
- O conteúdo do gov.br/sped é publicado sob CC BY-ND 3.0: pode ser redistribuído **sem modificação**, com atribuição. Editar o XSD (por exemplo, para tornar a assinatura opcional) seria obra derivada. Isto não é parecer jurídico.
- Os XSDs de evento importam `./xmldsig-core-schema.xsd`, que o pacote não traz, e exigem `ds:Signature` depois do evento.
- **Validação da prévia:** `reinf_preview.py` valida com lxml (dependência de runtime `lxml>=5.2,<7`) uma **cópia em memória** de cada evento com um `<Signature xmlns="http://www.w3.org/2000/09/xmldsig#"/>` vazio, e um resolvedor troca o import do xmldsig por [`xmldsig-marcador-previa.xsd`](../../apps/api/src/contabil/regulatory/data/reinf/xmldsig-marcador-previa.xsd), schema auxiliar **próprio**, escrito do zero, que só declara o `Signature` e aceita qualquer conteúdo. O parser não acessa rede nem resolve entidades.
- O XML do zip sai **sem** a assinatura e sem o marcador. Por isso nenhum arquivo do zip passa no XSD oficial como está, e o LEIA-ME diz isso.

**Prévia**
- Reusa as exportações assíncronas da ADR 031. `POST /v1/legal-entities/{id}/exports` com `kind: reinf_r4000_preview_v1` e `period_id` cria a exportação e o evento `ReinfPreviewRequested`. O worker chama `run_reinf_preview`, guarda o zip como documento (`document_type = other`, `source_type = generated`, `application/zip`) e grava o resumo.
- `GET /v1/exports/{id}` devolve `{kind, period_id, competence, layout_version: "2.1.2", file_name, sha256, document_id, notice, transmittable: false, counts, checks, issues}`. `GET /v1/exports/{id}/file` baixa o zip.
- Eventos:
  - um **R-4020** por CNPJ de beneficiário, com um `idePgto` por natureza e um `infoPgto` por pagamento (MOU 2.1.2.1, p. 106). Valores em `vlrBruto` e em `retencoes` (`vlrBaseIR`, `vlrIR`, `vlrBaseAgreg`, `vlrAgreg`);
  - um **R-4010** por CPF, com `vlrRendBruto`, `vlrRendTrib` (a base do IR) e `vlrIR`;
  - um **R-4099** de fechamento (`fechRet = 0`) quando há ao menos um R-4010 ou R-4020. O `ideRespInf` vem do representante legal da ADR 030 (`signatories_for`); telefone e e-mail não estão no cadastro e viram pendência `warning`; sem representante ou sem CPF, o R-4099 sai sem `ideRespInf` e entra uma pendência `blocker`. Nada é inventado.
  - Sem pagamento na competência: pendência `blocker` `no_payments`, nenhum evento, e o zip só com o LEIA-ME.
- Campos fixos: `tpAmb = 2` (produção restrita, para nunca parecer arquivo de produção), `procEmi = 1`, `verProc = contabil-<versão>`, `indRetif = 1`, `tpInsc = 1`, `nrInsc` = raiz de 8 posições do CNPJ, `ideEstab` = CNPJ completo da empresa (centralizado na matriz). O nome do beneficiário não vai ao XML: o leiaute só aceita `nmBenef` quando não há CNPJ ou CPF.
- **Id do evento:** `ID` + `1` + raiz do CNPJ completada com zeros **à direita** até 14 posições + data e hora de Brasília (AAAAMMDDHHMMSS) + sequência de 5 dígitos. Segue o Anexo II (`REGRA_VALIDA_ID_EVENTO`), que manda usar a mesma inscrição do `ideContri/nrInsc`, e o padrão do XSD de 23/09/2026 (`ID[0-9][0-9A-Z]{14}[0-9]{19}`).
- Valores com vírgula decimal e duas casas (`10000,00`), como o XSD exige.
- O zip (`REINF-R4000-PREVIA-<cnpj>-<AAAAMM>.zip`) leva um XML por evento (`R-4010-001.xml`, `R-4020-001.xml`, ..., `R-4099-001.xml`) e o `LEIA-ME.txt`. A data dos arquivos do zip é a da geração, então o hash é reproduzível para o mesmo instante.
- `checks.xsd_valid` é verdadeiro só quando há evento e todos validam. Sem evento, é falso (nada foi validado). Cada erro do XSD vira pendência `blocker` `xsd_invalid` com a mensagem do lxml (até 5 por evento).
- `checks.ir_matches_ledger` é `null`: a conferência do IR retido com o razão fica fora, porque o plano mínimo não tem conta de IRRF a recolher (pendência `out_of_scope`).
- A prévia confere de novo cada pagamento gravado (não confia em dado gravado por seed, migração ou SQL). O que não passa fica fora dos eventos e vira pendência `blocker` (`nature_outside_table` para natureza fora do recorte; `payment_invalid` para o resto). Pagamento à própria empresa vira `warning`, porque o leiaute admite exceções. Base sem valor retido vira `warning` (`ir_not_withheld`, `csrf_not_withheld`).
- Pendências fixas: `assumption` para `dtFG` = data do pagamento, R-1000 já enviado, CSRF agregada, Simples Nacional não conferido e centralização na matriz; `out_of_scope` para a conferência com o razão e para assinatura, lote e envio.
- `fix` aponta onde corrigir: `withholding_payments`, `signatories`, `legal_entity` ou `null`.

**Amostras do piloto**
- `pilot_samples.py` grava três pagamentos fictícios (dois PJ e um PF, com CNPJ e CPF inventados e dígitos calculados) na competência corrente da empresa "em andamento" de cada catálogo, se a competência estiver aberta e ainda sem pagamento. Os valores são de exemplo e não derivam de alíquota.

## O que não foi conferido

- **A prévia não foi importada em nenhum programa da Receita nem enviada à produção restrita.** O XSD só confere a forma; as regras do Anexo II (`REGRA_VALIDA_BENEF`, `REGRA_EXISTE_INFO_CONTRIBUINTE` etc.) não foram executadas.
- O schema W3C real do xmldsig não foi testado; a validação usa o schema auxiliar.
- O Manual do Desenvolvedor 2.8 (28/08/2026) não foi lido; a regra da produção restrita (§8.1) é a da versão 2.7.
- As descrições da Tabela 01 vieram da nota de pesquisa, não da planilha oficial, e não foi baixada uma Tabela 01 posterior à NT 04/2026.
- O Anexo II lido (2.1.2b, 10/2025) ainda diz "completar com zeros à direita"; o comunicado de 23/09/2026 aceita também à esquerda. A prévia usa à direita, aceito pelas duas regras.
- A dispensa do IR na fonte para beneficiário do Simples Nacional não foi confirmada em fonte primária.
- A retenção de PIS e Cofins a partir de 2027 (EC 132/2023) não tem norma da EFD-Reinf publicada até 11/11/2026.

## Consequências

- **O que o contador ainda precisa decidir:** a pergunta 63 (R-4000 ou outra obrigação) e a pergunta 77 do [caderno](../accountant-discovery-workbook.md): data do crédito contra data do pagamento no `dtFG`, IR de beneficiário do Simples e CSRF agregada ou separada.
- **Uma versão nova do leiaute** troca os XSDs inteiros por outro pacote oficial, numa pasta com o namespace novo, e atualiza o README e os hashes. Os XSDs nunca são editados.
- **Fora da POC:** R-1000, R-4040, R-4080, R-9000, retificação (`indRetif = 2` com recibo), reabertura (`fechRet = 1`), lote, assinatura, certificado e transmissão. A `configs/product.yaml` mantém `production_transmission: false`.
- **Desvio do contrato combinado:** o contrato pedia o id com o CNPJ completo de 14 posições. A prévia usa a raiz de 8 posições com zeros à direita, porque o Anexo II manda o id usar a mesma inscrição do `nrInsc`. O XSD aceita as duas formas; a forma da API e da tela não muda.
