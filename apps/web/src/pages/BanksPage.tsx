import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, api } from "../api";
import { can, useSession } from "../session";

type Account = { account_id: string; code: string; name: string; account_type: string; postable: boolean; active: boolean };
type BankAccount = {
  bank_account_id: string;
  account_id: string;
  name: string;
  bank_code: string;
  branch: string;
  account_number_masked: string;
  currency: string;
  active: boolean;
};

export function BanksPage() {
  const { entityId, me } = useSession();
  const queryClient = useQueryClient();
  const accounts = useQuery({
    queryKey: ["accounts", entityId],
    queryFn: () => api<{ items: Account[] }>(`/v1/legal-entities/${entityId}/accounts`),
  });
  const banks = useQuery({
    queryKey: ["bank-accounts", entityId],
    queryFn: () => api<{ items: BankAccount[] }>(`/v1/bank-accounts?legal_entity_id=${entityId}`),
  });
  const assets = (accounts.data?.items ?? []).filter((account) => account.postable && account.active && account.account_type === "asset");
  const [accountId, setAccountId] = useState("");
  const [name, setName] = useState("");
  const [bankCode, setBankCode] = useState("");
  const [branch, setBranch] = useState("");
  const [last4, setLast4] = useState("");
  const create = useMutation({
    mutationFn: () =>
      api("/v1/bank-accounts", {
        body: {
          legal_entity_id: entityId,
          account_id: accountId,
          name,
          bank_code: bankCode,
          branch,
          account_number_masked: last4,
        },
      }),
    onSuccess: async () => {
      setName("");
      setLast4("");
      await queryClient.invalidateQueries({ queryKey: ["bank-accounts", entityId] });
    },
  });
  const errorText = create.isError ? (create.error instanceof ApiError ? `${create.error.title}. ${create.error.message}` : "Falha ao cadastrar.") : null;

  return (
    <section>
      <h1>Bancos</h1>
      <p className="muted">A conta banco aponta para um ativo do razão. Só os quatro últimos dígitos ficam guardados.</p>
      {can(me.roles, "preparer", "approver", "admin") ? (
        <form
          className="row"
          onSubmit={(event) => {
            event.preventDefault();
            create.mutate();
          }}
        >
          <label>
            Conta do razão
            <select data-testid="bank-ledger-account" value={accountId} onChange={(event) => setAccountId(event.target.value)}>
              <option value="">Selecione</option>
              {assets.map((account) => (
                <option key={account.account_id} value={account.account_id}>
                  {account.code} {account.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Nome
            <input data-testid="bank-name" value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label>
            Banco
            <input data-testid="bank-code" value={bankCode} onChange={(event) => setBankCode(event.target.value)} />
          </label>
          <label>
            Agência
            <input data-testid="bank-branch" value={branch} onChange={(event) => setBranch(event.target.value)} />
          </label>
          <label>
            Final
            <input data-testid="bank-last4" value={last4} inputMode="numeric" maxLength={4} onChange={(event) => setLast4(event.target.value)} />
          </label>
          <button type="submit" data-testid="save-bank-account">Cadastrar</button>
        </form>
      ) : null}
      {errorText ? <p className="error">{errorText}</p> : null}
      <table>
        <thead>
          <tr><th>Nome</th><th>Banco</th><th>Agência</th><th>Final</th><th>Moeda</th></tr>
        </thead>
        <tbody>
          {(banks.data?.items ?? []).map((account) => (
            <tr key={account.bank_account_id}>
              <td>{account.name}</td>
              <td>{account.bank_code}</td>
              <td>{account.branch}</td>
              <td>{account.account_number_masked}</td>
              <td>{account.currency}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
