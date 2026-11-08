import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, api } from "../api";
import { formatCnpj, formatDate } from "../format";
import { can, useSession } from "../session";
import { LEGAL_REP_ROLES } from "./signatories";

type AccountantOption = {
  user_id: string;
  display_name: string;
  crc: string;
  crc_category: string;
  eligible: boolean;
  regularity_valid_until: string | null;
};
type EntitySignatories = {
  legal_entity_id: string;
  accountant: { user_id: string; name: string; crc: string; caption: string; regularity_number: string | null; regularity_valid_until: string | null } | null;
  legal_representative: { name: string; cpf: string | null; role: string | null; caption: string } | null;
  updated_at: string | null;
  accountant_options?: AccountantOption[];
};

export function CompanySignatoriesPage() {
  const { id = "" } = useParams();
  const { me, entities } = useSession();
  const entity = entities.find((item) => item.legal_entity_id === id);
  const admin = can(me.roles, "admin");
  const current = useQuery({
    queryKey: ["signatories", id],
    enabled: admin && Boolean(id),
    queryFn: () => api<EntitySignatories>(`/v1/legal-entities/${id}/signatories`),
  });

  return (
    <>
      <section className="page-header">
        <div>
          <span className="eyebrow">Governança · {entity ? `${entity.name} · CNPJ ${formatCnpj(entity.cnpj)}` : "Empresa"}</span>
          <h1>Assinaturas das demonstrações</h1>
          <p>
            O contador responsável e o representante legal assinam a DRE e o Balanço. O contador é alguém do escritório com CRC de contador
            cadastrado no próprio perfil. O CPF do representante não sai na demonstração.
          </p>
        </div>
      </section>
      {!admin ? (
        <section className="panel">
          <p className="muted">Só o admin do escritório define quem assina pela empresa.</p>
        </section>
      ) : current.isError ? (
        <section className="panel">
          <p className="error">{current.error instanceof ApiError ? current.error.message : "Não foi possível ler os signatários."}</p>
        </section>
      ) : current.data ? (
        <SignatoriesForm data={current.data} entityId={id} />
      ) : (
        <section className="panel"><p className="muted">Carregando…</p></section>
      )}
    </>
  );
}

// Monta depois da leitura; os campos começam com o que já está salvo.
function SignatoriesForm({ data, entityId }: { data: EntitySignatories; entityId: string }) {
  const queryClient = useQueryClient();
  const options = data.accountant_options ?? [];
  const [accountant, setAccountant] = useState(data.accountant?.user_id ?? "");
  const [repName, setRepName] = useState(data.legal_representative?.name ?? "");
  const [repCpf, setRepCpf] = useState(data.legal_representative?.cpf ?? "");
  const [repRole, setRepRole] = useState(data.legal_representative?.role ?? "socio_administrador");
  const [notice, setNotice] = useState("");
  const save = useMutation({
    mutationFn: () =>
      api<EntitySignatories>(`/v1/legal-entities/${entityId}/signatories`, {
        method: "PUT",
        body: {
          accountant_user_id: accountant || null,
          legal_rep_name: repName.trim() || null,
          legal_rep_cpf: repName.trim() ? repCpf : null,
          legal_rep_role: repName.trim() ? repRole : null,
        },
      }),
    onSuccess: async (saved) => {
      setNotice(
        saved.accountant
          ? `Salvo. A DRE e o Balanço passam a sair com ${saved.accountant.name} — ${saved.accountant.caption}.`
          : "Salvo. A empresa está sem responsável técnico; a impressão sai com a linha de assinatura em branco.",
      );
      await queryClient.invalidateQueries({ queryKey: ["signatories", entityId] });
      await queryClient.invalidateQueries({ queryKey: ["income-statement", entityId] });
      await queryClient.invalidateQueries({ queryKey: ["balance-sheet", entityId] });
    },
  });
  const chosen = options.find((option) => option.user_id === accountant);

  return (
    <section className="panel">
      <form
        className="signatories-form"
        onSubmit={(event) => {
          event.preventDefault();
          setNotice("");
          save.mutate();
        }}
      >
        <fieldset className="row">
          <legend>Responsável técnico</legend>
          <label>
            Contador
            <select data-testid="signatories-accountant" value={accountant} onChange={(event) => setAccountant(event.target.value)}>
              <option value="">Nenhum</option>
              {options.map((option) => (
                <option key={option.user_id} value={option.user_id} disabled={!option.eligible}>
                  {option.display_name} — {option.crc}{option.eligible ? "" : " (técnico, não assina)"}
                </option>
              ))}
            </select>
          </label>
          {chosen?.regularity_valid_until ? (
            <p className="muted">Certidão de regularidade válida até {formatDate(chosen.regularity_valid_until)}.</p>
          ) : chosen ? (
            <p className="muted">Sem certidão de regularidade informada no perfil.</p>
          ) : null}
        </fieldset>
        {options.length === 0 ? (
          <p className="muted" data-testid="signatories-no-options">
            Ninguém do escritório cadastrou o CRC ainda. Cada contador cadastra o próprio em <Link to="/app/rastro/perfil">Perfil</Link>.
          </p>
        ) : null}
        <fieldset className="row">
          <legend>Representante legal</legend>
          <label>
            Nome
            <input data-testid="signatories-rep-name" value={repName} onChange={(event) => setRepName(event.target.value)} />
          </label>
          <label>
            CPF
            <input data-testid="signatories-rep-cpf" value={repCpf} inputMode="numeric" autoComplete="off" onChange={(event) => setRepCpf(event.target.value)} />
          </label>
          <label>
            Cargo
            <select data-testid="signatories-rep-role" value={repRole} onChange={(event) => setRepRole(event.target.value)}>
              {LEGAL_REP_ROLES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
        </fieldset>
        <div className="actions">
          <button type="submit" data-testid="signatories-save" disabled={save.isPending}>Salvar assinaturas</button>
          <Link to="/app/rastro/administracao">Voltar para Administração</Link>
        </div>
      </form>
      {notice ? <p className="ok" data-testid="signatories-notice">{notice}</p> : null}
      {save.isError ? <p className="error">{save.error instanceof ApiError ? save.error.message : "Falha ao salvar as assinaturas."}</p> : null}
    </section>
  );
}
