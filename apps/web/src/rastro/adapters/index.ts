import { api } from "../../api";
import { rastroDemoEnabled } from "../demo";

const DEMO_NOTE = "Dados sintéticos em memória. Nenhuma ação grava lançamento, aprovação, transmissão ou aceite.";

export type AdapterSource =
  | { mode: "demo"; note: string }
  | { mode: "missing"; endpoint: string }
  | { mode: "live"; endpoint: string; payload: unknown };

function demoOr(load: () => Promise<AdapterSource>): Promise<AdapterSource> {
  if (rastroDemoEnabled()) {
    return Promise.resolve({ mode: "demo", note: DEMO_NOTE });
  }
  return load();
}

function needsCompany(legalEntityId: string, endpoint: string): AdapterSource | null {
  if (legalEntityId) {
    return null;
  }
  return { mode: "missing", endpoint: `${endpoint} A sala não inventa empresa quando o escritório ainda não tem uma.` };
}

export function getTodaySummary(): Promise<AdapterSource> {
  return demoOr(async () => ({
    mode: "missing",
    endpoint: "TODO: endpoint necessário para a fila de exceções do dia.",
  }));
}

export function getCloseRun(legalEntityId: string): Promise<AdapterSource> {
  return demoOr(async () => {
    const blocked = needsCompany(legalEntityId, "TODO: endpoint necessário para o checklist de fechamento.");
    if (blocked) {
      return blocked;
    }
    const payload = await api<{ items: { close_run_id?: string | null }[] }>(
      `/v1/legal-entities/${encodeURIComponent(legalEntityId)}/periods`,
    );
    const closeRunId = payload.items.find((item) => item.close_run_id)?.close_run_id;
    if (!closeRunId) {
      return {
        mode: "live",
        endpoint: "POST /v1/periods/{period_id}/close-runs abre a execução. A lista ainda não tem uma.",
        payload,
      };
    }
    const checklist = await api<unknown>(`/v1/close-runs/${encodeURIComponent(closeRunId)}`);
    return {
      mode: "live",
      endpoint: "GET /v1/close-runs/{close_run_id}",
      payload: checklist,
    };
  });
}

export function getReconciliationCases(legalEntityId: string): Promise<AdapterSource> {
  return demoOr(async () => {
    const blocked = needsCompany(legalEntityId, "GET /v1/bank-accounts e GET /v1/reconciliation-cases.");
    if (blocked) {
      return blocked;
    }
    const accounts = await api<{ items: { bank_account_id: string }[] }>(
      `/v1/bank-accounts?legal_entity_id=${encodeURIComponent(legalEntityId)}`,
    );
    const bankAccountId = accounts.items[0]?.bank_account_id;
    if (!bankAccountId) {
      return { mode: "live", endpoint: "GET /v1/bank-accounts", payload: accounts };
    }
    const payload = await api<unknown>(`/v1/reconciliation-cases?bank_account_id=${encodeURIComponent(bankAccountId)}`);
    return { mode: "live", endpoint: "GET /v1/reconciliation-cases", payload };
  });
}

export function getImportBatch(legalEntityId: string): Promise<AdapterSource> {
  return demoOr(async () => {
    const blocked = needsCompany(legalEntityId, "GET /v1/import-batches.");
    if (blocked) {
      return blocked;
    }
    const payload = await api<unknown>(`/v1/import-batches?legal_entity_id=${encodeURIComponent(legalEntityId)}`);
    return { mode: "live", endpoint: "GET /v1/import-batches", payload };
  });
}

export function getLedgerEvents(legalEntityId: string): Promise<AdapterSource> {
  return demoOr(async () => {
    const blocked = needsCompany(legalEntityId, "GET /v1/journals e GET /v1/audit-events.");
    if (blocked) {
      return blocked;
    }
    const payload = await api<unknown>(`/v1/journals?legal_entity_id=${encodeURIComponent(legalEntityId)}&limit=50`);
    return {
      mode: "live",
      endpoint: "GET /v1/journals. A trilha de auditoria separada é GET /v1/audit-events.",
      payload,
    };
  });
}

export function getAiReviews(): Promise<AdapterSource> {
  return demoOr(async () => ({
    mode: "missing",
    endpoint: "TODO: endpoint necessário para sugestão de IA. Sugestão não publica lançamento nem transmite obrigação.",
  }));
}

export function getObligations(): Promise<AdapterSource> {
  return demoOr(async () => ({
    mode: "missing",
    endpoint: "TODO: endpoint necessário para obrigação, protocolo e recibo.",
  }));
}

export function getIntegrations(): Promise<AdapterSource> {
  return demoOr(async () => ({
    mode: "missing",
    endpoint: "TODO: endpoint necessário para saúde de conector.",
  }));
}

export function getEvidencePackage(legalEntityId: string): Promise<AdapterSource> {
  return demoOr(async () => {
    const blocked = needsCompany(legalEntityId, "TODO: endpoint necessário para o pacote de fechamento.");
    if (blocked) {
      return blocked;
    }
    const payload = await api<unknown>(
      `/v1/documents?legal_entity_id=${encodeURIComponent(legalEntityId)}`,
    );
    return {
      mode: "live",
      endpoint: "GET /v1/documents. Não existe pacote de fechamento; a resposta é a lista de documentos.",
      payload,
    };
  });
}
