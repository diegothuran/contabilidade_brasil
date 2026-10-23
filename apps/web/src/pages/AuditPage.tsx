import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

type AuditEvent = {
  event_id: string;
  event_type: string;
  occurred_at: string;
  actor: { ref: string };
  target: { type: string; ref: string };
  reason: string | null;
};

export function AuditPage() {
  const events = useQuery({ queryKey: ["audit"], queryFn: () => api<{ items: AuditEvent[] }>("/v1/audit-events") });
  const verify = useQuery({ queryKey: ["audit-verify"], queryFn: () => api<{ valid: boolean; checked: number; broken_event_id: string | null }>("/v1/audit-events/verify") });

  return (
    <section>
      <h1>Auditoria</h1>
      {verify.data ? (
        <p className={verify.data.valid ? "ok" : "error"} data-testid="audit-verify">
          {verify.data.valid ? `Cadeia íntegra (${verify.data.checked} eventos).` : `Cadeia rompida em ${verify.data.broken_event_id}.`}
        </p>
      ) : null}
      <table>
        <thead><tr><th>Quando</th><th>Evento</th><th>Ator</th><th>Alvo</th><th>Motivo</th></tr></thead>
        <tbody>
          {(events.data?.items ?? []).map((event) => (
            <tr key={event.event_id}>
              <td>{event.occurred_at}</td>
              <td>{event.event_type}</td>
              <td>{event.actor.ref}</td>
              <td>{event.target.type} {event.target.ref}</td>
              <td>{event.reason ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
