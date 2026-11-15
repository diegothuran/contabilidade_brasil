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

type ClientSummary = {
  summary_id: string;
  status: "draft" | "published" | "withdrawn";
  payload: { sentences: string[] };
  created_by: string;
  published_by: string | null;
  withdrawn_reason: string | null;
};

const SUMMARY_STATUS: Record<string, string> = {
  draft: "Rascunho, o cliente ainda não vê",
  published: "Publicado para o cliente",
  withdrawn: "Retirado",
};

function ClientSummaryPanel({ periodId }: { periodId: string }) {
  const { me } = useSession();
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const [asking, setAsking] = useState(false);
  const canGenerate = can(me.roles, "preparer", "approver", "admin");
  const canDecide = can(me.roles, "approver", "admin");
  const key = ["client-summary", periodId];
  const summary = useQuery({
    queryKey: key,
    queryFn: async (): Promise<ClientSummary | null> => {
      try {
        return await api<ClientSummary>(`/v1/periods/${periodId}/client-summary`);
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          return null;
        }
        throw error;
      }
    },
  });
  const done = async () => {
    setReason("");
    setAsking(false);
    await queryClient.invalidateQueries({ queryKey: key });
  };
  const generate = useMutation({ mutationFn: () => api(`/v1/periods/${periodId}/client-summary`, { body: {} }), onSuccess: done });
  const publish = useMutation({ mutationFn: () => api(`/v1/periods/${periodId}/client-summary/publish`, { body: {} }), onSuccess: done });
  const withdraw = useMutation({
    mutationFn: () => api(`/v1/periods/${periodId}/client-summary/withdraw`, { body: { reason: reason.trim() } }),
    onSuccess: done,
  });
  const current = summary.data ?? null;
  const error = summary.error ?? generate.error ?? publish.error ?? withdraw.error;
  const errorText = error instanceof ApiError ? `${error.title}. ${error.message}` : error ? "Falha na operação." : "";
  const isOwnDraft = current?.status === "draft" && current.created_by === me.user_id;
  return (
    <section className="panel" data-testid="client-summary-panel">
      <span className="eyebrow">Cliente da empresa</span>
      <h2>Resumo para o cliente</h2>
      <p className="muted">Frases fixas calculadas do razão fechado. Quem gera não publica, e a reabertura retira o resumo.</p>
      {current ? (
        <>
          <p><strong>{SUMMARY_STATUS[current.status]}</strong></p>
          <ul data-testid="client-summary-sentences">
            {current.payload.sentences.map((sentence) => <li key={sentence}>{sentence}</li>)}
          </ul>
        </>
      ) : (
        <p className="muted">Ainda não há resumo desta competência.</p>
      )}
      {current?.status === "withdrawn" && current.withdrawn_reason ? <p className="muted">Motivo da retirada: {current.withdrawn_reason}</p> : null}
      {isOwnDraft && canDecide ? <p className="muted">Você gerou este rascunho. Outra pessoa precisa publicar.</p> : null}
      <div className="row">
        {canGenerate && (!current || current.status === "draft") ? (
          <button type="button" className="secondary" disabled={generate.isPending} onClick={() => generate.mutate()}>
            {current ? "Recalcular resumo" : "Gerar resumo"}
          </button>
        ) : null}
        {canDecide && current?.status === "draft" && !isOwnDraft ? (
          <button type="button" disabled={publish.isPending} onClick={() => publish.mutate()}>Publicar</button>
        ) : null}
        {canDecide && current?.status === "published" ? (
          <button type="button" className="secondary" onClick={() => setAsking(true)}>Retirar</button>
        ) : null}
      </div>
      {asking ? (
        <div className="row">
          <input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Motivo da retirada (mínimo 10 caracteres)" aria-label="Motivo da retirada" />
          <button type="button" disabled={reason.trim().length < 10 || withdraw.isPending} onClick={() => withdraw.mutate()}>Confirmar retirada</button>
          <button type="button" className="secondary" onClick={() => setAsking(false)}>Cancelar</button>
        </div>
      ) : null}
      {errorText ? <p className="error">{errorText}</p> : null}
    </section>
  );
}

export function CloseRunPage() {
  const { periodId = "" } = useParams();
  const { entityId, me } = useSession();
  const queryClient = useQueryClient();
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState("");
  const canDecide = can(me.roles, "approver", "admin");
  const canOpen = can(me.roles, "preparer", "approver", "admin");
  // Leitura só lê. A execução de fechamento nasce por ação explícita (abrir checklist),
  // nunca por um refetch da tela.
  const run = useQuery({
    queryKey: ["close-run", entityId, periodId],
    queryFn: async (): Promise<{ run: CloseRun | null; status: string }> => {
      const listed = await api<{
        items: { period_id: string; status: string; close_run_id?: string | null; close_run_status?: string | null }[];
      }>(`/v1/legal-entities/${entityId}/periods`);
      const period = listed.items.find((item) => item.period_id === periodId);
      if (!period) {
        throw new ApiError(404, "Não encontrado", "Período não encontrado.");
      }
      const current = period.close_run_id && (period.status === "closed" || period.close_run_status === "open");
      if (!current) {
        return { run: null, status: period.status };
      }
      return { run: await api<CloseRun>(`/v1/close-runs/${period.close_run_id}`), status: period.status };
    },
  });
  const openRun = useMutation({
    mutationFn: () => api<{ close_run_id: string }>(`/v1/periods/${periodId}/close-runs`, { body: {} }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["close-run", entityId, periodId] });
      await queryClient.invalidateQueries({ queryKey: ["periods", entityId] });
    },
  });
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ["close-run", entityId, periodId] });
    await queryClient.invalidateQueries({ queryKey: ["periods", entityId] });
  };
  const decide = useMutation({
    mutationFn: (action: { itemId: string; status: "completed" | "not_applicable"; reason?: string }) =>
      api(`/v1/close-runs/${run.data?.run?.close_run_id}/items/${action.itemId}`, {
        body: { status: action.status, reason: action.reason },
      }),
    onSuccess: refresh,
  });
  const closeRun = useMutation({
    mutationFn: () => api(`/v1/close-runs/${run.data?.run?.close_run_id}/close`, { body: {} }),
    onSuccess: async () => {
      setNotice("Competência fechada. O snapshot ficou gravado.");
      await refresh();
    },
  });

  const current = run.data?.run ?? undefined;
  const missingRun = run.data !== undefined && run.data.run === null;
  const blockers = blockersOf(current);
  const error = run.error ?? openRun.error ?? decide.error ?? closeRun.error;
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
      {missingRun ? (
        <section className="panel" data-testid="close-run-missing">
          <p>Esta competência ainda não tem execução de fechamento aberta.</p>
          {canOpen && run.data?.status !== "closed" ? (
            <button type="button" data-testid="open-close-run" disabled={openRun.isPending} onClick={() => openRun.mutate()}>
              Abrir checklist
            </button>
          ) : (
            <p className="muted">Quem prepara ou aprova a competência abre o checklist.</p>
          )}
        </section>
      ) : null}
      {run.data?.status === "closed" ? <ClientSummaryPanel periodId={periodId} /> : null}
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
