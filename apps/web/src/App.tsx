import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { ApiError, api } from "./api";
import { userManager } from "./auth";
import { AccountsPage } from "./pages/AccountsPage";
import { AuditPage } from "./pages/AuditPage";
import { BanksPage } from "./pages/BanksPage";
import { ReconciliationPage } from "./pages/ReconciliationPage";
import { JournalDetailPage } from "./pages/JournalDetailPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { ImportDetailPage, ImportsPage } from "./pages/ImportsPage";
import { JournalFormPage } from "./pages/JournalFormPage";
import { JournalsPage } from "./pages/JournalsPage";
import { PeriodsPage } from "./pages/PeriodsPage";
import { TrialBalancePage } from "./pages/TrialBalancePage";
import { Entity, Me, SessionProvider } from "./session";

const ENTITY_KEY = "contabil.entity";

export function App() {
  const [ready, setReady] = useState(false);
  const [signedIn, setSignedIn] = useState(false);

  useEffect(() => {
    userManager.getUser().then((user) => {
      setSignedIn(Boolean(user && !user.expired));
      setReady(true);
    });
  }, []);

  if (!ready) {
    return <p className="muted">Carregando sessão…</p>;
  }
  if (!signedIn) {
    return (
      <main className="login">
        <section>
          <p className="muted">Fundação local</p>
          <h1>Fechar com evidência</h1>
          <p>O razão, a aprovação e a trilha desta fase rodam neste ambiente. Entre com um usuário de demonstração.</p>
          <button type="button" data-testid="login-button" onClick={() => void userManager.signinRedirect()}>
            Entrar
          </button>
        </section>
      </main>
    );
  }
  return <Shell />;
}

function Shell() {
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/v1/me") });
  const entities = useQuery({ queryKey: ["entities"], queryFn: () => api<{ items: Entity[] }>("/v1/legal-entities") });
  const [entityId, setEntityId] = useState(() => sessionStorage.getItem(ENTITY_KEY) ?? "");

  useEffect(() => {
    const items = entities.data?.items ?? [];
    if (items.length === 0) {
      return;
    }
    if (!items.some((item) => item.legal_entity_id === entityId)) {
      setEntityId(items[0].legal_entity_id);
    }
  }, [entities.data, entityId]);

  useEffect(() => {
    if (entityId) {
      sessionStorage.setItem(ENTITY_KEY, entityId);
    }
  }, [entityId]);

  if (me.isError || entities.isError) {
    const error = me.error ?? entities.error;
    const detail = error instanceof ApiError ? error.message : "Não foi possível carregar o escritório.";
    return <p className="error">{detail}</p>;
  }
  if (me.isLoading || entities.isLoading || !me.data || !entities.data) {
    return <p className="muted">Carregando escritório…</p>;
  }
  if (entities.data.items.length === 0) {
    return <p className="muted">O escritório {me.data.tenant_name} ainda não tem empresa.</p>;
  }
  if (!entityId) {
    return <p className="muted">Carregando escritório…</p>;
  }

  return (
    <SessionProvider value={{ me: me.data, entities: entities.data?.items ?? [], entityId, setEntityId }}>
      <div className="shell">
        <header className="topbar">
          <div>
            <div className="brand">Contabilidade</div>
            <div className="muted">{me.data.tenant_name} · {me.data.display_name}</div>
          </div>
          <label>
            Empresa
            <select data-testid="entity-select" value={entityId} onChange={(event) => setEntityId(event.target.value)}>
              {(entities.data?.items ?? []).map((entity) => (
                <option key={entity.legal_entity_id} value={entity.legal_entity_id}>
                  {entity.name}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="secondary" onClick={() => void userManager.signoutRedirect()}>
            Sair
          </button>
        </header>
        <nav className="nav">
          <NavLink to="/app/journals" end>Lançamentos</NavLink>
          <NavLink to="/app/journals/new">Novo lançamento</NavLink>
          <NavLink to="/app/trial-balance">Balancete</NavLink>
          <NavLink to="/app/accounts">Plano de contas</NavLink>
          <NavLink to="/app/documents">Documentos</NavLink>
          <NavLink to="/app/banks">Bancos</NavLink>
          <NavLink to="/app/reconciliation">Conciliação</NavLink>
          <NavLink to="/app/imports">Importação</NavLink>
          <NavLink to="/app/periods">Períodos</NavLink>
          <NavLink to="/app/audit">Auditoria</NavLink>
        </nav>
        <main className="content">
          <Routes>
            <Route path="/app/journals/new" element={<JournalFormPage />} />
            <Route path="/app/journals/:journalId" element={<JournalDetailPage />} />
            <Route path="/app/journals" element={<JournalsPage />} />
            <Route path="/app/trial-balance" element={<TrialBalancePage />} />
            <Route path="/app/accounts" element={<AccountsPage />} />
            <Route path="/app/documents" element={<DocumentsPage />} />
            <Route path="/app/banks" element={<BanksPage />} />
            <Route path="/app/reconciliation" element={<ReconciliationPage />} />
            <Route path="/app/imports/:batchId" element={<ImportDetailPage />} />
            <Route path="/app/imports" element={<ImportsPage />} />
            <Route path="/app/periods" element={<PeriodsPage />} />
            <Route path="/app/audit" element={<AuditPage />} />
            <Route path="*" element={<JournalsPage />} />
          </Routes>
        </main>
      </div>
    </SessionProvider>
  );
}
