# Inventário estático do frontend Rastro

**Escopo histórico:** commit `88ac9fe336cf1dce0f80005d246823b8637ada07` — leitura estática de `AGENTS.md`, `docs/rastro/SPEC.md`, `docs/adr/018-uma-casca-visual.md`, CSS e componentes pertinentes antes da adoção v0.7.0. A seção histórica abaixo preserva os achados originais; o bloco final registra o que foi reconciliado no runtime da renovação. Dados e capturas da execução permanecem sintéticos e fora do Git.

## Síntese de identidade

**Rastro** é uma sala de fechamento contábil orientada a trabalho, exceções e evidência: escritório → empresa/CNPJ → competência → estado do fechamento. A identidade observada é sóbria e operacional: papel azul muito claro, superfícies brancas, tinta azul-marinho, azul Rastro para ação/contexto, e cores semânticas discretas para atenção, perigo, informação e conclusão. A voz de interface é em português, com vocabulário de fechamento, pendência, fonte, hash, reconciliação, aprovação e protocolo; o produto deve sempre permitir voltar à fonte e saber quem decidiu.

A assinatura visual normativa está em `docs/rastro/SPEC.md:77-85`: `--ink-900: #162536`, `--blue-rastro: #1f5c86`, `--paper: #f5f8fb`, `--surface: #ffffff`, `--line: #dfe7ee`, semântica `#2f80ed / #b7791f / #b84048 / #2f855a`, Inter para interface e Newsreader/Georgia para títulos, raios 10/8/999 e motion 140–180ms. **Não tratar o verde/bege legado de `styles.css` como identidade Rastro, nem copiar paleta ou timings de Paralaxe.** Não houve pesquisa externa nem uma superfície Paralaxe foi usada como fonte desta análise.

## `observado_estatico`

### 1. Cascata e tokens efetivos

- Histórico: `apps/web/src/rastro/rastro.css:3-34` definia a casca efetiva sob `.rastro`, mas `--info` era `#2876c5`, divergente do contrato `#2f80ed`.
- A casca usa Inter via import externo e fallback (`rastro.css:1,30-34`); Newsreader/Georgia aparece em headings e números de pacote (`rastro.css:46,57,146` e vários componentes). O carregamento real da fonte não foi verificado.
- A estrutura visual é uma casca única: sidebar fixa de 260px, workspace deslocado, topbar sticky e barra de contexto (`rastro.css:54-119`, `RastroShell.tsx:249-383`). O menu, contexto e rotas seguem ADR 018 (`docs/adr/018-uma-casca-visual.md:11-25`).
- Há raios efetivos variados: painel 11px, métrica 10px, controles 7px, company-current 8px, badges 999px (`rastro.css:102,125,134,143,159`). Isso se aproxima, mas não é literalmente 10/8/999 em todos os casos da spec.
- `apps/web/src/styles.css:1-132` ainda define globalmente o desenho antigo verde/bege (`#0f6e56`, `#f3efe6`, `#fffdf8`, raios 6/12). Como várias páginas live/portal usam `<table>`, `<button>`, `<input>` e classes `secondary` sem o wrapper `.routine` ou classes Rastro (`OfficeHome.tsx:105-157`, `DocumentsPage.tsx:87-183`, `PortalPage.tsx:97-218`), a cascata global ainda participa dessas superfícies. O `rastro.css` importado no `App.tsx:5` e em `RastroShell.tsx:24` encapsula a casca, mas não normaliza todos os controles não classificados. Estados de erro/carregamento fora de `.rastro` também caem no CSS legado (`App.tsx:129-149`).
- Histórico: havia topbar translúcida com blur e gradientes sutis, divergentes da diretriz anti-ornamento.

### 2. Motion real e responsividade

- Não há `@keyframes` nem animação contínua encontrada. As transições reais são: navegação `150ms ease` (`rastro.css:70`), botões `150ms ease` com leve `translateY(-1px)` no hover (`rastro.css:125-126`) e abertura da sidebar móvel `160ms ease` (`rastro.css:186`). Estão dentro do movimento normativo Rastro de 140–180ms; não introduzir timings de outra marca.
- `prefers-reduced-motion` reduz transições/animações para `1ms` e desliga smooth scrolling CSS (`rastro.css:189-190`). Porém `TrialBalancePage.tsx:96-100` chama `scrollIntoView({ behavior: "smooth" })` em JavaScript; estaticamente não há guarda explícita de reduced motion para essa chamada. Runtime não foi verificado.
- Breakpoints efetivos: `1180px` (oculta/reativa meta de contexto, estreita grids e 2 colunas para IA/integrações), `960px` (sidebar 230px, grids principais em uma coluna, stack lateral de duas, listas roláveis), `760px` (sidebar off-canvas, scrim, workspace full-width, contexto em grid, métricas 2 colunas e cards empilhados, drawer full-width) e `420px` (tipografia/espacamentos reduzidos) (`rastro.css:184-187,226-233`). Existem overrides tardios em `226-230` que reexibem `context-meta`, status e `context-link` no mobile depois de regras anteriores os ocultarem; a ordem final do arquivo é a regra efetiva estática.
- A impressão do balancete/razão remove sidebar/topbar/contexto/botões e mantém heading, empresa, CNPJ, competência, emissão e disclaimer (`rastro.css:319-340`, `TrialBalancePage.tsx:24,55-61,163-216`).

