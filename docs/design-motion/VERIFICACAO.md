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
| `npm run typecheck`, `npm run lint`, `npm run build` | Aprovados | Frontend e testes TypeScript |
| `git diff --check` | Aprovado | Integridade básica do diff |
| Validador da skill | Aprovado | Frontmatter e estrutura de recursos |
| Playwright do acabamento | Quatro testes passaram | Navegador Chromium local, respostas da API e sessão estritamente sintéticas |

Os quatro testes de navegador verificam o acabamento e estados em desktop e 390px sem rolagem horizontal da página; saída normal do foco da sidebar no desktop; contenção e restauração de foco no menu móvel e painel de evidências, com Escape; ausência de animação no painel com movimento reduzido; representação de `1.234,50 D` e `1.234,50 C` e scroll estático do razão; e portal do cliente sem sidebar ou seletor de competência do escritório. As capturas revisadas usam somente organizações e pessoas fictícias.

Durante a revisão foram corrigidos o seletor ambíguo do botão de fechar a navegação, um ciclo de Tab que não podia valer para o desktop, o reaparecimento do botão móvel pela cascata CSS e o anúncio de filtros comuns como abas ARIA sem o comportamento completo de abas. Nenhuma correção altera decisões contábeis ou permissões.

## Reproduzir após o clone

Os testes usam uma instância Vite **local dedicada**, com OIDC fictício e sem URL de API de produção. Não execute com variáveis do piloto ou com dados de clientes.

No primeiro terminal:

```bash
cd apps/web
npm ci
VITE_OIDC_AUTHORITY=http://synthetic.invalid \
VITE_OIDC_CLIENT_ID=rastro-visual \
VITE_API_URL= VITE_RASTRO_DEMO=true \
npm run dev -- --host 127.0.0.1 --port 5173
```

No segundo terminal:

```bash
cd apps/web
npx playwright install chromium
npx playwright test e2e/visual-refresh.spec.ts --workers=1
```

As capturas são escritas em `apps/web/test-results/visual-refresh`, fora do Git. Para utilizar Chromium já instalado, pode-se definir `PLAYWRIGHT_EXECUTABLE_PATH`; para outro diretório de capturas, `RASTRO_VISUAL_OUTPUT`.

## Limites

Os doze casos de eval em `eval-cases.json` continuam `not_run`: a suite local cobre aspectos de alguns casos, mas não comprova seus oracles completos. Não foram executados os testes de integração contra Postgres/RLS e object storage, a suite ponta a ponta ligada ao compose, a avaliação comportamental da skill dentro do Claude, uma validação de acessibilidade com usuários ou uma medição de performance em produção. A impressão e o CSV foram preservados no diff, mas não receberam nesta rodada uma nova execução completa de regressão de impressão.

Os testes sintéticos de navegador não autenticam usuários reais nem provam isolamento server-side. Não houve deploy, acesso ao piloto hospedado, escrita em banco ou storage externos, emissão de documento, publicação de journal, transmissão fiscal ou aprovação material. A publicação deve permanecer em branch de PR até a revisão do usuário.
