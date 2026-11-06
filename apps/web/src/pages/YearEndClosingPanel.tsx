import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api } from "../api";
import { can, useSession } from "../session";

type Account = { account_id: string; code: string; name: string; account_type: string; postable: boolean; active: boolean };
type Closing = { journal: { journal_id: string } };

// Aparece no balancete de dezembro. Gera só o rascunho: outro usuário aprova e publica.
export function YearEndClosingPanel({ fiscalYear }: { fiscalYear: number }) {
  const { me, entityId } = useSession();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const allowed = can(me.roles, "preparer", "admin");
  const accounts = useQuery({
    queryKey: ["accounts", entityId],
    enabled: allowed && Boolean(entityId),
    queryFn: () => api<{ items: Account[] }>(`/v1/legal-entities/${entityId}/accounts`),
  });
  const equity = useMemo(
    () => (accounts.data?.items ?? []).filter((item) => item.account_type === "equity" && item.postable && item.active),
    [accounts.data],
  );
  const [accountId, setAccountId] = useState("");
  useEffect(() => {
    if (!accountId && equity.length > 0) {
      setAccountId((equity.find((item) => item.code === "3.2.01") ?? equity[0]).account_id);
    }
  }, [accountId, equity]);

  const close = useMutation({
    mutationFn: () =>
      api<Closing>(`/v1/legal-entities/${entityId}/year-end-closing`, {
        body: { fiscal_year: fiscalYear, retained_earnings_account_id: accountId },
      }),
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({ queryKey: ["journals", entityId] });
      navigate(`/app/journals/${created.journal.journal_id}`);
    },
  });

  if (!allowed) {
    return null;
  }
  const error = close.error instanceof ApiError ? close.error.message : close.error ? "Não foi possível gerar o encerramento." : "";

  return (
    <section className="panel report-closing" data-testid="year-end-closing">
      <div>
        <span className="eyebrow">Encerramento do exercício {fiscalYear}</span>
        <h2 className="report-title">Zerar receitas e despesas</h2>
        <p>
          O sistema monta um rascunho em 31/12 que leva o saldo das contas de resultado para a conta do patrimônio líquido escolhida.
          Nada é publicado agora: outro usuário revisa, aprova e publica. Depois disso, janeiro abre com o resultado no PL.
        </p>
      </div>
      <div className="report-closing__form">
        <label>
          <span>Conta de lucros ou prejuízos acumulados</span>
          <select value={accountId} onChange={(event) => setAccountId(event.target.value)} disabled={equity.length === 0}>
            {equity.map((item) => (
              <option key={item.account_id} value={item.account_id}>{item.code} {item.name}</option>
            ))}
          </select>
        </label>
        <button type="button" className="button" disabled={!accountId || close.isPending} onClick={() => close.mutate()}>
          {close.isPending ? "Gerando…" : "Gerar rascunho do encerramento"}
        </button>
      </div>
      {equity.length === 0 && accounts.data ? (
        <p className="muted">A empresa não tem conta do patrimônio líquido que receba lançamento. Crie uma em Plano de contas.</p>
      ) : null}
      {error ? <p className="error" role="alert">{error}</p> : null}
    </section>
  );
}
