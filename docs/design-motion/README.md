# Rastro — reaproveitar conceito e movimento

O Rastro já possui sua própria linguagem: fechamento com evidência, casca de trabalho, contexto de escritório/empresa/competência, papel claro, tinta/azul, Inter e Newsreader. A adaptação mantém essa identidade; traz da abordagem anterior somente o processo **fonte visual → motion map → revisão → código**, não a paleta, os componentes de recrutamento ou a stack da Paralaxe.

A base histórica consultada é `88ac9fe336cf1dce0f80005d246823b8637ada07`. O [contrato de interface](../rastro/SPEC.md) é v0.7.0 e o aplicativo usa React/Vite com API FastAPI separada. A adoção v0.7.0 modifica apenas a apresentação do frontend e sua acessibilidade; não modifica API, domínio, estado material, autorização ou dados do piloto.

## Arquivos e uso

A skill de projeto está em [SKILL.md](../../.claude/skills/rastro-visual-handoff/SKILL.md). No Claude Code, após os arquivos serem aplicados na raiz:

```text
/rastro-visual-handoff
Leia a SPEC vigente, o CSS e os componentes do Rastro.
Comece por Hoje e evidências, com dados fictícios.
Preserve identidade, contexto e estados reais da API.
Entregue inventário, motion map e handoff antes de alterar a aplicação.
Não gere imagens ou vídeos pagos sem autorização.
```

O [inventário histórico](inventory.md) liga os achados a arquivos/linhas e registra a reconciliação v0.7.0. [Tokens](../../design/rastro/tokens.json) registram a identidade runtime e as primitives opcionais. [Primitives CSS](../../design/rastro/motion.css) continuam fora do app e não implementam foco, autorização ou persistência. A [spec complementar](spec.md) tem 6 requisitos; as avaliações de aplicação seguem separadas dos checks de arquivo.

O extrator foi adaptado para CSS separado, necessário neste repositório. Não precisa de chave, navegador ou geração externa:

```bash
python3 .claude/skills/rastro-visual-handoff/scripts/inspect_visual.py \
  --input apps/web/src/rastro/rastro.css \
  --output design/generated-private/rastro-css.json
python3 -m pytest tests/contract/test_visual_handoff_contracts.py -q
```

Não sobrescreve saída existente. Para outra versão, usar nome novo. O relatório é leitura textual: não calcula cascata final, não executa TSX/JS, não busca imports CSS e não mede runtime. Conferir estilos computados e o componente em ambiente local autorizado antes de afirmar fidelidade.

## O que preservar e o que conferir

Navegação/botões usam 150ms, sidebar mobile 160ms e painel/toast 160ms, dentro do contrato 140–180ms. Não transportar os drawers de 260/280ms da Paralaxe. O painel/toast foi adotado no runtime v0.7.0; a primitive de design continua opcional.

As divergências históricas de `--info`, raios, topbar/blur e cascata bege/verde foram reconciliadas no runtime v0.7.0. O inventário continua distinguindo o que foi observado no commit-base do que foi alterado e testado localmente.

Hoje/evidências são a primeira âncora visual. Balancete/razão precisam de precisão/D/C, contexto e impressão; não animar saldo ou total por count-up. Portal usa linguagem/papéis próprios, sem menu/razão/aprovação de escritório. Demonstração Orbe permanece separada e áreas sem contrato não são preenchidas com estados fictícios gerados.

## Gates do handoff

A captura usa só dados sintéticos. Fontes/screenshot/vídeo ficam em `design/source-private/` e `design/generated-private/`, excluídas do Git. Código/mídia externa precisa de direitos/licença; Neo Stitch pode ser usado como ferramenta de exploração externa, mas não é dependência/conector deste projeto. Imagem/vídeo é evidência de desenho, não aprovação de ledger, consentimento ou protocolo de órgão.

Antes da adoção efetiva foram atualizados SPEC/changelog, ADR 018, README, caderno do contador, OpenAPI e roteiro do piloto, como manda [AGENTS.md](../../AGENTS.md). A atualização é visual-only: não houve chamada externa, migração, transmissão, publicação contábil, escrita no piloto ou despesa.

Os novos testes de arquivos entram no comando de contratos da CI existente. Checks locais não executam a skill dentro do Claude nem comprovam foco/browser/RLS/compose/produção. As avaliações de aplicação continuam pendentes; resultados de execução devem ser registrados em relatório separado com ambiente, evidências e limitações.

O [relatório de verificação](VERIFICACAO.md) registra os 70 testes unitários da API, 17 contratos e quatro testes de navegador sintéticos aprovados, com comandos de reprodução após o clone. A execução de navegador cobre foco, reduced-motion, layout, D/C e portal; não equivale à execução completa dos doze casos de eval, aos testes de integração com infraestrutura ou à validação contábil do produto.
