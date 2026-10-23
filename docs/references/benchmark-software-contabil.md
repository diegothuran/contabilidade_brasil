# Benchmark de software contábil e ERP para o Brasil

**Relatório acionável para fundação de um produto de software contábil**  
**Corte da pesquisa recebida:** 11/10/2026, conforme fichas fornecidas.  
**Escopo geográfico:** Brasil, com comparação de produtos globais quando relevantes para o desenho competitivo.

## Sumário executivo

O mercado não é uma fila única de “sistemas contábeis”. Ele é formado por pelo menos cinco grupos com necessidades, economias e riscos diferentes:

1. **Suítes para escritórios contábeis brasileiros**, como Domínio, Alterdata e Contmatic, cujo valor está na operação recorrente de muitos CNPJs, obrigações, folha, portais, produtividade e suporte local.
2. **ERPs brasileiros para PMEs**, como Omie, Conta Azul e Bling, que começam pela operação comercial/financeira e se conectam ao contador. A profundidade de contabilidade estatutária varia muito e não deve ser inferida a partir de DRE gerencial, categorias ou exportação fiscal.
3. **ERPs brasileiros mid-market/enterprise**, como TOTVS Protheus e Senior, com grande amplitude operacional, implantação parametrizada, fiscal localizado e forte dependência de parceiros e versões.
4. **ERPs globais mid-market**, como SAP Business One, NetSuite, Business Central e Sage Intacct, nos quais o núcleo financeiro pode ser robusto, mas a cobertura brasileira depende de localização, parceiro, add-on, edição e contrato.
5. **Contabilidade cloud e ERP modular global**, como QuickBooks Online, Xero, Odoo e Zoho Books. São referências de UX, APIs e distribuição; no Brasil, a fiscalidade e o estado comercial precisam ser validados separadamente.

A oportunidade recomendada não é copiar a maior lista de menus. É lançar um **ledger brasileiro auditável e exportável**, integrado a um **motor regulatório versionado**, com onboarding e migração que reduzam o risco de troca para o escritório. O produto deve tornar explícito aquilo que muitos concorrentes deixam difuso: cobertura por UF/município/obrigação, edição, limites, SLA, RPO/RTO, preço, API, retenção e responsabilidade do parceiro.

### Decisões de produto recomendadas

- **Beachhead:** escritórios com aproximadamente 20–200 CNPJs, em dois ou três estados com demanda fiscal conhecida, que sofrem com fechamento, conciliação, documentos e comunicação com clientes.
- **MVP:** razão de partidas dobradas, plano de contas/referencial, importação, conciliação, fechamento controlado, documentos fiscais recebidos, ECD/ECF assistidas, portal do cliente, auditoria, API e exportação completa.
- **Não iniciar:** cobertura nacional de todos os municípios, folha completa, banking próprio, marketplace amplo, IA autônoma que altera livros ou obrigações, manufatura profunda e dezenas de conectores sem matriz de manutenção.
- **Diferencial de confiança:** cada número deve ser explicável do documento de origem ao lançamento, obrigação, protocolo, recibo e usuário que aprovou.
- **Princípio regulatório:** legislação, XSD, tabelas, prazos e regras são dados versionados; não são constantes escondidas no código do ERP.

## 1. Delimitação, método e honestidade do benchmark

### 1.1 O que este documento afirma — e o que não afirma

Este é um **benchmark representativo**, não uma afirmação impossível de que cobre literalmente todos os softwares contábeis, ERPs, provedores fiscais, bancos, aplicativos ou escritórios do mercado. A lista foi construída a partir das fichas estruturadas recebidas e representa líderes, referências ou alternativas relevantes por segmento. Produtos menores, soluções verticais, sistemas municipais, add-ons e fornecedores que não publicam documentação suficiente podem estar ausentes.

A análise distingue quatro níveis:

- **Fato documentado:** capacidade, preço, métrica ou limitação sustentada por uma fonte pública indicada nas referências.
- **Claim do fornecedor:** afirmação comercial ou institucional do próprio fornecedor, como número de clientes, usuários, parceiros, satisfação ou liderança. É registrado com data e atribuição, mas não tratado como market share auditado.
- **Lacuna pública:** não foi encontrada evidência suficiente nas fontes acessadas. Lacuna não é prova de inexistência.
- **Inferência/recomendação:** conclusão de arquitetura, estratégia ou construção derivada da comparação. Não descreve o schema interno ou a implementação do concorrente.

Quando uma ficha diz que um produto “integra”, isso pode significar módulo nativo, arquivo, API, parceiro, serviço contratado ou portal externo. O relatório mantém essa diferença. Quando uma página lista uma obrigação, isso não comprova cobertura de todos os eventos, UFs, municípios, regimes e versões.

### 1.2 Critérios de seleção

Os produtos foram selecionados por uma combinação de:

- **relevância de mercado e distribuição declarada**, sem transformar claims corporativos em participação independente;
- **representação de segmentos**: escritório contábil, ERP/PME, ERP enterprise brasileiro, ERP global, cloud accounting e open-source/modular;
- **profundidade funcional observável** em contabilidade, fiscal, financeiro, operações, integrações, APIs, segurança e implantação;
- **evidência pública reutilizável**, preferindo páginas oficiais, documentação técnica, manuais regulatórios e, quando útil, diretórios independentes explicitamente qualificados;
- **valor de aprendizagem para um produto novo**, incluindo limitações e riscos, não apenas recursos de marketing.

A base regulatória brasileira foi tratada como uma ficha própria porque nenhum fornecedor, sozinho, define o que é necessário para cumprir ECD, ECF, NF-e, NFS-e, eSocial, EFD-Reinf, DCTFWeb e outras obrigações. O SPED mantém programas e validadores separados para diferentes escriturações e documentos [48].

### 1.3 Como ler as tabelas

As matrizes usam termos curtos para permitir comparação. “Nativo” significa documentado no produto/linha analisada; “parceiro” indica dependência de terceiro; “localização” indica variação por país, UF, município, edição ou release; “não comprovado” significa ausência de evidência suficiente nas fichas. Não são notas ou rankings universais.

## 2. Mapa de mercado por segmento

| Segmento | Produtos representativos | Posicionamento observado | ICP principal | Risco de compra dominante |
|---|---|---|---|---|
| Escritórios contábeis brasileiros | Domínio, Alterdata, Contmatic | Suíte de contábil, fiscal, folha, obrigações, produtividade, portais e atendimento | Escritórios com carteira de CNPJs, equipes fiscal/folha/contábil e necessidade de automação local | Custo de troca, versões legais, certificados, treinamento e fragmentação por pacote |
| ERP/PME brasileiro | Omie, Conta Azul, Bling | ERP cloud operacional com financeiro, vendas, estoque, notas e integração com contador | Pequenas e médias empresas de serviços, comércio, varejo, e-commerce e indústria leve | Confundir DRE/categoria/SPED auxiliar com contabilidade estatutária completa; cobertura fiscal variável |
| ERP brasileiro mid-market/enterprise | TOTVS Protheus, Senior | Backoffice amplo, fiscal parametrizável, indústria/serviços, multiempresa e parceiros | Empresas médias/grandes, grupos, filiais, indústria, serviços e operações complexas | Implantação longa, customizações, TCO, dependência de release e parceiros |
| ERP global mid-market | SAP Business One, NetSuite, Business Central, Sage Intacct | Núcleo global financeiro/operacional, extensibilidade e localizações | Empresas em crescimento, subsidiárias, grupos multinacionais e mid-market | Localização brasileira, add-ons, licenças, parceiros e fit-gap real |
| Contabilidade cloud para pequenas empresas | QuickBooks Online, Xero, Zoho Books | Bookkeeping, invoices, bills, banking, relatórios, apps e colaboração | Pequenas empresas, autônomos e contadores em países suportados | Disponibilidade regional, fiscal local, add-ons e portabilidade semântica |
| Open-source/modular | Odoo | Apps integrados, Community/Enterprise, SaaS/PaaS/on-premise e customização | PMEs, indústria, e-commerce, serviços e equipes que aceitam configuração | Governança de customizações, upgrades, terceiros e localização fiscal |
| Infraestrutura regulatória | Base regulatória brasileira | Normas, schemas, PVAs, webservices, certificados, prazos e evidências | Qualquer produto que transmita ou gere escrituração no Brasil | Mudança de leiaute, indisponibilidade de órgão, certificados e retenção legal |

### 2.1 Posicionamento e ICP em uma frase

- **Domínio:** plataforma integrada de operação contábil brasileira para escritórios, com One/Pro/Max e serviços acoplados. É forte em amplitude e ecossistema; arquitetura e TCO são menos transparentes publicamente.
- **Alterdata:** núcleo contábil documentado e escada Community–First–Fit–Master–Empresarial, combinando local/cloud e gestão de escritório.
- **Contmatic:** ecossistema Phoenix em nuvem, com automações, portal do cliente, robôs e APIs; ainda apresenta elementos híbridos para certificados e diretórios locais.
- **TOTVS Protheus:** ERP configurável para operações médias e grandes, no qual contabilização, fiscal e operações dependem de parâmetros, localizações, release e parceiros.
- **Senior:** família X/XT com foco empresarial, indústria, serviços, fiscal, HCM e ecossistema; não é uma única implantação arquitetural.
- **Omie:** ERP cloud de PME, financeiro-fiscal e operacional; contabilidade geral aparece com mais profundidade no OneFlow, que é produto distinto.
- **Conta Azul:** ERP financeiro-fiscal e canal para contadores; o produto público detalha integração contábil mais que razão estatutário nativo.
- **Bling:** ERP de comércio/e-commerce, estoque, canais, fiscal e financeiro gerencial; SPED é explicitamente auxiliar/parcial e contabilidade completa não é comprovada.
- **SAP Business One:** ERP global para SMB/lower mid-market com núcleo financeiro e operacional consistente; Brasil depende da localização e de add-ons/parceiros.
- **NetSuite:** ERP cloud para mid-market/global, OneWorld, consolidação e extensibilidade; localização brasileira depende de SuiteApps e especialistas.
- **Business Central:** ERP Microsoft para PMEs e mid-market, forte integração com Azure/Microsoft 365 e opção online/on-premises; o Brasil é identificado como Partner/W1.
- **QuickBooks Online:** referência de bookkeeping cloud e ecossistema nos mercados atendidos; a página oficial informa que os produtos foram descontinuados no Brasil [38].
- **Xero:** contabilidade cloud global, reconciliação e marketplace; a cobertura brasileira não foi comprovada nas fontes consultadas.
- **Sage Intacct:** finance-first cloud para organizações em crescimento, multi-entidade, projetos e receita; localização brasileira não foi comprovada.
- **Odoo:** plataforma modular open-source com contabilidade, CRM, vendas, estoque, MRP e localização brasileira via módulos/Avalara; requer governança de customização.
- **Zoho Books:** cloud accounting integrado à suíte Zoho, com forte API e planos progressivos; edição/fiscal brasileira não foi comprovada.

