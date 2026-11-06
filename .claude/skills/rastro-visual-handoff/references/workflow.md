# Handoff visual do Rastro

## Fontes e precedência

O contrato vigente é `docs/rastro/SPEC.md`; a montagem real é React/Vite em `apps/web`, não Next.js. Comparar o contrato com `src/rastro/rastro.css`, `src/styles.css`, Shell e componente do incremento. O CSS global contém estilos legados; `.rastro` é a casca atual. Não restaurar o antigo visual bege/verde nem importar paleta da Paralaxe/JarvisOS.

Tokens observados e propostas ficam em `design/rastro/tokens.json`. Diferença entre contrato e código é pergunta/diff, não autorização para escolher silenciosamente. Manter Inter/Newsreader, tinta/azul, papel claro, status textual e visão de trabalho/exceções. O nome definitivo continua decisão de produto; esta skill preserva o nome de interface existente Rastro.

## Captura e motion

Registrar rota, commit, viewport, papel, empresa fictícia, competência, estado e fontes disponíveis. Para CSS separado, usar o extrator com --input apontando para `.css`; para protótipo local, `.html`. O script não executa TSX/JS, imports CSS ou browser e não mede cascata. Revisar output antes de publicar: até CSS pode conter informação privada.

Captura real só em ambiente local autorizado e com dados sintéticos. Não usar o piloto hospedado, logins de clientes ou endpoints reais de escrita para descobrir o desenho. Não ler XML, extratos, documentos ou certificados para obter referência visual. Revisar a screenshot para CNPJ real/URLs privadas/segredos antes de envio.

Movimento atual observado: navegação/botões 150ms e sidebar mobile 160ms. O contrato manda 140–180ms. Entradas de painel/scrim em nosso CSS são propostas, ainda não importadas. Se não houver vídeo, o mapa de interação e os estilos são suficientes; não gerar vídeo por obrigação.

Vídeo generativo, se autorizado, mantém câmera, rótulos, dinheiro, D/C, hash, números, datas e geometria. Só mover elemento nomeado; nenhum brilho/verde deve representar publicação/aceite. Modelos/limites/preço são verificados no provedor escolhido antes de despesa. Neo Stitch é ferramenta externa opcional, não backend do SaaS; verificar licença e dependências reais antes de copiar código. As skills globais de outro ambiente não são presumidas disponíveis.

Se o ambiente não lê MP4, extrair frames sintéticos locais com ffmpeg e registrar timestamps/fps, usando ferramenta autorizada para observar movimento. Frames não provam suavidade ou duração. Nunca usar MP4 como formulário/gráfico interativo ou contar animação como integração real.

## Contexto contábil

Hoje trabalha empresa/competência reais da sessão; abrir pendência pode trocar contexto conforme SPEC. Não animar troca silenciosa nem manter rascunho/cache de empresa anterior. Saldo/debito/crédito usam precisão e formatação existentes; não interpolar dinheiro ou trocar D/C para caber num mock.

No portal, cliente vê sua empresa da membership; não acrescentar menus de ledger, seletor de escritório/competência ou ações Confirmar/Devolver. Demo Orbe continua explicitamente sintética e separada. Revisões de IA, obrigações e conectores sem contrato permanecem vazios; não preencher com cards de sucesso gerados.

Recebido não é confirmado, hash exibido não prova cadeia validada, fila não é pacote pronto, protocolo não é aceite. Efeito material depende da API, papel, segregação e idempotência, nunca do fim da animação. Preservar autoria/reversão e documento original.

## Implementação e revisão

Começar por CSS escopado e componente existente. Não instalar Motion/GSAP/Three.js ou canvas de design por default. Manter acessibilidade de dialog quando aplicável: título, Escape, foco inicial/contido/retorno, rolagem. Preferência reduced-motion atua também em JS, loops e scroll, sem depender de animationend para liberar fluxo.

Comparar estados estáveis em viewports iguais, papel/contexto/fixtures iguais e fontes carregadas ou fallback registrado. Testar teclado, rede lenta, erro, conflito, troca de empresa e impressão do balancete/razão. Não usar pixel diff sozinho para aprovar precisão, permissão ou conformidade.

Uma alteração de experiência exige atualização da SPEC/changelog, ADR afetada, README, caderno do contador, OpenAPI e piloto no mesmo commit, conforme AGENTS.md. Se apenas tooling/documentação, declarar que código/contratos produtivos não mudaram. Sempre separar checks de arquivo da skill no Claude, testes de browser e integração compose.
