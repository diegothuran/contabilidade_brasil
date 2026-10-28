import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { api } from "../api";
import { can, useSession } from "../session";
import {
  getCloseRun,
  getAiReviews,
  getEvidencePackage,
  getImportBatch,
  getIntegrations,
  getLedgerEvents,
  getObligations,
  getReconciliationCases,
  getTodaySummary,
  type AdapterSource,
} from "./adapters";
import { CompanySearch } from "./CompanySearch";

type PeriodItem = {
  period_id: string;
  fiscal_year: number;
  month: number;
  status: string;
};

const PERIOD_STATUS: Record<string, string> = {
  open: "Aberto",
  closed: "Fechado",
  reopened: "Reaberto",
  closing: "Fechando",
};

const pages: Record<string, { title: string; legacy: string; load: (legalEntityId: string) => Promise<AdapterSource> }> = {
  "/app/rastro": { title: "Hoje", legacy: "/app/journals", load: () => getTodaySummary() },
  "/app/rastro/fechamentos": { title: "Fechamentos", legacy: "/app/periods", load: getCloseRun },
  "/app/rastro/conciliacao": { title: "Conciliação", legacy: "/app/reconciliation", load: getReconciliationCases },
  "/app/rastro/migracoes": { title: "Migrações", legacy: "/app/imports", load: getImportBatch },
  "/app/rastro/ledger": { title: "Dados e ledger", legacy: "/app/journals", load: getLedgerEvents },
  "/app/rastro/revisoes-ia": { title: "Revisões de IA", legacy: "/app/audit", load: () => getAiReviews() },
  "/app/rastro/obrigacoes": { title: "Obrigações e entregas", legacy: "/app/periods", load: () => getObligations() },
  "/app/rastro/integracoes": { title: "Integrações", legacy: "/app/banks", load: () => getIntegrations() },
  "/app/rastro/biblioteca": { title: "Evidências", legacy: "/app/documents", load: getEvidencePackage },
};

function pageFor(pathname: string) {
  if (pathname.startsWith("/app/rastro/fechamentos/")) {
    return pages["/app/rastro/fechamentos"];
  }
  return pages[pathname] ?? pages["/app/rastro"];
}

function itemCount(payload: unknown): number | null {
  if (!payload || typeof payload !== "object" || !("items" in payload)) {
    return null;
  }
  const items = (payload as { items?: unknown }).items;
  return Array.isArray(items) ? items.length : null;
}

function preferredPeriod(items: PeriodItem[]): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1;
  const sorted = [...items].sort((left, right) => left.fiscal_year - right.fiscal_year || left.month - right.month);
  const started = sorted.filter((item) => item.fiscal_year < year || (item.fiscal_year === year && item.month <= month));
  const pool = started.length > 0 ? started : sorted;
  const current = pool.find((item) => item.fiscal_year === year && item.month === month && (item.status === "open" || item.status === "reopened"));
  if (current) {
    return current.period_id;
  }
  const open = [...pool].reverse().find((item) => item.status === "open" || item.status === "reopened");
  return (open ?? pool.at(-1))?.period_id ?? "";
}

function periodTone(status: string): string {
  if (status === "closed") {
    return "success";
  }
  if (status === "open") {
    return "info";
  }
  if (status === "reopened" || status === "closing") {
    return "attention";
  }
  return "neutral";
}

const NO_PERIODS: PeriodItem[] = [];

export function LiveContextBar() {
  const { me, entities, entityId, setEntityId, periodId, setPeriodId } = useSession();
  const periods = useQuery({
    queryKey: ["periods", entityId],
    enabled: Boolean(entityId),
    queryFn: () => api<{ items: PeriodItem[] }>(`/v1/legal-entities/${entityId}/periods`),
  });
  const items = periods.data?.items ?? NO_PERIODS;

  useEffect(() => {
    if (!entityId || periods.isLoading) {
      return;
    }
    if (items.length === 0) {
      if (periodId) {
        setPeriodId("");
      }
      return;
    }
    if (!items.some((item) => item.period_id === periodId)) {
      setPeriodId(preferredPeriod(items));
    }
  }, [entityId, items, periodId, periods.isLoading, setPeriodId]);

  const current = items.find((item) => item.period_id === periodId);

  return (
    <section className="context-bar" aria-label="Contexto operacional">
      <div className="context-label"><span className="context-dot" />Contexto de trabalho</div>
      <CompanySearch entities={entities} entityId={entityId} setEntityId={setEntityId} isAdmin={can(me.roles, "admin")} />
      <label className="context-select context-select--period">
        <span>Competência</span>
        <select data-testid="context-period" value={periodId} disabled={items.length === 0} onChange={(event) => setPeriodId(event.target.value)}>
          {items.length === 0 ? <option value="">Sem competência</option> : null}
          {items.map((item) => (
            <option key={item.period_id} value={item.period_id}>
              {String(item.month).padStart(2, "0")}/{item.fiscal_year}
            </option>
          ))}
        </select>
      </label>
      <span className={`status-badge status-badge--${current ? periodTone(current.status) : "neutral"}`}>
        <i aria-hidden="true" />
        {current ? (PERIOD_STATUS[current.status] ?? current.status) : "Sem período"}
      </span>
    </section>
  );
}

export function LiveSurface() {
  const location = useLocation();
  const { entityId } = useSession();
  const page = pageFor(location.pathname);
  const source = useQuery({
    queryKey: ["rastro-live", location.pathname, entityId],
    queryFn: () => page.load(entityId),
  });
  const count = source.data?.mode === "live" ? itemCount(source.data.payload) : null;

  return (
    <section className="page-header">
      <div>
        <span className="eyebrow">Sala de fechamento · sem demonstração</span>
        <h1>{page.title}</h1>
        {source.isLoading ? <p>Carregando a fonte desta tela.</p> : null}
        {source.isError ? <p>{source.error.message}</p> : null}
        {source.data?.mode === "missing" ? <p>{source.data.endpoint}</p> : null}
        {source.data?.mode === "live" ? (
          <p>
            {source.data.endpoint}
            {count === null ? "" : ` Itens nesta página: ${count}.`}
            {" "}O desenho da sala ainda não traduz esse contrato. A rotina já existente continua disponível.
          </p>
        ) : null}
        {source.data?.mode === "demo" ? <p>{source.data.note}</p> : null}
      </div>
      <div className="page-header__action">
        <Link className="button button--secondary" to={page.legacy}>Abrir rotina existente</Link>
      </div>
    </section>
  );
}