## 3. Matrizes comparativas

### 3.1 Contabilidade, fiscal, financeiro e operações

| Produto | Segmento | Contabilidade e fiscal | Financeiro | Operações |
|---|---|---|---|---|
| Domínio | Escritórios BR | Contabilidade, fechamento por período, conciliação, ECD/ECF/LALUR; fiscal/folha integrados. Cobertura exata por edição/UF/município não é pública | Contas, guias, pagamentos/e-CAC, honorários e serviços financeiros do ecossistema | Folha, portais, patrimônio, tarefas, documentos e produtividade |
| Alterdata | Escritórios BR | Double-entry, planos, lançamentos, conciliação, fechamento, livros, ECD/ECF/Lalur; obrigações por pacote | Financeiro, bancos, títulos, boletos e baixas | Fiscal, DP, ativo, eContador, protocolo, CND, tarefas |
| Contmatic | Escritórios BR | Plano geral/individual, partidas, OFX/OFC/XLS, fechamento e ECD/ECF; aquisições de ativo exigem Fiscal ou manual | Financeiro, conciliações e integração com folha/fiscal | G5, Folha, JR, Robomatic, portais e gestão de escritório |
| TOTVS Protheus | ERP BR enterprise | Plano, dimensões, LP online/offline, ECD e fiscal parametrizável | AP/AR, tesouraria, bancos API/CNAB, borderôs | Vendas, compras, estoque, projetos, ativos, indústria e contratos |
| Senior | ERP BR enterprise | Plano contábil/auxiliar/referencial, roteiro de fechamento, zeramento, ECD; fiscal via X/eDocs/XT | AP/AR, tesouraria, banking e conciliações | Indústria, serviços, HCM, estoque, logística, contratos e projetos |
| Omie | ERP/PME BR | Painel do Contador gera/mapeia lançamentos; OneFlow documenta razão e fechamento, mas é produto separado | AP/AR, caixa, cobrança, conciliação e DRE gerencial | Vendas, compras, estoque, produção, CRM, serviços e e-commerce conforme edição |
| Conta Azul | ERP/PME BR | Integração/exportação para Domínio, SCI, Alterdata e outros; razão completo não comprovado no Pro | Financeiro, cobrança, bancos, categorias, competência/caixa, DRE | Vendas, contratos, serviços, compras, estoque, emissão fiscal |
| Bling | Comércio/e-commerce BR | DRE gerencial e SPED auxiliar/parcial; ledger estatutário, ECD/ECF e ativo não comprovados | AP/AR, OFX, conciliação, boletos, Conta Digital | Marketplace, pedidos, estoque, expedição, PDV, logística e produção simples |
| SAP Business One | ERP global mid-market | Double-entry, COA, subledgers, reconciliação, períodos, ativos e localização BR; eSocial/obrigações completas não comprovadas | AP/AR, bancos, pagamentos, reconciliação, multi-moeda | Compras, vendas, estoque, MRP, produção, CRM e serviços |
| NetSuite | ERP global cloud | GL, AR/AP, multi-book, OneWorld, ativos, receita e Brazil Localization; SPED/eSocial/Reinf não comprovados como nativos | Caixa, pagamentos, bancos, consolidação, billing | CRM, order, procurement, inventory, WMS, projetos e revenue |
| Business Central | ERP global mid-market | GL, posting groups, dimensões, períodos, ativos, close; Brasil depende de Partner/W1 | AP/AR, bancos, reconciliação, cash flow e budgets | Compras, vendas, estoque, WMS, projetos, MRP, manufatura e serviço |
| QuickBooks Online | Cloud accounting | Double-entry, GL, lock date, relatórios e ativos em edições específicas; Brasil descontinuado | Banking, AR/AP, pagamentos, payroll e cash flow em mercados suportados | Faturamento, projetos, estoque básico, apps e payroll regional |
| Xero | Cloud accounting | Double-entry, journals, lock dates, reconciliação, ativos e relatórios; Brasil não comprovado | Banking, AR/AP, pagamentos e forecasts | Invoicing, bills, projetos, apps, payroll regional e Inventory Plus |
| Sage Intacct | Finance cloud | GL, subledgers, dimensões, close, multi-entidade, receita e ativos; Brasil não comprovado | AP/AR, cash, purchasing, payment, revenue | Projetos, billing, Salesforce connector e dimensões operacionais |
| Odoo | Open-source/modular | Double-entry, multiempresa, tax, reconciliação, ativos, fechamento e l10n_br; cobertura DF-e/obrigações varia | AR/AP, bancos, payments, despesas e budgets | CRM, vendas, compras, estoque, MRP, POS, projetos e serviços |
| Zoho Books | Cloud accounting | Double-entry, journals, lock, ativos e relatórios; fiscal BR não comprovado | AR/AP, banking, expenses, BillPay, pagamentos | Vendas, compras, estoque, projetos, CRM e e-commerce via suíte |

### 3.2 Integrações, arquitetura, negócio e confiança

| Produto | Integrações e ecossistema | Implantação | Arquitetura e extensibilidade | Modelo de negócio | Pontos fortes | Lacunas/riscos |
|---|---|---|---|---|---|---|
| Domínio | APIs ERP/XML/TXT, Conta Azul, SIEG, AWS, portais e serviços próprios | Híbrida: módulos locais, Web e nuvem; venda consultiva | API de ERP com OAuth, lote assíncrono e status; modelo interno não público | One/Pro/Max, add-ons, Web, backup, portais e serviços financeiros | Amplitude BR, suporte, integração interna e lock-in funcional | Preço, tenancy, SLA, RPO/RTO, webhooks e cobertura por edição pouco transparentes |
| Alterdata | ePlugin, eContador, ERP4Me, OFX/TXT/XLS/PDF, parceiros | Local, nuvem e ofertas híbridas | API anunciada, RTM, layouts e jobs; endpoints/quotas não públicos | Community, First, Fit, Master e Empresarial; complementos | Profundidade contábil, escada de entrada e gestão de escritório | Fragmentação de pacote, Windows/servidor, API e cobertura fiscal variável |
| Contmatic | APIs JSON/webhooks, parceiros, arquivos, Robomatic e sincronizador | Cloud com ponte local para A3/diretórios | APIs, nuvem, tarefas agendadas e componentes locais | Planos por clientes/GB/acessos e implantação | Automação, portal, atualização frequente e ecossistema | Preços/limites inconsistentes, tenancy/SLA/RPO/RTO não públicos |
| TOTVS | REST/JWT, TSS/SEFAZ, bancos API/CNAB, parceiros e ADVPL | Licença/assinatura, on-premise/cloud, parceiro | AppServer, DBAccess, REST, jobs, ADVPL e banco homologado | Quote-based, módulos, serviços, parceiros e cloud | Amplitude enterprise e parametrização | Complexidade, upgrades, customização, TCO e APIs não uniformes |
| Senior | Senior X REST/webhooks, XT Web Services, SBS, HCM/eDocs, parceiros | X cloud native e XT legado/híbrido conforme linha | APIs, jobs, cargas assíncronas; tenancy, banco e SLA não públicos | Enterprise, módulos, consumo de API e parceiros | Indústria/serviços, fiscal evolutivo e ecossistema | Fragmentação X/XT/eDocs, preço, versões e cobertura local |
| Omie | API v1, webhooks, Omie.Cash, Hub, Store, contábil e apps | SaaS cloud | REST/JSON, limites publicados, multi-organização inferida | Assinatura por faixa de receita e add-ons/serviços | UX, canal contador, API e integração operacional | Contabilidade estatutária separada, NFS-e e cobertura variável |
| Conta Azul | API REST/OAuth, Domínio/SCI/Alterdata, 100+ integrações, bancos e fiscal parceiro | SaaS cloud, self-service e partner-led | API e arquivos; documentação de webhooks/sandbox conflitante | Assinatura por faturamento, usuários e Conta Azul Mais | Financeiro/PME, contador e recorrência | Brasil fiscal/contábil assimétrico, backup e migração limitados |
| Bling | API v3/OAuth/webhooks HMAC, marketplaces, logística e parceiros | SaaS cloud | REST, fila de webhooks, limite por conta; internals desconhecidos | Cobalto–Elite, pedidos/usuários/storage e add-ons | Comércio multicanal e expedição | Contabilidade não comprovada, backup manual, dependências de terceiros |
| SAP Business One | Service Layer REST/OData, DI API, SDK, BTP, add-ons | On-premise ou cloud/on-demand | HANA/SQL, Service Layer, SDK e webhooks recentes | Named users, licença/assinatura e parceiro | Double-entry, MRP, localizações e extensibilidade | Localização BR, parceiros, preço e tenancy não uniformes |
| NetSuite | REST/SOAP/RESTlet, SuiteScript/SDF, Connect e SuiteApps | SaaS cloud, sandbox e Release Preview | Records, SuiteCloud, OneWorld, APIs e scripts | Assinatura anual, módulos, usuários e implementação | Multi-entidade, receita, consolidação e analytics | Preço, customização, localizações e compliance BR por add-on |
| Business Central | REST/OData/SOAP, webhooks, AL, Power Platform, Dataverse, M365 | SaaS Azure e on-premise | Multitenant Azure, Azure SQL, extensões AL, APIs | Por usuário/edição, Premium/Essentials, parceiros e apps | Ecossistema Microsoft, MRP, segurança e SLA | Brasil Partner/W1, webhooks/backup com caveats, parceiro |
| QuickBooks | REST/GraphQL, CDC/webhooks, Payments, Payroll e marketplace | SaaS cloud | Company file, APIs separadas, apps; internals não públicos | Freemium/trials, planos por usuário e add-ons | UX, bookkeeping, ecossistema e contadores | Brasil descontinuado e localização por país |
| Xero | APIs, OAuth, webhooks HMAC, App Store, payroll/payments | SaaS cloud | APIs por tenant, limites, webhooks e marketplace | Assinatura por organização, add-ons e uso | Reconciliação, apps, segurança e canal contador | Brasil não comprovado, dependências de apps/limites |
| Sage Intacct | REST/OAuth, XML, Platform Services, DDS, Salesforce e apps | SaaS cloud, partner-led | Multi-entidade, dimensões, API e extração | Quote-based modular | Finance-first, close, revenue e audit trail | Localização BR não comprovada, preço e dependência de parceiro |
| Odoo | JSON-2, RPC legado, webhooks, import/export, Avalara e apps | Online, Odoo.sh e on-premise | Python/PostgreSQL, addons, ORM, ACLs e Studio | Free/Standard/Custom, usuários, hosting e IAP | Modularidade, código aberto, operações integradas | Upgrade, terceiros, Brasil fiscal e API Custom-only |
| Zoho Books | REST v3/OAuth, webhooks, Zoho CRM/Inventory/Expense e apps | SaaS cloud, web/mobile/Windows | Organizations, API regional, quotas e customizações | Free/planos por organização, limites e add-ons | API, progressão de planos e suíte Zoho | Auditoria/localização BR, backup e RPO/RTO limitados |

