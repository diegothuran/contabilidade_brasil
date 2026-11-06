# Verificação — renovação visual Rastro v0.7.0

Verificação local em 06/11/2026, sobre a main `88ac9fe336cf1dce0f80005d246823b8637ada07`. A alteração combina a skill própria de handoff com melhorias aplicadas em `apps/web`. Não modifica a API de negócio, migrações, autenticação, papéis, RLS, precisão monetária ou fluxo de upload. A descrição do OpenAPI foi atualizada sem mudar seu contrato.

## Resultados executados

| Verificação | Resultado | Alcance |
|---|---|---|
| Testes unitários da API | 70 passaram; zero falhas, erros ou skips | Testes locais já existentes, sem infraestrutura externa |
| Contratos da fundação e handoff | 17 passaram | Schemas, fixtures, extrator, paths seguros, identidade e rastreabilidade |
| `validate_specs.py` | Aprovado | Nove schemas, fixtures e invariantes contábeis |
| `check_internal_links.py` | Aprovado | Links internos Markdown |
| Validador OpenAPI | Aprovado | Estrutura do contrato HTTP |
| `pyflakes src` da API | Aprovado | Análise estática |
| `npm run typecheck`, `npm run lint`, `npm run build` | Aprovados, incluindo a configuração isolada de Playwright | Frontend e testes TypeScript |
| `git diff --check` | Aprovado | Integridade básica do diff |
| Validador da skill | Aprovado | Frontmatter e estrutura de recursos |
| `npm run e2e:visual` | Quatro testes passaram em 10,1 s na execução final | Chromium local, API e sessão fictícias, com servidor dedicado iniciado e encerrado pelo Playwright |
| Descoberta das suítes | 6 testes em 5 arquivos na configuração integrada; 4 em 1 arquivo na visual | Os testes de acabamento não foram descartados: possuem configuração e job próprios |

Os quatro testes de navegador verificam o acabamento e estados em desktop e 390px sem rolagem horizontal da página; saída normal do foco da sidebar no desktop; contenção e restauração de foco no menu móvel e painel de evidências, com Escape; ausência de animação no painel com movimento reduzido; representação de `1.234,50 D` e `1.234,50 C` e scroll estático do razão; e portal do cliente sem sidebar ou seletor de competência do escritório. As capturas revisadas usam somente organizações e pessoas fictícias.

Durante a revisão foram corrigidos o seletor ambíguo do botão de fechar a navegação, um ciclo de Tab que não podia valer para o desktop, o reaparecimento do botão móvel pela cascata CSS e o anúncio de filtros comuns como abas ARIA sem o comportamento completo de abas. Nenhuma correção altera decisões contábeis ou permissões.

## Correção encontrada na primeira CI do PR

A primeira CI passou em **API/contratos/documentação**, **Interface** e **Integração no compose**. O job de navegador também tentou executar os quatro testes sintéticos contra o servidor do compose, configurado com Keycloak real de testes, em vez do OIDC fictício usado por suas fixtures; os quatro não chegaram às telas esperadas.

A correção separa ambientes, sem mudar a autenticação da aplicação nem afrouxar asserts. `playwright.config.ts` mantém os seis testes integrados. `playwright.visual.config.ts` executa os quatro de acabamento com servidor dedicado em `127.0.0.1:5174`, API interceptada e OIDC fictício. O workflow adiciona o job **Acabamento visual sintético**, que executa todos os quatro; não é um skip, `continue-on-error` ou substituição dos E2E com Keycloak. Os testes visuais isolados, lint, tipos e build foram reexecutados localmente e passaram.

O resultado da nova execução remota deve ser conferido no PR; uma execução local não equivale a esse resultado. A falha inicial fica registrada, não apagada nem apresentada como aprovação.

## Reproduzir após o checkout do PR

```bash
cd apps/web
npm ci
npx playwright install chromium
npm run e2e:visual
```

O Playwright inicia e encerra seu próprio Vite sintético. Não precisa de servidor manual, banco, Keycloak ou credenciais do piloto; não reutiliza um servidor já rodando. Para usar Chromium instalado, definir `PLAYWRIGHT_EXECUTABLE_PATH`.

As capturas são escritas em `apps/web/test-results/visual-refresh`, fora do Git. Para outro destino, definir `RASTRO_VISUAL_OUTPUT`. O HTML da CI fica em `apps/web/playwright-report-visual`, também ignorado pelo Git e anexado como artefato **playwright-visual**.

`npm run e2e` continua destinado ao compose com suas dependências de testes, conforme o workflow existente. Não usar dados nem configurações do piloto para qualquer suíte.

## Limites

Os doze casos de eval em `eval-cases.json` continuam `not_run`: a suíte cobre aspectos de alguns casos, não seus oracles completos. A rodada local não executou Postgres/RLS e object storage reais, a suíte ligada ao compose, o comportamento da skill no Claude, acessibilidade com usuários ou performance produtiva. A impressão e o CSV foram preservados no diff, sem uma nova regressão completa de impressão. Os jobs da primeira CI acima são resultados remotos distintos da rodada local.

Os testes sintéticos de navegador não autenticam usuários reais nem provam isolamento server-side. Não houve deploy, acesso ao piloto hospedado, escrita em banco ou storage externos, emissão de documento, publicação de journal, transmissão fiscal ou aprovação material. A publicação permanece em branch de PR para revisão do usuário.
