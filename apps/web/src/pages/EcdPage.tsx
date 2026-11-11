import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, api, downloadFile } from "../api";
import { can, useSession } from "../session";
import { ReportSwitcher, useReportContext } from "./reports";

// Prévia da ECD (ADR 031): gera o .txt do leiaute para conferência no PVA. Não transmite nem assina.

type Registration = {
  legal_entity_id: string;
  configured: boolean;
  uf: string | null;
  municipality_ibge: string | null;
  registry_kind: "junta" | "cartorio" | null;
  nire: string | null;
  registry_date: string | null;
  special_situation: string | null;
  book_number: number | null;
};

type Issue = { code: string; severity: string; message: string; register: string | null; fix: string | null };

type Preview = {
  kind: string;
  fiscal_year: number;
  file_name: string;
  sha256: string;
  notice: string;
  result: string;
  counts: Record<string, number>;
  checks: Record<string, boolean>;
  issues: Issue[];
};

type Form = {
  uf: string;
  municipality_ibge: string;
  registry_kind: "junta" | "cartorio";
  nire: string;
  registry_date: string;
  special_situation: string;
  book_number: string;
};

const NOTICE = "Prévia para conferência no PVA. Não transmitir.";

const SEVERITY: Record<string, { label: string; order: number }> = {
  blocker: { label: "Falta", order: 0 },
  warning: { label: "Atenção", order: 1 },
  assumption: { label: "Suposição", order: 2 },
  out_of_scope: { label: "Fora da prévia", order: 3 },
};

const CHECK_LABEL: Record<string, string> = {
  i200_matches_i250: "Cada lançamento (I200) fecha com as partidas (I250)",
  i155_rolls_forward: "Saldos mensais (I155): inicial + débitos − créditos = final",
  i355_matches_income_statement: "Saldos antes do encerramento (I355) somam o resultado da DRE",
  j100_balances: "Balanço (J100): ativo = passivo + patrimônio líquido",
  block_counts: "Contagens dos blocos e do registro 9900",
};

const SITUATIONS = [
  ["", "Nenhuma"],
  ["1", "Cisão"],
  ["2", "Fusão"],
  ["3", "Incorporação"],
  ["4", "Extinção"],
] as const;

function emptyForm(): Form {
  return { uf: "PE", municipality_ibge: "", registry_kind: "junta", nire: "", registry_date: "", special_situation: "", book_number: "1" };
}

function toForm(registration: Registration): Form {
  if (!registration.configured) {
    return emptyForm();
  }
  return {
    uf: registration.uf ?? "",
    municipality_ibge: registration.municipality_ibge ?? "",
    registry_kind: registration.registry_kind ?? "junta",
    nire: registration.nire ?? "",
    registry_date: registration.registry_date ?? "",
    special_situation: registration.special_situation ?? "",
    book_number: String(registration.book_number ?? 1),
  };
}

function fixLink(fix: string | null, entityId: string): { to: string; label: string } | null {
  switch (fix) {
    case "ecd_registration":
      return { to: "#dados-escrituracao", label: "Preencher os dados da escrituração" };
    case "signatories":
      return { to: `/app/rastro/empresas/${entityId}/assinaturas`, label: "Definir os signatários" };
    case "accounts":
      return { to: "/app/accounts", label: "Abrir o plano de contas" };
    case "journals":
      return { to: "/app/rastro/ledger", label: "Ver os lançamentos" };
    case "year_end_closing":
      return { to: "/app/rastro/balancete", label: "Gerar o encerramento no balancete de dezembro" };
    default:
      return null;
  }
}

