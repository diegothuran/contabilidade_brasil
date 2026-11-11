import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, api, downloadFile } from "../api";
import { formatDate, formatMoney } from "../format";
import { can, isClient, useSession } from "../session";
import { ReportSwitcher, useReportContext } from "./reports";

// Prévia da EFD-Reinf R-4000: pagamentos com retenção informados pelo usuário e o zip dos eventos para conferência.
// O sistema não calcula imposto, não assina e não transmite.

type BeneficiaryKind = "pj" | "pf";

type Payment = {
  id: string;
  legal_entity_id: string;
  period_id: string;
  payment_date: string;
  beneficiary_kind: BeneficiaryKind;
  beneficiary_document: string;
  beneficiary_name: string;
  nature_code: string;
  gross_amount: string;
  ir_base: string | null;
  ir_amount: string | null;
  csrf_base: string | null;
  csrf_amount: string | null;
  description: string | null;
  created_by: string;
  created_at: string;
};

type Nature = { code: string; description: string; beneficiary_kind: BeneficiaryKind };

type Issue = { code: string; severity: string; message: string; event: string | null; fix: string | null };

type Preview = {
  kind: string;
  period_id: string;
  competence: string;
  file_name: string;
  sha256: string;
  notice: string;
  transmittable: boolean;
  counts: Record<string, number>;
  checks: { xsd_valid?: boolean; ir_matches_ledger?: boolean | null } & Record<string, boolean | null | undefined>;
  issues: Issue[];
  layout_version: string;
};

type Form = {
  beneficiary_kind: BeneficiaryKind;
  beneficiary_document: string;
  beneficiary_name: string;
  nature_code: string;
  payment_date: string;
  gross_amount: string;
  ir_base: string;
  ir_amount: string;
  csrf_base: string;
  csrf_amount: string;
  description: string;
};

const NOTICE = "Prévia para conferência. Não assinar nem transmitir.";

const SEVERITY: Record<string, { label: string; order: number }> = {
  blocker: { label: "Falta", order: 0 },
  warning: { label: "Atenção", order: 1 },
  assumption: { label: "Suposição", order: 2 },
  out_of_scope: { label: "Fora da prévia", order: 3 },
};

const EVENTS = ["R-4010", "R-4020", "R-4099"] as const;

const EVENT_LABEL: Record<string, string> = {
  "R-4010": "pagamentos a pessoa física",
  "R-4020": "pagamentos a pessoa jurídica",
  "R-4099": "fechamento da competência",
};

const FIELDS = [
  "beneficiary_kind",
  "beneficiary_document",
  "beneficiary_name",
  "nature_code",
  "payment_date",
  "gross_amount",
  "ir_base",
  "ir_amount",
  "csrf_base",
  "csrf_amount",
  "description",
] as const;

function emptyForm(kind: BeneficiaryKind = "pj"): Form {
  return {
    beneficiary_kind: kind,
    beneficiary_document: "",
    beneficiary_name: "",
    nature_code: "",
    payment_date: "",
    gross_amount: "",
    ir_base: "",
    ir_amount: "",
    csrf_base: "",
    csrf_amount: "",
    description: "",
  };
}

// Mostra só parte do documento: no CNPJ, os 2 primeiros caracteres e a filial (12.***.***/0001-**);
// no CPF, os 6 do meio (***.456.789-**). O documento inteiro não aparece na lista.
function maskDocument(kind: BeneficiaryKind, document: string): string {
  const clean = document.replace(/[^0-9A-Za-z]/g, "").toUpperCase();
  if (kind === "pj" && clean.length === 14) {
    return `${clean.slice(0, 2)}.***.***/${clean.slice(8, 12)}-**`;
  }
  if (kind === "pf" && clean.length === 11) {
    return `***.${clean.slice(3, 6)}.${clean.slice(6, 9)}-**`;
  }
  return "Documento não reconhecido";
}

// Aceita "1.234,56" ou "1234.56"; o envio é string decimal com ponto, sem float. Vazio vira null.
function toDecimal(value: string): string | null {
  const text = value.trim().replace(/\s/g, "");
  if (!text) {
    return null;
  }
  return text.includes(",") ? text.replace(/\./g, "").replace(",", ".") : text;
}

function money(value: string | null): string {
  return value === null ? "—" : formatMoney(value);
}