## 4. Síntese transversal antes das reviews

### 4.1 O que virou commodity

- contas a pagar/receber, caixa, boletos e relatórios básicos;
- importação de CSV/XLS/OFX e exportação de relatórios;
- emissão ou captura de alguns documentos fiscais, sempre com cobertura local variável;
- usuários, papéis, portal ou colaboração com contador;
- dashboards financeiros, DRE gerencial e conciliação bancária básica;
- cloud, aplicativo móvel, trial ou venda por assinatura nos produtos de entrada;
- APIs de alguma forma, mas com grande diferença de qualidade, limites, autenticação e estabilidade.

### 4.2 O que é diferencial defensável

- **Ledger confiável:** partidas dobradas, subledgers reconciliáveis, imutabilidade, reversão, fechamento e drill-down de origem.
- **Regulatório como plataforma:** registry de leiautes, XSDs, regras, prazos, certificados, eventos, recibos, retificações e matriz de cobertura.
- **Operação de escritório:** carteira multiempresa, pendências por responsável, documentos, tarefas, protocolo, portal e evidência de entrega.
- **Migração:** saldos, históricos, XML, plano referencial, certificados, usuários, permissões e reconciliação pós-carga.
- **Transparência:** pricing, limites, SLA, RPO/RTO, cobertura, changelog legal, API, exportação e responsabilidade de parceiros publicados.
- **Observabilidade fiscal:** status por órgão/versão, rejeições explicadas, fila, retry, contingência, reconciliação e saúde do certificado.

### 4.3 Infraestrutura regulatória brasileira mínima

ECD e ECF são dependentes entre si: ECD cobre Diário, Razão, auxiliares, balancetes, balanços e fichas; ECF usa dados da ECD e controla e-Lalur/e-Lacs [49][50]. NF-e possui autorizadores e webservices por UF/ambiente, além de eventos e contingência [51]. NFS-e nacional tem APIs, XSDs e parâmetros municipais, mas não elimina a necessidade de cobertura e configuração local [52]. eSocial e EFD-Reinf trabalham com eventos, versões, assinaturas, recibos, reabertura e retificação [53][54]. DCTFWeb consolida eSocial, EFD-Reinf e MIT e libera o fluxo de declaração/DARF após os fechamentos de origem [55].

O produto precisa ainda tratar certificados A1/A3 e procurações, guardar XML e retornos, manter calendário por CNPJ/estabelecimento/regime/UF/município e cumprir retenção aplicável. O Ajuste SINIEF 2/25 estabelece prazo mínimo de 132 meses para XMLs de vários DF-e listados, mas não lista NFS-e da mesma maneira; retenção deve ser parametrizável por documento e autoridade [57]. A LGPD exige finalidade, necessidade, segurança, prevenção e responsabilização, mesmo quando o tratamento decorre de obrigação legal [56].

### 4.4 Capacidades críticas para a confiança do contador

1. **Explicabilidade:** “por que este lançamento existe?” deve levar ao documento, regra, usuário, data, lote e evento fiscal.
2. **Reprodução:** o contador deve poder reconstituir saldos, arquivo, versão de leiaute, assinatura e recibo.
3. **Controle de mudança:** período fechado não muda silenciosamente; reabertura exige motivo, permissão e trilha.
4. **Portabilidade:** exportar ledger, plano, documentos, XML, recibos, configurações e auditoria em formato documentado.
5. **Cobertura honesta:** indicar “nativo”, “parceiro”, “arquivo”, “não coberto” e “homologação pendente” por obrigação/localidade.
6. **Resiliência:** indisponibilidade de SEFAZ, prefeitura, certificado ou parceiro cria fila e runbook, não perda ou duplicidade.
7. **Privacidade:** isolamento por escritório/empresa, MFA, segregação de funções, minimização e retenção legal.

## 5. Reviews individuais — produtos brasileiros e base regulatória

### 5.1 Domínio Sistemas (Thomson Reuters)

**Caso de uso e posicionamento.** O Domínio é uma plataforma voltada a escritórios contábeis e, na variante Empresarial, a empresas pequenas, médias e grandes. One, Pro e Max graduam maturidade, complexidade e acesso a módulos. O produto promete deslocar o escritório de tarefas repetitivas para serviços consultivos; a afirmação de liderança é marketing da própria Thomson Reuters, não market share independente [1].

**Módulos e workflows.** O núcleo cobre Contabilidade, Escrita Fiscal, Folha, Patrimônio, LALUR, Honorários, Administrar/Auditoria, Portais, Messenger/Processos, BOX-e, Contabilidade Digital, Conta Digital, Cobranças, Benefícios e serviços de certificados. O workflow típico é: importar documentos e extratos; escriturar/apurar; calcular folha; alimentar a contabilidade; conciliar; gerar obrigações; entregar documentos pelo portal; fechar o período. A página contábil documenta importação de extrato, conciliação, centros de custo e bloqueio depois do fechamento [2].

**Contabilidade e fiscal.** Há evidência pública de fechamento que impede alterações após impostos, folha ou fechamento contábil, de integração Fiscal/Folha/Contábil, patrimônio com depreciação/CIAP e LALUR para Lucro Real. A documentação pública não expõe todo o schema do razão, regras de partidas dobradas, moeda/multiempresa ou reabertura; esses pontos não devem ser inferidos. A API de ERP aceita XML/TXT, rubricas e documentos em lote, usa OAuth e consulta assíncrona de status [3].

**Arquitetura, segurança e negócio.** A oferta é híbrida na experiência: Domínio Web hospeda banco em nuvem e Evolução em Nuvem fornece módulos online; AWS é citada como infraestrutura e o Web divulga quatro backups diários [4]. Isso não prova multi-tenancy, região, RPO/RTO, SLA, SGBD ou DR. Auditoria filtra usuário, empresa, tabela e operação; certificados centralizam validade e emissão, mas custódia de chave/HSM não é pública. Preços são cotados, por pacotes e add-ons, com venda consultiva.

**Forças, limitações e lição.** A maior força é a combinação local de fiscal, folha, contábil, portais e suporte, que aumenta custo de troca. As maiores limitações são opacidade de TCO/cobertura, fragmentação por edição e dependência de órgãos/parceiros. Lição de construção: reproduzir a integração operacional, mas publicar schema semântico, matriz de cobertura, API versionada, exportação, SLA e pricing.

### 5.2 Alterdata Contábil

**Caso de uso e posicionamento.** A Alterdata oferece uma escada Community/Grátis, First, Fit, Master 36 e Empresarial. O Contábil é o núcleo de escritórios e empresas que precisam de contabilidade, Fiscal, Departamento Pessoal, Financeiro, ativo, CIAP e gestão de relacionamento. O produto pode ser local, em nuvem ou híbrido, e a documentação do módulo é mais explícita sobre operações contábeis que a de vários concorrentes [5][6].

**Módulos e workflows.** O fluxo documentado configura empresa, regime, plano e centros; mapeia Fiscal e DP; gera lançamentos automáticos; importa lotes; concilia; executa análise crítica; simula ou encerra exercício; emite Diário, Razão, Balanço, Balancete e DRE. eContador, Protocolo, CND, eTarefas, nf-stock e parceiros ampliam o produto além do razão. ePlugin oferece operações de contabilidade, documentos, CND, tarefas e rotinas de DP [7].

**Contabilidade e fiscal.** Há plano personalizado, lançamentos simples/múltiplos, históricos, centros, rateio, OFX/TXT/Excel/PDF, conciliação automática e desfazimento de encerramento. A documentação indica fechamento anual, trimestral ou especial, mas isso não prova um hard close imutável de competência. ECD/ECF/Lalur aparecem na ficha, enquanto a cobertura de cada obrigação depende de pacote, versão, regime, UF e município.

**Arquitetura, segurança e negócio.** Instalação local exige Windows e rede; a nuvem oferece backups, mas foram divulgados períodos de sete dias para backup automático e três semanas no Bunker, sem RPO/RTO contratual público. Auditoria registra usuário, máquina, data/hora e ação. First tinha preço público “a partir de R$ 11,66/dia” no recorte informado; Fit/Master/Empresarial são majoritariamente cotados. A API é anunciada, mas endpoints, webhooks, quotas e SLA não são públicos.

**Forças, limitações e lição.** A profundidade contábil documentada e a entrada gratuita são forças. Fragmentação por pacote, dependência de Windows e cobertura fiscal municipal incompleta são riscos. Lição: oferecer UX de fechamento simulado/desfazer e importação de legado, mas transformar limites e dependências em entitlements visíveis.

### 5.3 Contmatic Phoenix

**Caso de uso e posicionamento.** Phoenix combina Contábil, G5 Fiscal, JR, Folha, SST, ativo, Busca XML, CND, Gestão do Escritório, Contador Online, Robomatic e nuvem. A oferta é cloud, medida por acessos, clientes/CNPJ e GB, e direcionada a contadores autônomos, escritórios pequenos/médios e equipes maiores. Métricas de clientes, usuários e colaboradores são claims corporativos com inconsistências entre páginas [8].

**Módulos e workflows.** O fluxo inclui importar NF/XML e SPED no G5, apurar, integrar com Contábil, calcular folha, transmitir eventos, fechar, gerar ECD/ECF, controlar ativo e distribuir documentos pelo Contador Online. Robomatic agenda rotinas, pausa execuções, cria pendências e registra logs. O Sincronizador troca arquivos e registros entre linha Phoenix e portal.

**Contabilidade, fiscal e API.** Phoenix documenta plano geral/individual, contas sintéticas/analíticas, double-entry, lançamentos simples/compostos, OFX/OFC/XLS, conciliação e fechamento. Integração de ativo leva depreciações, baixas e transferências, mas aquisições dependem do Fiscal ou lançamento manual. A plataforma Developer anuncia APIs JSON, chave e webhooks; o catálogo público de endpoints, limites e escopos não foi comprovado [9][10].

**Arquitetura, segurança e negócio.** O produto é anunciado como 100% cloud, mas A3 requer driver, Java, USB e aplicativo local; A1 é carregado para a nuvem. A política declara provedores Amazon/GCP nos EUA, backup diário verificado e canal de DPO, sem RPO/RTO público. Planos variam de até cinco clientes a ilimitado, mas há inconsistência pública sobre o limite do Elite. Isso exige validação contratual.

**Forças, limitações e lição.** Automação orientada a escritório, cadência de releases e portal são forças. Elementos híbridos, custos/limites pouco transparentes e dependência de parceiro fiscal são riscos. Lição: separar um núcleo web de uma ponte local segura para A3, sem expor PFX e senha em diretórios.

### 5.4 TOTVS Protheus / Backoffice

