import { useQuery } from "@tanstack/react-query";
import { Fragment, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api, downloadFile } from "../api";
import { formatMoney } from "../format";
import { can, useSession } from "../session";
import { DISCLAIMER, ReportHeading, ReportSwitcher, isZero, printOnly, useReportContext } from "./reports";
import { signaturesPath, type StatementSignatories } from "./signatories";

type Row<K extends string> = { account_id: string; code: string; name: string } & Record<K, string>;
type Group<K extends string> = { code: string; name: string; rows: Row<K>[] } & Record<K, string>;
type IncomeStatement = {
  sections: ({ account_type: string; title: string; groups: Group<"month" | "year_to_date">[] } & Record<"month" | "year_to_date", string>)[];
  result: { month: string; year_to_date: string };
  signatories: StatementSignatories;
};
type BalanceSheet = {
  sections: { account_type: string; title: string; balance: string; unclosed_result?: string; groups: Group<"balance">[] }[];
  total_assets: string;
  total_liabilities_and_equity: string;
  difference: string;
  signatories: StatementSignatories;
};

const NOTE = "Demonstração gerencial: os grupos são as contas raiz do plano da empresa, sem o layout oficial.";

function StatementLayout({
  title,
  description,
  target,
  csvPath,
  csvName,
  ready,
  metrics,
  signatories,
  children,
}: {
  title: string;
  description: string;
  target: string;
  csvPath: string;
  csvName: string;
  ready: boolean;
  metrics: ReactNode;
  signatories: StatementSignatories | undefined;
  children: ReactNode;
}) {
  const { entityText, periodText, issuedAt } = useReportContext();
  return (
    <div className="report-page">
      <section className="page-header">
        <div>
          <span className="eyebrow">Relatórios · {entityText} · {periodText}</span>
          <h1>{title}</h1>
          <p>{description}</p>
          <ReportSwitcher />
        </div>
        <div className="page-header__action report-actions">
          <button type="button" className="button" data-testid={`print-${target}`} disabled={!ready} onClick={() => printOnly(target)}>
            Imprimir
          </button>
          <button
            type="button"
            className="button button--secondary secondary"
            data-testid={`csv-${target}`}
            disabled={!ready}
            onClick={() => void downloadFile(csvPath, csvName)}
          >
            Baixar CSV (Excel)
          </button>
        </div>
      </section>
      {metrics}
      <section className="panel panel--flush">
        <ReportHeading title={title} entity={entityText} period={periodText} issuedAt={issuedAt} />
        {children}
        {ready ? <Signatures signatories={signatories ?? null} /> : null}
        <p className="report-note">{NOTE} {DISCLAIMER}</p>
      </section>
    </div>
  );
}

// Linhas de assinatura no fim da demonstração (ADR 030). Sem cadastro, a linha diz isso e a impressão não é bloqueada.
function Signatures({ signatories }: { signatories: StatementSignatories }) {
  const { me, entityId } = useSession();
  const accountant = signatories?.accountant ?? null;
  const representative = signatories?.legal_representative ?? null;
  const missing = !accountant || !representative;
  return (
    <>
      {missing ? (
        <p className="report-signatures__notice" role="status" data-testid="signatures-missing">
          <strong>Aviso:</strong>{" "}
          {!accountant ? "esta empresa ainda não tem responsável técnico" : "falta o representante legal"} nas assinaturas.{" "}
          {can(me.roles, "admin") ? (
            <Link to={signaturesPath(entityId)}>Definir as assinaturas da empresa</Link>
          ) : (
            <span>Peça ao admin do escritório para definir as assinaturas da empresa.</span>
          )}
        </p>
      ) : null}
      <div className="report-signatures" data-testid="report-signatures">
        <SignatureLine signatory={accountant} missing="Responsável técnico não cadastrado" />
        <SignatureLine signatory={representative} missing="Representante legal não cadastrado" />
      </div>
    </>
  );
}

