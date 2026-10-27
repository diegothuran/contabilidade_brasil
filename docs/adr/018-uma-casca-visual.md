# ADR 018 — Uma casca visual

**Status:** proposed · **Data:** 25 de outubro de 2026

## Contexto

A sala de fechamento e as rotinas do razão conviviam em dois desenhos. A sala usava a barra azul, o papel e a barra de contexto. As rotinas abriam um segundo menu, com outro fundo e outro seletor de empresa. No piloto, com a demonstração ligada, a barra de contexto listava a empresa fictícia Orbe e não as empresas do escritório.

O [ADR 016](016-frontend-separado.md) já tinha colocado as duas superfícies no mesmo serviço de interface. Faltava decidir que elas são a mesma tela.

## Decisão

Depois do login há uma casca só: a sala descrita em [docs/rastro/SPEC.md](../rastro/SPEC.md).

- A barra lateral é o menu do produto: Hoje, Fechamentos, Pendências, Balancete, Conciliação, Migrações, Dados e ledger, Revisões de IA, Obrigações e entregas, Evidências, Integrações, Rotinas do razão e Administração.
- A barra de contexto lista as empresas do escritório e as competências dessa empresa. Trocar a empresa troca o `legal_entity_id` usado pelas rotinas. O seletor da Orbe fica só na rota de demonstração.
- Fechamentos, conciliação, migrações, lançamentos, evidências, balancete, plano, bancos e auditoria abrem dentro dessa casca. Onde ainda não há contrato — revisões de IA, obrigações, conectores e administração — a mesma casca diz isso, sem inventar estado.
- A caminhada sintética da Orbe continua em `/app/rastro/demonstracao` enquanto `VITE_RASTRO_DEMO` não for `false`. Ela não é o contexto de trabalho e não grava lançamento.
- As rotas antigas (`/app/journals` e vizinhas) continuam, renderizadas na mesma casca, para não quebrar link já publicado.

## Consequências

Não existe segunda navegação. Um item do menu não devolve o usuário ao desenho anterior.

A demonstração deixa de ocupar Hoje. Quem entra vê a empresa selecionada e os lançamentos dela. Regime e UF só aparecem na demonstração, porque o cadastro da empresa ainda não guarda esses campos.

Publicar esta decisão é uma mudança de interface. A API não muda.