**Caso de uso e posicionamento.** Protheus é ERP para empresas médias e grandes com Financeiro, Contabilidade, Fiscal, Compras, Vendas, Estoque, Ativo, Projetos, Contratos e manufatura. Pode ser contratado por licença ou assinatura, em servidores próprios ou cloud. A TOTVS declara mais de 10 mil clientes e 200 milhões de acessos anuais para a linha; é métrica da companhia, não do módulo contábil isolado [11].

**Módulos e workflows.** Procure-to-pay, order-to-cash, estoque, projetos e ativos postam via Lançamentos Padrão (LPs), online ou offline. O Financeiro oferece AP/AR, borderô, bancos por CNAB/API e baixa posterior. Fechamento valida calendário, integrações, Tracker, apuração e ECD. O Tracker liga título financeiro a lançamento contábil por tabelas de vínculo específicas; isso é uma trilha observada, não um schema completo.

**Contabilidade, fiscal e extensibilidade.** O plano tem dimensões e parâmetros de débito/crédito; entidades podem ser obrigatórias ou opcionais. ECD exige calendário, plano referencial, signatários, participantes, saldos, apuração e validação no PVA. Configurador de Tributos, TSS/SEFAZ e módulos fiscais cobrem regras por vigência, mas a ficha não confirma todos os documentos/UFs. REST, JWT/Bearer, ADVPL, DBAccess, jobs e OpenTelemetry formam a superfície técnica [12][13].

**Segurança, operação e negócio.** RBAC por usuário/grupo, empresa/filial, rotina e campo; Embedded Audit Trail registra antes/depois, IP, login e dicionário quando ativado. TOTVS Cloud PaaS declara certificações e disponibilidade de 98% a 98,5% conforme plano, mas isso não é SLA de toda instalação Protheus [14]. Preço, customização, implementação e parceiros são cotados.

**Forças, limitações e lição.** Amplitude operacional, parceiros e parametrização fiscal são forças. Complexidade de release, customização, relatórios descontinuados, dependência de TSS e ausência de TCO público são riscos. Lição: um produto novo deve oferecer o mesmo poder por contratos de extensão versionados, não por acesso direto ao banco.

### 5.5 Senior Sistemas ERP

**Caso de uso e posicionamento.** Senior é uma família que inclui ERP senior X, ERP XT, eDocs, HCM, TMS/WMS, Banking, Analytics e componentes setoriais. O produto atual é divulgado como cloud native e web, enquanto XT mantém documentação de processos e regras próprias. A Senior divulga claims de adoção diferentes entre páginas; eles não são uma série comparável.

**Módulos e workflows.** O roteiro F049FEC encadeia notas, ativos, faturamento, impostos, integração contábil, CIAP, conciliações e relatórios; o zeramento cria partidas contrárias, pode consolidar filiais e transfere resultado. AP/AR, tesouraria e banking alimentam controladoria. Indústria cobre engenharia, PPCP, chão de fábrica, custos, qualidade e manutenção; serviços cobre contratos, projetos, ordens e NFS-e.

**Contabilidade, fiscal e integrações.** O ERP X expõe planos contábil, auxiliar, centro de custos, financeiro e referencial SPED. Senior X APIs documentam pedidos, NFs e webhooks assíncronos; XT tem Web Services separados. Reforma Tributária, eDocs e calendários de exigências demonstram que licença e versão são dependências. O SBS governa tokens, aprovação de desenvolvedor, ambiente e telemetria, mas não publica um limite universal [15][16][17].

**Arquitetura, segurança e negócio.** Multiempresa/multifilial e cargas assíncronas são observáveis; tenancy, banco, isolamento, RPO/RTO e criptografia não são detalhados publicamente. O modelo enterprise é consultivo, com módulos, consumo de API e parceiros. Certificados, XML, protocolos e eventos têm alta importância, mas a custódia das chaves não foi especificada.

**Forças, limitações e lição.** Profundidade em indústria/serviços e portal de exigências legais são forças. Fragmentação X/XT/eDocs, dependência de licenças, municípios e parceiros são riscos. Lição: separar core contábil do registry legal e publicar uma matriz de cobertura por produto, release e órgão.

### 5.6 Omie

**Caso de uso e posicionamento.** Omie é um ERP cloud para PMEs com Financeiro, Vendas, Serviços, Compras, Estoque, Produção, CRM, Omie.Cash e ecossistema de apps. O Painel do Contador importa plano, mapeia categorias e gera lançamentos/layouts; OneFlow documenta uma contabilidade mais completa, mas é produto distinto [18].

**Módulos e workflows.** O fluxo é documento-primeiro: cotação/pedido ou ordem de serviço gera financeiro, estoque e nota; contratos recorrentes geram venda/cobrança/NFS-e quando suportados; pagamentos são conciliados. O Painel envia notas, baixas e lançamentos para o sistema contábil. O produto opera bem como subledger operacional, mas a evidência pública não autoriza chamá-lo de razão estatutário completo.

**Fiscal, API e arquitetura.** A API v1 lista vendas, NF-e/NFC-e, serviços, estoque, produção, finanças e Painel; webhooks são configuráveis por aplicativo. NFS-e depende de município, certificado, credenciamento e padrão. A documentação publica limites por IP/App Key/método, concorrência e paginação [19]. O guia técnico declara AWS Brasil, TLS 1.3, AES-256, WAF, MFA, logs e backups diários, mas não publica RPO/RTO numérico [20].

**Negócio, forças e riscos.** A página de preços usa faixas de receita e mostra ERP Padrão e Multivarejo a partir de valores públicos no recorte. O contador é canal de distribuição. Forças: UX, integração operacional, API e fluxo recorrente. Riscos: contabilidade estatutária externa, NFS-e heterogênea, exportação limitada e dependências de terceiros. Lição: decidir explicitamente se o novo produto é ERP com integração contábil ou contabilidade geral; não esconder a fronteira.

### 5.7 Conta Azul

**Caso de uso e posicionamento.** Conta Azul é ERP financeiro-fiscal cloud para pequenas e médias empresas, com forte distribuição via contadores. Publica planos por faturamento, usuários e módulos; Conta Azul Mais oferece painel, automação fiscal e integração com Domínio, SCI e Alterdata [21][22].

**Módulos e workflows.** Venda gera parcelas, documento fiscal e recebível; compras geram estoque/custo e contas a pagar; contratos geram cobrança e NFS-e quando o município permite; bancos alimentam conciliação. O DRE é gerencial, com competência/caixa e centros. A documentação pública não comprova razão geral, lock contábil, ativo, ECD ou ECF nativos no Pro.

**Fiscal, integrações e segurança.** Emissão de NF-e, NFC-e e NFS-e é localizada por CNPJ, IE, IM, credenciamento, certificado e município. A automação fiscal da Conta Azul Mais captura determinados documentos por UF e transmite ao Domínio; há limitações explícitas para CT-e de saída, NFS-e e notas especiais. A API é REST/OAuth, mas há inconsistências públicas sobre webhooks, sandbox e PKCE [23].

**Negócio, forças e riscos.** A página acessada listava preços públicos, teste curto e planos com 1–15 usuários; Conta Azul Mais tinha preços/níveis de parceiro, com conflitos de lote mínimo. Backup completo é CSV, não restauração direta, e NFS-e fica fora desse pacote. Força: canal contador, simplicidade, recorrência e financeiro. Lição: fazer exportação semanticamente completa e não tratar uma tela de backup como continuidade.

### 5.8 Bling

**Caso de uso e posicionamento.** Bling é ERP SaaS de comércio e e-commerce: marketplaces, pedidos, estoque, expedição, PDV, NF, financeiro e logística. A empresa declara mais de 300 mil negócios e mais de 250 integrações; são claims comerciais [24].

**Módulos e workflows.** Pedido de canal entra, reserva estoque, gera financeiro, emite NF quando configurado, passa por checkout/etiqueta/rastreio e devolve status. Compras e XML atualizam estoque/custo. Financeiro suporta contas, OFX, baixa e conciliação. DRE é gerencial; SPED Fiscal/Contribuições é parcial e depende do cadastro, com orientação para validação do contador.

**Fiscal, API e segurança.** NF-e/NFC-e e NFS-e têm escopo por UF, município e provedor; CT-e/MDF-e dependem de integração externa documentada. API v3 usa OAuth e webhooks HMAC, com limite de 3 requisições por segundo e 120 mil/dia por conta [25]. Backup é manual, temporário e sob responsabilidade do cliente; registro de atividades é consultivo, não restaura alterações.

**Negócio, forças e riscos.** Planos Cobalto a Elite variam por usuários, armazenamento, pedidos e API; há trial, implantação e parceiros. Força: operação multicanal. Risco: não comprovar razão, ECD/ECF, ativo ou fechamento estatutário. Lição: transformar contabilidade e evidência de auditoria em diferencial para o comércio, sem perder a velocidade de pedido/expedição.

### 5.9 Base regulatória brasileira

**Por que é uma review própria.** A base regulatória não é concorrente comercial; é o conjunto de dependências que todos os concorrentes precisam operar. O SPED mantém páginas separadas para ECD, ECF, EFD-Contribuições, EFD ICMS/IPI, EFD-Reinf, eSocial, NF-e, NFS-e, CT-e e MDF-e [48].

**ECD e ECF.** ECD transmite Diário, Razão, auxiliares, balancetes, balanços e fichas; a regra geral de entrega é o último dia útil de junho do ano seguinte. ECF suporta IRPJ/CSLL, recupera dados da ECD e controla e-Lalur/e-Lacs; a regra geral é o último dia útil de julho [49][50]. Produto deve gerar arquivo, validar no PVA, assinar conforme papel, guardar hash/recibo e manter cadeia original-substituta.

**DF-e e NFS-e.** NF-e tem autorizadores por UF e ambientes, XML assinado, protocolo, eventos, consulta e contingência [51]. NFS-e nacional oferece APIs de parâmetros, DPS, emissão, consulta e eventos, mas a cobertura depende da adesão municipal e de regras locais [52]. A arquitetura precisa de adaptadores, não um único “emissor nacional”.

**eSocial, EFD-Reinf e DCTFWeb.** eSocial usa eventos de tabelas, não periódicos, periódicos e SST com XSDs e notas técnicas [53]. EFD-Reinf trabalha com lotes/eventos, protocolo, consulta assíncrona, fechamento, reabertura e retificação [54]. DCTFWeb consolida eSocial, Reinf e MIT, e uma retificação normalmente exige corrigir a origem [55].

**Segurança, retenção e lição.** Certificados ICP-Brasil, A1/A3, procurações e assinaturas devem ser tratados como infraestrutura crítica. LGPD exige segurança, necessidade e responsabilização [56]. O Ajuste SINIEF 2/25 estabelece 132 meses para XMLs de vários DF-e [57]. Lição: o motor regulatório deve ser produto versionado, com filas, idempotência, evidência e matriz de cobertura por CNPJ, regime, UF, município e edição.