function SignatureLine({ signatory, missing }: { signatory: { name: string; caption: string } | null; missing: string }) {
  return (
    <div className="report-signature">
      <span className="report-signature__line" aria-hidden="true" />
      {signatory ? (
        <>
          <strong>{signatory.name}</strong>
          <span>{signatory.caption}</span>
        </>
      ) : (
        <span className="report-signature__missing">{missing}</span>
      )}
    </div>
  );
}

function Status({ loading, error, periodId, columns }: { loading: boolean; error: boolean; periodId: string; columns: number }) {
  const text = !periodId ? "Escolha uma competência na barra." : error ? "Não foi possível carregar a demonstração." : loading ? "Carregando…" : "";
  return text ? <tbody><tr><td colSpan={columns}>{text}</td></tr></tbody> : null;
}

export function IncomeStatementPage() {
  const { entityId, periodId } = useReportContext();
  const report = useQuery({
    queryKey: ["income-statement", entityId, periodId],
    enabled: Boolean(periodId),
    queryFn: () => api<IncomeStatement>(`/v1/legal-entities/${entityId}/income-statement?period_id=${periodId}`),
  });
  const data = report.data;
  const revenue = data?.sections.find((section) => section.account_type === "revenue");
  const expense = data?.sections.find((section) => section.account_type === "expense");
  const profit = data && !data.result.year_to_date.startsWith("-");

  return (
    <StatementLayout
      title="DRE"
      description="Receitas, despesas e resultado do mês e do ano até a competência. O encerramento do exercício não entra."
      target="dre"
      csvPath={`/v1/legal-entities/${entityId}/income-statement.csv?period_id=${periodId}`}
      csvName="dre.csv"
      ready={Boolean(data)}
      signatories={data?.signatories}
      metrics={
        data ? (
          <section className="metric-strip report-metrics" aria-label="Resumo da DRE">
            <article className="metric metric--info"><span>Receitas no ano</span><strong>{formatMoney(revenue?.year_to_date ?? "0")}</strong><small>Mês: {formatMoney(revenue?.month ?? "0")}</small></article>
            <article className="metric metric--info"><span>Despesas no ano</span><strong>{formatMoney(expense?.year_to_date ?? "0")}</strong><small>Mês: {formatMoney(expense?.month ?? "0")}</small></article>
            <article className={`metric ${profit ? "metric--success" : "metric--danger"}`} data-testid="income-result">
              <span>{profit ? "Lucro no ano" : "Prejuízo no ano"}</span>
              <strong>{formatMoney(data.result.year_to_date.replace("-", ""))}</strong>
              <small>Resultado do mês: {formatMoney(data.result.month)}</small>
            </article>
          </section>
        ) : null
      }
    >
      <div className="table-scroll">
        <table className="data-table report-table">
          <thead>
            <tr><th>Código</th><th>Conta</th><th className="amount">Mês</th><th className="amount">Acumulado no ano</th></tr>
          </thead>
          <Status loading={report.isLoading} error={report.isError} periodId={periodId} columns={4} />
          {data ? (
            <>
              {data.sections.map((section) => (
                <tbody key={section.account_type}>
                  <tr className="report-row--section">
                    <td colSpan={2}>{section.title}</td>
                    <td className="amount">{formatMoney(section.month)}</td>
                    <td className="amount">{formatMoney(section.year_to_date)}</td>
                  </tr>
                  {section.groups.map((group) => (
                    <Fragment key={group.code}>
                      {section.groups.length > 1 ? (
                        <tr className="report-row--group">
                          <td>{group.code}</td><td>{group.name}</td>
                          <td className="amount">{formatMoney(group.month)}</td>
                          <td className="amount">{formatMoney(group.year_to_date)}</td>
                        </tr>
                      ) : null}
                      {group.rows.map((row) => (
                        <tr key={row.account_id}>
                          <td>{row.code}</td><td>{row.name}</td>
                          <td className="amount">{formatMoney(row.month)}</td>
                          <td className="amount">{formatMoney(row.year_to_date)}</td>
                        </tr>
                      ))}
                    </Fragment>
                  ))}
                  {section.groups.every((group) => group.rows.length === 0) ? (
                    <tr><td colSpan={4} className="muted">Sem valor no ano.</td></tr>
                  ) : null}
                </tbody>
              ))}
              <tfoot>
                <tr>
                  <td colSpan={2}>Resultado do período</td>
                  <td className="amount">{formatMoney(data.result.month)}</td>
                  <td className="amount">{formatMoney(data.result.year_to_date)}</td>
                </tr>
              </tfoot>
            </>
          ) : null}
        </table>
      </div>
    </StatementLayout>
  );
}

