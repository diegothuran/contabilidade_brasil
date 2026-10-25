import type { AiSuggestion, CloseTask, Integration, LedgerEvent, ReconciliationItem, WorkItem } from "./types";

export const office = {
  name: "Martins & Rocha Contabilidade",
  unit: "Unidade São Paulo",
  user: "Marina Rocha",
  role: "Aprovadora contábil",
};

export const companies = [
  { id: "orbe", name: "Orbe Serviços Digitais Ltda.", cnpj: "12.345.678/0001-90", regime: "Lucro Presumido", uf: "SP", state: "Pré-fechamento" },
  { id: "aurora", name: "Aurora Comércio e Design Ltda.", cnpj: "43.210.987/0001-17", regime: "Simples Nacional", uf: "SP", state: "Aguardando documentos" },
  { id: "maralto", name: "Mar Alto Logística Ltda.", cnpj: "07.216.458/0001-63", regime: "Lucro Real", uf: "RJ", state: "Aberto" },
];

export const periods = ["01/2025", "12/2024", "11/2024"];

export const workItems: WorkItem[] = [
  {
    id: "wi-migration",
    tone: "danger",
    eyebrow: "Migração · bloqueio material",
    title: "Diferença de R$ 14.280,00 entre abertura e razão",
    detail: "12 contas permaneceram sem mapeamento após o dry-run. A publicação do lote está bloqueada.",
    company: "Orbe Serviços Digitais Ltda.",
    period: "01/2025",
    responsible: "Caio Mendes",
    evidence: "Lote IMP-2025-01-018 · versão de mapeamento 4",
    route: "/migracoes",
    action: "Ver diferença",
    due: "Hoje, 14:00",
  },
  {
    id: "wi-document",
    tone: "attention",
    eyebrow: "Documento · aguardando cliente",
    title: "Extrato de investimento ainda não foi recebido",
    detail: "A conciliação de aplicações financeiras depende do arquivo de janeiro e impede o checklist financeiro.",
    company: "Orbe Serviços Digitais Ltda.",
    period: "01/2025",
    responsible: "Cliente · Orbe",
    evidence: "Solicitação DOC-483 · enviada há 5 dias",
    route: "/fechamentos/2025-01",
    action: "Abrir solicitação",
    due: "Hoje, 17:00",
  },
  {
    id: "wi-ai",
    tone: "attention",
    eyebrow: "Assistência · baixa confiança",
    title: "Revisar sugestão de classificação para tarifa bancária",
    detail: "A sugestão possui 62% de confiança e altera a classificação gerencial do período.",
    company: "Orbe Serviços Digitais Ltda.",
    period: "01/2025",
    responsible: "Marina Rocha",
    evidence: "Sugestão IA-071 · regra de recorrência v1.4",
    route: "/revisoes-ia",
    action: "Revisar sugestão",
    due: "Hoje, 16:30",
  },
  {
    id: "wi-obligation",
    tone: "info",
    eyebrow: "Obrigação · retorno pendente",
    title: "ECD pré-validada, aguardando conferência final",
    detail: "A regra v2025.1 está aplicada. Há 1 observação não bloqueante na composição do pacote.",
    company: "Orbe Serviços Digitais Ltda.",
    period: "01/2025",
    responsible: "Lucas Barros",
    evidence: "Pré-validação REG-ECF-091 · regra v2025.1",
    route: "/obrigacoes",
    action: "Ver pré-validação",
    due: "Amanhã, 10:00",
  },
];