### 5.10 SAP Business One

**Caso de uso.** SAP Business One é ERP global para SMB/lower mid-market e subsidiárias, com finanças, compras, vendas, estoque, CRM, produção e MRP. Pode operar on-premise ou cloud/on-demand, com HANA ou SQL, cliente desktop, Web Client e mobile [26][27].

**Contabilidade e operação.** O modelo é robusto: COA hierárquico, determinação automática de contas, contas de controle, posting de documentos, double-entry, períodos, reconciliação bancária/interna, ativos e fechamento. MRP gera recomendações de compra, produção e transferência; produção tem estados, consumo manual/backflush, output e custo. O ciclo de fechamento exige reconciliação, inventário, ativos, impostos e lock de período.

**Brasil, APIs e arquitetura.** A localização brasileira cobre CNPJ/IE, filiais, tax engine, notas e SPED em determinado escopo, mas não foi comprovado suporte completo a eSocial, CT-e, MDF-e, NFS-e, EFD-Reinf ou DCTFWeb. Service Layer expõe REST/OData/JSON, Basic/OAuth, CRUD, consultas, batch e, em releases recentes, webhooks [28]. DI API, SDK, Integration Framework, BTP e add-ons ampliam a superfície.

**Segurança, negócio e lição.** Autorizações por usuário/grupo/módulo, logs de sistema/negócio e opções HANA/SQL são documentados; tenancy, RPO/RTO e preço dependem de deployment/parceiro. A rede de parceiros e localizações é força; fit-gap brasileiro e complexidade de upgrade são riscos. Lição: oferecer ledger e MRP integrados, mas um localization pack brasileiro com matriz de obrigações verificável.

### 5.11 Oracle NetSuite

**Caso de uso.** NetSuite é ERP cloud para mid-market/enterprise com Financial Management, CRM, inventory, procurement, projetos, billing, revenue e OneWorld [29]. OneWorld acrescenta subsidiárias, nexus, múltiplas moedas, intercompany, consolidação e, quando contratado, multi-book [30].

**Contabilidade e operação.** Double-entry, journals, períodos open/locked/closed, close checklist, subledgers, ativos, receita e relatórios com drill-down são documentados [31]. AR/AP, quote-to-cash, procure-to-pay, inventory, projetos e revenue-to-close formam um fluxo integrado. O motor de receita e os livros múltiplos são referências importantes para contratos e grupos.

**Brasil e extensibilidade.** Brazil Localization cobre registros, NF-e/NFS-e, impostos e arquivos bancários em combinação com Electronic Invoicing, LATAM Tax Engine e certificações; as fontes não comprovam ECD, ECF, EFDs, Reinf, DCTFWeb ou eSocial nativos em todos os cenários [30]. SuiteTalk REST, SOAP, RESTlets, SuiteScript, SuiteFlow, SDF, SuiteAnalytics Connect e SuiteApps permitem integração profunda [32].

**Segurança, negócio e lição.** Oracle declara RBAC, MFA, audit trail, SOC/ISO, replicação e disponibilidade média histórica, mas RPO/RTO e tenancy detalhados são contratualmente dependentes. Modelo é quote-based, anual, por módulos, usuários e implementação. Forças: multi-entidade, receita, analytics e extensão. Riscos: TCO, SuiteApps e localização. Lição: separar pricing de core, compliance e implementação, com exportação e testes de migração.

### 5.12 Microsoft Dynamics 365 Business Central

**Caso de uso.** Business Central atende PMEs e mid-market em finanças, vendas, compras, estoque, projetos, planejamento, warehouse, manufatura e serviço. Há edição online Azure e on-premise, Essentials/Premium/Team Members e forte integração com Microsoft 365, Power Platform e Entra [33].

**Contabilidade e operação.** G/L, COA, posting groups, dimensões, AR/AP, bancos, reconciliação, ativos, períodos e relatórios são nativos. MPS/MRP, BOM, routing, work centers, ordens e projetos ligam operação a custo e contabilidade. A documentação nota que não há recurso dedicado de by-product, uma limitação relevante para manufatura de processo.

**Brasil, APIs e segurança.** A lista de disponibilidade identifica Brazil como Available, base W1 e ownership Partner; portanto fiscal brasileiro deve ser validado no app/parceiro. REST API v2, OData/SOAP, AL, Power Automate, Dataverse e webhooks são documentados [35]. O online é multitenant Azure com Azure SQL, isolamento, TDE, Entra/MFA, auditoria e SLA de 99,9% divulgado, mas a documentação tem diferenças públicas sobre retenção de backups (28 versus 30 dias) [34].

**Negócio e lição.** A página US informava US$ 80 Essentials, US$ 110 Premium e US$ 8 Team Members/mês, mas isso é preço regional e não TCO. Forças: ecossistema Microsoft, segurança e operações. Riscos: parceiro brasileiro, releases e APIs/webhooks com renovação. Lição: publicar compatibilidade de localização e contratos de webhook/backup em vez de depender de marketing de cloud.

### 5.13 QuickBooks Online

**Caso de uso.** QuickBooks é referência de bookkeeping cloud para pequenas empresas, com invoices, bills, banking, payments, payroll, reports, projects, inventory e marketplace. A API expõe Account, Customer, Vendor, Invoice, Bill, Payment e JournalEntry, e o modelo funcional é double-entry [36][37].

**Contabilidade e operação.** Bank feeds, categorização, matching, reconciliação, P&L, balanço, GL, aging e lock date são pontos fortes. Advanced inclui custom roles, batch, Excel e backup/restore; fixed assets/depreciação variam por plano. Fluxo é simples e adequado a SMB, mas operações globais e fiscais são localizadas.

**Brasil e negócio.** A página brasileira informa que os produtos QuickBooks não estão mais disponíveis no Brasil [38]. Não se deve atribuir emissão NF-e, NFS-e, SPED, eSocial ou DCTFWeb à oferta atual. Nos EUA, preços observados variavam de Free a Advanced, com add-ons de payroll/payments; a Intuit reportou US$ 4,120 bilhões de receita de QBO Online Accounting no FY2025, que é receita, não usuários.

**Segurança e lição.** Intuit declara SSL, firewall, backups, activity log e audit trail; detalhes de RPO/RTO, residência, retenção e criptografia em repouso não foram completamente publicados nas fontes acessadas. Lição: copiar a simplicidade de onboarding, lock date e API, mas construir desde o início localização brasileira e portabilidade.

### 5.14 Xero

**Caso de uso.** Xero é SaaS contábil global para SMBs e contadores, com invoices, bills, bank feeds, reconciliação, ativos, projetos, relatórios, payroll regional, pagamentos e App Store. A empresa reportou 4,9 milhões de customers no FY26; é métrica corporativa, não adoção brasileira auditada [39].

**Contabilidade e operação.** O modelo API documenta Account e ManualJournal com duas ou mais linhas balanceadas, tracking e tax types. Reconciliation usa Rule, Match, Memory e Prediction/JAX; lock date protege o fechamento. AR/AP, recurring invoices, approvals, bills e ativos completam o fluxo.

**Brasil, APIs e segurança.** Não foi localizada documentação de NF-e, NFS-e, SPED, eSocial ou DCTFWeb brasileiros. Accounting API, OAuth, tenant connections, webhooks HMAC, replay de 31 dias e limites de concorrência/minuto/dia são bem documentados [40]. Xero declara ISO 27001, SOC 2 e PCI DSS, mas não publica RPO/RTO detalhado do Books [41].

**Negócio e lição.** Edições US tinham Early/Growing/Established e add-ons de payroll/inventory; preços e recursos são regionais. Forças: reconciliação, API, marketplace e canal de contadores. Riscos: localização, dependência de apps e caps de volume. Lição: fazer um JAX brasileiro explicável somente depois de consolidar dados e regras confiáveis.

### 5.15 Sage Intacct

**Caso de uso.** Sage Intacct é finance-first cloud para organizações em crescimento, com AP, AR, Cash Management, GL, Purchasing, Order Management, dimensões, projetos, revenue, multi-entidade, consolidação e ativos [42]. A Sage declara 30 mil+ finance teams e 350+ integrações, claims comerciais.

**Contabilidade e operação.** Há double-entry, subledgers em tempo real, dimensões, true close por subledger, intercompany, moeda, ownership, revenue recognition, billing e audit trail. É referência para modelar entidade legal, dimensão, contrato e fechamento, não necessariamente para manufatura ou folha.

**Brasil, API e segurança.** Não foi encontrada prova pública de localização para ECD, ECF, EFDs, NF-e/NFS-e, eSocial, Reinf ou DCTFWeb. REST/OAuth2, XML legado, Platform Services, webhooks/triggers, Salesforce connector e DDS estruturam a extensibilidade [43]. Sage declara TLS, criptografia, MFA/SSO, audit trail, SOC e SLA de 99,8%, mas detalhes de RPO/RTO e retenção são de diligência.

**Negócio e lição.** O modelo é quote-based, modular e partner-led. Forças: close, revenue, dimensões, multi-entidade e auditoria. Riscos: preço e parceiro, localização brasileira e convivência REST/XML. Lição: construir conectores locais sobre um core global somente se o contrato de versão e a evidência regulatória forem fortes.

### 5.16 Odoo Accounting / ERP

**Caso de uso.** Odoo é uma suíte open-source/modular com Community/Enterprise, Odoo Online, Odoo.sh e on-premise. Contabilidade, CRM, vendas, compras, estoque, MRP, POS, projetos e serviços podem compor um ERP único [44].

**Contabilidade e operação.** Odoo documenta double-entry, multiempresa, regimes de competência/caixa, multi-moeda, banking, reconciliação, ativos, depreciação, budgets e fechamento com lock dates. ORM, addons, Python/PostgreSQL, ACLs e record rules permitem grande extensão, mas também aumentam risco de customização.

**Brasil, API e segurança.** A localização brasileira tem l10n_br, contas baseadas no SPED, impostos e módulos de documentos; NF-e/NFC-e/NFS-e usam rota Avalara/AvaTax em escopo documentado, com A1 e limitações de NFS-e. CT-e, MDF-e, ECD/ECF, Reinf e eSocial não foram comprovados como cobertura universal. JSON-2 é Custom-only; RPC antigo está em descontinuação [45].

**Negócio e lição.** Community reduz barreira, enquanto Standard/Custom, hosting, IAP, apps e parceiros compõem TCO. Segurança declara backups, isolamento e criptografia, mas SLA/RPO/RTO detalhados variam. Forças: modularidade e código aberto. Riscos: upgrade, terceiros e fiscal. Lição: APIs e contratos de extensão precisam ser tratados como produto, não como liberdade sem governança.

### 5.17 Zoho Books

