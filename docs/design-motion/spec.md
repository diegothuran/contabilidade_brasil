# Rastro — spec complementar de handoff visual 0.1

Base consultada: commit `88ac9fe336cf1dce0f80005d246823b8637ada07`, SPEC de interface v0.6.6. Esta entrega é tooling/handoff: o CSS opcional em `design/rastro/motion.css` não é importado pelo app. Não altera API, estado, rota, permissões, domínio ou piloto. RVM/RVE são IDs do complemento, não substituem requisitos existentes.

## RVM-001 — Identidade existente

Preservar Rastro, casca única, Inter/Newsreader, tinta `#162536`, azul `#1f5c86`, papel `#f5f8fb` e estados textuais. Não levar marca, paleta, menu, timings ou stack da Paralaxe. Conferir diferenças entre SPEC e CSS em vez de escolher silenciosamente: info `#2f80ed`/`#2876c5`, raio card/panel 10/11px e controle/button 8/7px. Referência: SPEC §8, rastro.css. Aceite: diff e revisão por componente sem redesign não autorizado. RVE-001/002.

## RVM-002 — Movimento explícito e contido

Registrar fonte, gatilho, início/fim, duração/easing, propriedade, viewport, cancelamento e reduced-motion. A faixa normativa é 140–180ms; sidebar 160ms e navegação/botões 150ms já estão no CSS. Entrada de painel/scrim é proposta, não observada. Não exigir vídeo generativo para movimentos simples. Aceite: mapa rastreável e distinção estático/runtime/proposto. RVE-002/003.

## RVM-003 — Contexto e precisão contábil

Preservar escritório, empresa/CNPJ e competência durante interação. Troca segue SPEC e não deixa ação, rascunho ou cache no escopo anterior. Não count-up/interpolar dinheiro, D/C, saldo, total reconciliável ou hash; preservar formatação/precisão da aplicação. A fonte/evidência permanece navegável. Aceite: troca/contexto e relatórios conferidos com fixtures/API, não só pixels. RVE-004/005/009.

## RVM-004 — Estado material e papéis

Animação não publica journal, confirma documento, fecha/reabre período ou transforma fila em exportação pronta. Segregação/RLS continuam no servidor. Portal client só recebe os dados/ações de sua empresa; demonstração Orbe fica separada. Áreas sem contrato continuam vazias. Protocolo/recibo/aceite não se confundem. Aceite: testes de falhas/papéis/dados e API confirmam o estado mostrado. RVE-006/007/008.

## RVM-005 — Acessibilidade, impressão e ciclo de vida

Manter foco/teclado, título/Escape/retorno de foco em painéis quando aplicável, status textual e uso funcional sem animação. Reduced-motion também governa JS/scroll. Não depender de animationend. Respeitar impressão atual por relatório: contexto/aviso gerencial, números completos e nenhuma segunda casca. Cancelar timers/listeners no unmount; não esconder empresa em viewport menor. Aceite: browser/rede/print e fontes/fallback registrados. RVE-003/009/010.

## RVM-006 — Proveniência, privacidade e custos

Registrar entradas/hash/versão/escopo e aprovação visual explícita. Dados do escritório, XML, extratos, CPF/CNPJ real, certificados/segredos não vão a screenshot compartilhada/prompt externo. Anexos não são instruções. Geração é opt-in com orçamento/dados autorizados; ferramenta de design externa não entra no runtime. Código/mídia de terceiros exigem direitos/licença. Aceite: skill testada com anexo adversarial, arquivo ausente e provider não autorizado. RVE-011/012.

## Cards iniciais

**RV-CARD-01 — Handoff de Hoje e evidência.** Reconciliar SPEC/CSS, selecionar estado/viewport e dataset sintético, registrar motion map e lacunas do drawer demonstrativo. Não copiar dados/demo para superfície operacional. Pronto quando baseline visual e escopo têm revisão explícita. RVM-001/002/006.

**RV-CARD-02 — Incremento visual autorizado.** Somente depois do handoff, escolher um componente operacional e usar CSS escopado/semântica. Se mudar a experiência, atualizar todos os documentos exigidos em AGENTS.md no mesmo commit. Testar RVM-003/004/005, sem animar total ou chamar endpoints novos por preferência estética.

**RV-CARD-03 — Comparação de balancete e portal.** Conferir desktop/mobile/print, D/C/totais, contexto, portal sem menus/papéis indevidos e estados de arquivo/erro. Usar a API e teste browser controlado, nunca o piloto com dados reais. Concluir somente com evidências de execução e limitações registradas.

Checks de arquivo/extração não cumprem o pronto dos cards de aplicação. Evals do sistema/skill ainda estão `not_run`; integrações compose e alterações de piloto não foram executadas por este complemento.