export function EcdPage() {
  const { me, entityId } = useSession();
  const { period, entityText } = useReportContext();
  const queryClient = useQueryClient();
  const isAdmin = can(me.roles, "admin");
  const canGenerate = can(me.roles, "preparer", "approver", "admin");
  const [year, setYear] = useState<number>(() => new Date().getFullYear());
  const [form, setForm] = useState<Form>(emptyForm);
  const [exportId, setExportId] = useState<string | null>(null);
  const [operationId, setOperationId] = useState<string | null>(null);

  useEffect(() => {
    if (period) {
      setYear(period.fiscal_year);
    }
  }, [period]);
  useEffect(() => {
    setExportId(null);
    setOperationId(null);
  }, [entityId, year]);

  const registration = useQuery({
    queryKey: ["ecd-registration", entityId],
    enabled: Boolean(entityId),
    queryFn: () => api<Registration>(`/v1/legal-entities/${entityId}/ecd-registration`),
  });
  useEffect(() => {
    if (registration.data) {
      setForm(toForm(registration.data));
    }
  }, [registration.data]);

  const save = useMutation({
    mutationFn: () =>
      api<Registration>(`/v1/legal-entities/${entityId}/ecd-registration`, {
        method: "PUT",
        body: {
          uf: form.uf.trim().toUpperCase(),
          municipality_ibge: form.municipality_ibge.trim(),
          registry_kind: form.registry_kind,
          nire: form.registry_kind === "junta" ? form.nire.trim() || null : null,
          registry_date: form.registry_date || null,
          special_situation: form.special_situation || null,
          book_number: Number(form.book_number),
        },
      }),
    onSuccess: async (saved) => {
      queryClient.setQueryData(["ecd-registration", entityId], saved);
    },
  });

  const operation = useQuery({
    queryKey: ["operation", operationId],
    enabled: Boolean(operationId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "accepted" || status === "running" ? 1500 : false;
    },
    queryFn: () => api<{ status: string }>(`/v1/operations/${operationId}`),
  });
  const ready = operation.data?.status === "completed";
  const preview = useQuery({
    queryKey: ["ecd-preview", exportId],
    enabled: Boolean(exportId) && ready,
    queryFn: () => api<Preview>(`/v1/exports/${exportId}`),
  });
  const generate = useMutation({
    mutationFn: () =>
      api<{ export_id: string; operation_id: string }>(`/v1/legal-entities/${entityId}/exports`, {
        body: { kind: "ecd_preview_v1", fiscal_year: year },
      }),
    onSuccess: (created) => {
      setExportId(created.export_id);
      setOperationId(created.operation_id);
    },
  });

  const issues = [...(preview.data?.issues ?? [])].sort(
    (left, right) => (SEVERITY[left.severity]?.order ?? 9) - (SEVERITY[right.severity]?.order ?? 9),
  );
  const blockers = issues.filter((issue) => issue.severity === "blocker").length;
  const saveError = save.error instanceof ApiError ? save.error.message : save.error ? "Não foi possível salvar." : "";
  const generateError = generate.error instanceof ApiError ? generate.error.message : generate.error ? "Não foi possível pedir a prévia." : "";
  const years = [year - 1, year, year + 1].filter((item, index, list) => list.indexOf(item) === index);

  return (
    <div className="report-page ecd-page">
      <section className="page-header">
        <div>
          <span className="eyebrow">Relatórios · {entityText}</span>
          <h1>Prévia da ECD</h1>
          <p>
            Gera o arquivo da Escrituração Contábil Digital (leiaute 9) a partir do razão, para importar e conferir no PVA da Receita.
            O sistema não transmite, não assina e não usa certificado.
          </p>
          <ReportSwitcher />
        </div>
      </section>

      <p className="ecd-notice" role="note" data-testid="ecd-notice">{NOTICE}</p>

      <section className="panel" id="dados-escrituracao" data-testid="ecd-registration">
        <span className="eyebrow">Dados da escrituração</span>
        <h2 className="report-title">Sede, registro e livro</h2>
        <p className="muted">
          Vão para os registros 0000 e I030. O município usa o código IBGE de 7 dígitos (Recife é 2611606). O NIRE é dado pela Junta
          Comercial e começa com o código da UF (26 em Pernambuco). Sociedade registrada em cartório não tem NIRE.
        </p>
        {registration.isError ? <p className="error">Não foi possível ler os dados da escrituração.</p> : null}
        <form
          className="ecd-form"
          onSubmit={(event) => {
            event.preventDefault();
            save.mutate();
          }}
        >
          <fieldset disabled={!isAdmin || save.isPending}>
            <label>
              <span>UF da sede</span>
              <input value={form.uf} maxLength={2} onChange={(event) => setForm({ ...form, uf: event.target.value })} required />
            </label>
            <label>
              <span>Município (código IBGE)</span>
              <input
                value={form.municipality_ibge}
                inputMode="numeric"
                maxLength={7}
                onChange={(event) => setForm({ ...form, municipality_ibge: event.target.value })}
                required
              />
            </label>
            <label>
              <span>Registro</span>
              <select
                value={form.registry_kind}
                onChange={(event) => setForm({ ...form, registry_kind: event.target.value as Form["registry_kind"] })}
              >
                <option value="junta">Junta Comercial (com NIRE)</option>
                <option value="cartorio">Cartório de pessoas jurídicas (sem NIRE)</option>
              </select>
            </label>
            {form.registry_kind === "junta" ? (
              <label>
                <span>NIRE</span>
                <input value={form.nire} inputMode="numeric" maxLength={14} onChange={(event) => setForm({ ...form, nire: event.target.value })} />
              </label>
            ) : null}
            <label>
              <span>{form.registry_kind === "cartorio" ? "Data de abertura" : "Data do arquivamento"}</span>
              <input type="date" value={form.registry_date} onChange={(event) => setForm({ ...form, registry_date: event.target.value })} />
              {form.registry_kind === "cartorio" ? (
                <small className="muted" data-testid="ecd-opening-date-hint">Sem NIRE, a ECD usa a data de abertura do CNPJ no I030.</small>
              ) : null}
            </label>
            <label>
              <span>Situação especial</span>
              <select value={form.special_situation} onChange={(event) => setForm({ ...form, special_situation: event.target.value })}>
                {SITUATIONS.map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
            <label>
              <span>Número de ordem do livro</span>
              <input
                type="number"
                min={1}
                value={form.book_number}
                onChange={(event) => setForm({ ...form, book_number: event.target.value })}
                required
              />
            </label>
            {isAdmin ? (
              <button type="submit" className="button">{save.isPending ? "Salvando…" : "Salvar dados da escrituração"}</button>
            ) : null}
          </fieldset>
        </form>
        {!isAdmin ? <p className="muted">Só o administrador do escritório altera estes dados.</p> : null}
        {save.isSuccess ? <p className="state-message" role="status">Dados da escrituração salvos.</p> : null}
        {saveError ? <p className="error" role="alert">{saveError}</p> : null}
      </section>

      <section className="panel" data-testid="ecd-generate">
        <span className="eyebrow">Arquivo</span>
        <h2 className="report-title">Gerar a prévia</h2>
        <div className="ecd-actions">
          <label>
            <span>Ano-calendário</span>
            <select value={year} onChange={(event) => setYear(Number(event.target.value))}>
              {years.map((item) => (
                <option key={item} value={item}>{item}</option>
              ))}
            </select>
          </label>
          {canGenerate ? (
            <button type="button" className="button" disabled={!entityId || generate.isPending} onClick={() => generate.mutate()}>
              {generate.isPending ? "Pedindo…" : "Gerar prévia"}
            </button>
          ) : (
            <p className="muted">A consulta não gera a prévia.</p>
          )}
        </div>
        {operation.data && !ready && operation.data.status !== "failed" ? (
          <p className="state-message" role="status">Gerando a prévia…</p>
        ) : null}
        {operation.data?.status === "failed" ? <p className="error" role="alert">A geração falhou. Tente de novo; o pedido fica registrado na auditoria.</p> : null}
        {generateError ? <p className="error" role="alert">{generateError}</p> : null}
        {preview.data ? (
          <div className="ecd-result" data-testid="ecd-result">
            <p>
              <strong>{preview.data.file_name}</strong> · {blockers === 0 ? "sem pendência bloqueante" : `${blockers} pendência(s) antes do PVA`}
            </p>
            <button
              type="button"
              className="button button--secondary secondary"
              data-testid="ecd-download"
              onClick={() => void downloadFile(`/v1/exports/${exportId}/file`, preview.data?.file_name ?? "ecd-previa.txt")}
            >
              Baixar arquivo (.txt)
            </button>
            <p className="muted">SHA-256 {preview.data.sha256}</p>
          </div>
        ) : null}
      </section>

      {preview.data ? (
        <section className="panel" data-testid="ecd-issues">
          <span className="eyebrow">O que falta</span>
          <h2 className="report-title">Pendências da prévia</h2>
          <ul className="ecd-issues">
            {issues.map((issue, index) => {
              const link = fixLink(issue.fix, entityId);
              return (
                <li key={`${issue.code}-${index}`} className={`ecd-issue ecd-issue--${issue.severity}`}>
                  <span className="ecd-issue__severity">{SEVERITY[issue.severity]?.label ?? issue.severity}</span>
                  {issue.register ? <code>{issue.register}</code> : null}
                  <span>{issue.message}</span>
                  {link ? (
                    link.to.startsWith("#") ? <a href={link.to}>{link.label}</a> : <Link to={link.to}>{link.label}</Link>
                  ) : null}
                </li>
              );
            })}
          </ul>
          <h3>Conferências internas</h3>
          <ul className="ecd-checks">
            {Object.entries(preview.data.checks).map(([name, passed]) => (
              <li key={name}>{passed ? "Fecha" : "Não fecha"} · {CHECK_LABEL[name] ?? name}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
