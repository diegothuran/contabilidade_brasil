import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, api } from "../api";
import { STATUS_LABEL, can, useSession } from "../session";

type Period = {
  period_id: string;
  fiscal_year: number;
  month: number;
  status: string;
  pending_reopen_request_id?: string | null;
};

export function PeriodsPage() {
  const { entityId, me } = useSession();
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("Ajuste autorizado da competência");
  const periods = useQuery({
    queryKey: ["periods", entityId],
    queryFn: () => api<{ items: Period[] }>(`/v1/legal-entities/${entityId}/periods`),
  });
  const act = useMutation({
    mutationFn: (action: { path: string; body?: unknown }) => api(action.path, { body: action.body ?? {} }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["periods", entityId] });
    },
  });

  return (
    <section>
      <h1>Fechamentos</h1>
      <p className="muted">O fechamento desta fase é o lock da competência. O checklist completo fica para a fase de close run.</p>
      {act.isError ? <p className="error">{act.error instanceof ApiError ? `${act.error.title}. ${act.error.message}` : "Falha na operação."}</p> : null}
      <table>
        <thead><tr><th>Competência</th><th>Estado</th><th></th></tr></thead>
        <tbody>
          {(periods.data?.items ?? []).map((period) => (
            <tr key={period.period_id}>
              <td>{period.fiscal_year}-{String(period.month).padStart(2, "0")}</td>
              <td>{STATUS_LABEL[period.status] ?? period.status}</td>
              <td className="actions">
                {(period.status === "open" || period.status === "reopened") && can(me.roles, "approver", "admin") ? (
                  <button type="button" onClick={() => act.mutate({ path: `/v1/periods/${period.period_id}/close` })}>Fechar</button>
                ) : null}
                {period.status === "closed" && !period.pending_reopen_request_id && can(me.roles, "preparer", "approver", "admin") ? (
                  <>
                    <input value={reason} onChange={(event) => setReason(event.target.value)} />
                    <button type="button" className="secondary" onClick={() => act.mutate({ path: `/v1/periods/${period.period_id}/reopen-requests`, body: { reason } })}>Pedir reabertura</button>
                  </>
                ) : null}
                {period.pending_reopen_request_id && can(me.roles, "approver", "admin") ? (
                  <button type="button" onClick={() => act.mutate({ path: `/v1/reopen-requests/${period.pending_reopen_request_id}/approve` })}>Aprovar reabertura</button>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