**Caso de uso.** Zoho Books é cloud accounting integrado a CRM, Inventory, Expense, Commerce, Payments, Payroll e Analytics. Planos Free a Ultimate atendem microempresas a operações maiores; a página US exibia preços e limites regionais [46].

**Contabilidade e operação.** O produto documenta double-entry, journals, contas, AR/AP, banking, reconciliação, lock por módulo/data, ativos e relatórios. Workflows, custom functions, webhooks e portal do cliente ampliam a operação. Não há evidência de uma edição fiscal brasileira completa.

**Fiscal, API e segurança.** Tax help acessada é predominantemente US, com sales/use tax, Avalara e 1099. REST API v3 usa OAuth, organization_id, quotas por minuto/dia e webhooks com assinatura/histórico [47]. Zoho declara ISO/SOC, 2FA e backups, mas auditoria comparável está documentada apenas para determinadas regiões, não Brasil; RPO/RTO e tenancy interno não são públicos.

**Forças, limitações e lição.** Forças: API, suíte e progressão de planos. Riscos: localização BR, backup iniciado no máximo a cada 15 dias, limites e dependência regional. Lição: publicação de capacidades por país e exportação com metadados é mais importante que uma promessa genérica de “global”.

## 6. Arquitetura de referência para o produto concorrente

Esta seção é **recomendação de construção**, não descrição de qualquer concorrente.

### 6.1 Bounded contexts e módulos

1. **Identity & Tenancy:** organização/escritório, usuário, papel, tenant, empresa, filial, estabelecimento, CNPJ/CPF, IE/IM, procurações, certificados e consentimentos.
2. **Master Data:** pessoas, clientes, fornecedores, produtos, serviços, contas bancárias, plano de contas, plano referencial, centros de custo, dimensões, impostos e códigos fiscais.
3. **Commercial Operations:** vendas, compras, contratos, pedidos, recebimentos, entregas, devoluções, estoque e serviços.
4. **Subledger Finance:** contas a pagar/receber, parcelas, caixa/bancos, conciliação, cobrança, pagamentos, juros, descontos e competência/caixa.
5. **General Ledger:** journals, lotes, partidas, saldos, períodos, rateios, fechamento, reversões, livros e demonstrações.
6. **Fiscal Engine:** regras, tax codes, bases, retenções, CFOP/NCM/CST/CSOSN/NBS, jurisdição, vigência, cenários e simulação.
7. **Government Connectors:** NF-e, NFC-e, NFS-e, CT-e, MDF-e, SPED, eSocial, EFD-Reinf, DCTFWeb/MIT e futuros documentos da Reforma Tributária.
8. **Documents & Evidence:** XML original, PDF auxiliar, anexos, XSD, assinatura, hash, protocolo, recibo, resposta, cadeia de eventos e retenção.
9. **Close & Compliance Workflow:** calendário, obrigações, pré-requisitos, aprovações, fechamento, reabertura, retificação e checklist.
10. **Client/Accountant Collaboration:** portal, tarefas, solicitações, comentários, protocolos, publicação e permissões por cliente.
11. **Integration Platform:** API, OAuth, webhooks, importadores, exportadores, jobs, conectores, rate limits e marketplace.
12. **Analytics & Observability:** relatórios semânticos, indicadores de fechamento, trilhas, métricas de fila, status de órgão, auditoria e alertas.

### 6.2 Modelo de dados contábil

Entidades essenciais:

- `Organization`/`Tenant` e `AccountingOffice`;
- `LegalEntity`, `Branch` e `Establishment`;
- `AccountingPeriod`, `FiscalYear`, `PostingCalendar` e `CloseRun`;
- `ChartOfAccounts`, `Account`, `AccountVersion` e `ReferentialMapping`;
- `Dimension`, `CostCenter`, `Project`, `Department` e `TrackingValue`;
- `Journal`, `JournalEntry`, `JournalLine`, `Batch` e `SourceDocument`;
- `SubledgerDocument`, `Receivable`, `Payable`, `BankTransaction`, `InventoryMovement` e `FixedAsset`;
- `TaxContext`, `TaxRule`, `TaxCode`, `TaxCalculation` e `Obligation`;
- `FiscalDocument`, `FiscalEvent`, `SchemaVersion`, `Transmission`, `Protocol` e `Receipt`;
- `Certificate`, `Credential`, `PowerOfAttorney`, `Signature` e `KeyUsage`;
- `AuditEvent`, `Approval`, `Permission`, `RetentionPolicy` e `ExportPackage`.

Invariantes transacionais:

1. Para todo journal publicado, a soma dos débitos deve ser igual à soma dos créditos na moeda funcional e nas moedas de controle aplicáveis.
2. Journal publicado é imutável; correção é novo journal de reversão, ajuste ou retificação vinculado ao original.
3. Toda linha publicada possui entidade, período, conta, origem, data de lançamento, moeda, valor e autor/serviço de origem.
4. Conta sintética não recebe lançamento quando a hierarquia a define como não-postável.
5. Período fechado rejeita postagem normal; reabertura exige papel autorizado, motivo, aprovação e evento auditável.
6. Saldo de subledger e razão devem reconciliar por chave de lote, competência, entidade e moeda; divergência gera pendência, não ajuste silencioso.
7. Documento fiscal e evento externo devem ser idempotentes por chave de documento/evento, CNPJ, ambiente e versão; reenvio não duplica escrituração.
8. `FiscalDocument` preserva o XML/JSON/texto original e o retorno do órgão; alterações de representação geram nova versão derivada.
9. Uma credencial não pode ser usada fora do tenant, CNPJ, ambiente ou procuração autorizados.
10. Toda exportação, download de dados pessoais, reabertura, cancelamento, baixa e transmissão deve criar `AuditEvent`.

### 6.3 Motor fiscal por regras e vigência

O motor deve ser um serviço separado do ledger, com:

- registry de órgão, documento, versão de leiaute, XSD, tabela, regra e data de vigência;
- jurisdição por UF, município, regime, atividade, estabelecimento e situação especial;
- cálculo determinístico com explicação de base, alíquota, redução, retenção e origem do parâmetro;
- validação estrutural, semântica e de dependência;
- ambientes de homologação e produção;
- assinatura e cofre de certificados;
- filas assíncronas, retry, backoff, circuit breaker e dead-letter queue;
- protocolo, recibo, rejeição, cancelamento, retificação, reabertura e reconciliação;
- changelog legal, testes de regressão e feature flags por competência.

### 6.4 Fechamento, reconciliação e documentos

O fechamento deve ser um grafo de tarefas, não apenas um botão:

1. validar cadastro, período e dependências;
2. importar documentos e identificar duplicidades;
3. processar subledgers e integrações;
4. conciliar bancos, AR/AP, estoque, ativos e impostos;
5. revisar exceções e aprovar ajustes;
6. gerar demonstrações e arquivos;
7. validar com PVA/órgão quando aplicável;
8. transmitir, guardar recibos e marcar obrigação entregue;
9. bloquear período e gerar snapshot de evidência.

A conciliação precisa suportar correspondência 1:1, 1:N e N:1, tolerância configurável, regras explicáveis, match manual, estorno, baixa parcial, tarifas, juros, diferença de câmbio e reconciliação por documento.

### 6.5 Permissões, auditoria, APIs e observabilidade

- **RBAC + ABAC:** escopo por escritório, empresa, estabelecimento, departamento, obrigação, conta, período e operação.
- **Segregação:** preparar, revisar, aprovar e transmitir devem poder ser papéis distintos.
- **Auditoria:** before/after, usuário/serviço, timestamp, IP/dispositivo quando permitido, motivo, aprovação, regra, certificado, hash, protocolo e resultado.
- **API:** OAuth2/OIDC, scopes, rotação, sandbox, OpenAPI, paginação, idempotency key, batch e limites públicos.
- **Webhooks:** assinatura HMAC, event ID, timestamp, replay, retry e polling incremental de reconciliação.
- **Observabilidade:** trace por documento, lote e transmissão; métricas de latência, fila, rejeição, retry, cobertura, validade de certificado, throughput e restauração.

### 6.6 Resiliência, segurança e LGPD

Usar isolamento forte de tenant, criptografia em trânsito/repouso, KMS/HSM para chaves, backups imutáveis, cópia geográfica, restore testado, RPO/RTO publicados, status page, circuit breakers e operação manual documentada. Dados de folha, CPF, bancários e XML devem ser classificados e minimizados. Retenção legal não autoriza manter tudo indefinidamente; a política deve reconciliar Ajuste SINIEF, escrituração, auditoria, legal hold e direitos do titular. A base legal, finalidade, controlador/operador, suboperadores, incidentes e exportação devem ser explícitos.

## 7. Especificação funcional inicial

### 7.1 MVP — provar o ledger e o fechamento de um escritório

#### Épico A — onboarding e migração

**Objetivo:** colocar um escritório e seus primeiros clientes em operação com baixo risco.

**Critérios de aceitação**

- cadastrar escritório, usuários, papéis, clientes, CNPJ, filial, estabelecimento, regime, município, período inicial e fuso;
- importar plano de contas, plano referencial, saldos de abertura, clientes, fornecedores, centros de custo e contas bancárias por CSV/XLSX validado;
- executar dry-run que mostra erros por linha, duplicidades, contas sem mapeamento e diferença de saldos antes de publicar;
- preservar `external_id`, origem, arquivo, usuário, data e lote de importação;
- emitir relatório de reconciliação entre saldo de origem e saldo importado;
- permitir reprocessamento idempotente e rollback lógico do lote.

#### Épico B — ledger e livros

**Critérios de aceitação**

- criar journal draft, submeter para aprovação, publicar, reverter e consultar histórico;
- impedir publicação com débitos e créditos desequilibrados;
- suportar conta, centro de custo, projeto, entidade, filial, moeda, histórico e documento de origem;
- gerar Diário, Razão, balancete, balanço, DRE e composição de saldo com drill-down;
- permitir lançamento automático a partir de AR/AP, banco e documento fiscal;
- manter journals publicados imutáveis e registrar ajustes como novos journals relacionados.

#### Épico C — financeiro e conciliação

**Critérios de aceitação**

- importar OFX/CSV e conectar pelo menos um fluxo de extrato documentado;
- sugerir correspondências por valor, data, documento e regra, mostrando motivo e confiança;
- suportar 1:1, 1:N, N:1, baixa parcial, taxa, juros, desconto e reversão;
- bloquear edição de transação conciliada até desfazer a conciliação;
- reconciliar saldo do extrato com o saldo contábil e gerar exceções rastreáveis;
- gerar contas a pagar/receber a partir de documentos e registrar baixas.

#### Épico D — fechamento e auditoria

**Critérios de aceitação**

- criar calendário e estado de período aberto, em fechamento, fechado e reaberto;
- executar checklist de pendências, conciliações, saldos e documentos;
- impedir lançamento normal em período fechado;
- exigir motivo, aprovação e auditoria para reabertura;
- gerar pacote de fechamento com relatórios, hash, usuário, timestamp, versão de regras e arquivos;
- permitir exportar auditoria em formato estruturado.

