import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, api } from "../api";
import { can, useSession } from "../session";

type Account = {
  account_id: string;
  code: string;
  name: string;
  account_type: string;
  postable: boolean;
  active: boolean;
};

export function AccountsPage() {
  const { entityId, me } = useSession();
  const queryClient = useQueryClient();
  const accounts = useQuery({
    queryKey: ["accounts", entityId],
    queryFn: () => api<{ items: Account[] }>(`/v1/legal-entities/${entityId}/accounts`),
  });
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [accountType, setAccountType] = useState("expense");
  const [postable, setPostable] = useState(true);
  const create = useMutation({
    mutationFn: () =>
      api(`/v1/legal-entities/${entityId}/accounts`, {
        body: { code, name, account_type: accountType, postable, parent_id: null },
      }),
    onSuccess: async () => {
      setCode("");
      setName("");
      await queryClient.invalidateQueries({ queryKey: ["accounts", entityId] });
    },
  });

  return (
    <section>
      <h1>Plano de contas</h1>
      {can(me.roles, "preparer", "admin") ? (
        <form className="row" onSubmit={(event) => { event.preventDefault(); create.mutate(); }}>
          <label>Código<input value={code} onChange={(event) => setCode(event.target.value)} /></label>
          <label>Nome<input value={name} onChange={(event) => setName(event.target.value)} /></label>
          <label>
            Tipo
            <select value={accountType} onChange={(event) => setAccountType(event.target.value)}>
              <option value="asset">Ativo</option>
              <option value="liability">Passivo</option>
              <option value="equity">Patrimônio</option>
              <option value="revenue">Receita</option>
              <option value="expense">Despesa</option>
            </select>
          </label>
          <label>Postável<input type="checkbox" checked={postable} onChange={(event) => setPostable(event.target.checked)} /></label>
          <button type="submit" disabled={!code || !name || create.isPending}>Criar conta</button>
        </form>
      ) : null}
      {create.isError ? <p className="error">{create.error instanceof ApiError ? create.error.message : "Falha ao criar conta."}</p> : null}
      <table>
        <thead><tr><th>Código</th><th>Nome</th><th>Tipo</th><th>Postável</th></tr></thead>
        <tbody>
          {(accounts.data?.items ?? []).map((account) => (
            <tr key={account.account_id}>
              <td>{account.code}</td>
              <td>{account.name}</td>
              <td>{account.account_type}</td>
              <td>{account.postable ? "Sim" : "Não"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
