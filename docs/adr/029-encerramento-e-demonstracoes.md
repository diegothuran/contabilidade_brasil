# ADR 029 — Encerramento do exercício e demonstrações gerenciais

**Status:** proposed · **Data:** 6 de novembro de 2026

Decisão provisória. Ela se apoia na resposta de um contador só (perguntas 22 e 49 do [caderno](../accountant-discovery-workbook.md)).

## Contexto

O balancete acumula o saldo desde o primeiro lançamento. Sem um lançamento de encerramento, janeiro abre com receitas e despesas carregando o ano anterior.

O contador respondeu que as contas de resultado "são zeradas e lançadas ao BP com prejuízo ou lucros acumulados". Ele também quer as demonstrações sempre atualizadas por competência. Antes deste ADR, DRE e Balanço não existiam.

## Decisão

**Encerramento**
- `POST /v1/legal-entities/{id}/year-end-closing` monta um **rascunho** em 31/12, com `source_type = closing`. Só preparer ou admin podem chamar a rota.
- O rascunho zera cada conta de receita e de despesa com saldo e leva a diferença para a conta do patrimônio líquido escolhida a cada encerramento. O plano modelo traz `3.2.01 Lucros ou prejuízos acumulados`.
- O lançamento segue o fluxo normal (ADR 004): enviar, aprovar e publicar, e quem criou não aprova. Nada é publicado pela rotina.
- A rotina recusa nestes casos:
  - há lançamento do exercício em rascunho, pendente ou aprovado;
  - já existe encerramento do ano que não foi rejeitado nem revertido;
  - as contas de resultado estão zeradas;
  - dezembro está fechado.
- Para refazer o encerramento, o usuário reverte o lançamento e gera outro.
- O saldo considerado vai até 31/12 e inclui exercícios anteriores não encerrados. Nesse caso, a resposta avisa.
- `POST /v1/journals` recusa `source_type = closing`. O balancete não muda de cálculo: o saldo volta a zero porque o lançamento existe, e não por uma regra de exibição.

**Demonstrações gerenciais**
- **DRE:** `GET /v1/legal-entities/{id}/income-statement` mostra o mês e o acumulado do ano.
  - Exclui o encerramento e a reversão dele. Assim, a DRE de dezembro continua mostrando o resultado depois do encerramento.
- **Balanço:** `GET /v1/legal-entities/{id}/balance-sheet` mostra o saldo no fim da competência.
  - Enquanto o exercício não é encerrado, o resultado aparece no PL na linha "Resultado do exercício não encerrado".
  - A conferência devolve `ativo − (passivo + PL)`.
- **Linhas:** os grupos são as contas raiz do plano da empresa, pelo `parent_id`, e só aparecem contas com valor.
- **Exportação e aviso:** as duas têm CSV, como o balancete, e o aviso "Não é livro contábil oficial".

## Consequências

- **Layout oficial:** o layout da Lei 6.404 (circulante e não circulante, linhas da DRE) depende do plano de contas real e fica para as perguntas 18 e 53.
- **Passagem pelo encerramento:** se ela usa uma conta de apuração do resultado ou vai direto para lucros acumulados é a pergunta 55. O que bloqueia o encerramento é a pergunta 56.
- **Empresas existentes:** a migração `0014_closing_source` amplia a check constraint de `journal_entries.source_type`. As empresas criadas antes dela não ganham a conta `3.2.01` automaticamente. O admin cria a conta em Plano de contas.