#### Épico E — documentos e portal

**Critérios de aceitação**

- receber XML/PDF/anexo por upload, e-mail ou API, com deduplicação por chave/hash;
- classificar documento, relacionar cliente/fornecedor, competência e origem;
- publicar documento ao cliente em portal com permissões e confirmação de leitura;
- abrir solicitação/tarefa com responsável, prazo, status e comentário;
- preservar documento original sem alteração destrutiva.

#### Épico F — API e segurança

**Critérios de aceitação**

- disponibilizar OAuth2/client credentials para integração de parceiro;
- ter scopes, rotação/revogação, rate limit, idempotency key e logs;
- oferecer OpenAPI, ambiente de testes, paginação, lote e consulta de status;
- exigir MFA para administradores e suportar RBAC por escritório/empresa;
- registrar login, exportação, mudança de permissão e ação contábil.

### 7.2 V1 — fiscal brasileiro e operação multiempresa

#### Épico G — emissão e recepção fiscal

**Critérios de aceitação**

- cobrir uma matriz inicial explicitamente publicada de NF-e e documentos de entrada em UFs escolhidas;
- validar schema, regras, assinatura, ambiente e certificado antes do envio;
- transmitir de forma assíncrona, guardar XML, protocolo, retorno e chave;
- tratar autorização, rejeição, cancelamento, inutilização, consulta e contingência quando o conector suportar;
- receber XML distribuído ou importado e reconciliar com documento, financeiro e lançamento;
- classificar recursos como nativo, parceiro ou indisponível por UF/versão.

#### Épico H — ECD/ECF assistidas

**Critérios de aceitação**

- gerar arquivos a partir do ledger, plano referencial, saldos e signatários;
- verificar consistência de partidas, saldos, DRE, balanço e períodos;
- exportar arquivo e pacote para validação no PVA;
- guardar versão de leiaute, programa, arquivo, hash, assinaturas e recibo;
- suportar ECF com recuperação de ECD e saldos da ECF anterior conforme escopo;
- tratar substituição como nova versão relacionada, sem apagar original.

#### Épico I — multiempresa e escritório

**Critérios de aceitação**

- permitir trocar de empresa sem misturar dados ou permissões;
- operar fechamento em lote com execução isolada e resultado por CNPJ;
- dashboards de pendências, prazos, documentos faltantes e tempo de fechamento;
- delegar acesso limitado ao cliente e ao contador responsável;
- gerar relatórios consolidados somente quando a regra de consolidação estiver configurada.

#### Épico J — calendário e obrigações

**Critérios de aceitação**

- manter obrigação, órgão, competência, prazo, condição e dependência;
- notificar certificado próximo do vencimento e obrigação pendente;
- registrar aprovação, transmissão, protocolo, recibo e situação;
- suportar retificação e reabertura com vínculo ao original;
- importar atualização legal sem reimplantar o ledger.

### 7.3 V2 — escala regulatória e diferenciação

- EFD-Reinf, eSocial e DCTFWeb/MIT como workflow de eventos dependentes;
- NFS-e nacional e adaptadores municipais selecionados com matriz pública;
- cofre/HSM e agente seguro para A1/A3, com procuração e segregação;
- conectores bancários e API de parceiros com webhooks assinados, replay e dead-letter;
- ativos/depreciação, CIAP, LALUR, folha integrada ou conectores de folha;
- assistente de conciliação explicável, com aprovação humana e trilha da sugestão;
- pacote de migração round-trip com arquivos, anexos, configurações e evidências;
- status page por governo, parceiro, fila e certificado;
- marketplace de integrações certificadas e contratos de compatibilidade;
- suporte a auditoria independente e exportação de evidências com legal hold.

## 8. Estratégia de negócio

### 8.1 ICP, beachhead e proposta de valor

**ICP inicial:** escritórios contábeis brasileiros com 20–200 CNPJs, equipe de pelo menos contábil/fiscal/administrativo e dor de fechamento, documentos, conciliação, cobrança de pendências e transmissão. Escolher dois ou três estados e um conjunto de regimes/documentos em que a equipe consiga testar profundamente.

**Beachhead:** substituir planilha, exportações fragmentadas e tarefas manuais entre escritório e cliente, não substituir toda a suíte no primeiro dia. O produto deve coexistir com o legado, importar saldos e gerar arquivos, reduzindo a objeção “não posso parar o fechamento”.

**Proposta de valor:** “Feche e entregue com evidência: cada saldo, documento, regra, assinatura, protocolo e aprovação é rastreável; a cobertura fiscal é pública e versionada; seus dados são exportáveis.”

### 8.2 Canais e parcerias

- venda consultiva direta para escritórios âncora;
- programa de contadores com carteira, treinamento e ambiente multiempresa;
- parceiros de implantação certificados por estado e módulo;
- integração com ERPs/marketplaces via API e marketplace;
- parceria com provedores de documentos, certificados, assinatura e contadores, sem transferir responsabilidade de compliance sem contrato;
- conteúdo técnico de changelog legal, matriz de cobertura e guias de migração;
- comunidade e Academy para reduzir dependência de suporte individual.

### 8.3 Pricing e packaging

Recomendação inicial, sem inventar valores:

- **Core Office:** escritório, usuários, empresas, ledger, fechamento, relatórios, portal básico e exportação.
- **Fiscal Local:** cobrança por faixa de CNPJ/documentos e cobertura de obrigações/UFs publicadas.
- **Compliance Advanced:** eventos eSocial/Reinf/DCTFWeb, certificados, armazenamento legal, filas, protocolos e suporte prioritário.
- **Partner/API:** quotas, webhooks, sandbox, logs, ambientes e conectores.
- **Add-ons:** folha, ativos, honorários, banking, OCR, armazenamento adicional e integrações de terceiros.

Publicar limites de empresas, usuários, documentos, armazenamento, API, retenção, suporte e restauração. Não usar “ilimitado” sem explicar fair use, throughput e preço de saída.

### 8.4 Unit economics e customer success

Acompanhar, por coorte e segmento:

- CAC por canal e proporção partner-led;
- tempo até primeiro CNPJ importado, primeiro fechamento e primeira obrigação transmitida;
- custo de onboarding/migração por CNPJ;
- margem bruta por documento, evento, storage, assinatura e suporte;
- taxa de rejeição e retrabalho fiscal;
- ativação de API, conectores e portal;
- retenção líquida, expansão por módulo e churn logo após o primeiro fechamento;
- chamados por CNPJ, tempo de resolução e causas de erro de certificado;
- taxa de restore testado e sucesso de exportação;
- concentração de receita em um órgão, parceiro ou conector.

Customer success deve ter playbooks de onboarding, migração, primeiro fechamento, mudança de versão, renovação de certificado, contingência e auditoria. O sucesso não é apenas login; é fechamento reconciliado e obrigação aceita.

### 8.5 Custos regulatórios e barreiras competitivas

Os custos recorrentes são equipe fiscal/contábil, monitoramento de mudanças, homologação por órgão, manutenção de XSD/tabelas, suporte de certificados, storage de XML, incidentes de órgão, parceiros e testes de regressão. A barreira competitiva sustentável será a base de regras versionadas, histórico, confiança do contador, cobertura demonstrável e migração — não somente número de telas.

## 9. Roadmap de 12–18 meses

| Período | Entregas principais | Dependências | Equipe/competências aproximadas | Riscos e controles |
|---|---|---|---|---|
| Meses 0–3 | Discovery com escritórios; modelo de tenant/entidade; ledger, plano, journals, períodos; importação inicial; segurança base; protótipo de portal | Escritórios design partners, modelo contábil, decisão de ICP | 1 produto, 1 líder técnico, 3–4 backend/full-stack, 1 contábil, 1 QA, segurança compartilhada | Escopo excessivo; congelar MVP e registrar lacunas |
| Meses 3–6 | AR/AP, bancos/OFX, conciliação, documentos, portal/tarefas, auditoria, API OAuth, dashboards e fechamento | Ledger estável, RBAC, storage, observabilidade | 4–6 engenharia, 1 contábil, 1 QA/automação, 1 UX, 1 DevSecOps parcial | Duplicidade e saldos divergentes; testes property-based e reconciliação |
| Meses 6–9 | MVP em produção controlada; NF-e em UFs escolhidas; ECD/ECF assistidas; exportação de pacote; status de fila/certificado | Contratos com provedores/órgãos, homologação, cofre de certificados | +1 especialista fiscal, +1 SRE, +1 suporte/migração; engenharia mantém núcleo | Rejeição fiscal, certificado, PVA; canary, fila, replay e runbook manual |
| Meses 9–12 | V1 multiempresa; mais UFs/documentos; calendário; obrigações selecionadas; partner API/webhooks; migração automatizada | Matriz legal, testes por edição, portal do contador | 6–9 engenharia, 2 fiscal/contábil, 1 QA fiscal, 1 CS, 1 parcerias | Cobertura prometida maior que capacidade; publicar matriz e limitar ICP |
| Meses 12–15 | EFD-Reinf/eSocial/DCTFWeb por fluxo priorizado; NFS-e nacional e municípios selecionados; ativos/CIAP/LALUR conforme demanda | Estado de eventos, certificados/procurações, dependências de origem | +2 especialistas regulatórios, +1 SRE, +1 QA de compliance | Dependência entre órgãos; state machine, feature flags e reabertura |
| Meses 15–18 | Marketplace certificado; analytics avançado; restore/DR demonstrado; SOC/ISO em preparação conforme necessidade; expansão geográfica | Volume, controles, contratos, auditoria independente | 8–12 engenharia total, 2–3 fiscal/contábil, SRE, segurança, CS e parceiros | Crescimento quebrar suporte; SLO, capacity planning e go/no-go por UF |

### 9.1 Build versus buy

**Construir:** ledger, modelo de fechamento, regras de permissão, trilha de auditoria, portal, workflow de obrigações, matriz de cobertura, API de produto, importação/migração e observabilidade de negócio. São ativos centrais e fonte de diferenciação.

**Comprar ou integrar inicialmente:** OCR, envio de e-mail/SMS, storage de objetos, observabilidade de infraestrutura, serviço de assinatura quando a custódia for contratualmente adequada, conectores bancários e alguns provedores municipais. Ainda assim, manter adaptador próprio, reconciliação e exportação; o produto não pode ficar sem explicação porque um terceiro está indisponível.

**Evitar comprar sem due diligence:** “compliance nacional” de caixa preta, certificados sem segregação, API sem contrato de versão, parceiros sem SLA, serviço financeiro regulado que não seja necessário ao MVP e IA que altere lançamentos sem aprovação.

### 9.2 Riscos de segurança e compliance

