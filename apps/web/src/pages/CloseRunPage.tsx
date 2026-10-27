import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, api } from "../api";
import { can, useSession } from "../session";

type CloseItem = {
  item_id: string;
  title: string;
  status: string;
  detail: string;
  count: number | null;
  blocking: boolean;
  href: string;
  reference: string;
  not_applicable_reason: string | null;
  decided_by: string | null;
};

type CloseRun = {
  close_run_id: string;
  status: string;
  run_number: number;
  checklist_version: string;
  checklist: CloseItem[];
  snapshot_sha256: string | null;
  closed_at: string | null;
  closed_by: string | null;
};

const ITEM_STATUS: Record<string, string> = {
  pending: "Pendente",
  in_progress: "Em andamento",
  blocked: "Bloqueia",
  completed: "Concluído",
  not_applicable: "Não aplicável",
};

const TONE: Record<string, string> = {
  pending: "attention",
  blocked: "danger",
  completed: "success",
  not_applicable: "info",
  in_progress: "info",
};

function blockersOf(run: CloseRun | undefined): CloseItem[] {
  return (run?.checklist ?? []).filter((item) => item.blocking && item.status !== "completed" && item.status !== "not_applicable");
}

export function CloseRunPage() {
  const { periodId = "" } = useParams();
  const { entityId, me } = useSession();
  const queryClient = useQueryClient();
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState("");
  const canDecide = can(me.roles, "approver", "admin");
  const run = useQuery({
    queryKey: ["close-run", entityId, periodId],
    queryFn: async () => {
      const listed = await api<{ items: { period_id: string; status: string; close_run_id?: string | null }[] }>(
        `/v1/legal-entities/${entityId}/periods`,
      );
      const period = listed.items.find((item) => item.period_id === periodId);
      if (!period) {
        throw new ApiError(404, "Não encontrado", "Período não encontrado.");
      }
      if (period.status === "closed" && period.close_run_id) {
        return api<CloseRun>(`/v1/close-runs/${period.close_run_id}`);
      }
      const opened = await api<{ close_run_id: string }>(`/v1/periods/${periodId}/close-runs`, { body: {} });
      return api<CloseRun>(`/v1/close-runs/${opened.close_run_id}`);
    },
  });
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ["close-run", entityId, periodId] });
    await queryClient.invalidateQueries({ queryKey: ["periods", entityId] });
  };
  const decide = useMutation({
    mutationFn: (action: { itemId: string; status: "completed" | "not_applicable"; reason?: string }) =>
      api(`/v1/close-runs/${run.data?.close_run_id}/items/${action.itemId}`, {
        body: { status: action.status, reason: action.reason },
      }),
    onSuccess: refresh,
  });
  const closeRun = useMutation({
    mutationFn: () => api(`/v1/close-runs/${run.data?.close_run_id}/close`, { body: {} }),
    onSuccess: async () => {
      setNotice("Competência fechada. O snapshot ficou gravado.");
      await refresh();
    },
  });

  const current = run.data;
  const blockers = blockersOf(current);
  const error = run.error ?? decide.error ?? closeRun.error;
  const errorText = error instanceof ApiError ? `${error.title}. ${error.message}` : error ? "Falha na operação." : "";

  async function downloadPackage() {
    if (!current) {
      return;
    }
    const payload = await api<unknown>(`/v1/close-runs/${current.close_run_id}/evidence-package`);
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `pacote-${current.close_run_id}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <>
      <section className="page-header">
        <div>
          <span className="eyebrow">Fechamento</span>
          <h1>Checklist da competência</h1>
          <p>A competência só fecha quando cada bloqueio está concluído ou marcado como não aplicável, com motivo. O snapshot não é editado.</p>
        </div>
      </section>
      {current ? (
        <section className="close-hero panel">
          <div className="close-hero__state">
            <h2>
              {current.checklist.filter((item) => item.status === "completed" || item.status === "not_applicable").length} de {current.checklist.length} itens resolvidos
            </h2>
            <p>
              Execução {current.run_number} · {current.checklist_version}
              {blockers.length > 0 ? ` · ${blockers.length} bloqueio(s) pendente(s).` : " · Nenhum bloqueio pendente."}
            </p>
          </div>
          <div className="close-hero__actions">
            {current.status === "open" && canDecide ? (
              <button type="button" data-testid="close-period" disabled={blockers.length > 0 || closeRun.isPending} onClick={() => closeRun.mutate()}>
                Fechar
              </button>
            ) : null}
            {current.snapshot_sha256 ? (
              <button type="button" className="secondary" data-testid="download-package" onClick={() => void downloadPackage()}>
                Baixar pacote
              </button>
            ) : null}
          </div>
        </section>
      ) : null}
      {notice ? <p className="ok">{notice}</p> : null}
      {errorText ? <p className="error">{errorText}</p> : null}
      {blockers.length > 0 ? (
        <p className="muted">Falta resolver: {blockers.map((item) => item.title).join(", ")}.</p>
      ) : null}
      {current?.snapshot_sha256 ? (
        <p className="muted" data-testid="snapshot-sha">
          SHA-256 do snapshot: {current.snapshot_sha256}
          {current.closed_by ? ` · fechado por ${current.closed_by}` : ""}
          {current.closed_at ? ` em ${current.closed_at}` : ""}
        </p>
      ) : null}
      <section className="panel panel--flush">
        <div className="checklist-list" data-testid="close-checklist">
          {(current?.checklist ?? []).map((item) => (
            <article className="checklist-row" key={item.item_id}>
              <div className={`check-icon check-icon--${TONE[item.status] ?? "info"}`}>{item.status === "completed" || item.status === "not_applicable" ? "✓" : "!"}</div>
              <div className="checklist-row__main">
                <div className="checklist-row__title">
                  <span>{ITEM_STATUS[item.status] ?? item.status}{item.blocking ? " · bloqueia" : ""}</span>
                  <h3>{item.title}</h3>
                </div>
                <p>{item.detail}</p>
                <div className="checklist-row__meta">
                  <span>{item.reference}</span>
                  {item.count !== null ? <span>{item.count}</span> : null}
                  <Link className="inline-action" to={item.href}>Abrir origem</Link>
                </div>
                {item.not_applicable_reason ? <div className="resolution-record"><strong>Motivo: </strong>{item.not_applicable_reason}{item.decided_by ? ` · ${item.decided_by}` : ""}</div> : null}
                {current?.status === "open" && canDecide && item.status !== "completed" && item.status !== "not_applicable" ? (
                  <div className="row">
                    {item.item_id === "trial_balance_review" ? (
                      <button type="button" data-testid="review-trial-balance" disabled={decide.isPending} onClick={() => decide.mutate({ itemId: item.item_id, status: "completed" })}>
                        Revisar balancete
                      </button>
                    ) : null}
                    <input
                      data-testid={`waive-${item.item_id}`}
                      value={reasons[item.item_id] ?? ""}
                      onChange={(event) => setReasons((currentReasons) => ({ ...currentReasons, [item.item_id]: event.target.value }))}
                      placeholder="Motivo para marcar como não aplicável"
                    />
                    <button
                      type="button"
                      className="secondary"
                      disabled={(reasons[item.item_id] ?? "").trim().length < 10 || decide.isPending}
                      onClick={() => decide.mutate({ itemId: item.item_id, status: "not_applicable", reason: reasons[item.item_id] })}
                    >
                      Não se aplica
                    </button>
                  </div>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}
