import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, api } from "../api";
import { can, useSession } from "../session";

type Decision = { decision: "procede" | "nao_procede"; note: string | null; decided_by: string; decided_at: string };
type Finding = {
  finding_id: string;
  position: number;
  relevance: "alta" | "média" | "baixa";
  category: string;
  title: string;
  explanation: string;
  evidence: string[];
  source: "model";
  decision: Decision | null;
};
type Review = {
  review_id: string;
  operation_id: string;
  status: "requested" | "completed" | "incomplete" | "failed";
  model: string;
  prompt_version: string;
  stop_reason: string | null;
  requested_by: string;
  requested_at: string;
  completed_at: string | null;
  stale: boolean;
  findings: Finding[];
};
type Listing = { period_id: string; ai_reviews_enabled: boolean; items: Review[] };

const CATEGORY: Record<string, string> = {
  variacao: "Variação",
  classificacao: "Classificação",
  saldo: "Saldo",
  coerencia: "Coerência",
  pendencia: "Pendência",
  outro: "Outro",
};
const DECISION: Record<Decision["decision"], string> = { procede: "Procede", nao_procede: "Não procede" };

// Evidência citada pelo ponto → tela onde a pessoa confere. A conta abre pelo balancete da competência.
function evidenceLink(ref: string): { to: string; label: string } {
  const [kind, value] = ref.split(":", 2);
  if (kind === "conta") return { to: "/app/rastro/balancete", label: `Conta ${value}` };
  if (kind === "conferencia") return { to: "/app/rastro/balancete", label: `Conferência ${value}` };
  if (kind === "indicador") return { to: "/app/rastro/dre", label: `Indicador ${value.replace(/_/g, " ")}` };
  return { to: "/app/rastro/fechamentos", label: `Pendência ${value.replace(/_/g, " ")}` };
}

function FindingCard({ finding, canDecide, onDecided }: { finding: Finding; canDecide: boolean; onDecided: () => Promise<void> }) {
  const [note, setNote] = useState("");
  const [errorText, setErrorText] = useState("");
  const decide = useMutation({
    mutationFn: (decision: Decision["decision"]) =>
      api(`/v1/ai-review-findings/${finding.finding_id}/decisions`, { body: { decision, note: note.trim() || null } }),
    onSuccess: async () => {
      setNote("");
      setErrorText("");
      await onDecided();
    },
    onError: (error) => setErrorText(error instanceof ApiError ? error.message : "Não foi possível registrar a decisão."),
  });
  return (
    <article className="checklist-row" data-testid="ai-review-finding">
      <div className="checklist-row__main">
        <div className="checklist-row__title">
          <strong>{finding.title}</strong>
          <span className="muted"> · relevância {finding.relevance} · {CATEGORY[finding.category] ?? finding.category}</span>
        </div>
        {/* SPEC §7: sem decisão o ponto é `sugerido`; com decisão, `revisado`. */}
        <span className="muted" data-testid="ai-review-state">
          {finding.decision ? `Revisado: ${DECISION[finding.decision.decision]}` : "Sugerido pela IA — confira"}
        </span>
        <p>{finding.explanation}</p>
        <div className="checklist-row__meta">
          {finding.evidence.map((ref) => {
            const link = evidenceLink(ref);
            return (
              <Link key={ref} className="inline-action" to={link.to}>
                {link.label}
              </Link>
            );
          })}
        </div>
        {finding.decision ? (
          <div className="resolution-record" data-testid="ai-review-decision">
            <strong>{DECISION[finding.decision.decision]}</strong>
            {finding.decision.note ? ` · ${finding.decision.note}` : ""} · {finding.decision.decided_by}
          </div>
        ) : null}
        {canDecide ? (
          <div className="row">
            <input
              aria-label={`Nota sobre ${finding.title}`}
              placeholder="Nota (opcional)"
              maxLength={500}
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
            <button type="button" className="secondary" disabled={decide.isPending} onClick={() => decide.mutate("procede")}>
              Procede
            </button>
            <button type="button" className="secondary" disabled={decide.isPending} onClick={() => decide.mutate("nao_procede")}>
              Não procede
            </button>
          </div>
        ) : null}
        {errorText ? <p className="error">{errorText}</p> : null}
      </div>
    </article>
  );
}