function fixLink(fix: string | null, entityId: string): { to: string; label: string } | null {
  switch (fix) {
    case "withholding_payments":
      return { to: "#novo-pagamento", label: "Corrigir os pagamentos" };
    case "signatories":
      return { to: `/app/rastro/empresas/${entityId}/assinaturas`, label: "Definir o representante legal" };
    // Os dados cadastrais da empresa ainda não têm tela de edição; a pendência aparece sem link.
    default:
      return null;
  }
}

function checkTexts(checks: Preview["checks"]): string[] {
  const texts = [checks.xsd_valid ? "Valida no XSD" : "Não valida no XSD"];
  if (checks.ir_matches_ledger === true) {
    texts.push("O IR retido confere com o razão");
  } else if (checks.ir_matches_ledger === false) {
    texts.push("O IR retido não confere com o razão");
  } else {
    texts.push("IR retido contra o razão: não conferido nesta prévia");
  }
  return texts;
}

export function ReinfPage() {
  const { me, entityId } = useSession();
  const { periodId, period, periodText, entityText } = useReportContext();
  const queryClient = useQueryClient();
  const blocked = isClient(me.roles);
  const canWrite = can(me.roles, "preparer", "approver", "admin");
  const [form, setForm] = useState<Form>(() => emptyForm());
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [exportId, setExportId] = useState<string | null>(null);
  const [operationId, setOperationId] = useState<string | null>(null);
  const closed = period?.status === "closed";

  useEffect(() => {
    setExportId(null);
    setOperationId(null);
    setConfirmDelete(null);
  }, [entityId, periodId]);

  const paymentsKey = ["withholding-payments", entityId, periodId];
  const payments = useQuery({
    queryKey: paymentsKey,
    enabled: Boolean(entityId && periodId) && !blocked,
    retry: false,
    queryFn: () =>
      api<{ items: Payment[] }>(`/v1/legal-entities/${entityId}/withholding-payments?period_id=${encodeURIComponent(periodId)}`),
  });

  const natures = useQuery({
    queryKey: ["reinf-natures", form.beneficiary_kind],
    enabled: canWrite && !blocked,
    staleTime: 60 * 60 * 1000,
    queryFn: () => api<{ version: string; items: Nature[] }>(`/v1/regulatory/reinf/natures?beneficiary_kind=${form.beneficiary_kind}`),
  });

  const create = useMutation({
    mutationFn: () => {
      const pj = form.beneficiary_kind === "pj";
      return api<Payment>(`/v1/legal-entities/${entityId}/withholding-payments`, {
        body: {
          period_id: periodId,
          payment_date: form.payment_date,
          beneficiary_kind: form.beneficiary_kind,
          beneficiary_document: form.beneficiary_document.replace(/[^0-9A-Za-z]/g, "").toUpperCase(),
          beneficiary_name: form.beneficiary_name.trim(),
          nature_code: form.nature_code,
          gross_amount: toDecimal(form.gross_amount) ?? "",
          ir_base: toDecimal(form.ir_base),
          ir_amount: toDecimal(form.ir_amount),
          csrf_base: pj ? toDecimal(form.csrf_base) : null,
          csrf_amount: pj ? toDecimal(form.csrf_amount) : null,
          description: form.description.trim() || null,
        },
      });
    },
    onSuccess: async () => {
      setForm(emptyForm(form.beneficiary_kind));
      setExportId(null);
      setOperationId(null);
      await queryClient.invalidateQueries({ queryKey: paymentsKey });
    },
  });

  const remove = useMutation({
    mutationFn: (paymentId: string) =>
      api<void>(`/v1/legal-entities/${entityId}/withholding-payments/${paymentId}`, { method: "DELETE" }),
    onSuccess: async () => {
      setConfirmDelete(null);
      setExportId(null);
      setOperationId(null);
      await queryClient.invalidateQueries({ queryKey: paymentsKey });
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
    queryKey: ["reinf-preview", exportId],
    enabled: Boolean(exportId) && ready,
    queryFn: () => api<Preview>(`/v1/exports/${exportId}`),
  });
  const generate = useMutation({
    mutationFn: () =>
      api<{ export_id: string; operation_id: string }>(`/v1/legal-entities/${entityId}/exports`, {
        body: { kind: "reinf_r4000_preview_v1", period_id: periodId },
      }),
    onSuccess: (created) => {
      setExportId(created.export_id);
      setOperationId(created.operation_id);
    },
  });

  if (blocked) {
    return (
      <div className="report-page reinf-page">
        <section className="page-header">
          <div>
            <h1>Prévia da EFD-Reinf</h1>
            <p className="error" role="alert" data-testid="reinf-forbidden">Esta tela é do escritório. O cliente da empresa não tem acesso.</p>
          </div>
        </section>
      </div>
    );
  }

  const createError = create.error instanceof ApiError ? create.error : null;
  const errorFor = (field: (typeof FIELDS)[number]): string => {
    if (!createError) {
      return "";
    }
    return createError.errors
      .filter((item) => item.loc[item.loc.length - 1] === field)
      .map((item) => item.msg)
      .join(" ");
  };
  const unplacedErrors = createError
    ? createError.errors.filter((item) => !FIELDS.includes(item.loc[item.loc.length - 1] as (typeof FIELDS)[number])).map((item) => item.msg)
    : [];
  const createMessage = create.error ? (createError ? createError.message : "Não foi possível salvar o pagamento.") : "";
  const removeError = remove.error instanceof ApiError ? remove.error.message : remove.error ? "Não foi possível excluir o pagamento." : "";
  const generateError = generate.error instanceof ApiError ? generate.error.message : generate.error ? "Não foi possível pedir a prévia." : "";
  const paymentsForbidden = payments.error instanceof ApiError && payments.error.status === 403;
  const issues = [...(preview.data?.issues ?? [])].sort(
    (left, right) => (SEVERITY[left.severity]?.order ?? 9) - (SEVERITY[right.severity]?.order ?? 9),
  );
  const groups = Object.keys(SEVERITY)
    .concat(issues.map((issue) => issue.severity).filter((severity) => !(severity in SEVERITY)))
    .filter((severity, index, list) => list.indexOf(severity) === index)
    .map((severity) => ({ severity, items: issues.filter((issue) => issue.severity === severity) }))
    .filter((group) => group.items.length > 0);
  const blockers = issues.filter((issue) => issue.severity === "blocker").length;
  const items = payments.data?.items ?? [];
  const eventNames: string[] = [...EVENTS, ...Object.keys(preview.data?.counts ?? {}).filter((name) => !(EVENTS as readonly string[]).includes(name))];
  const pj = form.beneficiary_kind === "pj";

  const fieldNote = (field: (typeof FIELDS)[number]) => {
    const message = errorFor(field);
    return message ? (
      <small className="error reinf-field-error" id={`reinf-error-${field}`} data-testid={`reinf-error-${field}`}>
        Recusado: {message}
      </small>
    ) : null;
  };
  const described = (field: (typeof FIELDS)[number]) => (errorFor(field) ? { "aria-invalid": true, "aria-describedby": `reinf-error-${field}` } : {});

  return (
    <div className="report-page reinf-page">
      <section className="page-header">
        <div>
          <span className="eyebrow">Relatórios · {entityText} · {periodText}</span>
          <h1>Prévia da EFD-Reinf</h1>
          <p>
            Monta os eventos R-4010, R-4020 e R-4099 da série R-4000 a partir dos pagamentos com retenção informados aqui, valida no XSD
            oficial e entrega um .zip para conferência. O sistema não calcula imposto, não assina e não transmite.
          </p>
          <ReportSwitcher />
        </div>
      </section>

      <p className="ecd-notice" role="note" data-testid="reinf-notice">{NOTICE}</p>

      {!entityId || !periodId ? (
        <p className="state-message" role="status" data-testid="reinf-no-context">Escolha a empresa e a competência na barra para ver os pagamentos.</p>
      ) : null}

      <section className="panel panel--flush" data-testid="reinf-payments">
        <div className="table-toolbar report-toolbar">
          <div>
            <span className="eyebrow">Pagamentos com retenção</span>
            <h2 className="report-title">Competência {periodText}</h2>
          </div>
          <span className="table-count">
            {payments.isLoading ? "Carregando" : payments.data ? `${items.length} pagamento(s)` : ""}
          </span>
        </div>
        {closed ? <p className="state-message reinf-inline" role="status">Competência fechada: a lista não aceita inclusão nem exclusão.</p> : null}
        {payments.isLoading ? <p className="state-message reinf-inline" role="status">Carregando os pagamentos…</p> : null}
        {paymentsForbidden ? (
          <p className="error reinf-inline" role="alert" data-testid="reinf-payments-forbidden">Seu papel não lê os pagamentos desta empresa.</p>
        ) : payments.isError ? (
          <p className="error reinf-inline" role="alert">Não foi possível ler os pagamentos.</p>
        ) : null}
        {payments.data && items.length === 0 ? (
          <p className="state-message reinf-inline" data-testid="reinf-payments-empty">
            Nenhum pagamento com retenção nesta competência. Sem pagamento, a prévia não gera evento.
          </p>
        ) : null}
        {items.length > 0 ? (
          <div className="table-scroll">
            <table className="data-table report-table">
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Beneficiário</th>
                  <th>Natureza</th>
                  <th className="amount">Bruto</th>
                  <th className="amount">IR (base / valor)</th>
                  <th className="amount">CSRF (base / valor)</th>
                  {canWrite ? <th><span className="sr-only">Ações</span></th> : null}
                </tr>
              </thead>
              <tbody>
                {items.map((payment) => (
                  <tr key={payment.id} data-testid="reinf-payment-row">
                    <td>{formatDate(payment.payment_date)}</td>
                    <td>
                      <strong>{payment.beneficiary_name}</strong>
                      <span>
                        {payment.beneficiary_kind === "pj" ? "PJ" : "PF"} · {maskDocument(payment.beneficiary_kind, payment.beneficiary_document)}
                      </span>
                    </td>
                    <td><code>{payment.nature_code}</code></td>
                    <td className="amount">{formatMoney(payment.gross_amount)}</td>
                    <td className="amount">
                      {money(payment.ir_base)} / {payment.ir_base !== null && payment.ir_amount === null ? "dispensado" : money(payment.ir_amount)}
                    </td>
                    <td className="amount">
                      {payment.beneficiary_kind === "pf" ? "não se aplica" : `${money(payment.csrf_base)} / ${money(payment.csrf_amount)}`}
                    </td>
                    {canWrite ? (
                      <td>
                        {confirmDelete === payment.id ? (
                          <span className="reinf-confirm">
                            <button
                              type="button"
                              className="button button--secondary secondary"
                              data-testid="reinf-delete-confirm"
                              disabled={remove.isPending}
                              onClick={() => remove.mutate(payment.id)}
                            >
                              {remove.isPending ? "Excluindo…" : "Confirmar exclusão"}
                            </button>
                            <button type="button" className="text-button" onClick={() => setConfirmDelete(null)}>Cancelar</button>
                          </span>
                        ) : (
                          <button
                            type="button"
                            className="text-button"
                            data-testid="reinf-delete"
                            disabled={closed}
                            onClick={() => {
                              remove.reset();
                              setConfirmDelete(payment.id);
                            }}
                          >
                            Excluir
                          </button>
                        )}
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        {removeError ? <p className="error reinf-inline" role="alert">{removeError}</p> : null}
      </section>

      <section className="panel" id="novo-pagamento" data-testid="reinf-form">
        <span className="eyebrow">Novo pagamento</span>
        <h2 className="report-title">Pagamento com retenção</h2>
        {canWrite ? (
          <>
            <p className="muted">
              Informe os valores como estão no documento. O sistema confere a coerência (base não menor que o valor, data dentro da
              competência, natureza da tabela) e não calcula imposto. IR dispensado: preencha a base e deixe o valor vazio. A CSRF
              (CSLL, Cofins e PIS agregados) só vale para pessoa jurídica.
            </p>
            <form
              className="ecd-form reinf-form"
              onSubmit={(event) => {
                event.preventDefault();
                create.mutate();
              }}
            >
              <fieldset disabled={create.isPending || closed || !entityId || !periodId}>
                <label>
                  <span>Tipo de beneficiário</span>
                  <select
                    data-testid="reinf-kind"
                    value={form.beneficiary_kind}
                    onChange={(event) => {
                      const kind = event.target.value as BeneficiaryKind;
                      setForm({ ...form, beneficiary_kind: kind, nature_code: "", csrf_base: "", csrf_amount: "" });
                    }}
                    {...described("beneficiary_kind")}
                  >
                    <option value="pj">Pessoa jurídica (CNPJ)</option>
                    <option value="pf">Pessoa física (CPF)</option>
                  </select>
                  {fieldNote("beneficiary_kind")}
                </label>
                <label>
                  <span>{pj ? "CNPJ do beneficiário" : "CPF do beneficiário"}</span>
                  <input
                    data-testid="reinf-document"
                    value={form.beneficiary_document}
                    maxLength={pj ? 18 : 14}
                    autoComplete="off"
                    onChange={(event) => setForm({ ...form, beneficiary_document: event.target.value })}
                    required
                    {...described("beneficiary_document")}
                  />
                  {fieldNote("beneficiary_document")}
                </label>
                <label>
                  <span>Nome do beneficiário</span>
                  <input
                    data-testid="reinf-name"
                    value={form.beneficiary_name}
                    maxLength={150}
                    onChange={(event) => setForm({ ...form, beneficiary_name: event.target.value })}
                    required
                    {...described("beneficiary_name")}
                  />
                  {fieldNote("beneficiary_name")}
                </label>
                <label className="reinf-form__wide">
                  <span>Natureza do rendimento</span>
                  <select
                    data-testid="reinf-nature"
                    value={form.nature_code}
                    onChange={(event) => setForm({ ...form, nature_code: event.target.value })}
                    required
                    {...described("nature_code")}
                  >
                    <option value="">{natures.isLoading ? "Carregando a tabela…" : "Escolha a natureza"}</option>
                    {(natures.data?.items ?? []).map((nature) => (
                      <option key={nature.code} value={nature.code}>{nature.code} · {nature.description}</option>
                    ))}
                  </select>
                  {natures.isError ? <small className="error">Não foi possível ler a tabela de naturezas.</small> : null}
                  {natures.data ? <small className="muted">Tabela 01 da prévia, versão {natures.data.version}.</small> : null}
                  {fieldNote("nature_code")}
                </label>
                <label>
                  <span>Data do pagamento</span>
                  <input
                    type="date"
                    data-testid="reinf-date"
                    value={form.payment_date}
                    onChange={(event) => setForm({ ...form, payment_date: event.target.value })}
                    required
                    {...described("payment_date")}
                  />
                  {fieldNote("payment_date")}
                </label>
                <label>
                  <span>Valor bruto (R$)</span>
                  <input
                    data-testid="reinf-gross"
                    inputMode="decimal"
                    placeholder="0,00"
                    value={form.gross_amount}
                    onChange={(event) => setForm({ ...form, gross_amount: event.target.value })}
                    required
                    {...described("gross_amount")}
                  />
                  {fieldNote("gross_amount")}
                </label>
                <label>
                  <span>Base do IR (R$)</span>
                  <input
                    data-testid="reinf-ir-base"
                    inputMode="decimal"
                    placeholder="0,00"
                    value={form.ir_base}
                    onChange={(event) => setForm({ ...form, ir_base: event.target.value })}
                    {...described("ir_base")}
                  />
                  {fieldNote("ir_base")}
                </label>
                <label>
                  <span>IR retido (R$)</span>
                  <input
                    data-testid="reinf-ir-amount"
                    inputMode="decimal"
                    placeholder="0,00"
                    value={form.ir_amount}
                    onChange={(event) => setForm({ ...form, ir_amount: event.target.value })}
                    {...described("ir_amount")}
                  />
                  {fieldNote("ir_amount")}
                </label>
                {pj ? (
                  <>
                    <label>
                      <span>Base da CSRF (R$)</span>
                      <input
                        data-testid="reinf-csrf-base"
                        inputMode="decimal"
                        placeholder="0,00"
                        value={form.csrf_base}
                        onChange={(event) => setForm({ ...form, csrf_base: event.target.value })}
                        {...described("csrf_base")}
                      />
                      {fieldNote("csrf_base")}
                    </label>
                    <label>
                      <span>CSRF retida (R$)</span>
                      <input
                        data-testid="reinf-csrf-amount"
                        inputMode="decimal"
                        placeholder="0,00"
                        value={form.csrf_amount}
                        onChange={(event) => setForm({ ...form, csrf_amount: event.target.value })}
                        {...described("csrf_amount")}
                      />
                      {fieldNote("csrf_amount")}
                    </label>
                  </>
                ) : null}
                <label className="reinf-form__wide">
                  <span>Descrição (opcional)</span>
                  <input
                    data-testid="reinf-description"
                    value={form.description}
                    maxLength={200}
                    onChange={(event) => setForm({ ...form, description: event.target.value })}
                    {...described("description")}
                  />
                  {fieldNote("description")}
                </label>
                <button type="submit" className="button" data-testid="reinf-save">
                  {create.isPending ? "Salvando…" : "Incluir pagamento"}
                </button>
              </fieldset>
            </form>
            {create.isSuccess ? <p className="state-message" role="status">Pagamento incluído.</p> : null}
            {createMessage ? (
              <p className="error" role="alert" data-testid="reinf-save-error">
                {createMessage}
                {unplacedErrors.length > 0 ? ` ${unplacedErrors.join(" ")}` : ""}
              </p>
            ) : null}
          </>
        ) : (
          <p className="muted" data-testid="reinf-readonly">Só preparador, aprovador e admin incluem ou excluem pagamentos.</p>
        )}
      </section>

      <section className="panel" data-testid="reinf-generate">
        <span className="eyebrow">Arquivo</span>
        <h2 className="report-title">Gerar a prévia</h2>
        <div className="ecd-actions">
          {canWrite ? (
            <button
              type="button"
              className="button"
              data-testid="reinf-generate-button"
              disabled={!entityId || !periodId || generate.isPending}
              onClick={() => generate.mutate()}
            >
              {generate.isPending ? "Pedindo…" : "Gerar prévia"}
            </button>
          ) : (
            <p className="muted">A consulta não gera a prévia.</p>
          )}
        </div>
        {operation.data && !ready && operation.data.status !== "failed" ? (
          <p className="state-message" role="status" data-testid="reinf-generating">Gerando a prévia…</p>
        ) : null}
        {operation.data?.status === "failed" ? (
          <p className="error" role="alert">A geração falhou. Tente de novo; o pedido fica registrado na auditoria.</p>
        ) : null}
        {preview.isError ? <p className="error" role="alert">Não foi possível ler o resultado da prévia.</p> : null}
        {generateError ? <p className="error" role="alert">{generateError}</p> : null}
        {preview.data ? (
          <div className="ecd-result" data-testid="reinf-result">
            <p>
              <strong data-testid="reinf-file-name">{preview.data.file_name}</strong> ·{" "}
              {blockers === 0 ? "sem pendência bloqueante" : `${blockers} pendência(s) bloqueante(s)`} · leiaute {preview.data.layout_version} ·{" "}
              {preview.data.transmittable ? "transmissível" : "não transmissível"}
            </p>
            <button
              type="button"
              className="button button--secondary secondary"
              data-testid="reinf-download"
              onClick={() => void downloadFile(`/v1/exports/${exportId}/file`, preview.data?.file_name ?? "reinf-r4000-previa.zip")}
            >
              Baixar arquivo (.zip)
            </button>
            <p className="muted">SHA-256 {preview.data.sha256}</p>
            <p className="muted">{preview.data.notice}</p>
          </div>
        ) : null}
      </section>

      {preview.data ? (
        <section className="panel" data-testid="reinf-issues">
          <span className="eyebrow">O que a prévia montou</span>
          <h2 className="report-title">Eventos e conferências</h2>
          <ul className="ecd-checks" data-testid="reinf-counts">
            {eventNames.map((name) => (
              <li key={name}>
                <code>{name}</code> · {preview.data?.counts[name] ?? 0} evento(s){EVENT_LABEL[name] ? ` · ${EVENT_LABEL[name]}` : ""}
              </li>
            ))}
          </ul>
          <h3>Conferências</h3>
          <ul className="ecd-checks" data-testid="reinf-checks">
            {checkTexts(preview.data.checks).map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
          <h3>Pendências</h3>
          {groups.length === 0 ? <p className="muted">Nenhuma pendência.</p> : null}
          {groups.map((group) => (
            <div key={group.severity} className="reinf-issue-group" data-testid={`reinf-issues-${group.severity}`}>
              <h4>{SEVERITY[group.severity]?.label ?? group.severity} ({group.items.length})</h4>
              <ul className="ecd-issues">
                {group.items.map((issue, index) => {
                  const link = fixLink(issue.fix, entityId);
                  return (
                    <li key={`${issue.code}-${index}`} className={`ecd-issue ecd-issue--${issue.severity}`}>
                      <span className="ecd-issue__severity">{SEVERITY[issue.severity]?.label ?? issue.severity}</span>
                      {issue.event ? <code>{issue.event}</code> : null}
                      <span>{issue.message}</span>
                      {link ? (
                        link.to.startsWith("#") ? <a href={link.to}>{link.label}</a> : <Link to={link.to}>{link.label}</Link>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </section>
      ) : null}
    </div>
  );
}
