import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, api, uploadDocument } from "../api";
import { STATUS_LABEL, can, useSession } from "../session";

type Account = { account_id: string; code: string; name: string; postable: boolean; active: boolean };
type BankAccount = { bank_account_id: string; account_id: string; name: string; account_number_masked: string };
type Statement = { statement_id: string; status: string; error_message: string | null; transactions_new: number; transactions_duplicate: number };
type Candidate = { candidate_id: string; score: number; explanation: string[] };
type CounterpartSuggestion = {
  account_id: string;
  code: string;
  name: string;
  confidence: string;
  justification: string;
  source: "history" | "model";
  provider_version: string;
};
type Case = {
  case_id: string;
  bank_account_id: string;
  status: string;
  journal_id: string | null;
  reason: string | null;
  bank_transaction: { date: string; amount: string; direction: string; description: string };
  candidates: Candidate[];
  counterpart_suggestions?: CounterpartSuggestion[];
  model_suggestions_enabled?: boolean;
};
type Summary = {
  ledger_balance: string;
  statement_balance: string | null;
  pending_inflow_count: number;
  pending_inflow_total: string;
  pending_outflow_count: number;
  pending_outflow_total: string;
  unmatched_ledger_count: number;
  unmatched_ledger_total: string;
};

const DIRECTION: Record<string, string> = { inflow: "Entrada", outflow: "Saída" };

// Operação de sugestão por IA concluída com aviso (operations.error_code) ou com falha.
const SUGGESTION_WARNING: Record<string, string> = {
  limite_diario: "Limite diário de sugestões por IA atingido: parte dos casos ficou sem sugestão da IA.",
  resposta_incompleta: "A IA não respondeu todos os casos. Confira os que ficaram sem sugestão.",
};
type SuggestionNotice = { kind: "error" | "warning"; text: string };

// Sugestão é sempre "sugerida" (SPEC §7, ADR 035): a tela pré-seleciona e a pessoa confirma.
function suggestionLabel(suggestion: CounterpartSuggestion): string {
  const account = `${suggestion.code} ${suggestion.name} (confiança ${suggestion.confidence})`;
  return suggestion.source === "model" ? `Sugerido pela IA: ${account} — confira` : `Sugerido pelo histórico: ${account}`;
}

// Só a primeira sugestão aceita conta como acerto (rank 1); trocar a conta é escolha manual.
function chosenOrigin(suggestions: CounterpartSuggestion[], accountId: string): { suggestion_source: string; suggestion_rank: 1 | null } {
  const first = suggestions[0];
  if (first && first.account_id === accountId) {
    return { suggestion_source: first.source, suggestion_rank: 1 };
  }
  return { suggestion_source: "manual", suggestion_rank: null };
}

