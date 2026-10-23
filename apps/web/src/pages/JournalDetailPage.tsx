import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, api } from "../api";
import { STATUS_LABEL, can, useSession } from "../session";

type JournalLine = { line_id: string; account_id: string; side: string; amount: string; description: string };
type Journal = {
  journal_id: string;
  status: string;
  description: string;
  entry_date: string;
  currency: string;
  created_by: string;
  period_id: string;
  lines: JournalLine[];
  source: { source_type: string; source_id: string; reverses_journal_id: string | null };
};

export function JournalDetailPage() {
  const { journalId = "" } = useParams();
  const navigate = useNavigate();
  const { entityId, me } = useSession();
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("Revisão recusada");
  const journal = useQuery({
    queryKey: ["journal", journalId],
    queryFn: () => api<Journal>(`/v1/journals/${journalId}`),
  });
  const reversals = useQuery({
    queryKey: ["reversal-of", journalId, entityId],
    enabled: journal.data?.status === "reversed",
    queryFn: () => api<{ items: Journal[] }>(`/v1/journals?legal_entity_id=${entityId}&reverses_journal_id=${journalId}`),
  });
  const act = useMutation({
    mutationFn: (action: { path: string; body?: unknown }) => api<Journal>(action.path, { body: action.body ?? {} }),
    onSuccess: async (updated) => {
      await queryClient.invalidateQueries({ queryKey: ["journal", journalId] });
      await queryClient.invalidateQueries({ queryKey: ["journals", entityId] });
      await queryClient.invalidateQueries({ queryKey: ["trial", entityId] });
      if (updated.journal_id !== journalId) {
        navigate(`/app/journals/${updated.journal_id}`);
      }
    },
  });

  if (!journal.data) {
    return journal.isError ? <p className="error">{journal.error.message}</p> : <p className="muted">Carregando lançamento…</p>;
  }

  const current = journal.data;
  const own = current.created_by === me.user_id;
  const errorText = act.isError ? (act.error instanceof ApiError ? `${act.error.title}. ${act.error.message}` : "Falha na operação.") : null;

  return (
    <section>
      <h1>{current.description}</h1>
      <p>
        <span className="badge" data-testid="journal-status">{STATUS_LABEL[current.status] ?? current.status}</span>
        {" "}{current.entry_date} · {current.currency} · {current.period_id} · criado por {current.created_by}
      </p>
      <p className="muted">Origem {current.source.source_type} · {current.source.source_id}</p>
      {current.source.source_type === "bank" ? (
        <p>
          Caso de conciliação <Link to={`/app/reconciliation?case=${current.source.source_id}`}>{current.source.source_id}</Link>
        </p>
      ) : null}
      {current.source.source_type === "import" ? (
        <p>
          Lote de origem{" "}
          <Link to={`/app/imports/${current.source.source_id.replace(/^opening:/, "")}`}>
            {current.source.source_id.replace(/^opening:/, "")}
          </Link>
        </p>
      ) : null}
      {current.source.reverses_journal_id ? (
        <p>Reverte <Link to={`/app/journals/${current.source.reverses_journal_id}`}>{current.source.reverses_journal_id}</Link></p>
      ) : null}
      {(reversals.data?.items ?? []).map((item) => (
        <p key={item.journal_id}>Revertido por <Link to={`/app/journals/${item.journal_id}`}>{item.description}</Link></p>
      ))}
      <table>
        <thead>
          <tr><th>Conta</th><th>Histórico</th><th>Lado</th><th>Valor</th></tr>
        </thead>
        <tbody>
          {current.lines.map((line) => (
            <tr key={line.line_id}>
              <td>{line.account_id}</td>
              <td>{line.description}</td>
              <td>{line.side === "debit" ? "Débito" : "Crédito"}</td>
              <td className="amount">{line.amount}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {errorText ? <p className="error">{errorText}</p> : null}
      <div className="actions">
        {current.status === "draft" && can(me.roles, "preparer", "admin") ? (
          <button type="button" data-testid="submit-journal" onClick={() => act.mutate({ path: `/v1/journals/${current.journal_id}/submit` })}>Enviar para aprovação</button>
        ) : null}
        {current.status === "pending_approval" && !own && can(me.roles, "approver", "admin") ? (
          <>
            <button type="button" data-testid="approve-journal" onClick={() => act.mutate({ path: `/v1/journals/${current.journal_id}/approve` })}>Aprovar</button>
            <input value={reason} onChange={(event) => setReason(event.target.value)} />
            <button type="button" className="secondary" onClick={() => act.mutate({ path: `/v1/journals/${current.journal_id}/reject`, body: { reason } })}>Rejeitar</button>
          </>
        ) : null}
        {current.status === "approved" && !own && can(me.roles, "approver", "admin") ? (
          <button type="button" data-testid="publish-journal" onClick={() => act.mutate({ path: `/v1/journals/${current.journal_id}/publish` })}>Publicar</button>
        ) : null}
        {current.status === "published" && can(me.roles, "preparer", "approver", "admin") ? (
          <button type="button" className="secondary" onClick={() => act.mutate({ path: `/v1/journals/${current.journal_id}/reverse` })}>Reverter</button>
        ) : null}
      </div>
    </section>
  );
}