### 3. Semântica, foco e teclado

- Há bons fundamentos: `main`, `aside`, `nav`, `header`, labels de formulário, tabelas de dados, texto além da cor em badges e estados, `role="status"` para demo/toast e `role="dialog" aria-modal="true"` no painel de evidência (`RastroShell.tsx:252,286,338-350,352-360,745-775`).
- O drawer é a melhor referência para handoff: guarda foco anterior, move foco para fechar, fecha com Escape, restaura foco e implementa loop de Tab (`RastroShell.tsx:745-765`). Não há foco/trap/Escape equivalente para a sidebar móvel (`RastroShell.tsx:252-340`). O fundo também não recebe `inert`/`aria-hidden` quando o drawer está aberto; o diálogo estático está correto, mas a experiência completa não foi validada com tecnologia assistiva.
- Foco visível existe para `button`, `select` e `a` (`rastro.css:189`) e busca tem foco próprio (`rastro.css:109`). Não há regra geral equivalente para `input`/`textarea`; controles sem `.routine` dependem do navegador/CSS global. `CompanySearch` implementa busca enquanto digita, aproximação, acentos/CNPJ e setas/Enter/Escape (`CompanySearch.tsx:18-145`, `companyMatch.ts:6-102`), mas não usa `aria-activedescendant` para o item ativo.
- A barra de progresso usa `aria-label` no `div`, mas não `role="progressbar"`/valores (`RastroShell.tsx:499-500`). Breadcrumb usa `div` rotulado, não uma lista/nav semântica (`RastroShell.tsx:341-345`). São melhorias de handoff, não mudanças de identidade.

### 4. Estado, contexto e semântica de domínio

- O contexto live vem de `SessionProvider` e `LiveContextBar` (`App.tsx:96-165`, `session.tsx:27-45`, `LiveSurface.tsx:91-136`), com empresa/CNPJ selecionada ao lado da busca, competência e estado. A busca fuzzy é implementada estaticamente (`CompanySearch.tsx:77-145`). A demo é deliberadamente separada: `RastroShell` inicia `companyId="orbe"`, `period="01/2025"` e mantém estado local; o banner avisa que não grava efeitos reais (`RastroShell.tsx:167-195,352-381`). Isso preserva a distinção sistema/demonstração exigida por `SPEC.md:59-61,118-120`.
- Hoje live lê fila do escritório, documentos sem pedido e lançamentos da empresa selecionada (`OfficeHome.tsx:52-67,91-157`); a fila troca empresa/competência via `sessionStorage` e reload (`OfficeHome.tsx:25-30`). A ação primária é encaminhar para pendência e o balancete tem atalho, coerente com `SPEC.md:65-71`.
- Fechamento live bloqueia fechar enquanto há itens pendentes, exige motivo para “não aplicável”, preserva referência/decisor/snapshot e oferece pacote (`CloseRunPage.tsx:47-110,122-203`). Balancete usa strings/`BigInt`, explicita D/C, diferença, seleção de conta e razão abaixo (`TrialBalancePage.tsx:26-42,102-126,152-284`). Isso é domínio contábil material a preservar, não decoração.
- Evidências live tem exportação assíncrona e estados textuais em fila/gerando/pronto/falhou (`DocumentsPage.tsx:24-29,50-67,87-124`), mas a lista de documentos não explicita loading/error/empty nem usa a barra de competência para o campo de competência do upload (`DocumentsPage.tsx:40-49,126-182`). A spec pede contexto único e estados planejáveis (`SPEC.md:69,87-89`); registrar como lacuna, não inventar UI.
- O portal do cliente é uma superfície de papel distinta e sem menu do escritório, com escritório, razão social/CNPJ, pedidos, prazos, histórico, upload sem pedido, conversa e Sair (`PortalPage.tsx:97-218`, `SPEC.md:122-128`). É correto não misturar journal/balancete/fechamento no handoff do portal. A implementação ainda usa controles/tabelas globais sem classes Rastro; o upload sem pedido limpa o formulário mas não invalida explicitamente a query de pedidos (`PortalPage.tsx:48-58`), portanto atualização imediata da lista é runtime não verificada.
- `LiveSurface.tsx:140-171` e os adaptadores (`adapters/index.ts:25-137`) descrevem endpoints/fallbacks live, mas `RastroShell.tsx:384-412` renderiza diretamente páginas de rotina e `PlannedPage`; `LiveSurface` não é o conteúdo dessas rotas. Isso deve ser tratado como superfície de integração/futuro, não como estado visual comprovado.

## `proposto`

Uma skill/handoff visual próprio do Rastro deve preservar:

