import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, api } from "../api";
import { can, useSession } from "../session";

type Member = { user_id: string; display_name: string; roles: string[]; legal_entity_id?: string };

const ROLE_OPTIONS = [
  ["preparer", "Prepara"],
  ["approver", "Aprova"],
  ["admin", "Administra"],
  ["viewer", "Consulta"],
  ["client", "Cliente"],
] as const;

export function AdministrationPage() {
  const { me } = useSession();
  const admin = can(me.roles, "admin");
  if (!admin) {
    return (
      <section className="page-header">
        <div>
          <span className="eyebrow">Governança</span>
          <h1>Administração</h1>
          <p>Só o admin convida alguém para o escritório.</p>
        </div>
      </section>
    );
  }
  return <InviteOffice />;
}

function InviteOffice() {
  const { entities } = useSession();
  const queryClient = useQueryClient();
  const members = useQuery({
    queryKey: ["users"],
    queryFn: () => api<{ items: Member[] }>("/v1/users"),
  });
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [roles, setRoles] = useState<string[]>(["viewer"]);
  const [legalEntityId, setLegalEntityId] = useState("");
  const [notice, setNotice] = useState("");
  const invite = useMutation({
    mutationFn: () =>
      api<{ user_id: string }>("/v1/users", {
        body: {
          username,
          display_name: displayName,
          email,
          roles,
          ...(roles.includes("client") ? { legal_entity_id: legalEntityId } : {}),
        },
      }),
    onSuccess: async () => {
      setUsername("");
      setDisplayName("");
      setEmail("");
      setRoles(["viewer"]);
      setLegalEntityId("");
      setNotice("Convite enviado para o e-mail. A pessoa troca a senha no primeiro acesso.");
      await queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });

  function toggleRole(role: string) {
    setRoles((current) => {
      if (role === "client") {
        return current.includes("client") ? [] : ["client"];
      }
      const withoutClient = current.filter((item) => item !== "client");
      return withoutClient.includes(role) ? withoutClient.filter((item) => item !== role) : [...withoutClient, role];
    });
  }

  const errorText = invite.isError
    ? invite.error instanceof ApiError
      ? invite.error.message
      : "Falha ao convidar."
    : members.isError
      ? members.error instanceof ApiError
        ? members.error.message
        : "Falha ao listar o escritório."
      : "";

  return (
    <>
      <section className="page-header">
        <div>
          <span className="eyebrow">Governança</span>
          <h1>Administração</h1>
          <p>O convite sai por e-mail, com uma senha temporária. O cliente fica ligado a uma empresa e não abre a sala do escritório. Esta tela não mostra a senha.</p>
        </div>
      </section>
      <section className="panel">
        <h2>Convidar</h2>
        <form
          className="row"
          onSubmit={(event) => {
            event.preventDefault();
            setNotice("");
            invite.mutate();
          }}
        >
          <label>
            Nome de usuário
            <input data-testid="invite-username" value={username} onChange={(event) => setUsername(event.target.value)} />
          </label>
          <label>
            Nome de exibição
            <input data-testid="invite-display-name" value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
          </label>
          <label>
            E-mail
            <input data-testid="invite-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
          </label>
          <fieldset className="row">
            <legend>Papéis</legend>
            {ROLE_OPTIONS.map(([role, label]) => (
              <label key={role}>
                <input
                  type="checkbox"
                  data-testid={`invite-role-${role}`}
                  checked={roles.includes(role)}
                  onChange={() => toggleRole(role)}
                />
                {label}
              </label>
            ))}
          </fieldset>
          {roles.includes("client") ? (
            <label>
              Empresa
              <select value={legalEntityId} onChange={(event) => setLegalEntityId(event.target.value)} required>
                <option value="">Escolha a empresa</option>
                {entities.map((entity) => (
                  <option key={entity.legal_entity_id} value={entity.legal_entity_id}>{entity.name}</option>
                ))}
              </select>
            </label>
          ) : null}
          <button type="submit" data-testid="invite-user" disabled={!username.trim() || !displayName.trim() || !email.trim() || roles.length === 0 || (roles.includes("client") && !legalEntityId) || invite.isPending}>
            Enviar convite
          </button>
        </form>
        {notice ? <p className="ok" data-testid="invite-notice">{notice}</p> : null}
        {errorText ? <p className="error">{errorText}</p> : null}
      </section>
      <section className="panel panel--flush">
        <div className="table-toolbar">
          <span className="eyebrow">Escritório</span>
          <span className="table-count">{members.data?.items.length ?? 0} pessoas</span>
        </div>
        <div className="table-scroll">
          <table className="data-table" data-testid="user-list">
            <thead>
              <tr><th>Nome</th><th>Usuário</th><th>Papéis</th><th>Empresa</th></tr>
            </thead>
            <tbody>
              {(members.data?.items ?? []).map((member) => (
                <tr key={member.user_id}>
                  <td>{member.display_name}</td>
                  <td>{member.user_id}</td>
                  <td>{member.roles.join(", ")}</td>
                  <td>{member.legal_entity_id ? entities.find((entity) => entity.legal_entity_id === member.legal_entity_id)?.name ?? member.legal_entity_id : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