export function AiReviewsPage() {
  const { me, periodId } = useSession();
  const queryClient = useQueryClient();
  const [operationId, setOperationId] = useState<string | null>(null);
  const [errorText, setErrorText] = useState("");
  const canAct = can(me.roles, "preparer", "approver", "admin");
  const key = ["ai-reviews", periodId];

  const reviews = useQuery({
    queryKey: key,
    enabled: Boolean(periodId),
    queryFn: () => api<Listing>(`/v1/periods/${periodId}/ai-reviews`),
  });
  const operation = useQuery({
    queryKey: ["operation", operationId],
    enabled: Boolean(operationId),
    queryFn: () => api<{ status: string; error_code: string | null }>(`/v1/operations/${operationId}`),
    refetchInterval: (query) => (query.state.data?.status === "accepted" || query.state.data?.status === "running" ? 1500 : false),
  });
  const running = Boolean(operationId) && !["completed", "failed"].includes(operation.data?.status ?? "accepted");

  useEffect(() => {
    const status = operation.data?.status;
    if (status === "completed" || status === "failed") {
      setOperationId(null);
      void queryClient.invalidateQueries({ queryKey: key });
    }
    // A chave muda só com a competência; a operação concluída recarrega a lista.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [operation.data?.status]);

  const request = useMutation({
    mutationFn: () => api<{ operation_id: string; review_id: string }>(`/v1/periods/${periodId}/ai-reviews`, { body: {} }),
    onSuccess: async (created) => {
      setErrorText("");
      setOperationId(created.operation_id);
      await queryClient.invalidateQueries({ queryKey: key });
    },
    onError: (error) => setErrorText(error instanceof ApiError ? `${error.title}. ${error.message}` : "Não foi possível pedir a revisão."),
  });

  const items = reviews.data?.items ?? [];
  const latest = items[0];
  const enabled = reviews.data?.ai_reviews_enabled ?? false;

  return (
    <>
      <section className="page-header">
        <div>
          <span className="eyebrow">Rastreabilidade</span>
          <h1>Revisões de IA</h1>
          <p>A IA lê o balancete, a DRE, as conferências e as pendências da competência e sugere pontos para conferir. Cada ponto cita a evidência.</p>
        </div>
      </section>
      <section className="panel" data-testid="ai-review-notice">
        <p className="muted">
          Sugestão da IA para conferência. Não altera o razão, não decide o checklist e não vai ao cliente. Só dados fictícios do piloto (ADR 036).
        </p>
        {!periodId ? <p className="muted">Escolha a competência na barra do topo.</p> : null}
        {periodId && !enabled && reviews.data ? <p className="muted">Revisão por IA indisponível neste ambiente.</p> : null}
        {periodId && enabled && canAct ? (
          <p className="row">
            <button type="button" data-testid="request-ai-review" disabled={running || request.isPending} onClick={() => request.mutate()}>
              Pedir revisão à IA
            </button>
            {running || request.isPending ? <span className="muted">Revisando…</span> : null}
          </p>
        ) : null}
        {errorText ? <p className="error">{errorText}</p> : null}
      </section>
      {reviews.isError ? <p className="error">Não foi possível carregar as revisões.</p> : null}
      {reviews.data && !latest ? <p className="muted">Ainda não há revisão desta competência.</p> : null}
      {latest ? (
        <section className="panel panel--flush" data-testid="ai-review-latest">
          <div className="panel">
            <span className="eyebrow">Revisão mais recente</span>
            <p className="muted">
              Pedida por {latest.requested_by} · {latest.model} · {latest.prompt_version}
            </p>
            {latest.status === "requested" ? <p className="muted">Revisão em andamento.</p> : null}
            {latest.status === "failed" ? <p className="error">A revisão falhou. Peça de novo mais tarde.</p> : null}
            {latest.status === "incomplete" ? <p className="muted">A IA não devolveu uma resposta completa. Peça de novo.</p> : null}
            {latest.stale ? (
              <p className="muted" data-testid="ai-review-stale">Os números da competência mudaram depois desta revisão. Peça outra para conferir.</p>
            ) : null}
            {latest.status === "completed" && latest.findings.length === 0 ? <p className="muted">A IA não apontou nada nesta competência.</p> : null}
          </div>
          <div className="checklist-list">
            {latest.findings.map((finding) => (
              <FindingCard
                key={finding.finding_id}
                finding={finding}
                canDecide={canAct}
                onDecided={() => queryClient.invalidateQueries({ queryKey: key })}
              />
            ))}
          </div>
        </section>
      ) : null}
      {items.length > 1 ? (
        <p className="muted">{items.length - 1} revisão(ões) anterior(es) desta competência ficam no histórico da API.</p>
      ) : null}
    </>
  );
}
