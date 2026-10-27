import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api } from "../api";
import { addAmounts, parseAmount } from "../money";
import { useSession } from "../session";

type Account = { account_id: string; code: string; name: string; postable: boolean; active: boolean };
type Period = { period_id: string; start_date: string; status: string };
type DraftLine = { accountId: string; side: "debit" | "credit"; amount: string; description: string };

const emptyLine = (side: "debit" | "credit"): DraftLine => ({ accountId: "", side, amount: "", description: "Linha" });

export function JournalFormPage() {
  const { entityId, periodId, setPeriodId } = useSession();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const accounts = useQuery({
    queryKey: ["accounts", entityId],
    queryFn: () => api<{ items: Account[] }>(`/v1/legal-entities/${entityId}/accounts`),
  });
  const periods = useQuery({
    queryKey: ["periods", entityId],
    queryFn: () => api<{ items: Period[] }>(`/v1/legal-entities/${entityId}/periods`),
  });
  const openPeriods = (periods.data?.items ?? []).filter((period) => period.status === "open" || period.status === "reopened");
  const postable = (accounts.data?.items ?? []).filter((account) => account.postable && account.active);
  const [entryDate, setEntryDate] = useState("");
  const [description, setDescription] = useState("");
  const [lines, setLines] = useState<DraftLine[]>([emptyLine("debit"), emptyLine("credit")]);

  const activePeriodId = openPeriods.some((period) => period.period_id === periodId) ? periodId : "";
  const selectedPeriod = openPeriods.find((period) => period.period_id === activePeriodId);
  const activeDate = entryDate || selectedPeriod?.start_date || "";
  const debit = addAmounts(lines.filter((line) => line.side === "debit").map((line) => line.amount));
  const credit = addAmounts(lines.filter((line) => line.side === "credit").map((line) => line.amount));
  const balanced = useMemo(() => {
    if (!description.trim() || !activePeriodId || !activeDate) {
      return false;
    }
    if (lines.some((line) => !line.accountId || !line.description.trim() || parseAmount(line.amount) === null)) {
      return false;
    }
    return debit === credit;
  }, [activeDate, activePeriodId, credit, debit, description, lines]);

  const save = useMutation({
    mutationFn: () =>
      api<{ journal_id: string }>("/v1/journals", {
        body: {
          legal_entity_id: entityId,
          period_id: activePeriodId,
          currency: "BRL",
          entry_date: activeDate,
          description,
          source_type: "manual",
          lines: lines.map((line) => ({
            account_id: line.accountId,
            side: line.side,
            amount: line.amount.trim(),
            description: line.description,
            dimension_values: {},
          })),
        },
      }),
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({ queryKey: ["journals", entityId] });
      navigate(`/app/journals/${created.journal_id}`);
    },
  });

  function updateLine(index: number, patch: Partial<DraftLine>) {
    setLines((current) => current.map((line, lineIndex) => (lineIndex === index ? { ...line, ...patch } : line)));
  }

  return (
    <section>
      <h1>Novo lançamento</h1>
      <div className="row">
        <label>
          Período
          <select data-testid="period-select" value={activePeriodId} onChange={(event) => { setPeriodId(event.target.value); setEntryDate(""); }}>
            {openPeriods.map((period) => (
              <option key={period.period_id} value={period.period_id}>{period.period_id}</option>
            ))}
          </select>
        </label>
        <label>
          Data
          <input data-testid="entry-date" type="date" value={activeDate} onChange={(event) => setEntryDate(event.target.value)} />
        </label>
        <label>
          Descrição
          <input data-testid="journal-description" value={description} onChange={(event) => setDescription(event.target.value)} />
        </label>
      </div>
      <div className="lines">
        {lines.map((line, index) => (
          <div className="row" key={index}>
            <label>
              Conta
              <select data-testid={`line-account-${index}`} value={line.accountId} onChange={(event) => updateLine(index, { accountId: event.target.value })}>
                <option value="">Selecione</option>
                {postable.map((account) => (
                  <option key={account.account_id} value={account.account_id}>{account.code} {account.name}</option>
                ))}
              </select>
            </label>
            <label>
              Lado
              <select data-testid={`line-side-${index}`} value={line.side} onChange={(event) => updateLine(index, { side: event.target.value as DraftLine["side"] })}>
                <option value="debit">Débito</option>
                <option value="credit">Crédito</option>
              </select>
            </label>
            <label>
              Valor
              <input data-testid={`line-amount-${index}`} value={line.amount} inputMode="decimal" onChange={(event) => updateLine(index, { amount: event.target.value })} />
            </label>
            <label>
              Histórico
              <input value={line.description} onChange={(event) => updateLine(index, { description: event.target.value })} />
            </label>
          </div>
        ))}
      </div>
      <p className="totals" data-testid="journal-totals">Débitos {debit} · Créditos {credit}</p>
      {save.isError ? <p className="error">{save.error instanceof ApiError ? `${save.error.title}. ${save.error.message}` : "Falha ao salvar."}</p> : null}
      <div className="actions">
        <button type="button" className="secondary" onClick={() => setLines((current) => [...current, emptyLine("debit")])}>Adicionar linha</button>
        <button type="button" data-testid="save-journal" disabled={!balanced || save.isPending} onClick={() => save.mutate()}>
          Salvar rascunho
        </button>
      </div>
    </section>
  );
}
