import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";
import { STATUS_LABEL, can, useSession } from "../session";

type Journal = {
  journal_id: string;
  description: string;
  entry_date: string;
  status: string;
};

export function OfficeHome() {
  const { me, entities, entityId } = useSession();
  const company = entities.find((item) => item.legal_entity_id === entityId);
  const journals = useQuery({
    queryKey: ["journals", entityId, "home"],
    enabled: Boolean(entityId),
    queryFn: () => api<{ items: Journal[] }>(`/v1/journals?legal_entity_id=${entityId}&limit=8`),
  });

  if (!company) {
    return (
      <section className="page-header">
        <div>
          <span className="eyebrow">{me.tenant_name}</span>
          <h1>O escritório ainda não tem empresa.</h1>
          <p>Cadastre uma empresa fictícia para ver lançamentos, plano e períodos nesta sala.</p>
        </div>
        {can(me.roles, "admin") ? (
          <div className="page-header__action">
            <Link className="button" to="/app/companies/new">Cadastrar empresa</Link>
          </div>
        ) : (
          <p>Peça ao administrador para cadastrar a empresa.</p>
        )}
      </section>
    );
  }

  const items = journals.data?.items ?? [];
  return (
    <>
      <section className="page-header">
        <div>
          <span className="eyebrow">{company.name}</span>
          <h1>O que esta empresa tem no razão.</h1>
          <p>A empresa e a competência da barra valem para lançamentos, balancete, plano, bancos e períodos.</p>
        </div>
        <div className="page-header__action">
          <Link className="button" to="/app/rastro/ledger">Abrir lançamentos</Link>
        </div>
      </section>
      <section className="panel panel--flush">
        <div className="table-toolbar">
          <span className="eyebrow">Lançamentos recentes</span>
          <span className="table-count">{journals.isLoading ? "Carregando" : `${items.length} nesta lista`}</span>
        </div>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr><th>Data</th><th>Descrição</th><th>Estado</th></tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr><td colSpan={3}>Nenhum lançamento nesta empresa.</td></tr>
              ) : items.map((journal) => (
                <tr key={journal.journal_id}>
                  <td>{journal.entry_date}</td>
                  <td><Link to={`/app/journals/${journal.journal_id}`}>{journal.description}</Link></td>
                  <td>{STATUS_LABEL[journal.status] ?? journal.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

const routines = [
  ["/app/journals/new", "Novo lançamento", "Cria um rascunho equilibrado na empresa da barra."],
  ["/app/trial-balance", "Balancete", "Saldos da competência escolhida."],
  ["/app/accounts", "Plano de contas", "Modelo mínimo e contas da empresa."],
  ["/app/banks", "Bancos", "Conta corrente ligada ao plano."],
  ["/app/audit", "Auditoria", "Eventos do escritório."],
] as const;

export function RoutinesPage() {
  const { me } = useSession();
  return (
    <>
      <section className="page-header">
        <div>
          <span className="eyebrow">Sistema</span>
          <h1>Rotinas do razão</h1>
          <p>Estas rotinas ficam na mesma sala. A empresa continua a da barra de contexto.</p>
        </div>
      </section>
      <section className="evidence-grid">
        {routines.map(([to, title, detail]) => (
          <article className="panel evidence-card" key={to}>
            <div className="evidence-card__content">
              <h2>{title}</h2>
              <p>{detail}</p>
              <Link className="inline-action" to={to}>Abrir →</Link>
            </div>
          </article>
        ))}
        {can(me.roles, "admin") ? (
          <article className="panel evidence-card">
            <div className="evidence-card__content">
              <h2>Nova empresa</h2>
              <p>Cadastro fictício, com matriz, plano mínimo e doze períodos.</p>
              <Link className="inline-action" to="/app/companies/new">Cadastrar →</Link>
            </div>
          </article>
        ) : null}
      </section>
    </>
  );
}

export function PlannedPage({ title, detail }: { title: string; detail: string }) {
  return (
    <section className="page-header">
      <div>
        <span className="eyebrow">Sem contrato nesta versão</span>
        <h1>{title}</h1>
        <p>{detail}</p>
      </div>
    </section>
  );
}
