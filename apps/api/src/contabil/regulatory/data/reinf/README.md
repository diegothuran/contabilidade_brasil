# Dados da EFD-Reinf no registry (ADR 032)

## XSDs oficiais (`v2_01_02/`)

Os três arquivos desta pasta são cópia **sem modificação** de arquivos do pacote oficial
"XSD EFD-Reinf v2.1.2 - 23092026", publicado pela Receita Federal no portal do Sped:

- Página: https://www.gov.br/sped/pt-br/assuntos/escrituracoes-digitais/efd-reinf/documento-tecnicos/versao-atual/esquemas-xsd
- Download: https://www.gov.br/sped/pt-br/assuntos/escrituracoes-digitais/efd-reinf/documento-tecnicos/versao-atual/esquemas-xsd/xsd-efd-reinf-v2-1-2-23092026.zip/@@download/file
- Arquivo de origem: `XSD EFD-Reinf v2.1.2-23092026.zip`, 57.951 bytes,
  SHA-256 `ff878035d2b80fe435bb5bb48a8e863d44685aff7ffc9d88b7ba11bc207c2559`.
- Consulta: 11/11/2026.

| Arquivo | SHA-256 |
|---|---|
| `R-4010-evt4010PagtoBeneficiarioPF-v2_01_02.xsd` | `1117909497a6bcd93b0ce633aa51d793f075944bc1f85fcacafc9b28262fd357` |
| `R-4020-evt4020PagtoBeneficiarioPJ-v2_01_02.xsd` | `39da69e212d97dcb8f75e6c9fc8b41924eb461c4b2fcac18b14088d9f269793f` |
| `R-4099-evt4099FechamentoDirf-v2_01_02.xsd` | `d770a5cf3c6301477e8fafbc315a2ced23d89840730924143b61e6ba4c654a51` |

**Licença e atribuição.** O conteúdo do gov.br/sped é publicado sob a licença Creative Commons
Atribuição-SemDerivações 3.0 Não Adaptada (CC BY-ND 3.0, https://creativecommons.org/licenses/by-nd/3.0/deed.pt_BR).
Autoria: Receita Federal do Brasil, Sped. Os arquivos não foram editados; o `.gitattributes` os guarda byte a byte,
com o fim de linha CR+LF original. Para atualizar, troque os arquivos inteiros por outro pacote oficial e atualize
esta tabela. Não edite os XSDs (por exemplo, para tornar a assinatura opcional): isso seria obra derivada.

Os XSDs importam `./xmldsig-core-schema.xsd`, que o pacote oficial não traz.

## Schema auxiliar (`xmldsig-marcador-previa.xsd`)

Escrito do zero pela plataforma. Só declara um `Signature` vazio no namespace do xmldsig, para que a prévia valide
o evento contra o XSD oficial com um marcador de "não assinado" numa cópia em memória. Não valida assinatura.
O XML entregue no zip sai sem o marcador.

## Tabela 01 (`natureza-rendimentos.json`)

Recorte da Tabela 01 (Natureza dos Rendimentos) com os códigos usados pela prévia, com a fonte e a versão no
próprio arquivo. Não traz alíquota.
