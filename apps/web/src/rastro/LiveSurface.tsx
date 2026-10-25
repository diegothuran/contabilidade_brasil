import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
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
import { useSession } from "../session";

type PeriodItem = {
  period_id: string;
  fiscal_year: number;
  month: number;
  status: string;
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

export function LiveContextBar() {
  const { entities, entityId, setEntityId } = useSession();
  const [periodId, setPeriodId] = useState("");
  const periods = useQuery({
    queryKey: ["rastro-periods", entityId],
    enabled: Boolean(entityId),
    queryFn: () => getCloseRun(entityId),
  });
  const items = periods.data?.mode === "live" && periods.data.payload && typeof periods.data.payload === "object"
    ? ((periods.data.payload as { items?: PeriodItem[] }).items ?? [])
    : [];
  const selected = entities.find((entity) => entity.legal_entity_id === entityId);

  useEffect(() => {
    if (items.length === 0) {
      setPeriodId("");
      return;
    }
    if (!items.some((item) => item.period_id === periodId)) {
      setPeriodId(items[0].period_id);
    }
  }, [items, periodId]);

  const current = items.find((item) => item.period_id === periodId);

  return (
    <section className="context-bar" aria-label="Contexto operacional">
      <div className="context-label"><span className="context-dot" />Contexto de trabalho</div>
      <label className="context-select">
        <span>Cliente / CNPJ</span>
        <select
          value={entityId}
          disabled={entities.length === 0}
          onChange={(event) => setEntityId(event.target.value)}
        >
          {entities.length === 0 ? <option value="">Nenhuma empresa cadastrada</option> : null}
          {entities.map((entity) => (
            <option key={entity.legal_entity_id} value={entity.legal_entity_id}>{entity.name}</option>
          ))}
        </select>
      </label>
      <span className="context-cnpj">{selected?.cnpj || "Sem CNPJ no sistema"}</span>
      <label className="context-select context-select--period">
        <span>Competência</span>
        <select value={periodId} disabled={items.length === 0} onChange={(event) => setPeriodId(event.target.value)}>
          {items.length === 0 ? <option value="">Sem competência</option> : null}
          {items.map((item) => (
            <option key={item.period_id} value={item.period_id}>
              {String(item.month).padStart(2, "0")}/{item.fiscal_year}
            </option>
          ))}
        </select>
      </label>
      <span className="context-meta">{current ? current.status : "Sem período"}</span>
      <span className="status-badge status-badge--attention"><i aria-hidden="true" />{entityId ? "Troca ligada ao sistema" : "Sem empresa"}</span>
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