export const initialCloseTasks: CloseTask[] = [
  { id: "close-import", domain: "Entradas", title: "Importações validadas", detail: "3 lotes importados; 1 lote de migração permanece separado para revisão.", state: "concluído", tone: "success", responsible: "Caio Mendes", evidence: "IMP-2025-01-011 a IMP-2025-01-014", updatedAt: "Hoje, 09:42" },
  { id: "close-bank", domain: "Conciliação", title: "Conciliação bancária", detail: "86 de 89 movimentos reconciliados. 3 casos estão atribuídos para revisão humana.", state: "atenção", tone: "attention", responsible: "Marina Rocha", evidence: "REC-218 a REC-220", updatedAt: "Hoje, 10:18", blocker: true },
  { id: "close-doc", domain: "Documentos", title: "Documentos de investimento", detail: "Extrato de aplicação financeira solicitado ao cliente; ainda sem leitura confirmada.", state: "bloqueado", tone: "danger", responsible: "Cliente · Orbe", evidence: "DOC-483 · solicitação enviada", updatedAt: "Há 5 dias", blocker: true },
  { id: "close-ledger", domain: "Ledger", title: "Balancete e saldos de controle", detail: "Saldos consolidados e razão verificados contra o plano de contas vigente.", state: "concluído", tone: "success", responsible: "Caio Mendes", evidence: "BAL-2025-01 · snapshot S-778", updatedAt: "Hoje, 11:02" },
  { id: "close-reg", domain: "Entrega", title: "Pré-validação de obrigação", detail: "Pacote ECD preparado com uma observação não bloqueante de descrição.", state: "aguardando aprovação", tone: "info", responsible: "Lucas Barros", evidence: "REG-ECF-091 · regra v2025.1", updatedAt: "Hoje, 11:14" },
];

export const initialReconciliations: ReconciliationItem[] = [
  {
    id: "rec-218",
    title: "TED recebida · Cliente Orbe",
    description: "Movimento de entrada importado do extrato OFX sem vínculo publicado.",
    value: "R$ 18.450,00",
    date: "29 jan 2025",
    source: "OFX · Banco Horizonte · FITID 848390",
    score: 92,
    state: "requer revisão",
    tone: "attention",
    explanation: ["Valor idêntico", "Data igual", "Histórico compatível: contrato mensal"],
    candidates: [
      { title: "Receita de serviços · NF 1842", value: "R$ 18.450,00", date: "29 jan 2025", account: "1.1.1.02 · Banco" },
      { title: "Adiantamento de cliente", value: "R$ 18.450,00", date: "28 jan 2025", account: "2.1.3.08 · Adiantamentos" },
    ],
    evidence: "REC-218 · extrato, lançamento JNL-882 e regra de score v1.0",
  },
  {
    id: "rec-219",
    title: "Tarifa de cobrança",
    description: "Débito bancário com descrição parcial; a regra encontrou uma despesa recorrente provável.",
    value: "R$ 73,20",
    date: "30 jan 2025",
    source: "OFX · Banco Horizonte · FITID 848414",
    score: 62,
    state: "requer revisão",
    tone: "attention",
    explanation: ["Valor idêntico", "Data dentro da tolerância de 3 dias", "Histórico parcialmente compatível"],
    candidates: [
      { title: "Despesa bancária · recorrência", value: "R$ 73,20", date: "28 jan 2025", account: "3.2.2.04 · Despesas bancárias" },
      { title: "Tarifa de plataforma", value: "R$ 73,20", date: "31 jan 2025", account: "3.2.3.01 · Serviços de terceiros" },
    ],
    evidence: "REC-219 · extrato, lançamento JNL-889 e tolerância configurada",
  },
  {
    id: "rec-220",
    title: "Pagamento de fornecedor",
    description: "Movimento foi reconciliado e aprovado pela preparadora em 28 de janeiro.",
    value: "R$ 4.680,00",
    date: "28 jan 2025",
    source: "OFX · Banco Horizonte · FITID 848201",
    score: 98,
    state: "reconciliado",
    tone: "success",
    explanation: ["Valor idêntico", "Data igual", "Documento vinculado"],
    candidates: [
      { title: "Fornecedor Nuvem Clara · fatura 881", value: "R$ 4.680,00", date: "28 jan 2025", account: "2.1.1.03 · Fornecedores" },
    ],
    evidence: "REC-220 · aprovação APR-019 · JNL-871",
  },
];

export const initialAiSuggestions: AiSuggestion[] = [
  { id: "ai-071", title: "Classificar tarifa bancária", target: "Movimento REC-219", confidence: 62, impact: "Altera a classificação gerencial; não publica lançamento.", state: "sugerido", tone: "attention", evidence: "Extrato OFX, recorrência de 3 meses e regra de similaridade", rule: "Assistência de classificação v1.4", responsible: "Marina Rocha", reversal: "Rejeitar ou reverter a aprovação antes de aplicar qualquer classificação." },
  { id: "ai-068", title: "Vincular documento a lançamento", target: "Documento DOC-472", confidence: 94, impact: "Cria vínculo de evidência, sem efeito no ledger.", state: "revisado", tone: "info", evidence: "CNPJ, valor e competência coincidentes", rule: "Extração documental v1.2", responsible: "Lucas Barros", reversal: "Desvincular a evidência e retornar a sugestão para revisão." },
  { id: "ai-061", title: "Agrupar três recibos de despesa", target: "Lote IMP-2025-01-014", confidence: 88, impact: "Prepara agrupamento para revisão do lote.", state: "aprovado", tone: "success", evidence: "Fornecedor, datas e soma dos valores", rule: "Agrupamento assistido v1.1", responsible: "Marina Rocha", reversal: "Reverter a aprovação; o lote não terá efeito até publicação humana.", outcome: "Aprovação registrada por Marina Rocha", decision: { actor: "Marina Rocha", at: "Hoje, 09:14" } },
];