export function BalanceSheetPage() {
  const { entityId, periodId } = useReportContext();
  const report = useQuery({
    queryKey: ["balance-sheet", entityId, periodId],
    enabled: Boolean(periodId),
    queryFn: () => api<BalanceSheet>(`/v1/legal-entities/${entityId}/balance-sheet?period_id=${periodId}`),
  });
  const data = report.data;
  const balanced = data ? isZero(data.difference) : true;

  return (
    <StatementLayout
      title="Balanço"
      description="Ativo, passivo e patrimônio líquido no fim da competência. Enquanto o exercício não é encerrado, o resultado aparece numa linha própria do PL."
      target="balanco"
      csvPath={`/v1/legal-entities/${entityId}/balance-sheet.csv?period_id=${periodId}`}
      csvName="balanco.csv"
      ready={Boolean(data)}
      signatories={data?.signatories}
      metrics={
        data ? (
          <section className="metric-strip report-metrics" aria-label="Resumo do balanço">
            <article className="metric metric--info"><span>Ativo</span><strong>{formatMoney(data.total_assets)}</strong><small>No fim da competência</small></article>
            <article className="metric metric--info"><span>Passivo + PL</span><strong>{formatMoney(data.total_liabilities_and_equity)}</strong><small>Inclui o resultado não encerrado</small></article>
            <article className={`metric ${balanced ? "metric--success" : "metric--danger"}`} data-testid="balance-sheet-difference">
              <span>Diferença</span><strong>{formatMoney(data.difference)}</strong><small>{balanced ? "Ativo igual a passivo + PL" : "Não fecha: há conta sem tipo coerente"}</small>
            </article>
          </section>
        ) : null
      }
    >
      <div className="table-scroll">
        <table className="data-table report-table">
          <thead>
            <tr><th>Código</th><th>Conta</th><th className="amount">Saldo</th></tr>
          </thead>
          <Status loading={report.isLoading} error={report.isError} periodId={periodId} columns={3} />
          {data
            ? data.sections.map((section) => (
                <tbody key={section.account_type}>
                  <tr className="report-row--section">
                    <td colSpan={2}>{section.title}</td>
                    <td className="amount">{formatMoney(section.balance)}</td>
                  </tr>
                  {section.groups.map((group) => (
                    <Fragment key={group.code}>
                      {section.groups.length > 1 ? (
                        <tr className="report-row--group">
                          <td>{group.code}</td><td>{group.name}</td>
                          <td className="amount">{formatMoney(group.balance)}</td>
                        </tr>
                      ) : null}
                      {group.rows.map((row) => (
                        <tr key={row.account_id}>
                          <td>{row.code}</td><td>{row.name}</td>
                          <td className="amount">{formatMoney(row.balance)}</td>
                        </tr>
                      ))}
                    </Fragment>
                  ))}
                  {section.unclosed_result && !isZero(section.unclosed_result) ? (
                    <tr className="report-row--opening">
                      <td></td><td>Resultado do exercício não encerrado</td>
                      <td className="amount">{formatMoney(section.unclosed_result)}</td>
                    </tr>
                  ) : null}
                </tbody>
              ))
            : null}
          {data ? (
            <tfoot>
              <tr>
                <td colSpan={2}>Passivo + patrimônio líquido</td>
                <td className="amount">{formatMoney(data.total_liabilities_and_equity)}</td>
              </tr>
            </tfoot>
          ) : null}
        </table>
      </div>
    </StatementLayout>
  );
}
