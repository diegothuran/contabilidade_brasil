export type Tone = "neutral" | "info" | "attention" | "danger" | "success";

export type WorkItem = {
  id: string;
  tone: Tone;
  eyebrow: string;
  title: string;
  detail: string;
  company: string;
  period: string;
  responsible: string;
  evidence: string;
  route: string;
  action: string;
  due: string;
};

export type CloseTask = {
  id: string;
  domain: string;
  title: string;
  detail: string;
  state: "concluído" | "atenção" | "bloqueado" | "aguardando aprovação";
  tone: Tone;
  responsible: string;
  evidence: string;
  updatedAt: string;
  blocker?: boolean;
  resolution?: string;
  resolvedBy?: string;
};

export type ReconciliationItem = {
  id: string;
  title: string;
  description: string;
  value: string;
  date: string;
  source: string;
  score: number;
  state: "requer revisão" | "reconciliado" | "rejeitado";
  tone: Tone;
  explanation: string[];
  candidates: { title: string; value: string; date: string; account: string }[];
  evidence: string;
  decision?: { candidate?: string; actor: string; at: string; reason?: string };
};

export type AiSuggestion = {
  id: string;
  title: string;
  target: string;
  confidence: number;
  impact: string;
  state: "sugerido" | "revisado" | "aprovado" | "rejeitado" | "revertido";
  tone: Tone;
  evidence: string;
  rule: string;
  responsible: string;
  reversal: string;
  outcome?: string;
  decision?: { actor: string; at: string; reason?: string };
};

export type LedgerEvent = {
  id: string;
  timestamp: string;
  actor: string;
  type: string;
  title: string;
  detail: string;
  source: string;
  state: string;
  tone: Tone;
  evidence: string;
};

export type Integration = {
  id: string;
  name: string;
  kind: string;
  health: "saudável" | "sincronizando" | "atenção" | "degradada";
  tone: Tone;
  lastSync: string;
  scope: string;
  queue: string;
  detail: string;
  fallback: string;
};