export const ledgerEvents: LedgerEvent[] = [
  { id: "evt-1902", timestamp: "31 jan 2025 · 11:14", actor: "Lucas Barros", type: "Pré-validação", title: "Pacote ECD preparado", detail: "Regra v2025.1 aplicada com uma observação não bloqueante.", source: "REG-ECF-091", state: "Pronto para aprovação", tone: "info", evidence: "Relatório de pré-validação e versão da regra" },
  { id: "evt-1899", timestamp: "31 jan 2025 · 10:18", actor: "Marina Rocha", type: "Conciliação", title: "Caso REC-220 aprovado", detail: "Vínculo entre extrato e fatura de fornecedor registrado sem alteração de origem.", source: "REC-220", state: "Reconciliado", tone: "success", evidence: "Score, candidatos, aprovação APR-019" },
  { id: "evt-1896", timestamp: "31 jan 2025 · 09:42", actor: "Caio Mendes", type: "Importação", title: "Lote de diário validado", detail: "1.248 linhas processadas; 1 duplicidade identificada e mantida no relatório.", source: "IMP-2025-01-014", state: "Dry-run concluído", tone: "success", evidence: "Hash, arquivo original, relatório de diferenças" },
  { id: "evt-1891", timestamp: "30 jan 2025 · 16:30", actor: "Sistema", type: "Assistência", title: "Sugestão de classificação criada", detail: "A IA sugeriu tarifa bancária com confiança de 62%; aguarda revisão humana.", source: "IA-071", state: "Sugerido", tone: "attention", evidence: "Modelo, regra, entrada e explicação" },
  { id: "evt-1884", timestamp: "29 jan 2025 · 14:07", actor: "Cliente · Orbe", type: "Documento", title: "Solicitação de extrato enviada", detail: "Cliente notificado pelo portal; leitura ainda não confirmada.", source: "DOC-483", state: "Aguardando cliente", tone: "danger", evidence: "Solicitação, destinatário, prazo e histórico" },
];

export const initialIntegrations: Integration[] = [
  { id: "int-bank", name: "Banco Horizonte", kind: "Open Finance · extratos", health: "saudável", tone: "success", lastSync: "Hoje, 10:04", scope: "Orbe · conta final 2049", queue: "0 itens em fila", detail: "Consentimento válido até 12 mar 2025.", fallback: "Importar OFX caso a conexão seja interrompida." },
  { id: "int-fiscal", name: "Registro Fiscal SP", kind: "Pré-validação · obrigação", health: "atenção", tone: "attention", lastSync: "Hoje, 09:37", scope: "Orbe · competência 01/2025", queue: "1 retorno aguardado", detail: "Versão da regra atualizada em 29 jan 2025.", fallback: "Gerar arquivo de conferência para validação manual." },
  { id: "int-docs", name: "Portal do cliente", kind: "Documentos e solicitações", health: "degradada", tone: "danger", lastSync: "Há 5 dias", scope: "Orbe · DOC-483", queue: "1 solicitação sem leitura", detail: "Lembrete agendado; entrega ainda não confirmada.", fallback: "Registrar contato manual mantendo a timeline." },
];

export const migrationRows = [
  { label: "Contas mapeadas", value: "248 de 260", tone: "success" as const, note: "12 contas sem destino definido" },
  { label: "Lançamentos analisados", value: "1.248", tone: "success" as const, note: "0 linhas inválidas" },
  { label: "IDs externos duplicados", value: "4", tone: "attention" as const, note: "Mantidos no relatório; não serão publicados" },
  { label: "Diferença residual", value: "R$ 14.280,00", tone: "danger" as const, note: "Exige justificativa e aprovação" },
];
