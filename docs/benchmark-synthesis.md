# Síntese do benchmark e hipóteses de oportunidade

O benchmark recebido mostra que o mercado é segmentado. Suítes como Domínio, Alterdata e Contmatic atendem escritórios brasileiros com módulos fiscais, contábeis, folha, portais e produtividade. Omie, Conta Azul e Bling começam pela operação de PMEs. TOTVS Protheus e Senior cobrem operações empresariais mais amplas. SAP Business One, NetSuite e Business Central são referências globais de ERP. QuickBooks, Xero, Sage Intacct, Odoo e Zoho Books ajudam a comparar UX, APIs, dimensões, reconciliação e extensibilidade [1].

A conclusão do benchmark não é montar uma lista maior de menus. Os recursos básicos, como contas a pagar e receber, importações, relatórios, conciliação simples, cloud e alguma API, aparecem em muitos produtos. O espaço de construção mais promissor combina um **ledger brasileiro auditável**, uma **infraestrutura regulatória versionada**, uma **operação de escritório multiempresa**, **migração reconciliável** e **transparência sobre cobertura, limites e responsabilidade** [1].

## Capacidades para aprender com os concorrentes

| Grupo | Padrão observado | O que aproveitar | O que não copiar sem validar |
| --- | --- | --- | --- |
| Suítes de escritório | Profundidade local, obrigações, portais e produtividade | Fluxo de carteira, pendências, fechamento e portal contador–cliente | Fragmentação por pacote, dependência de instalação e cobertura pouco transparente |
| ERP de PME | Onboarding, financeiro, vendas, estoque e canal contador | UX, recorrência, integração operacional e simplicidade | Confundir DRE gerencial com razão estatutário |
| ERP enterprise | Dimensões, multiempresa, subledgers, consolidação e extensões | Modelo de entidade, dimensões e contratos de extensão | Complexidade, TCO e dependência de consultoria |
| Cloud accounting global | Reconciliação, lock date, close, API e marketplace | Experiência de uso, API e trilha de fechamento | Localização brasileira não comprovada |
| Open source/modular | Customização e módulos compostos | Adaptadores e extensibilidade governada | Alteração livre no banco e upgrades sem contrato |

## Hipóteses de oportunidade

As hipóteses abaixo são derivadas da comparação. Elas não são afirmações de que nenhum concorrente oferece essas capacidades. Cada uma precisa ser testada com contadores e clientes.

### H1 — Fechamento com evidência ponta a ponta

**Hipótese:** escritórios perdem tempo para provar de onde veio um saldo e se uma obrigação foi realmente entregue. Um pacote de fechamento que una origem, journal, conciliação, relatório, arquivo, assinatura, protocolo e aprovação pode reduzir retrabalho.

**Experimento:** acompanhar três fechamentos reais ou retrospectivos e medir tempo, pendências, retrabalho e quantidade de telas/arquivos necessários para explicar cinco saldos.

### H2 — Migração sem risco de troca

**Hipótese:** o custo de troca e o medo de interromper o fechamento são barreiras maiores que a ausência de uma feature isolada. Importar saldos, plano, XML, documentos e configurações com dry-run e relatório de diferença pode ser diferencial.

**Experimento:** receber um conjunto anonimizado de exportações de um sistema atual e executar uma migração simulada. O aceite é explicar toda diferença e repetir o processo sem duplicar dados.

### H3 — Matriz de cobertura fiscal verificável

**Hipótese:** compradores têm dificuldade para saber o que é nativo, parceiro, arquivo, homologação pendente ou indisponível por UF, município, regime, versão e edição.

**Experimento:** publicar uma matriz de NF-e, XML de entrada e uma obrigação contábil em duas UFs. Pedir ao contador para encontrar a resposta de cobertura em menos de dois minutos.

### H4 — Conciliação que explica a sugestão

**Hipótese:** a conciliação automática é mais confiável quando mostra a regra, os candidatos, a tolerância, a origem e o motivo da sugestão, mantendo aprovação humana.

**Experimento:** comparar conciliação manual e assistida em extratos anonimizados. Medir precisão, falsos matches, tempo e reversões.

### H5 — Portal de pendências orientado a fechamento

**Hipótese:** portal e comunicação valem mais quando estão ligados a competência, documento faltante, responsável, prazo e impacto no fechamento, e não apenas a um repositório de arquivos.

**Experimento:** acompanhar uma competência com cinco clientes e medir tempo para resolver pendências e quantidade de mensagens fora do sistema.

### H6 — IA segura para assistência contábil

**Hipótese:** existe valor em sugerir classificação, explicar divergência, resumir pendência e preparar uma consulta, desde que a IA mostre evidência e nunca publique efeito contábil sozinha.

**Experimento:** usar um conjunto sintético para comparar sugestões com e sem evidência. O critério principal é a taxa de sugestões aceitas sem correção, não a fluência do texto.

## Diferencial orientador

A proposta inicial pode ser resumida como: **“feche e entregue com evidência”**. Isso transforma transparência em funcionalidade. O usuário vê cobertura, versão da regra, fila, rejeição, protocolo, responsável, retenção, exportação e saúde do conector.

## O que construir e o que integrar

O produto deve construir o ledger, fechamento, trilha, matriz de cobertura, migração, portal, API e reconciliação. Pode integrar inicialmente OCR, storage, notificações, alguns conectores bancários, assinatura e provedores fiscais, mas precisa manter adaptador, idempotência, reconciliação, exportação e explicação própria.

A análise completa recebida foi preservada em [benchmark-software-contabil.md](references/benchmark-software-contabil.md).

## References

[1]: references/benchmark-software-contabil.md "Benchmark de software contábil e ERP para o Brasil"
