# ADR 030 — Signatários das demonstrações

**Status:** proposed · **Data:** 8 de novembro de 2026

Decisão provisória. Ela responde em parte à pergunta 50 do [caderno](../accountant-discovery-workbook.md) e ainda depende da confirmação do contador.

## Contexto

A DRE e o Balanço gerenciais da [ADR 029](029-encerramento-e-demonstracoes.md) saem sem assinatura. Demonstração contábil é assinada pelo contador responsável, com nome, categoria e número no CRC, e pelo representante legal da empresa. A regularidade do contador é comprovada pela Certidão de Habilitação Profissional (CHP) da Resolução CFC 1.637/2021, em vigor desde 03/01/2022. Ela vale 90 dias e sai só pelo site do CRC de registro. A CHP substituiu a Certidão de Regularidade Profissional (Resolução CFC 1.402/2012), que por sua vez substituiu a DHP (Resoluções CFC 871/2000 e 1.363/2011). A pesquisa de 11/11/2026 não achou norma que obrigue a anexar a certidão à demonstração.

A ECD pede os mesmos dados no registro J930: pelo menos um signatário é o contador, com CRC, UF do CRC, certidão de regularidade e validade, e o representante legal assina com outro código. O manual do Leiaute 9 ainda chama o campo de "Certidão de Regularidade Profissional"; o número e a validade informados ali são os da CHP. Por isso as telas mantêm o nome "certidão de regularidade". A prévia da ECD (ADR 031, em outra frente) lê o mesmo cadastro.

O usuário decidiu que o CRC fica no perfil do contador e que cada empresa escolhe qual contador do escritório é o responsável técnico.

## Decisão

**Registro profissional (perfil)**
- Tabela `professional_registrations`, por escritório e por usuário (`tenant_id`, `user_id` únicos). Fica fora de `app_users`, que é global e sem RLS.
- Campos: CPF, UF do CRC, número do registro, categoria (`contador` ou `tecnico`), número da certidão de regularidade e validade, os dois últimos opcionais.
- `GET` e `PUT /v1/me/professional-registration`. Qualquer pessoa do escritório cadastra o próprio registro; o cliente da empresa recebe 403.
- O CPF passa pelos dígitos verificadores, a UF pela lista das 27, e o número segue o formato que o CRC imprime (`012345/O-8`). O sistema não consulta o CRC: o número e a certidão são declarados.

**Signatários da empresa**
- Tabela `entity_signatories`, uma linha por empresa: o contador escolhido (`accountant_user_id`) e o representante legal (nome, CPF e cargo).
- `GET /v1/legal-entities/{id}/signatories` abre para o escritório. `PUT` é só do admin.
- O contador precisa ser membro do escritório (não cliente), ter registro e ter categoria `contador`. Senão a resposta é 400. O técnico em contabilidade aparece na lista, mas não pode ser escolhido.
- O representante precisa de nome, CPF válido e cargo: sócio-administrador, administrador, diretor ou titular.
- Para quem não é admin, o CPF do representante sai mascarado (`***.456.789-**`). Só o admin recebe a lista de contadores com registro (`accountant_options`).
- As duas escritas passam por `Idempotency-Key` e gravam auditoria (`professional_registration_updated`, `entity_signatories_updated`). A trilha não guarda o CPF.

**Demonstrações**
- A DRE e o Balanço devolvem `signatories`: o contador com nome e legenda (`Contador, CRC-PE 012345/O`) e o representante com nome e cargo, ou `null`. O CPF não entra.
- A impressão termina com duas linhas de assinatura. O CSV traz a linha "Responsável técnico" no cabeçalho e o bloco "Assinaturas" no fim.
- Sem cadastro, a demonstração sai mesmo assim, com "Responsável técnico não cadastrado". Na tela aparece um aviso com o link para o admin definir as assinaturas.

**Leitura comum**
- `signatories/service.py` expõe `signatories_for(session, tenant_id, legal_entity_id)`, que a prévia da ECD usa no J930. A assinatura dela e os nomes dos dataclasses são contrato entre as duas frentes.

## Consequências

- **Certidão vencida não bloqueia:** a impressão não confere a validade da certidão. Bloquear ou não é a pergunta 57 do caderno.
- **Rotinas reservadas ao contador:** aprovar lançamento ou fechar competência continuam pelos papéis da [ADR 004](004-aprovacao-humana.md). Se alguma rotina passa a exigir CRC ativo é o resto da pergunta 50.
- **Troca de escritório:** o registro vale para o escritório em que foi cadastrado. Quem trabalha em dois escritórios ([ADR 022](022-troca-de-escritorio.md)) cadastra nos dois.
- **Contador e representante iguais:** o J930 não aceita o contador como responsável legal. Esta ADR não recusa o mesmo CPF nos dois papéis; essa conferência fica para a prévia da ECD.
- **Dados fictícios:** o seed e as amostras do piloto dão CRC-PE e CPF inventados aos usuários de teste. O CPF tem dígitos verificadores calculados (`seed/cpf.py`). A empresa vazia das amostras fica sem signatários, para mostrar o aviso.