export function ReconciliationPage() {
  const { entityId, me, periodId } = useSession();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [params] = useSearchParams();
  const linkedCaseId = params.get("case");
  const [bankAccountId, setBankAccountId] = useState("");
  const [status, setStatus] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [statementId, setStatementId] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [chosenCounterparts, setChosenCounterparts] = useState<Record<string, string>>({});
  const [suggestionOperationId, setSuggestionOperationId] = useState<string | null>(null);
  // Guarda o desfecho da última operação: a consulta da operação some quando ela termina.
  const [suggestionNotice, setSuggestionNotice] = useState<SuggestionNotice | null>(null);
  const banks = useQuery({
    queryKey: ["bank-accounts", entityId],
    queryFn: () => api<{ items: BankAccount[] }>(`/v1/bank-accounts?legal_entity_id=${entityId}`),
  });
  const accounts = useQuery({
    queryKey: ["accounts", entityId],
    queryFn: () => api<{ items: Account[] }>(`/v1/legal-entities/${entityId}/accounts`),
  });
  const linked = useQuery({
    queryKey: ["case", linkedCaseId],
    enabled: Boolean(linkedCaseId),
    queryFn: () => api<Case>(`/v1/reconciliation-cases/${linkedCaseId}`),
  });
  const selectedBank = bankAccountId || banks.data?.items[0]?.bank_account_id || "";
  const cases = useQuery({
    queryKey: ["cases", selectedBank, status],
    enabled: Boolean(selectedBank),
    queryFn: () => api<{ items: Case[] }>(`/v1/reconciliation-cases?bank_account_id=${selectedBank}${status ? `&status=${status}` : ""}`),
    refetchInterval: statementId ? 1000 : false,
  });
  const statement = useQuery({
    queryKey: ["statement", statementId],
    enabled: Boolean(statementId),
    queryFn: () => api<Statement>(`/v1/bank-statements/${statementId}`),
    refetchInterval: (query) => (query.state.data?.status === "received" ? 1000 : false),
  });
  const summary = useQuery({
    queryKey: ["bank-summary", selectedBank, periodId],
    enabled: Boolean(selectedBank && periodId),
    queryFn: () => api<Summary>(`/v1/bank-accounts/${selectedBank}/summary?period_id=${periodId}`),
  });

  const suggestionOperation = useQuery({
    queryKey: ["operation", suggestionOperationId],
    enabled: Boolean(suggestionOperationId),
    queryFn: () => api<{ status: string; error_code: string | null }>(`/v1/operations/${suggestionOperationId}`),
    refetchInterval: (query) => (query.state.data?.status === "accepted" || query.state.data?.status === "running" ? 1000 : false),
  });
  const suggestionRunning =
    Boolean(suggestionOperationId) && !["completed", "failed"].includes(suggestionOperation.data?.status ?? "accepted");

  useEffect(() => {
    const finished = suggestionOperation.data?.status;
    if (finished === "completed" || finished === "failed") {
      const code = suggestionOperation.data?.error_code ?? null;
      if (finished === "failed") {
        setSuggestionNotice({ kind: "error", text: "A sugestão por IA falhou. Siga com a escolha manual." });
      } else if (code && SUGGESTION_WARNING[code]) {
        setSuggestionNotice({ kind: "warning", text: SUGGESTION_WARNING[code] });
      } else {
        setSuggestionNotice(null);
      }
      setSuggestionOperationId(null);
      void queryClient.invalidateQueries({ queryKey: ["cases", selectedBank] });
    }
  }, [queryClient, selectedBank, suggestionOperation.data]);

  useEffect(() => {
    if (linked.data?.bank_account_id) {
      setBankAccountId(linked.data.bank_account_id);
    }
  }, [linked.data]);

  useEffect(() => {
    if (statement.data && statement.data.status !== "received") {
      setStatementId(null);
      void queryClient.invalidateQueries({ queryKey: ["cases", selectedBank] });
      void queryClient.invalidateQueries({ queryKey: ["bank-summary", selectedBank] });
    }
  }, [queryClient, selectedBank, statement.data]);

  const bank = (banks.data?.items ?? []).find((item) => item.bank_account_id === selectedBank);
  const counterparts = (accounts.data?.items ?? []).filter((account) => account.postable && account.active && account.account_id !== bank?.account_id);
  const upload = useMutation({
    mutationFn: async () => {
      if (!file || !selectedBank) {
        throw new ApiError(400, "Arquivo obrigatório", "Escolha o extrato CSV ou OFX.");
      }
      const document = await uploadDocument(file, { document_type: "bank_statement", legal_entity_id: entityId, competence: "2026-01" });
      return api<{ statement_id: string }>(`/v1/bank-accounts/${selectedBank}/statements`, { body: { document_id: document.document_id } });
    },
    onSuccess: (operation) => setStatementId(operation.statement_id),
  });
  const requestSuggestions = useMutation({
    mutationFn: () =>
      api<{ operation_id: string }>(`/v1/bank-accounts/${selectedBank}/counterpart-suggestions`, { body: { period_id: periodId } }),
    onMutate: () => setSuggestionNotice(null),
    onSuccess: (operation) => setSuggestionOperationId(operation.operation_id),
  });
  const modelEnabled = (cases.data?.items ?? []).some((item) => item.model_suggestions_enabled);
  const act = useMutation({
    mutationFn: (action: { caseId: string; path: string; body: unknown }) =>
      api<Case | { journal_id: string }>(`/v1/reconciliation-cases/${action.caseId}/${action.path}`, { body: action.body }),
    onSuccess: async (result, action) => {
      if (action.path === "journal" && "journal_id" in result) {
        navigate(`/app/journals/${result.journal_id}`);
        return;
      }
      await queryClient.invalidateQueries({ queryKey: ["cases", selectedBank] });
      await queryClient.invalidateQueries({ queryKey: ["bank-summary", selectedBank] });
    },
  });
  const failure = upload.error ?? act.error ?? requestSuggestions.error;
  const errorText = failure instanceof ApiError ? `${failure.title}. ${failure.message}` : failure ? "Falha na conciliação." : null;

  return (
    <section>
      <h1>Conciliação</h1>
      <p className="muted">O extrato vira casos. A sugestão não liga nada: um aprovador escolhe a linha do razão.</p>
      <div className="row">
        <label>
          Conta banco
          <select data-testid="bank-account-select" value={selectedBank} onChange={(event) => setBankAccountId(event.target.value)}>
            {(banks.data?.items ?? []).map((item) => (
              <option key={item.bank_account_id} value={item.bank_account_id}>
                {item.name} · {item.account_number_masked}
              </option>
            ))}
          </select>
        </label>
        <label>
          Estado
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">Todos</option>
            {["open", "suggested", "approved", "rejected", "reversed", "ignored"].map((value) => (
              <option key={value} value={value}>{STATUS_LABEL[value] ?? value}</option>
            ))}
          </select>
        </label>
      </div>
      {summary.data ? (
        <p>
          Saldo do razão {summary.data.ledger_balance} · saldo do último extrato {summary.data.statement_balance ?? "—"} · pendências{" "}
          {summary.data.pending_inflow_count} entradas ({summary.data.pending_inflow_total}) e {summary.data.pending_outflow_count} saídas ({summary.data.pending_outflow_total}) ·{" "}
          {summary.data.unmatched_ledger_count} linhas do razão sem vínculo ({summary.data.unmatched_ledger_total})
        </p>
      ) : null}
      {can(me.roles, "preparer", "approver", "admin") ? (
        <form
          className="row"
          onSubmit={(event) => {
            event.preventDefault();
            upload.mutate();
          }}
        >
          <label>
            Extrato
            <input data-testid="statement-file" type="file" accept=".csv,.ofx,text/csv,application/x-ofx" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          </label>
          <button type="submit" data-testid="import-statement">Enviar extrato</button>
        </form>
      ) : null}
      {modelEnabled && periodId && can(me.roles, "preparer", "approver", "admin") ? (
        <p className="row">
          <button
            type="button"
            data-testid="request-ai-suggestions"
            disabled={suggestionRunning || requestSuggestions.isPending}
            onClick={() => requestSuggestions.mutate()}
          >
            Pedir sugestão à IA
          </button>
          {suggestionRunning || requestSuggestions.isPending ? <span className="muted">Pedindo sugestões…</span> : null}
        </p>
      ) : null}
      {suggestionNotice ? (
        <p className={suggestionNotice.kind === "error" ? "error" : "muted"} data-testid="ai-suggestion-notice">
          {suggestionNotice.text}
        </p>
      ) : null}
      {statement.data?.status === "received" ? <p className="muted">Lendo extrato…</p> : null}
      {statement.data?.status === "failed" ? <p className="error">{statement.data.error_message}</p> : null}
      {errorText ? <p className="error">{errorText}</p> : null}
      {(cases.data?.items ?? []).map((item) => {
        const suggestions = item.counterpart_suggestions ?? [];
        const counterpart = chosenCounterparts[item.case_id] ?? suggestions[0]?.account_id ?? "";
        const selectedSuggestion = suggestions.find((suggestion) => suggestion.account_id === counterpart);
        return (
        <article key={item.case_id} data-testid="reconciliation-case">
          <p>
            <span className="badge" data-testid="case-status">{STATUS_LABEL[item.status] ?? item.status}</span>{" "}
            {item.bank_transaction.date} · {DIRECTION[item.bank_transaction.direction] ?? item.bank_transaction.direction} · {item.bank_transaction.amount}
          </p>
          <p>{item.bank_transaction.description}</p>
          {item.reason ? <p className="muted">{item.reason}</p> : null}
          {item.journal_id ? <p>Lançamento <Link to={`/app/journals/${item.journal_id}`}>{item.journal_id}</Link></p> : null}
          <ul>
            {item.candidates.map((candidate) => (
              <li key={candidate.candidate_id} data-testid="case-candidate">
                {candidate.score} · {candidate.explanation.join(" · ")}
                {can(me.roles, "approver", "admin") && (item.status === "open" || item.status === "suggested") ? (
                  <button type="button" data-testid="approve-case" onClick={() => act.mutate({ caseId: item.case_id, path: "approve", body: { candidate_id: candidate.candidate_id } })}>
                    Aprovar
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
          <div className="row">
            <input value={reason} placeholder="Motivo" onChange={(event) => setReason(event.target.value)} />
            {can(me.roles, "preparer", "approver", "admin") && ["open", "suggested", "rejected"].includes(item.status) ? (
              <>
                <button type="button" onClick={() => act.mutate({ caseId: item.case_id, path: "reject", body: { reason } })}>Rejeitar</button>
                <button type="button" onClick={() => act.mutate({ caseId: item.case_id, path: "ignore", body: { reason } })}>Ignorar</button>
              </>
            ) : null}
            {can(me.roles, "approver", "admin") && item.status === "approved" ? (
              <button type="button" onClick={() => act.mutate({ caseId: item.case_id, path: "reverse", body: { reason } })}>Reverter</button>
            ) : null}
            {can(me.roles, "preparer", "approver", "admin") && ["open", "rejected", "reversed"].includes(item.status) ? (
              <button type="button" onClick={() => act.mutate({ caseId: item.case_id, path: "resuggest", body: {} })}>Sugerir de novo</button>
            ) : null}
            {can(me.roles, "preparer", "admin") && !["approved", "ignored"].includes(item.status) ? (
              <>
                <select
                  value={counterpart}
                  onChange={(event) => setChosenCounterparts((current) => ({ ...current, [item.case_id]: event.target.value }))}
                >
                  <option value="">Contrapartida</option>
                  {counterparts.map((account) => (
                    <option key={account.account_id} value={account.account_id}>{account.code} {account.name}</option>
                  ))}
                </select>
                <button
                  type="button"
                  disabled={!counterpart}
                  onClick={() =>
                    act.mutate({
                      caseId: item.case_id,
                      path: "journal",
                      body: { counterpart_account_id: counterpart, ...chosenOrigin(suggestions, counterpart) },
                    })
                  }
                >
                  Criar lançamento
                </button>
              </>
            ) : null}
          </div>
          {selectedSuggestion && !["approved", "ignored"].includes(item.status) ? (
            <p className="muted" data-testid="counterpart-suggestion" title={selectedSuggestion.justification}>
              {suggestionLabel(selectedSuggestion)}
            </p>
          ) : null}
        </article>
        );
      })}
    </section>
  );
}
