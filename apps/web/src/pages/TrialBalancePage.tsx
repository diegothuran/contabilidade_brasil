import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useSession } from "../session";

type Period = { period_id: string; status: string };
type BalanceRow = { account_id: string; code: string; name: string; debit: string; credit: string; balance: string };
type DrillLine = { journal_id: string; line_id: string; entry_date: string; side: string; amount: string; description: string; journal_status: string };

export function TrialBalancePage() {
  const { entityId, periodId, setPeriodId } = useSession();
  const periods = useQuery({
    queryKey: ["periods", entityId],
    queryFn: () => api<{ items: Period[] }>(`/v1/legal-entities/${entityId}/periods`),
  });
  const [accountId, setAccountId] = useState("");
  const activePeriod = (periods.data?.items ?? []).some((period) => period.period_id === periodId) ? periodId : "";
  const balance = useQuery({
    queryKey: ["trial", entityId, activePeriod],
    enabled: Boolean(activePeriod),
    queryFn: () => api<{ rows: BalanceRow[]; debit_total: string; credit_total: string }>(`/v1/legal-entities/${entityId}/trial-balance?period_id=${activePeriod}`),
  });
  const drill = useQuery({
    queryKey: ["drill", accountId, activePeriod],
    enabled: Boolean(accountId && activePeriod),
    queryFn: () => api<{ lines: DrillLine[] }>(`/v1/accounts/${accountId}/lines?period_id=${activePeriod}`),
  });

  return (
    <section>
      <h1>Balancete</h1>
      <label>
        Período
        <select value={activePeriod} onChange={(event) => { setPeriodId(event.target.value); setAccountId(""); }}>
          {(periods.data?.items ?? []).map((period) => (
            <option key={period.period_id} value={period.period_id}>{period.period_id}</option>
          ))}
        </select>
      </label>
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
          <h2>Drill-down</h2>
          <table>
            <thead><tr><th>Data</th><th>Lançamento</th><th>Lado</th><th>Valor</th><th>Estado</th></tr></thead>
            <tbody>
              {(drill.data?.lines ?? []).map((line) => (
                <tr key={line.line_id}>
                  <td>{line.entry_date}</td>
                  <td><Link to={`/app/journals/${line.journal_id}`}>{line.description}</Link></td>
                  <td>{line.side === "debit" ? "Débito" : "Crédito"}</td>
                  <td className="amount">{line.amount}</td>
                  <td>{line.journal_status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}
    </section>
  );
}
