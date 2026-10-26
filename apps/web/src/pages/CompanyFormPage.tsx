import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api } from "../api";
import { useSession } from "../session";

const ENTITY_KEY = "contabil.entity";

export function CompanyFormPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { setEntityId } = useSession();
  const [name, setName] = useState("");
  const [cnpj, setCnpj] = useState("");
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const create = useMutation({
    mutationFn: () =>
      api<{ legal_entity_id: string }>("/v1/legal-entities", {
        body: { name, cnpj, fiscal_year: Number(year) },
      }),
    onSuccess: async (created) => {
      sessionStorage.setItem(ENTITY_KEY, created.legal_entity_id);
      setEntityId(created.legal_entity_id);
      await queryClient.invalidateQueries({ queryKey: ["entities"] });
      navigate("/app/accounts");
    },
  });

  return (
    <main className="content">
      <section className="panel">
        <h1>Cadastrar empresa</h1>
        <p className="muted">Use dados fictícios. O piloto guarda o cadastro nos Estados Unidos.</p>
        <form
          className="row"
          onSubmit={(event) => {
            event.preventDefault();
            create.mutate();
          }}
        >
          <label>
            Nome
            <input data-testid="company-name" value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label>
            CNPJ
            <input data-testid="company-cnpj" value={cnpj} onChange={(event) => setCnpj(event.target.value)} />
          </label>
          <label>
            Ano
            <input data-testid="company-year" value={year} onChange={(event) => setYear(event.target.value)} inputMode="numeric" />
          </label>
          <button type="submit" data-testid="save-company" disabled={!name.trim() || !cnpj.trim() || create.isPending}>
            Cadastrar
          </button>
        </form>
        {create.isError ? (
          <p className="error">{create.error instanceof ApiError ? create.error.message : "Falha ao cadastrar a empresa."}</p>
        ) : null}
      </section>
    </main>
  );
}
