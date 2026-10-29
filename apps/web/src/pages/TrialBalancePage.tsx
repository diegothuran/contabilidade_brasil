import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, downloadFile } from "../api";
import { formatBalance, formatCnpj, formatDate, formatMoney, formatPeriod } from "../format";
import { STATUS_LABEL, useSession } from "../session";

type BalanceRow = {
  account_id: string;
  code: string;
  name: string;
  opening_balance: string;
  debit: string;
  credit: string;
  balance: string;
  closing_balance: string;
};
type Balance = { rows: BalanceRow[]; debit_total: string; credit_total: string };
type DrillLine = { journal_id: string; line_id: string; entry_date: string; side: string; amount: string; description: string; journal_status: string };
type Ledger = { code: string; name: string; opening_balance: string; lines: DrillLine[] };
type Period = { period_id: string; fiscal_year: number; month: number };
type PrintTarget = "balancete" | "razao";

const DISCLAIMER = "Relatório gerencial gerado pelo sistema. Não é livro contábil oficial.";

// Soma de strings decimais em micros (6 casas, como a API), sem float.
function sum(values: string[]): string {
  const micros = values.reduce((total, value) => {
    const negative = value.startsWith("-");
    const [whole, fraction = ""] = value.replace("-", "").split(".");
    const amount = BigInt((whole || "0") + (fraction + "000000").slice(0, 6));
    return total + (negative ? -amount : amount);
  }, 0n);
  const negative = micros < 0n;
  const absolute = negative ? -micros : micros;
  const text = `${absolute / 1000000n}.${(absolute % 1000000n).toString().padStart(6, "0")}`;
  return negative ? `-${text}` : text;
}

function isZero(value: string): boolean {
  return /^-?0*(\.0*)?$/.test(value);
}

function printOnly(target: PrintTarget) {
  const className = `print-${target}`;
  document.body.classList.add(className);
  const cleanup = () => {
    document.body.classList.remove(className);
    window.removeEventListener("afterprint", cleanup);
  };
  window.addEventListener("afterprint", cleanup);
  window.print();
}

function ReportHeading({ title, entity, period, issuedAt }: { title: string; entity: string; period: string; issuedAt: string }) {
  return (
    <div className="report-print-heading">
      <strong>{title}</strong>
      <span>{entity}</span>
      <span>Competência: {period} · Emitido em {issuedAt}</span>
    </div>
  );
}

