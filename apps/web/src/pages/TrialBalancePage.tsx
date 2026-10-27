import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { STATUS_LABEL, useSession } from "../session";

type BalanceRow = { account_id: string; code: string; name: string; debit: string; credit: string; balance: string };
type DrillLine = { journal_id: string; line_id: string; entry_date: string; side: string; amount: string; description: string; journal_status: string };

export function TrialBalancePage() {
  const { entityId, periodId } = useSession();
  const [accountId, setAccountId] = useState("");
  useEffect(() => {
    setAccountId("");
  }, [periodId]);
  const balance = useQuery({
    queryKey: ["trial", entityId, periodId],
    enabled: Boolean(periodId),
    queryFn: () => api<{ rows: BalanceRow[]; debit_total: string; credit_total: string }>(`/v1/legal-entities/${entityId}/trial-balance?period_id=${periodId}`),
  });
  const selected = balance.data?.rows.find((row) => row.account_id === accountId);
  const drill = useQuery({
    queryKey: ["drill", accountId, periodId],
    enabled: Boolean(accountId && periodId),
    queryFn: () => api<{ lines: DrillLine[] }>(`/v1/accounts/${accountId}/lines?period_id=${periodId}`),
  });

  return (
    <section>
      <h1>Balancete</h1>
      <table>
        <thead><tr><th>Conta</th><th>Débito</th><th>Crédito</th><th>Saldo</th></tr></thead>
        <tbody>
          {(balance.data?.rows ?? []).map((row) => (
            <tr key={row.account_id}>
              <td><button type="button" className="secondary" onClick={() => setAccountId(row.account_id)}>{row.code} {row.name}</button></td>
              <td className="amount">{row.debit}</td>
              <td className="amount">{row.credit}</td>
              <td className="amount">{row.balance}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {balance.data ? <p>Totais {balance.data.debit_total} / {balance.data.credit_total}</p> : null}
      {accountId ? (
        <section>
          <h2>Lançamentos de {selected ? `${selected.code} ${selected.name}` : "a conta"}</h2>
          {drill.isLoading ? <p className="muted">Carregando lançamentos…</p> : null}
          {drill.data && drill.data.lines.length === 0 ? <p className="muted">Nenhum lançamento publicado nesta competência.</p> : null}
          {drill.data && drill.data.lines.length > 0 ? (
            <table>
              <thead><tr><th>Data</th><th>Lançamento</th><th>Lado</th><th>Valor</th><th>Estado</th></tr></thead>
              <tbody>
                {drill.data.lines.map((line) => (
                  <tr key={line.line_id}>
                    <td>{line.entry_date}</td>
                    <td><Link to={`/app/journals/${line.journal_id}`}>{line.description}</Link></td>
                    <td>{line.side === "debit" ? "Débito" : "Crédito"}</td>
                    <td className="amount">{line.amount}</td>
                    <td>{STATUS_LABEL[line.journal_status] ?? line.journal_status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </section>
      ) : null}
    </section>
  );
}
