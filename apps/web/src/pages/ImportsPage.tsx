import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, api, uploadDocument } from "../api";
import { STATUS_LABEL, can, useSession } from "../session";

type Batch = {
  batch_id: string;
  status: string;
  source_system: string;
  mode: string;
  created_by: string | null;
  published_by: string | null;
  summary: {
    rows_received: number;
    rows_valid: number;
    rows_invalid: number;
    debit_total: string;
    credit_total: string;
    difference: string;
  };
  errors: { row: number; code: string; message: string }[];
};

type Report = {
  rows: {
    account_code: string;
    source_debit: string;
    source_credit: string;
    ledger_debit: string;
    ledger_credit: string;
    difference: string;
    explanation: string;
  }[];
  journals: { journal_id: string; external_id: string }[];
};

type Period = { period_id: string; fiscal_year: number; month: number; status: string };

const KINDS = [
  ["journal", "Lançamentos"],
  ["opening_balance", "Saldo de abertura"],
  ["chart_of_accounts", "Plano de contas"],
] as const;

function needsPeriod(kind: string): boolean {
  return kind === "journal" || kind === "opening_balance";
}

export function ImportsPage() {
  const { entityId, me, periodId, setPeriodId } = useSession();
  const navigate = useNavigate();
  const [kind, setKind] = useState<(typeof KINDS)[number][0]>("journal");
  const [sourceSystem, setSourceSystem] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const periods = useQuery({
    queryKey: ["periods", entityId],
    queryFn: () => api<{ items: Period[] }>(`/v1/legal-entities/${entityId}/periods`),
  });
  const batches = useQuery({
    queryKey: ["batches", entityId],
    queryFn: () => api<{ items: Batch[] }>(`/v1/import-batches?legal_entity_id=${entityId}`),
  });
  const openPeriods = (periods.data?.items ?? []).filter((period) => period.status === "open" || period.status === "reopened");
  const activePeriod = openPeriods.some((period) => period.period_id === periodId) ? periodId : "";
  const create = useMutation({
    mutationFn: async () => {
      if (!file) {
        throw new ApiError(400, "Arquivo obrigatório", "Escolha o CSV do lote.");
      }
      const document = await uploadDocument(file, {
        document_type: "other",
        legal_entity_id: entityId,
        competence: "2026-01",
      });
      const operation = await api<{ operation_id: string }>("/v1/import-batches", {
        body: {
          legal_entity_id: entityId,
          source_system: sourceSystem,
          mode: "dry_run",
          period_id: needsPeriod(kind) ? activePeriod : null,
          files: [{ document_id: document.document_id, kind }],
        },
      });
      return operation;
    },
    onSuccess: async () => {
      const listed = await batches.refetch();
      const newest = listed.data?.items[0];
      if (newest) {
        navigate(`/app/imports/${newest.batch_id}`);
      }
    },
  });

  return (
    <section>
      <h1>Migrações</h1>
      <p className="muted">O lote nasce em simulação. Publicar é uma aprovação de outra pessoa e não duplica um identificador já importado.</p>
      {can(me.roles, "preparer", "approver", "admin") ? (
        <form
          className="row"
          onSubmit={(event) => {
            event.preventDefault();
            create.mutate();
          }}
        >
          <label>
            Tipo
            <select value={kind} onChange={(event) => setKind(event.target.value as (typeof KINDS)[number][0])}>
              {KINDS.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          <label>
            Sistema de origem
            <input data-testid="import-source" value={sourceSystem} onChange={(event) => setSourceSystem(event.target.value)} />
          </label>
          {needsPeriod(kind) ? (
            <label>
              Período
              <select data-testid="import-period" value={activePeriod} onChange={(event) => setPeriodId(event.target.value)}>
                {openPeriods.map((period) => (
                  <option key={period.period_id} value={period.period_id}>
                    {period.fiscal_year}-{String(period.month).padStart(2, "0")}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <label>
            Arquivo CSV
            <input data-testid="import-file" type="file" accept=".csv,text/csv" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          </label>
          <button type="submit" data-testid="create-batch" disabled={!file || !sourceSystem.trim() || create.isPending || (needsPeriod(kind) && !activePeriod)}>
            Simular lote
          </button>
        </form>
      ) : null}
      {create.isError ? <p className="error">{create.error instanceof ApiError ? `${create.error.title}. ${create.error.message}` : "Falha ao criar o lote."}</p> : null}
      <table>
        <thead><tr><th>Origem</th><th>Estado</th><th>Válidas</th><th>Inválidas</th></tr></thead>
        <tbody>
          {(batches.data?.items ?? []).map((batch) => (
            <tr key={batch.batch_id}>
              <td><Link to={`/app/imports/${batch.batch_id}`}>{batch.source_system}</Link></td>
              <td>{STATUS_LABEL[batch.status] ?? batch.status}</td>
              <td className="amount">{batch.summary.rows_valid}</td>
              <td className="amount">{batch.summary.rows_invalid}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export function ImportDetailPage() {
  const { batchId = "" } = useParams();
  const { me } = useSession();
  const [publishing, setPublishing] = useState(false);
  const [operationId, setOperationId] = useState<string | null>(null);
  const batch = useQuery({
    queryKey: ["batch", batchId],
    queryFn: () => api<Batch>(`/v1/import-batches/${batchId}`),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "received" || status === "validating") {
        return 1000;
      }
      if (publishing && status === "ready") {
        return 1000;
      }
      return false;
    },
  });
  const operation = useQuery({
    queryKey: ["operation", operationId],
    enabled: Boolean(operationId),
    queryFn: () => api<{ status: string; error_code: string | null }>(`/v1/operations/${operationId}`),
    refetchInterval: (query) => (query.state.data?.status === "accepted" || query.state.data?.status === "running" ? 1000 : false),
  });
  const report = useQuery({
    queryKey: ["report", batchId],
    enabled: batch.data?.status === "published" || batch.data?.status === "partially_published",
    queryFn: () => api<Report>(`/v1/import-batches/${batchId}/report`),
  });
  const publish = useMutation({
    mutationFn: () => api<{ operation_id: string }>(`/v1/import-batches/${batchId}/publish`, { body: {} }),
    onSuccess: (accepted) => {
      setPublishing(true);
      setOperationId(accepted.operation_id);
    },
  });

  if (!batch.data) {
    return batch.isError ? <p className="error">{batch.error.message}</p> : <p className="muted">Carregando lote…</p>;
  }
  const current = batch.data;
  const showPublish = current.status === "ready" && current.created_by !== me.user_id && can(me.roles, "approver", "admin");
  const errorText = publish.isError
    ? publish.error instanceof ApiError
      ? `${publish.error.title}. ${publish.error.message}`
      : "Falha ao publicar."
    : operation.data?.status === "failed"
      ? `A publicação falhou (${operation.data.error_code ?? "erro"}).`
      : null;

  return (
    <section>
      <h1>{current.source_system}</h1>
      <p>
        <span className="badge" data-testid="batch-status">{STATUS_LABEL[current.status] ?? current.status}</span>
        {" "}modo {current.mode}
        {current.published_by ? ` · publicado por ${current.published_by}` : ""}
      </p>
      <p className="muted">
        {current.summary.rows_received} linhas · {current.summary.rows_valid} válidas · {current.summary.rows_invalid} inválidas · débito {current.summary.debit_total} · crédito {current.summary.credit_total}
      </p>
      {errorText ? <p className="error">{errorText}</p> : null}
      {showPublish ? (
        <button type="button" data-testid="publish-batch" disabled={publish.isPending} onClick={() => publish.mutate()}>
          Publicar
        </button>
      ) : null}
      {current.errors.length > 0 ? (
        <table>
          <thead><tr><th>Linha</th><th>Código</th><th>Mensagem</th></tr></thead>
          <tbody>
            {current.errors.map((item) => (
              <tr key={`${item.row}-${item.code}`}>
                <td>{item.row}</td>
                <td>{item.code}</td>
                <td>{item.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {report.data ? (
        <div data-testid="import-report">
          <h2>Diferença</h2>
          <table>
            <thead>
              <tr><th>Conta</th><th>Fonte débito</th><th>Fonte crédito</th><th>Razão débito</th><th>Razão crédito</th><th>Diferença</th><th>Explicação</th></tr>
            </thead>
            <tbody>
              {report.data.rows.map((row) => (
                <tr key={row.account_code}>
                  <td>{row.account_code}</td>
                  <td className="amount">{row.source_debit}</td>
                  <td className="amount">{row.source_credit}</td>
                  <td className="amount">{row.ledger_debit}</td>
                  <td className="amount">{row.ledger_credit}</td>
                  <td className="amount">{row.difference}</td>
                  <td>{row.explanation || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <ul>
            {report.data.journals.map((item) => (
              <li key={item.journal_id}>
                <Link to={`/app/journals/${item.journal_id}`}>{item.external_id}</Link>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
