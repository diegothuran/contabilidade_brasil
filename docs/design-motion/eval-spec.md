# Eval spec — Rastro e motion

Os [12 casos RVE](eval-cases.json) cobrem os [6 requisitos RVM](spec.md). Todos começam `not_run`. Resultado de arquivo, aprovação visual e estado persistido são verificações distintas; não contar um teste do extrator como aprovação desses casos.

Checks locais: skill válida, extrator CSS/HTML, symlinks/sobrescrita, consistência tokens/CSS, IDs/cobertura e guardrails da skill. A suite do complemento roda com `python -m pytest tests/contract/test_visual_handoff_contracts.py -q` e também entra no comando de contratos da CI existente. Ela não chama Claude, servidor, provedor ou browser.

Testes comportamentais da skill: executar no Claude com entradas sintéticas e registrar tool calls para referência ausente, favorito/versão não aprovada, instrução adversarial, dado privado e provider sem orçamento. Não avaliar só a promessa textual de não chamar ferramenta.

Testes de produto: usar o frontend/API em ambiente local autorizado com fixtures e papéis controlados; não experimentar no piloto hospedado ou com dados de clientes. Registrar commit, viewport, fontes/fallback, contexto e respostas do servidor. Conferir precisão/D/C/totais, estado real, RLS, segregação e invariantes via API/integração, não só screenshot.

Para visual/motion, comparar estados estáveis equivalentes em viewports iguais e revisar trajetória/foco/texto além do pixel diff. Reduced-motion também atua em JS e preferência alterada em runtime. Não animar contagem monetária. Impresso/CSV precisam manter o relatório/contexto, independentemente do efeito de entrada.

Falha crítica de dados, autorização, precisão, estado material, privacidade ou acessibilidade bloqueia adoção do componente. Caso high requer correção ou decisão explícita documentada. Nenhuma similaridade visual ou verde na tela supera esses gates.

Criar relatório novo por execução com caso, resultado pass/fail/blocked/not_run, método, dataset, commit, ambiente e evidência sanitizada. Arquivos privados ficam em área excluída do Git. Sem compose/browser/Claude, registrar limite; não alterar `eval-cases.json` para simular sucesso.
