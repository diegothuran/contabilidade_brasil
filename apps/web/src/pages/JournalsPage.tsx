import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";
import { STATUS_LABEL, useSession } from "../session";

type Journal = {
  journal_id: string;
  description: string;
  entry_date: string;
  status: string;
  created_by: string;
};

export function JournalsPage() {
  const { entityId } = useSession();
  const journals = useQuery({
    queryKey: ["journals", entityId],
    queryFn: () => api<{ items: Journal[] }>(`/v1/journals?legal_entity_id=${entityId}&limit=50`),
  });

  return (
    <section>
      <h1>Lançamentos</h1>
      <p><Link to="/app/journals/new">Novo lançamento</Link></p>
      {journals.isError ? <p className="error">{journals.error.message}</p> : null}
      <table data-testid="journal-list">
        <thead>
          <tr>
            <th>Data</th>
            <th>Descrição</th>
            <th>Estado</th>
            <th>Criado por</th>
          </tr>
        </thead>
        <tbody>
          {(journals.data?.items ?? []).map((journal) => (
            <tr key={journal.journal_id}>
              <td>{journal.entry_date}</td>
              <td>
                <Link to={`/app/journals/${journal.journal_id}`}>{journal.description}</Link>
              </td>
              <td>
                <span className="badge" data-testid={`status-${journal.journal_id}`}>
                  {STATUS_LABEL[journal.status] ?? journal.status}
                </span>
              </td>
              <td>{journal.created_by}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