1. **Casca única e hierarquia:** sidebar de escritório, topbar/breadcrumb, barra global com empresa/CNPJ e competência, área de trabalho em papel, sem segundo menu ou fundo.
2. **Identidade Rastro:** `#162536`/`#1f5c86`, papel `#f5f8fb`, superfícies brancas, linhas frias, Inter + Newsreader, sombras discretas e controles compactos. Não reutilizar o verde/bege legado como direção, nem importar paleta/timings de Paralaxe.
3. **Movimento contido:** apenas transições de interação entre 140–180ms (os atuais 150/160ms são referência), sem keyframes decorativos; manter reduced motion e corrigir o scroll suave em JS para respeitá-lo.
4. **Trabalho contábil e rastreabilidade:** pendência bloqueadora, competência, débito/crédito, diferença, reconciliação como sugestão, journal imutável, origem preservada, hash/snapshot, ator/horário/motivo, e “enviado” separado de protocolo/recibo. Verde nunca deve ser apenas cor.
5. **Estados e papéis:** loading, vazio, erro, sem permissão e frescor/fonte; IA só como sugestão/revisão/aprovação/reversão; integrações/obrigações sem contrato permanecem explicitamente vazias; demo sempre sintética e local.
6. **Superfícies responsivas e acessíveis:** tabelas com leitura móvel, foco visível em todo controle, teclado na busca/drawer/sidebar, labels e semântica de progresso/dialog; manter impressão específica do balancete e razão.
7. **Fronteira do portal:** branch visual e vocabular própria para cliente, sem menu do escritório, competência/empresa selecionável ou linguagem de ledger.

### Boas superfícies iniciais para o handoff

- **Hoje:** melhor âncora de composição: responde o que bloqueia, em qual empresa/competência, prazo e próximo passo; combina fila, lançamentos recentes, atalho de balancete e contagem de envios sem pedido (`OfficeHome.tsx:91-157`).
- **Evidências:** demonstra a tese do produto — documento original, hash, exportação assíncrona, estado textual e drawer lateral de rastreabilidade (`DocumentsPage.tsx:87-183`, `RastroShell.tsx:745-775`).
- **Balancete e razão:** superfície de precisão contábil, com números sem float, D/C, diferença, busca, drill-down, impressão e CSV (`TrialBalancePage.tsx:26-42,128-284`).
- **Portal:** bom segundo fluxo para provar que a mesma marca suporta outro papel sem misturar domínio; preservar pedidos, prazo, arquivo, histórico, conversa e aviso por e-mail, sem importar a navegação do escritório (`PortalPage.tsx:97-218`).

## `runtime_nao_verificado`

Não foram verificados: carregamento real de fontes Google; ordem/deduplicação dos imports em bundler; respostas API, cache/invalidação e sincronização de empresa/competência; comportamento real nos breakpoints; contraste renderizado; foco em leitor de tela; scroll JS sob reduced motion; impressão em navegador; limites de dez arquivos/conversa; existência de dados reais; nem qualquer efeito externo. O relatório é exclusivamente estático e usa somente caminhos/linhas de código e contratos locais.

## Referências principais

- `docs/rastro/SPEC.md:59-120,122-155`
- `docs/adr/018-uma-casca-visual.md:5-27`
- `apps/web/src/rastro/rastro.css:1-190,226-340`
- `apps/web/src/rastro/RastroShell.tsx:167-435,745-775`
- `apps/web/src/rastro/OfficeHome.tsx:52-160`
- `apps/web/src/rastro/LiveSurface.tsx:91-171`
- `apps/web/src/rastro/CompanySearch.tsx:18-145`
- `apps/web/src/App.tsx:26-167` e `apps/web/src/styles.css:1-132`
- `apps/web/src/pages/DocumentsPage.tsx:31-185`, `TrialBalancePage.tsx:65-287`, `PortalPage.tsx:41-220`, `CloseRunPage.tsx:51-206`

## Adoção v0.7.0 — runtime reconciliado

- `apps/web/src/styles.css` agora é uma base Rastro compartilhada: elimina a paleta bege/verde legada de controles live/portal, normaliza tipografia, superfícies, raios, tabelas e foco.
- `rastro.css` usa `--info #2f80ed`, card 10px e controles 8px; topbar não usa blur e os efeitos de entrada de painel/toast são contidos em 160ms.
- `App.tsx`, `OfficeHome.tsx` e `DocumentsPage.tsx` exibem estados de carregamento, erro e vazio com texto; `PortalPage.tsx` recebe layout responsivo, tabs semânticas e controles legíveis sem adicionar menu do escritório.
- `RastroShell.tsx` contém foco/Escape/restauração na sidebar móvel, equivalente ao drawer de evidências. `TrialBalancePage.tsx` respeita `prefers-reduced-motion` no `scrollIntoView`.
- A precisão de dinheiro, D/C, hashes, impressão e contratos permanece lógica existente; não há count-up, interpolação ou `requestAnimationFrame` no front.