- chave A1 ou segredo exposto em log, backup, planilha ou suporte;
- A3/smart card sem agente seguro ou com operação manual não auditada;
- transmissão duplicada gerando nota, baixa ou obrigação repetida;
- reprocessar evento depois de retificação sem manter cadeia original;
- tenant de escritório visualizando dados de outro escritório;
- exportação contendo PII fora do escopo e sem expiração;
- retenção menor que obrigação ou eliminação automática durante auditoria;
- regra fiscal nova aplicada a competência histórica sem vigência;
- webhook perdido, status não reconciliado e usuário acreditando que obrigação foi aceita;
- backup sem restore testado e RPO/RTO não conhecido;
- parceiro alterando schema, preço ou disponibilidade sem aviso;
- logs editáveis ou incompletos, impossibilitando evidência perante cliente/órgão.

## 10. Recomendação final priorizada

### 10.1 Lançar primeiro

1. **Ledger de partidas dobradas, plano hierárquico e referencial**, com journals imutáveis, reversões, dimensões, entidades e períodos.
2. **Importação e migração reconciliável**, incluindo saldos, plano, clientes, documentos e IDs externos.
3. **Conciliação bancária explicável**, com OFX/CSV, matching, exceção, baixa parcial e reversão.
4. **Fechamento controlado**, checklist, lock, reabertura aprovada, snapshot e pacote de evidências.
5. **Documentos e portal contador–cliente**, com solicitações, tarefas, publicação, protocolo e permissões.
6. **NF-e e recepção de XML em escopo limitado**, com matriz de cobertura pública, certificados, fila, protocolo, rejeição e contingência conforme suporte.
7. **ECD/ECF assistidas**, com integração de plano referencial, validação PVA e cadeia de assinaturas/recibos.
8. **API e exportação de saída**, com OAuth, webhooks, idempotência, sandbox, OpenAPI e pacote completo de dados.
9. **Auditoria, RBAC/MFA e observabilidade**, desde o primeiro cliente, não como projeto posterior.
10. **Status e changelog legal**, para mostrar cobertura, versões, incidentes e dependências.

### 10.2 Adiar deliberadamente

- cobrir todos os municípios de NFS-e antes de ter adaptador/observabilidade e equipe regulatória;
- folha completa, SST e payroll próprio sem ICP e capacidade de suporte;
- conta digital, crédito, antecipação e custodiar dinheiro;
- marketplace com dezenas de apps sem política de segurança e compatibilidade;
- manufatura MRP/MES, WMS avançado e CRM amplo antes de validar o beachhead;
- IA autônoma para publicar journal, pagar título ou transmitir obrigação;
- customização livre no banco ou SDK sem contrato de versão;
- promessa de SaaS “multi-tenant seguro” sem isolamento, restore, testes e evidências;
- preço “ilimitado” sem fair use, exportação e custo de saída.

### 10.3 Decisão orientadora

A empresa deve competir em **confiança operacional mensurável**: menor tempo para fechar, menor retrabalho de rejeição, maior taxa de reconciliação explicável, exportação testada e cobertura fiscal verificável. Essa tese transforma as lacunas comuns do mercado — preço opaco, arquitetura desconhecida, integração ambígua e cobertura universal não comprovada — em requisitos de produto e venda.

## Referências

[1]: https://www.dominiosistemas.com.br/sistema-de-contabilidade/ "Sistema de Contabilidade | Soluções Domínio Thomson Reuters"
[2]: https://www.dominiosistemas.com.br/solucoes/dominio-pro/modulos/contabilidade/ "Módulo Contabilidade | Domínio Pro"
[3]: https://suporte.dominioatendimento.com/central/faces/solucao.html?codigo=8476 "Onvio API — Documentação Integração API para ERPs"
[4]: https://www.dominiosistemas.com.br/solucoes/dominio-web/ "Domínio Web: O sistema contábil na nuvem"
[5]: https://www.alterdata.com.br/contabil/alterdata-contabil "Alterdata Contábil"
[6]: https://ajuda.alterdata.com.br/wcont "Contábil — Documentação"
[7]: https://www.alterdata.com.br/contabil/eplugin "ePlugin Alterdata"
[8]: https://www.contmatic.com.br/sistema-contabil-contabil-phoenix "Contábil Phoenix — Sistema Contábil em Nuvem"
[9]: https://developer.contmatic.com.br/ "Contmatic Developer"
[10]: https://autoatendimento.contmatic.com.br/hc/pt-br/articles/36584389490067-Concilia%C3%A7%C3%A3o-banc%C3%A1ria "Contábil — Conciliação bancária"
[11]: https://www.totvs.com/sistema-de-gestao/totvs-backoffice-linha-protheus/ "ERP Protheus / TOTVS Backoffice – Linha Protheus"
[12]: https://tdn.totvs.com/pages/viewpage.action?pageId=6064745 "TOTVS Application Server: arquivo de configuração"
[13]: https://centraldeatendimento.totvs.com/hc/pt-br/articles/360053138694-Cross-Segmento-TOTVS-Backoffice-Linha-Protheus-ADVPL-API-Rela%C3%A7%C3%A3o-de-Funcion%C3%A1rios-Global-Acessar "API REST no Protheus: serviço employeedatacontent"
[14]: https://www.totvs.com/cloud/paas/ "TOTVS Cloud PaaS"
[15]: https://site.senior.com.br/erp/ "Sistema ERP da Senior — página oficial do produto"
[16]: https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/erp/home.htm "ERP senior X — manual oficial do usuário"
[17]: https://documentacao.senior.com.br/gestaoempresarialerp/5.10.4/menu_cadastros/f049fec.htm "F049FEC — Roteiro de fechamento contábil"
[18]: https://www.omie.com.br/funcionalidades/painel-do-contador/ "Omie — Sistema para contador/Painel do Contador"
[19]: https://developer.omie.com.br/service-list/ "Portal do Desenvolvedor Omie — Lista de APIs"
[20]: https://www.omie.com.br/uploads/guia_tecnico_2026.pdf "Omie — Guia técnico de Segurança da Informação do ERP 2026"
[21]: https://contaazul.com/planos/ "Planos e Preços Conta Azul"
[22]: https://ajuda.contaazul.com/hc/pt-br/articles/4413331050125-Dom%C3%ADnio-e-Conta-Azul-conhe%C3%A7a-a-integra%C3%A7%C3%A3o-entre-Dom%C3%ADnio-e-Conta-Azul "Domínio e Conta Azul: conheça a integração"
[23]: https://developers.contaazul.com/ "Visão Geral da API Conta Azul"
[24]: https://www.bling.com.br/ "Bling — sua plataforma completa de negócios"
[25]: https://developer.bling.com.br/webhooks "Bling API — Webhooks"
[26]: https://www.sap.com/products/erp/business-one.html "SAP Business One | ERP Software for Small Businesses"
[27]: https://help.sap.com/docs/SAP_BUSINESS_ONE/68a2e87fb29941b5bf959a184d9c6727/4506b86a7d720487e10000000a114a6b.html "SAP Business One 10.0 Online Help"
[28]: https://learning.sap.com/courses/leveraging-the-sap-business-one-service-layer/exploring-the-service-layer-api-architecture-and-capabilities "Exploring the Service Layer API Architecture and Capabilities"
[29]: https://www.netsuite.com/portal/products/erp.shtml "NetSuite Enterprise Resource Planning ERP System"
[30]: https://www.netsuite.com/portal/products/global-business-management.shtml "NetSuite Global Business Management"
[31]: https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/chapter_N1379709.html "NetSuite Accounting Overview"
[32]: https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/chapter_1540391670.html "Overview of SuiteTalk REST Web Services"
[33]: https://www.microsoft.com/en-us/dynamics-365/products/business-central "Dynamics 365 Business Central — página oficial do produto"
[34]: https://learn.microsoft.com/en-us/dynamics365/business-central/dev-itpro/service-overview "Service overview for Business Central online"
[35]: https://learn.microsoft.com/en-us/dynamics365/business-central/dev-itpro/api-reference/v2.0/ "Welcome to the API v2.0 for Business Central"
[36]: https://quickbooks.intuit.com/online/ "QuickBooks Online — página oficial de produto e comparação de planos"
[37]: https://developer.intuit.com/app/developer/qbo/docs/learn/explore-the-quickbooks-online-api "QuickBooks Online API: What you can do — Intuit Developer"
[38]: https://quickbooks.intuit.com/br/ "QuickBooks Online Brasil — descontinuação"
[39]: https://brandfolder.xero.com/NE531UQB/as/xqkt6qjxpxcc3mgstvkfh676/Xero_FY26_Annual_Report "Xero FY26 Annual Report"
[40]: https://developer.xero.com/documentation/guides/webhooks/overview/ "Xero API webhooks"
[41]: https://www.xero.com/us/security/ "Security at Xero"
[42]: https://www.sage.com/en-us/sage-business-cloud/intacct/ "Sage Intacct — visão geral oficial"
[43]: https://developer.intacct.com/ "Sage Intacct Developer e REST API"
[44]: https://www.odoo.com/ "Odoo — Open Source ERP"
[45]: https://www.odoo.com/documentation/19.0/pt_BR/applications/finance/fiscal_localizations/brazil.html "Odoo 19 — Brazil fiscal localization"
[46]: https://www.zoho.com/us/books/pricing/ "Zoho Books — Pricing"
[47]: https://www.zoho.com/books/api/v3/introduction/ "Zoho Books API v3 — Introduction"
[48]: https://www.gov.br/sped/ "Portal SPED — Sistema Público de Escrituração Digital"
[49]: https://www.gov.br/pt-br/servicos/entregar-escrituracao-contabil-digital "Entregar Escrituração Contábil Digital — gov.br"
[50]: https://www.gov.br/pt-br/servicos/entregar-escrituracao-contabil-fiscal "Entregar Escrituração Contábil Fiscal — gov.br"
[51]: https://www.nfe.fazenda.gov.br/portal/webServices.aspx?tipoConteudo=OUC/YVNWZfo= "NF-e — Relação de Serviços Web"
[52]: https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual "NFS-e — Documentação Atual (Produção)"
[53]: https://www.gov.br/esocial/pt-br/documentacao-tecnica "eSocial — Documentação Técnica"
[54]: https://www.gov.br/sped/pt-br/assuntos/escrituracoes-digitais/efd-reinf/manuais-e-documentos-tecnicos/manualorientacaodesenvolvedor-reinf-v2-8.pdf/@@display-file/file "Manual de Orientação ao Desenvolvedor EFD-Reinf v2.8"
[55]: https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/manuais/manual-dctfweb/manual-dctfweb-atualizacao-janeiro2025_versao_final.pdf "Manual da DCTFWeb janeiro 2025"
[56]: https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm "Lei nº 13.709/2018 — LGPD — Planalto"
[57]: https://www.confaz.fazenda.gov.br/legislacao/ajustes/2025/AJ002_25 "Ajuste SINIEF 2/25 — CONFAZ"