export function TrialBalancePage() {
  const { entityId, periodId, entities } = useSession();
  const [accountId, setAccountId] = useState("");
  const [search, setSearch] = useState("");
  const [onlyActive, setOnlyActive] = useState(true);
  const ledgerRef = useRef<HTMLElement>(null);
  useEffect(() => {
    setAccountId("");
  }, [periodId]);

  const entity = entities.find((item) => item.legal_entity_id === entityId);
  const periods = useQuery({
    queryKey: ["periods", entityId],
    enabled: Boolean(entityId),
    queryFn: () => api<{ items: Period[] }>(`/v1/legal-entities/${entityId}/periods`),
  });
  const period = periods.data?.items.find((item) => item.period_id === periodId);
  const periodText = period ? formatPeriod(period.fiscal_year, period.month) : "competência escolhida";
  const entityText = entity ? `${entity.name} · CNPJ ${formatCnpj(entity.cnpj)}` : "Empresa";
  const issuedAt = new Date().toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });

  const balance = useQuery({
    queryKey: ["trial", entityId, periodId],
    enabled: Boolean(periodId),
    queryFn: () => api<Balance>(`/v1/legal-entities/${entityId}/trial-balance?period_id=${periodId}`),
  });
  const drill = useQuery({
    queryKey: ["drill", accountId, periodId],
    enabled: Boolean(accountId && periodId),
    queryFn: () => api<Ledger>(`/v1/accounts/${accountId}/lines?period_id=${periodId}`),
  });
  useEffect(() => {
    if (accountId) {
      ledgerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [accountId]);

  const rows = useMemo(() => balance.data?.rows ?? [], [balance.data]);
  const visible = useMemo(() => {
    const term = search.trim().toLowerCase();
    return rows.filter((row) => {
      const active = !isZero(row.opening_balance) || !isZero(row.debit) || !isZero(row.credit);
      const matches = !term || row.code.toLowerCase().includes(term) || row.name.toLowerCase().includes(term);
      return matches && (!onlyActive || active);
    });
  }, [rows, search, onlyActive]);
  const moved = rows.filter((row) => !isZero(row.debit) || !isZero(row.credit)).length;
  const difference = balance.data ? sum([balance.data.debit_total, `-${balance.data.credit_total}`]) : "0";
  const balanced = isZero(difference);
  const selected = rows.find((row) => row.account_id === accountId);

  const ledgerRows = useMemo(() => {
    if (!drill.data) {
      return [];
    }
    let running = drill.data.opening_balance;
    return drill.data.lines.map((line) => {
      running = sum([running, line.side === "debit" ? line.amount : `-${line.amount}`]);
      return { ...line, running };
    });
  }, [drill.data]);
  const ledgerClosing = ledgerRows.length > 0 ? ledgerRows[ledgerRows.length - 1].running : drill.data?.opening_balance ?? "0";

  return (
    <div className="report-page">
      <section className="page-header report-balancete">
        <div>
          <span className="eyebrow">Relatórios · {entityText} · {periodText}</span>
          <h1>Balancete</h1>
          <p>Saldo anterior, movimento do mês e saldo atual de cada conta. Clique numa conta para ver o razão.</p>
        </div>
        <div className="page-header__action report-actions">
          <button type="button" className="button" data-testid="print-balancete" disabled={!balance.data} onClick={() => printOnly("balancete")}>
            Imprimir
          </button>
          <button
            type="button"
            className="button button--secondary secondary"
            data-testid="csv-balancete"
            disabled={!balance.data}
            onClick={() => void downloadFile(`/v1/legal-entities/${entityId}/trial-balance.csv?period_id=${periodId}`, "balancete.csv")}
          >
            Baixar CSV (Excel)
          </button>
        </div>
      </section>

      {balance.data ? (
        <section className="metric-strip report-metrics" aria-label="Resumo do balancete">
          <article className="metric metric--info"><span>Total de débitos</span><strong>{formatMoney(balance.data.debit_total)}</strong><small>Movimento do mês</small></article>
          <article className="metric metric--info"><span>Total de créditos</span><strong>{formatMoney(balance.data.credit_total)}</strong><small>Movimento do mês</small></article>
          <article className={`metric ${balanced ? "metric--success" : "metric--danger"}`} data-testid="balance-difference">
            <span>Diferença</span><strong>{formatMoney(difference)}</strong><small>{balanced ? "Débitos e créditos fecham" : "Não fecha: revise os lançamentos"}</small>
          </article>
          <article className="metric metric--attention"><span>Contas com movimento</span><strong>{moved}</strong><small>de {rows.length} contas que recebem lançamento</small></article>
        </section>
      ) : null}

      <section className="panel panel--flush report-balancete">
        <ReportHeading title="Balancete" entity={entityText} period={periodText} issuedAt={issuedAt} />
        <div className="table-toolbar report-toolbar">
          <label className="report-search">
            <span className="sr-only">Buscar conta</span>
            <input type="search" placeholder="Buscar por código ou nome" value={search} onChange={(event) => setSearch(event.target.value)} />
          </label>
          <label className="report-toggle">
            <input type="checkbox" checked={onlyActive} onChange={(event) => setOnlyActive(event.target.checked)} />
            Só contas com saldo ou movimento
          </label>
          <span className="table-count">{balance.isLoading ? "Carregando" : `${visible.length} de ${rows.length} contas`}</span>
        </div>
        <div className="table-scroll">
          <table className="data-table report-table">
            <thead>
              <tr><th>Código</th><th>Conta</th><th className="amount">Saldo anterior</th><th className="amount">Débito</th><th className="amount">Crédito</th><th className="amount">Saldo atual</th></tr>
            </thead>
            <tbody>
              {balance.isError ? (
                <tr><td colSpan={6}>Não foi possível carregar o balancete.</td></tr>
              ) : !periodId ? (
                <tr><td colSpan={6}>Escolha uma competência na barra.</td></tr>
              ) : visible.length === 0 && !balance.isLoading ? (
                <tr><td colSpan={6}>Nenhuma conta com saldo ou movimento nesta competência.</td></tr>
              ) : visible.map((row) => (
                <tr key={row.account_id} className={row.account_id === accountId ? "report-row--selected" : undefined}>
                  <td>{row.code}</td>
                  <td>
                    <button type="button" className="report-link" onClick={() => setAccountId(row.account_id)} aria-label={`Ver o razão de ${row.code} ${row.name}`}>
                      {row.name}
                    </button>
                  </td>
                  <td className="amount">{formatBalance(row.opening_balance)}</td>
                  <td className="amount">{formatMoney(row.debit)}</td>
                  <td className="amount">{formatMoney(row.credit)}</td>
                  <td className="amount"><strong>{formatBalance(row.closing_balance)}</strong></td>
                </tr>
              ))}
            </tbody>
            {balance.data ? (
              <tfoot>
                <tr>
                  <td colSpan={2}>Totais</td>
                  <td className="amount">{formatBalance(sum(rows.map((row) => row.opening_balance)))}</td>
                  <td className="amount">{formatMoney(balance.data.debit_total)}</td>
                  <td className="amount">{formatMoney(balance.data.credit_total)}</td>
                  <td className="amount">{formatBalance(sum(rows.map((row) => row.closing_balance)))}</td>
                </tr>
              </tfoot>
            ) : null}
          </table>
        </div>
        <p className="report-note">D = saldo devedor · C = saldo credor. {DISCLAIMER}</p>
      </section>

      {accountId ? (
        <section className="panel panel--flush report-razao" ref={ledgerRef} data-testid="ledger-panel">
          <ReportHeading title={`Razão · ${selected ? `${selected.code} ${selected.name}` : "conta"}`} entity={entityText} period={periodText} issuedAt={issuedAt} />
          <div className="table-toolbar report-toolbar">
            <div>
              <span className="eyebrow">Razão da conta</span>
              <h2 className="report-title">{selected ? `${selected.code} ${selected.name}` : "Conta"}</h2>
            </div>
            <div className="report-actions">
              <button type="button" className="button button--compact" data-testid="print-razao" disabled={!drill.data} onClick={() => printOnly("razao")}>
                Imprimir razão
              </button>
              <button
                type="button"
                className="button button--secondary button--compact secondary"
                data-testid="csv-razao"
                disabled={!drill.data}
                onClick={() => void downloadFile(`/v1/accounts/${accountId}/lines.csv?period_id=${periodId}`, "razao.csv")}
              >
                Baixar CSV
              </button>
              <button type="button" className="button button--secondary button--compact secondary" onClick={() => setAccountId("")}>
                Fechar
              </button>
            </div>
          </div>
          {drill.isLoading ? <p className="muted report-note">Carregando lançamentos…</p> : null}
          {drill.isError ? <p className="error">Não foi possível carregar o razão desta conta.</p> : null}
          {drill.data ? (
            <div className="table-scroll">
              <table className="data-table report-table">
                <thead>
                  <tr><th>Data</th><th>Histórico</th><th className="amount">Débito</th><th className="amount">Crédito</th><th className="amount">Saldo</th></tr>
                </thead>
                <tbody>
                  <tr className="report-row--opening">
                    <td></td><td>Saldo anterior</td><td></td><td></td>
                    <td className="amount">{formatBalance(drill.data.opening_balance)}</td>
                  </tr>
                  {ledgerRows.length === 0 ? (
                    <tr><td colSpan={5}>Nenhum lançamento publicado nesta competência.</td></tr>
                  ) : ledgerRows.map((line) => (
                    <tr key={line.line_id}>
                      <td>{formatDate(line.entry_date)}</td>
                      <td>
                        <Link to={`/app/journals/${line.journal_id}`}>{line.description}</Link>
                        {line.journal_status !== "published" ? <span className="badge">{STATUS_LABEL[line.journal_status] ?? line.journal_status}</span> : null}
                      </td>
                      <td className="amount">{line.side === "debit" ? formatMoney(line.amount) : ""}</td>
                      <td className="amount">{line.side === "credit" ? formatMoney(line.amount) : ""}</td>
                      <td className="amount">{formatBalance(line.running)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <td colSpan={4}>Saldo atual</td>
                    <td className="amount">{formatBalance(ledgerClosing)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          ) : null}
          <p className="report-note">D = saldo devedor · C = saldo credor. {DISCLAIMER}</p>
        </section>
      ) : null}
    </div>
  );
}
