import { useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from "react";
import { NavLink, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";
import { userManager } from "../auth";
import { AccountsPage } from "../pages/AccountsPage";
import { AdministrationPage } from "../pages/AdministrationPage";
import { AuditPage } from "../pages/AuditPage";
import { BanksPage } from "../pages/BanksPage";
import { CloseRunPage } from "../pages/CloseRunPage";
import { CompanyFormPage } from "../pages/CompanyFormPage";
import { DocumentRequestsPage } from "../pages/DocumentRequestsPage";
import { DocumentsPage } from "../pages/DocumentsPage";
import { ImportDetailPage, ImportsPage } from "../pages/ImportsPage";
import { JournalDetailPage } from "../pages/JournalDetailPage";
import { JournalFormPage } from "../pages/JournalFormPage";
import { JournalsPage } from "../pages/JournalsPage";
import { PeriodsPage } from "../pages/PeriodsPage";
import { ReconciliationPage as LedgerReconciliationPage } from "../pages/ReconciliationPage";
import { TrialBalancePage } from "../pages/TrialBalancePage";
import { useSession } from "../session";
import { focusCompanySearch } from "./CompanySearch";
import { LiveContextBar } from "./LiveSurface";
import { OfficeHome, PlannedPage, RoutinesPage } from "./OfficeHome";
import "./rastro.css";
import { rastroDemoEnabled } from "./demo";
import {
  companies,
  initialAiSuggestions,
  initialCloseTasks,
  initialIntegrations,
  initialReconciliations,
  ledgerEvents,
  migrationRows,
  periods,
  workItems,
} from "./data/mockData";
import type { AiSuggestion, CloseTask, Integration, ReconciliationItem, Tone, WorkItem } from "./data/types";


const RASTRO_HOME = "/app/rastro";

function useRastroNavigate() {
  const navigate = useNavigate();
  const location = useLocation();
  const base = location.pathname.startsWith("/app/rastro/demonstracao")
    ? "/app/rastro/demonstracao"
    : RASTRO_HOME;
  return (path: string) => {
    if (path.startsWith("/app/")) {
      navigate(path);
      return;
    }
    navigate(path === "/" ? base : `${base}${path}`);
  };
}

const navGroups = [
  {
    label: "Operação",
    items: [
      { to: "/app/rastro", label: "Hoje", mark: "H" },
      { to: "/app/rastro/fechamentos", label: "Fechamentos", mark: "F" },
      { to: "/app/rastro/pendencias", label: "Pendências", mark: "P" },
      { to: "/app/rastro/balancete", label: "Balancete", mark: "B" },
      { to: "/app/rastro/conciliacao", label: "Conciliação", mark: "C" },
      { to: "/app/rastro/migracoes", label: "Migrações", mark: "M" },
    ],
  },
  {
    label: "Rastreabilidade",
    items: [
      { to: "/app/rastro/ledger", label: "Dados e ledger", mark: "L" },
      { to: "/app/rastro/revisoes-ia", label: "Revisões de IA", mark: "I" },
      { to: "/app/rastro/obrigacoes", label: "Obrigações e entregas", mark: "O" },
      { to: "/app/rastro/biblioteca", label: "Evidências", mark: "E" },
    ],
  },
  {
    label: "Plataforma",
    items: [{ to: "/app/rastro/integracoes", label: "Integrações", mark: "N" }],
  },
];

const routeMeta: Record<string, { crumb: string; label: string }> = {
  "/app/rastro": { crumb: "Operação", label: "Hoje" },
  "/app/rastro/fechamentos": { crumb: "Operação", label: "Fechamentos" },
  "/app/rastro/fechamentos/2025-01": { crumb: "Fechamentos", label: "Competência 01/2025" },
  "/app/rastro/pendencias": { crumb: "Operação", label: "Pendências" },
  "/app/rastro/balancete": { crumb: "Operação", label: "Balancete" },
  "/app/rastro/conciliacao": { crumb: "Operação", label: "Conciliação" },
  "/app/rastro/migracoes": { crumb: "Operação", label: "Migrações" },
  "/app/rastro/ledger": { crumb: "Rastreabilidade", label: "Dados e ledger" },
  "/app/rastro/revisoes-ia": { crumb: "Rastreabilidade", label: "Revisões de IA" },
  "/app/rastro/obrigacoes": { crumb: "Rastreabilidade", label: "Obrigações e entregas" },
  "/app/rastro/integracoes": { crumb: "Plataforma", label: "Integrações" },
  "/app/rastro/biblioteca": { crumb: "Rastreabilidade", label: "Evidências" },
};

const workRoutes: Record<string, { crumb: string; label: string }> = {
  ...routeMeta,
  "/app/rastro/rotinas": { crumb: "Sistema", label: "Rotinas do razão" },
  "/app/rastro/administracao": { crumb: "Governança", label: "Administração" },
  "/app/journals": { crumb: "Rastreabilidade", label: "Lançamentos" },
  "/app/journals/new": { crumb: "Sistema", label: "Novo lançamento" },
  "/app/trial-balance": { crumb: "Sistema", label: "Balancete" },
  "/app/accounts": { crumb: "Sistema", label: "Plano de contas" },
  "/app/documents": { crumb: "Rastreabilidade", label: "Evidências" },
  "/app/banks": { crumb: "Sistema", label: "Bancos" },
  "/app/reconciliation": { crumb: "Operação", label: "Conciliação" },
  "/app/imports": { crumb: "Operação", label: "Migrações" },
  "/app/periods": { crumb: "Operação", label: "Fechamentos" },
  "/app/audit": { crumb: "Sistema", label: "Auditoria" },
  "/app/companies/new": { crumb: "Sistema", label: "Nova empresa" },
};

function currentRoute(pathname: string): { crumb: string; label: string } {
  if (pathname.startsWith("/app/rastro/demonstracao")) {
    const inner = pathname.slice("/app/rastro/demonstracao".length) || "/";
    const demoPath = inner === "/" ? "/app/rastro" : `/app/rastro${inner}`;
    if (demoPath.startsWith("/app/rastro/fechamentos/") && demoPath !== "/app/rastro/fechamentos") {
      const key = demoPath.slice("/app/rastro/fechamentos/".length);
      return { crumb: "Demonstração", label: key === "2025-01" ? "Competência 01/2025" : `Competência ${key}` };
    }
    const known = routeMeta[demoPath];
    return known ? { crumb: "Demonstração", label: known.label } : { crumb: "Demonstração", label: "Hoje" };
  }
  if (pathname.startsWith("/app/rastro/fechamentos/")) {
    return { crumb: "Fechamentos", label: "Checklist" };
  }
  if (pathname.startsWith("/app/journals/") && pathname !== "/app/journals/new") {
    return { crumb: "Rastreabilidade", label: "Lançamento" };
  }
  if (pathname.startsWith("/app/imports/") || pathname.startsWith("/app/rastro/migracoes/")) {
    return { crumb: "Operação", label: "Migração" };
  }
  return workRoutes[pathname] ?? { crumb: "Operação", label: "Hoje" };
}

function Routine({ children }: { children: ReactNode }) {
  return <div className="routine">{children}</div>;
}

type Toast = { title: string; detail: string } | null;
type ObligationState = "preparada" | "validada" | "transmitida" | "protocolo recebido" | "aceite confirmado";
type Company = (typeof companies)[number];
type ContextProps = { company: Company; period: string };

function initials(name: string): string {
  const parts = name.split(" ").filter(Boolean).slice(0, 2);
  return parts.map((part) => part[0]?.toUpperCase() ?? "").join("") || "U";
}

function demoCovers(company: Company, period: string): boolean {
  return company.id === "orbe" && period === "01/2025";
}

function DemoUnavailable({ company, period }: ContextProps) {
  return (
    <PageHeader
      eyebrow={`Demonstração · ${company.name} · ${period}`}
      title="Esta combinação não tem conteúdo sintético."
      description="O detalhe da sala cobre Orbe Serviços Digitais Ltda. na competência 01/2025. Trocar o cliente aqui não altera a empresa cadastrada no sistema."
    />
  );
}

export function RastroShell() {
  const location = useLocation();
  const session = useSession();
  const demo = rastroDemoEnabled();
  const actorName = session.me.display_name;
  const systemCompany = session.entities.find((entity) => entity.legal_entity_id === session.entityId);
  const [companyId, setCompanyId] = useState("orbe");
  const [period, setPeriod] = useState("01/2025");
  const [closeTasks, setCloseTasks] = useState<CloseTask[]>(initialCloseTasks);
  const [reconciliations, setReconciliations] = useState<ReconciliationItem[]>(initialReconciliations);
  const [aiSuggestions, setAiSuggestions] = useState<AiSuggestion[]>(initialAiSuggestions);
  const [integrations, setIntegrations] = useState<Integration[]>(initialIntegrations);
  const [evidence, setEvidence] = useState<string | null>(null);
  const [toast, setToast] = useState<Toast>(null);
  const [obligationState, setObligationState] = useState<ObligationState>("validada");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const company = companies.find((item) => item.id === companyId) ?? companies[0];
  const demonstration = location.pathname.startsWith("/app/rastro/demonstracao");
  const route = currentRoute(location.pathname);
  const unresolvedCloseItems = closeTasks.filter((task) => task.blocker).length;

  const notify = (title: string, detail: string) => setToast({ title, detail });

  const changeCompany = (id: string) => {
    setCompanyId(id);
    const next = companies.find((item) => item.id === id);
    if (next) notify("Contexto da demonstração", `${next.name} · ${period}. A empresa cadastrada no sistema não mudou.`);
  };

  const resolveCloseTask = (id: string, resolution: string) => {
    setCloseTasks((tasks) => tasks.map((task) => (
      task.id === id
        ? { ...task, state: "concluído", tone: "success", blocker: false, updatedAt: "Agora", resolution, resolvedBy: actorName }
        : task
    )));
    notify("Decisão registrada", "A resolução, a responsável e o horário foram vinculados ao checkpoint da demonstração.");
  };

  const decideReconciliation = (id: string, state: "reconciliado" | "rejeitado", candidate: string | undefined, reason?: string) => {
    setReconciliations((items) => items.map((item) => (
      item.id === id
        ? { ...item, state, tone: state === "reconciliado" ? "success" : "neutral", decision: { candidate, actor: actorName, at: "Agora", reason } }
        : item
    )));
    notify(
      state === "reconciliado" ? "Conciliação aprovada" : "Candidato rejeitado",
      state === "reconciliado"
        ? "O vínculo foi registrado apenas em memória para esta demonstração; a fonte e o candidato permanecem auditáveis."
        : "A transação não foi apagada. O caso continua preservado como decisão rejeitada.",
    );
  };

  const reviewSuggestion = (id: string, state: "aprovado" | "rejeitado" | "revertido", reason?: string) => {
    setAiSuggestions((items) => items.map((item) => (
      item.id === id
        ? {
          ...item,
          state,
          tone: state === "aprovado" ? "success" : "neutral",
          outcome: state === "aprovado" ? "Aprovação de demonstração registrada" : state === "revertido" ? "Aprovação revertida na demonstração" : "Rejeição de demonstração registrada",
          decision: { actor: actorName, at: "Agora", reason },
        }
        : item
    )));
    notify(
      state === "aprovado" ? "Sugestão aprovada para revisão" : state === "revertido" ? "Aprovação revertida" : "Sugestão rejeitada",
      "A decisão não altera journal nem transmite obrigação. O resultado fica associado à evidência, ao ator e ao horário.",
    );
  };

  const retryIntegration = (id: string) => {
    setIntegrations((items) => items.map((item) => (
      item.id === id
        ? { ...item, health: "sincronizando", tone: "info", lastSync: "Tentativa registrada agora", queue: "1 tentativa em fila" }
        : item
    )));
    notify("Tentativa registrada", "A demonstração registrou uma nova tentativa idempotente. Nenhum conector externo foi chamado.");
  };

  const selectedEvidence = useMemo(() => evidence, [evidence]);

  return (
    <div className="rastro">
    <div className="app-frame">
      <aside className={`sidebar ${sidebarOpen ? "sidebar--open" : ""}`} aria-label="Navegação principal">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true"><span>R</span><i /></div>
          <div>
            <strong>Rastro</strong>
            <small>fechamento com evidência</small>
          </div>
          <button className="icon-button sidebar-close" type="button" onClick={() => setSidebarOpen(false)} aria-label="Fechar navegação">×</button>
        </div>

        <div className="office-summary">
          <span className="eyebrow">Escritório</span>
          <strong>{session.me.tenant_name}</strong>
          <span>{demonstration ? "Demonstração sintética" : "Conectado ao sistema"}</span>
        </div>

        <nav className="main-nav">
          {navGroups.map((group) => (
            <div className="nav-group" key={group.label}>
              <span className="nav-group__label">{group.label}</span>
              {group.items.map((item) => (
                <NavLink
                  to={item.to}
                  end={item.to === "/app/rastro"}
                  key={item.to}
                  className={({ isActive }) => `nav-link ${isActive ? "nav-link--active" : ""}`}
                  onClick={() => setSidebarOpen(false)}
                >
                  <span className="nav-mark" aria-hidden="true">{item.mark}</span>
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </div>
          ))}
          <div className="nav-group">
            <span className="nav-group__label">Sistema</span>
            <NavLink to="/app/rastro/rotinas" className={({ isActive }) => `nav-link ${isActive ? "nav-link--active" : ""}`} onClick={() => setSidebarOpen(false)}>
              <span className="nav-mark" aria-hidden="true">R</span>
              <span>Rotinas do razão</span>
            </NavLink>
            {demo ? (
              <NavLink to="/app/rastro/demonstracao" className={({ isActive }) => `nav-link ${isActive ? "nav-link--active" : ""}`} onClick={() => setSidebarOpen(false)}>
                <span className="nav-mark" aria-hidden="true">D</span>
                <span>Demonstração</span>
              </NavLink>
            ) : null}
          </div>
          <div className="nav-group">
            <span className="nav-group__label">Governança</span>
            <NavLink to="/app/rastro/administracao" className={({ isActive }) => `nav-link ${isActive ? "nav-link--active" : ""}`} onClick={() => setSidebarOpen(false)}>
              <span className="nav-mark" aria-hidden="true">A</span>
              <span>Administração</span>
            </NavLink>
          </div>
        </nav>

        <div className="sidebar-footer">
          <div className="user-avatar" aria-hidden="true">{initials(actorName)}</div>
          <div>
            <strong>{actorName}</strong>
            <span>{session.me.roles.join(", ")}</span>
          </div>
          <button className="sidebar-logout" type="button" onClick={() => void userManager.signoutRedirect()}>Sair</button>
        </div>
      </aside>

      {sidebarOpen && <button className="sidebar-scrim" type="button" onClick={() => setSidebarOpen(false)} aria-label="Fechar navegação" />}

      <main className="workspace">
        <header className="topbar">
          <button className="icon-button menu-button" type="button" onClick={() => setSidebarOpen(true)} aria-label="Abrir navegação">☰</button>
          <div className="breadcrumb" aria-label="Localização atual">
            <span>{route.crumb}</span>
            <i>/</i>
            <strong>{route.label}</strong>
          </div>
          <div className="topbar-actions">
            <button className="command-button" type="button" onClick={focusCompanySearch}>Buscar <kbd>⌘ K</kbd></button>
            <button className="notice-button" type="button" onClick={() => notify("Notificações", "Há 4 itens atribuídos a você nesta competência.")}>3<span className="sr-only"> notificações</span></button>
          </div>
        </header>

        {demonstration ? (
          <p className="demo-banner" role="status">
            <strong>Demonstração sintética.</strong>
            <span>
              Nenhuma ação grava lançamento, aprovação, transmissão, protocolo ou aceite. No sistema: {session.me.tenant_name}
              {" · "}
              {systemCompany ? systemCompany.name : "nenhuma empresa cadastrada"}.
            </span>
          </p>
        ) : null}

        {demonstration ? <section className="context-bar" aria-label="Contexto operacional">
          <div className="context-label"><span className="context-dot" />Contexto de trabalho</div>
          <label className="context-select">
            <span>Cliente / CNPJ</span>
            <select value={companyId} onChange={(event) => changeCompany(event.target.value)}>
              {companies.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}
            </select>
          </label>
          <span className="context-cnpj">{company.cnpj}</span>
          <label className="context-select context-select--period">
            <span>Competência</span>
            <select value={period} onChange={(event) => { setPeriod(event.target.value); notify("Competência atualizada", `A visualização agora está em ${event.target.value}.`); }}>
              {periods.map((item) => <option value={item} key={item}>{item}</option>)}
            </select>
          </label>
          <span className="context-meta">{company.regime} · {company.uf}</span>
          <StatusBadge tone="attention" label={company.state} />
          <button className="context-link" type="button" onClick={() => notify("Escopo do contexto", "O filtro atual inclui empresa, competência, regime e UF. Filtros de tabela não mudam este contexto. A empresa do sistema permanece a mesma.")}>Ver escopo</button>
        </section> : <LiveContextBar />}

        <div className="page-container">
          <Routes>
            <Route path="/app/rastro" element={<OfficeHome />} />
            <Route path="/app/rastro/fechamentos" element={<Routine><PeriodsPage /></Routine>} />
            <Route path="/app/rastro/fechamentos/:periodId" element={<Routine><CloseRunPage /></Routine>} />
            <Route path="/app/rastro/pendencias" element={<Routine><DocumentRequestsPage /></Routine>} />
            <Route path="/app/rastro/balancete" element={<Routine><TrialBalancePage /></Routine>} />
            <Route path="/app/rastro/conciliacao" element={<Routine><LedgerReconciliationPage /></Routine>} />
            <Route path="/app/rastro/migracoes" element={<Routine><ImportsPage /></Routine>} />
            <Route path="/app/rastro/migracoes/:batchId" element={<Routine><ImportDetailPage /></Routine>} />
            <Route path="/app/rastro/ledger" element={<Routine><JournalsPage /></Routine>} />
            <Route path="/app/rastro/revisoes-ia" element={<PlannedPage title="Revisões de IA" detail="Não há sugestão ligada a esta empresa. Uma sugestão só passa a ter efeito depois de aprovação humana, e este contrato ainda não está nesta versão." />} />
            <Route path="/app/rastro/obrigacoes" element={<PlannedPage title="Obrigações e entregas" detail="Não há obrigação versionada para esta empresa. Transmissão, protocolo e recibo continuam fora desta versão." />} />
            <Route path="/app/rastro/biblioteca" element={<Routine><DocumentsPage /></Routine>} />
            <Route path="/app/rastro/integracoes" element={<PlannedPage title="Integrações" detail="Nenhum conector externo está configurado. As contas bancárias da empresa ficam em Rotinas do razão." />} />
            <Route path="/app/rastro/rotinas" element={<RoutinesPage />} />
            <Route path="/app/rastro/administracao" element={<Routine><AdministrationPage /></Routine>} />
            <Route path="/app/journals/new" element={<Routine><JournalFormPage /></Routine>} />
            <Route path="/app/journals/:journalId" element={<Routine><JournalDetailPage /></Routine>} />
            <Route path="/app/journals" element={<Routine><JournalsPage /></Routine>} />
            <Route path="/app/trial-balance" element={<Routine><TrialBalancePage /></Routine>} />
            <Route path="/app/accounts" element={<Routine><AccountsPage /></Routine>} />
            <Route path="/app/documents" element={<Routine><DocumentsPage /></Routine>} />
            <Route path="/app/banks" element={<Routine><BanksPage /></Routine>} />
            <Route path="/app/reconciliation" element={<Routine><LedgerReconciliationPage /></Routine>} />
            <Route path="/app/imports/:batchId" element={<Routine><ImportDetailPage /></Routine>} />
            <Route path="/app/imports" element={<Routine><ImportsPage /></Routine>} />
            <Route path="/app/periods" element={<Routine><PeriodsPage /></Routine>} />
            <Route path="/app/audit" element={<Routine><AuditPage /></Routine>} />
            <Route path="/app/companies/new" element={<Routine><CompanyFormPage /></Routine>} />
            {demo ? (
              <>
                <Route path="/app/rastro/demonstracao" element={<TodayPage company={company} period={period} tasks={closeTasks} reconciliations={reconciliations} integrations={integrations} obligationState={obligationState} onEvidence={setEvidence} onNotice={notify} />} />
                <Route path="/app/rastro/demonstracao/fechamentos" element={<CloseListPage company={company} period={period} tasks={closeTasks} onEvidence={setEvidence} />} />
                <Route path="/app/rastro/demonstracao/fechamentos/:period" element={<ClosePeriodPage company={company} period={period} tasks={closeTasks} unresolved={unresolvedCloseItems} onResolve={resolveCloseTask} onEvidence={setEvidence} onNotice={notify} />} />
                <Route path="/app/rastro/demonstracao/conciliacao" element={<ReconciliationPage company={company} period={period} items={reconciliations} onDecide={decideReconciliation} onEvidence={setEvidence} />} />
                <Route path="/app/rastro/demonstracao/migracoes" element={<MigrationPage company={company} period={period} actor={actorName} onEvidence={setEvidence} onNotice={notify} />} />
                <Route path="/app/rastro/demonstracao/ledger" element={<LedgerPage company={company} period={period} onEvidence={setEvidence} />} />
                <Route path="/app/rastro/demonstracao/revisoes-ia" element={<AiReviewPage company={company} period={period} items={aiSuggestions} onReview={reviewSuggestion} onEvidence={setEvidence} />} />
                <Route path="/app/rastro/demonstracao/obrigacoes" element={<ObligationPage company={company} period={period} state={obligationState} onAdvance={setObligationState} onEvidence={setEvidence} onNotice={notify} />} />
                <Route path="/app/rastro/demonstracao/integracoes" element={<IntegrationsPage company={company} period={period} items={integrations} onRetry={retryIntegration} onEvidence={setEvidence} />} />
                <Route path="/app/rastro/demonstracao/biblioteca" element={<EvidenceLibraryPage company={company} period={period} onEvidence={setEvidence} onNotice={notify} />} />
              </>
            ) : null}
            <Route path="*" element={<OfficeHome />} />
          </Routes>
        </div>
      </main>

      {demonstration && selectedEvidence ? <EvidenceDrawer evidence={selectedEvidence} onClose={() => setEvidence(null)} /> : null}
      {toast && <ToastMessage toast={toast} onDismiss={() => setToast(null)} />}
    </div>
    </div>
  );
}

function ClosePeriodPage(props: ContextProps & { tasks: CloseTask[]; unresolved: number; onResolve: (id: string, resolution: string) => void; onEvidence: (value: string) => void; onNotice: (title: string, detail: string) => void }) {
  const params = useParams();
  const periodKey = params.period ?? "";
  if (periodKey !== "2025-01" || !demoCovers(props.company, props.period)) {
    return <DemoUnavailable company={props.company} period={periodKey || props.period} />;
  }
  return <CloseDetailPage {...props} />;
}

function TodayPage({ company, period, tasks, reconciliations, integrations, obligationState, onEvidence, onNotice }: ContextProps & { tasks: CloseTask[]; reconciliations: ReconciliationItem[]; integrations: Integration[]; obligationState: ObligationState; onEvidence: (value: string) => void; onNotice: (title: string, detail: string) => void }) {
  const navigate = useRastroNavigate();
  if (!demoCovers(company, period)) {
    return <DemoUnavailable company={company} period={period} />;
  }
  const completed = tasks.filter((task) => task.state === "concluído").length;
  const blockers = tasks.filter((task) => task.blocker).length;
  const closingProgress = Math.round((completed / tasks.length) * 100);
  const reconciled = 85 + reconciliations.filter((item) => item.state === "reconciliado").length;
  const openReconciliations = reconciliations.filter((item) => item.state === "requer revisão").length;
  const openDocuments = tasks.filter((task) => task.domain === "Documentos" && task.state !== "concluído").length;
  const healthyIntegrations = integrations.filter((item) => item.health === "saudável").length;
  return (
    <>
      <PageHeader
        eyebrow={`Central de trabalho · ${company.name} · ${period}`}
        title={`O fechamento pede atenção em ${blockers + openReconciliations} pontos.`}
        description="Priorize itens que bloqueiam a competência. Cada decisão abre a fonte, a regra e a trilha de evidências."
        action={<button className="button button--secondary" type="button" onClick={() => navigate("/fechamentos/2025-01")}>Abrir fechamento</button>}
      />

      <section className="metric-strip" aria-label="Resumo operacional">
        <Metric label="Fechamento" value={`${closingProgress}%`} note={`${blockers} bloqueio(s) ativo(s)`} tone={blockers ? "attention" : "success"} />
        <Metric label="Conciliação" value={`${reconciled} / 89`} note={`${openReconciliations} caso(s) em revisão`} tone={openReconciliations ? "info" : "success"} />
        <Metric label="Documentos" value={String(openDocuments)} note={openDocuments ? "solicitação sem resposta" : "sem pendências abertas"} tone={openDocuments ? "danger" : "success"} />
        <Metric label="Entrega" value="1" note={obligationState} tone={obligationState === "aceite confirmado" ? "success" : "info"} />
      </section>

      <div className="workspace-grid">
        <section className="panel panel--flush priority-panel">
          <div className="panel-heading panel-heading--roomy">
            <div>
              <span className="eyebrow">Fila de exceções</span>
              <h2>O que exige uma decisão agora</h2>
            </div>
            <button className="text-button" type="button" onClick={() => onNotice("Filtro salvo", "A visão padrão prioriza bloqueios, vencimentos e decisões atribuídas a você.")}>Ajustar visão</button>
          </div>
          <div className="priority-list">
            {workItems.map((item) => <WorkItemRow key={item.id} item={item} companyName={company.name} period={period} onEvidence={onEvidence} onNavigate={() => navigate(item.route)} />)}
          </div>
        </section>

        <aside className="side-stack">
          <section className="panel close-pulse">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">Régua de competência</span>
              <h2>{period} · {company.name.split(" ")[0]}</h2>
              </div>
              <StatusBadge tone="attention" label="Pré-fechamento" />
            </div>
            <div className="progress-track" aria-label={`Fechamento com ${closingProgress} por cento concluído`}><span style={{ width: `${closingProgress}%` }} /></div>
            <div className="progress-scale"><span>Entradas</span><span>Conciliação</span><span>Fechamento</span><span>Entrega</span></div>
            <div className="close-pulse__stats">
              <strong>{completed} de {tasks.length}</strong><span>checkpoints concluídos</span>
              <button className="inline-action" type="button" onClick={() => navigate("/fechamentos/2025-01")}>Ver checkpoints →</button>
            </div>
          </section>

          <section className="panel evidence-callout">
            <div className="evidence-icon" aria-hidden="true">E</div>
            <div>
              <span className="eyebrow">Princípio de operação</span>
              <h3>Nenhum “ok” fica sem explicação.</h3>
              <p>Status, regra, fonte, responsável e horário compõem cada decisão material.</p>
              <button className="inline-action" type="button" onClick={() => onEvidence("SPEC v0.1.0 · invariantes, estados e definição de pronto")}>Abrir contrato de interface →</button>
            </div>
          </section>

          <section className="panel small-list">
            <div className="panel-heading"><h2>Próximos prazos</h2><button className="text-button" type="button" onClick={() => navigate("/obrigacoes")}>Calendário</button></div>
            <Deadline name="Conferir ECD" meta="Amanhã · 10:00" tone="attention" />
            <Deadline name="Solicitar extrato" meta="Hoje · 17:00" tone="danger" />
            <Deadline name="Revisar IA-071" meta="Hoje · 16:30" tone="attention" />
          </section>
          <section className="panel integration-summary">
            <div><span className="eyebrow">Saúde das integrações</span><h2>{healthyIntegrations} saudável(is) · {integrations.length - healthyIntegrations} com atenção</h2><p>Frescor, fila e fallback ficam visíveis antes do fechamento.</p></div>
            <button className="inline-action" type="button" onClick={() => navigate("/integracoes")}>Abrir integrações →</button>
          </section>
        </aside>
      </div>
    </>
  );
}

function CloseListPage({ company, period, tasks, onEvidence }: ContextProps & { tasks: CloseTask[]; onEvidence: (value: string) => void }) {
  const navigate = useRastroNavigate();
  if (!demoCovers(company, period)) {
    return <DemoUnavailable company={company} period={period} />;
  }
  const currentProgress = Math.round((tasks.filter((task) => task.state === "concluído").length / tasks.length) * 100);
  const rows = [
    { company: company.name, period, state: company.state, tone: "attention" as Tone, progress: currentProgress, blocker: `${tasks.filter((task) => task.blocker).length} bloqueios`, owner: "Marina Rocha" },
    { company: "Aurora Comércio e Design Ltda.", period: "01/2025", state: "Aguardando documentos", tone: "danger" as Tone, progress: 44, blocker: "4 documentos", owner: "Caio Mendes" },
    { company: "Mar Alto Logística Ltda.", period: "01/2025", state: "Aberto", tone: "info" as Tone, progress: 18, blocker: "Implantação", owner: "Lucas Barros" },
  ];
  return (
    <>
      <PageHeader eyebrow={`Fechamentos · competência ativa ${period}`} title="A carteira se organiza por competência, não por módulo." description="Acompanhe progresso real, bloqueios e responsáveis antes de abrir as rotinas especializadas." action={<button className="button" type="button" onClick={() => onEvidence("Calendário de fechamento · critérios de bloqueio e responsáveis")}>Ver calendário</button>} />
      <section className="panel panel--flush">
        <div className="table-toolbar">
          <div className="filter-row"><FilterPill label="01/2025" /><FilterPill label="Todos os responsáveis" /><FilterPill label="Com bloqueios" /></div>
          <span className="table-count">3 competências visíveis</span>
        </div>
        <div className="table-scroll">
          <table className="data-table">
            <thead><tr><th>Cliente / competência</th><th>Progresso</th><th>Estado</th><th>Bloqueios</th><th>Responsável</th><th><span className="sr-only">Ações</span></th></tr></thead>
            <tbody>{rows.map((row) => <tr key={row.company}><td><strong>{row.company}</strong><span>{row.period} · Lucro Presumido · SP</span></td><td><div className="mini-progress"><span style={{ width: `${row.progress}%` }} /></div><b>{row.progress}%</b></td><td><StatusBadge tone={row.tone} label={row.state} /></td><td><span className="table-note">{row.blocker}</span></td><td>{row.owner}</td><td><button className="text-button" type="button" disabled={row.company !== "Orbe Serviços Digitais Ltda." || period !== "01/2025"} onClick={() => navigate("/fechamentos/2025-01")}>Abrir →</button></td></tr>)}</tbody>
          </table>
        </div>
      </section>
    </>
  );
}

function CloseDetailPage({ company, period, tasks, unresolved, onResolve, onEvidence, onNotice }: ContextProps & { tasks: CloseTask[]; unresolved: number; onResolve: (id: string, resolution: string) => void; onEvidence: (value: string) => void; onNotice: (title: string, detail: string) => void }) {
  const navigate = useRastroNavigate();
  if (!demoCovers(company, period)) {
    return <DemoUnavailable company={company} period={period} />;
  }
  const completed = tasks.filter((task) => task.state === "concluído").length;
  const canApprove = unresolved === 0;
  return (
    <>
      <PageHeader eyebrow={`Fechamento · ${company.name} · ${period}`} title="Fechamento com checkpoints e evidências." description="A competência só avança quando bloqueios são resolvidos ou tratados com justificativa. O protótipo não fecha períodos reais." action={<button className="button button--secondary" type="button" onClick={() => navigate("/biblioteca")}>Ver pacote de evidências</button>} />
      <section className="close-hero panel">
        <div className="close-hero__state"><StatusBadge tone={canApprove ? "info" : "attention"} label={canApprove ? "Pronto para aprovação" : "Pré-fechamento"} /><h2>{completed} de {tasks.length} checkpoints concluídos</h2><p>{unresolved > 0 ? `${unresolved} item(ns) ainda impede(m) o avanço para aprovação.` : "Todos os bloqueios foram resolvidos nesta demonstração."}</p></div>
        <div className="close-hero__actions"><button className="button" type="button" disabled={!canApprove} onClick={() => onNotice("Aprovação preparada", "Em produção, esta ação exigirá papel autorizador, resumo de impacto e evento de auditoria.")}>Preparar aprovação</button><button className="button button--secondary" type="button" onClick={() => onEvidence("CloseRun CR-2025-01-ORBE · checklist, snapshot e política de bloqueio")}>Ver histórico</button></div>
      </section>
      <div className="detail-grid">
        <section className="panel panel--flush checklist-panel">
          <div className="panel-heading panel-heading--roomy"><div><span className="eyebrow">Checklist da competência</span><h2>Itens por domínio</h2></div><span className="table-count">Atualizado agora</span></div>
          <div className="checklist-list">{tasks.map((task) => <CloseTaskRow key={task.id} task={task} onResolve={onResolve} onEvidence={onEvidence} />)}</div>
        </section>
        <aside className="side-stack">
          <section className="panel evidence-summary"><span className="eyebrow">Pacote esperado</span><h2>8 grupos de evidência</h2><div className="evidence-summary__list"><span>Checklist e aprovações</span><span>Balancete e controles</span><span>Conciliações e diferenças</span><span>Obrigações e protocolos</span></div><button className="inline-action" type="button" onClick={() => onEvidence("PKG-2025-01-ORBE · manifesto de integridade em preparação")}>Explorar conteúdo →</button></section>
          <section className="panel note-card"><span className="eyebrow">Regra de controle</span><p>Alterações após fechamento criam reabertura com motivo e aprovação. Não substituem a versão anterior.</p></section>
        </aside>
      </div>
    </>
  );
}

function ReconciliationPage({ company, period, items, onDecide, onEvidence }: ContextProps & { items: ReconciliationItem[]; onDecide: (id: string, state: "reconciliado" | "rejeitado", candidate: string | undefined, reason?: string) => void; onEvidence: (value: string) => void }) {
  const [selectedId, setSelectedId] = useState(items[0]?.id ?? "");
  const [candidateIndex, setCandidateIndex] = useState(0);
  const [decisionReason, setDecisionReason] = useState("");
  if (!demoCovers(company, period)) {
    return <DemoUnavailable company={company} period={period} />;
  }
  const selected = items.find((item) => item.id === selectedId) ?? items[0];
  const openCases = items.filter((item) => item.state === "requer revisão").length;
  const reconciledCases = 85 + items.filter((item) => item.state === "reconciliado").length;
  const clientShortName = company.name.split(" ")[0];
  return (
    <>
      <PageHeader eyebrow={`Conciliação explicável · ${company.name} · ${period}`} title="Sugestão não é decisão contábil." description="Cada match mostra regra, fonte, tolerância e candidatos. A aprovação humana registra o vínculo sem apagar a origem." action={<button className="button button--secondary" type="button" onClick={() => onEvidence("Configuração de conciliação · tolerância de 3 dias · modo 1:1")}>Ver regra</button>} />
      <section className="metric-strip metric-strip--compact"><Metric label="Casos abertos" value={String(openCases)} note="requerem decisão" tone="attention" /><Metric label="Score médio" value="84%" note="somente como apoio" tone="info" /><Metric label="Aprovados" value={String(reconciledCases)} note="com trilha auditável" tone="success" /></section>
      <div className="reconciliation-grid">
        <section className="panel panel--flush reconciliation-list"><div className="panel-heading panel-heading--roomy"><div><span className="eyebrow">Fila da conta Banco Horizonte</span><h2>Casos da competência</h2></div><FilterPill label="Pendente" /></div>{items.map((item) => <button className={`reconciliation-row ${selected?.id === item.id ? "reconciliation-row--selected" : ""}`} type="button" key={item.id} onClick={() => setSelectedId(item.id)}><span className={`status-bar status-bar--${item.tone}`} /><span className="reconciliation-row__body"><b>{item.title.replace("Orbe", clientShortName)}</b><small>{item.date} · {item.value}</small><em>{item.state}</em></span><span className="score-pill">{item.score}%</span></button>)}</section>
        {selected && <section className="panel reconciliation-detail"><div className="panel-heading"><div><span className="eyebrow">Caso {selected.id.toUpperCase()}</span><h2>{selected.title.replace("Orbe", clientShortName)}</h2></div><StatusBadge tone={selected.tone} label={selected.state} /></div><p className="detail-lead">{selected.description}</p><div className="transaction-card"><div><span>Movimento externo</span><strong>{selected.value}</strong><small>{selected.date}</small></div><div><span>Fonte</span><b>{selected.source}</b><button className="inline-action" type="button" onClick={() => onEvidence(selected.evidence)}>Abrir evidência →</button></div></div><div className="explanation-box"><span className="eyebrow">Por que foi sugerido</span>{selected.explanation.map((reason) => <div className="reason-row" key={reason}><span>✓</span>{reason}</div>)}</div><div className="candidate-heading"><span className="eyebrow">Candidatos internos</span><span>Selecione o vínculo a decidir</span></div>{selected.candidates.map((candidate, index) => <button className={`candidate-card ${candidateIndex === index ? "candidate-card--selected" : ""}`} type="button" key={candidate.title} onClick={() => { setCandidateIndex(index); setDecisionReason(""); }}><span className="candidate-index">{index + 1}</span><span><strong>{candidate.title}</strong><small>{candidate.account} · {candidate.date}</small></span><b>{candidate.value}</b></button>)}{selected.state === "requer revisão" ? <div className="decision-bar"><div><strong>Confirme após revisar o escopo</strong><span>Candidato: {selected.candidates[candidateIndex]?.title ?? "nenhum"}. Ação e ator entram na trilha.</span><label className="decision-reason">Motivo em caso de rejeição<input value={decisionReason} onChange={(event) => setDecisionReason(event.target.value)} placeholder="Descreva por que este candidato não se aplica" /></label></div><div><button className="button button--secondary" type="button" disabled={!decisionReason.trim()} onClick={() => onDecide(selected.id, "rejeitado", selected.candidates[candidateIndex]?.title, decisionReason.trim())}>Rejeitar candidato</button><button className="button" type="button" onClick={() => onDecide(selected.id, "reconciliado", selected.candidates[candidateIndex]?.title)}>Aprovar conciliação</button></div></div> : <div className="resolved-note"><StatusBadge tone={selected.tone} label={selected.state} /><span>Decisão de {selected.decision?.candidate ?? "candidato selecionado"} registrada por {selected.decision?.actor ?? "responsável"} · {selected.decision?.at ?? "agora"}.</span></div>}</section>}
      </div>
    </>
  );
}

function MigrationPage({ company, period, actor, onEvidence, onNotice }: ContextProps & { actor: string; onEvidence: (value: string) => void; onNotice: (title: string, detail: string) => void }) {
  const [differenceAccepted, setDifferenceAccepted] = useState(false);
  const [dryRunLabel, setDryRunLabel] = useState("Dry-run concluído");
  const [acceptingDifference, setAcceptingDifference] = useState(false);
  const [justification, setJustification] = useState("");
  if (!demoCovers(company, period)) {
    return <DemoUnavailable company={company} period={period} />;
  }
  return (
    <>
      <PageHeader eyebrow={`Migração reconciliável · ${company.name} · ${period}`} title="Importar só é seguro quando a diferença é explicada." description="O lote preserva arquivo, hash, origem e versão de mapeamento. A prévia separa itens publicados, duplicados, inválidos e pendentes." action={<button className="button button--secondary" type="button" onClick={() => { setDryRunLabel("Dry-run atualizado agora"); onNotice("Prévia executada", "O dry-run de demonstração recalculou contagens sem publicar qualquer efeito."); }}>Executar prévia</button>} />
      <section className="migration-flow panel"><div className="flow-step flow-step--done"><span>1</span><div><b>Origem</b><small>Legado Atlas · CSV de diário</small></div></div><div className="flow-line" /><div className="flow-step flow-step--done"><span>2</span><div><b>Mapeamento</b><small>Versão 4 · 248 contas</small></div></div><div className="flow-line" /><div className="flow-step flow-step--active"><span>3</span><div><b>Reconciliação</b><small>Diferença material aberta</small></div></div><div className="flow-line" /><div className="flow-step"><span>4</span><div><b>Publicação</b><small>Requer aprovação</small></div></div></section>
      <div className="detail-grid"><section className="panel panel--flush"><div className="panel-heading panel-heading--roomy"><div><span className="eyebrow">IMP-2025-01-018</span><h2>{dryRunLabel}</h2></div><StatusBadge tone="attention" label="Requer revisão" /></div><div className="migration-stats">{migrationRows.map((row) => <div className="migration-stat" key={row.label}><StatusBadge tone={row.tone} label={row.label} /><strong>{row.value}</strong><span>{row.note}</span></div>)}</div><div className="migration-table"><div className="migration-table__head"><span>Controle</span><span>Origem</span><span>Destino</span><span>Resultado</span></div><div><strong>Saldos de abertura</strong><span>R$ 926.480,00</span><span>R$ 912.200,00</span><StatusBadge tone="danger" label="Diferença" /></div><div><strong>Débitos e créditos</strong><span>R$ 1.842.540,00</span><span>R$ 1.842.540,00</span><StatusBadge tone="success" label="Compatível" /></div><div><strong>Identificadores externos</strong><span>1.248</span><span>1.244 novos</span><StatusBadge tone="attention" label="4 duplicados" /></div></div></section><aside className="side-stack"><section className="panel evidence-summary"><span className="eyebrow">Decisão necessária</span><h2>Diferença residual</h2><p>O valor só pode seguir se houver mapeamento completo ou aceitação justificada pela pessoa aprovadora.</p><button className="button button--secondary" type="button" onClick={() => onEvidence("IMP-2025-01-018 · hash do arquivo, relatório de diferenças e mapeamento v4")}>Ver relatório</button>{acceptingDifference && !differenceAccepted && <div className="resolution-form migration-resolution"><label htmlFor="migration-justification">Justificativa e referência<input id="migration-justification" value={justification} onChange={(event) => setJustification(event.target.value)} placeholder="Ex.: diferença aceita conforme balancete assinado BAL-2025-01" /></label><div><button className="text-button" type="button" onClick={() => { setAcceptingDifference(false); setJustification(""); }}>Cancelar</button><button className="button button--compact" type="button" disabled={!justification.trim()} onClick={() => { setDifferenceAccepted(true); setAcceptingDifference(false); onNotice("Diferença aceita", `Justificativa registrada por ${actor}: ${justification.trim()}`); }}>Registrar justificativa</button></div></div>}<button className="button" type="button" disabled={differenceAccepted} onClick={() => setAcceptingDifference(true)}>{differenceAccepted ? "Justificativa registrada" : "Aceitar com justificativa"}</button></section><section className="panel note-card"><span className="eyebrow">Próximo estado</span><p>{differenceAccepted ? "A publicação pode ser preparada, sem criar lançamentos nesta demonstração." : "A publicação permanece indisponível enquanto a diferença estiver sem decisão."}</p><button className="inline-action" type="button" disabled={!differenceAccepted} onClick={() => onNotice("Publicação preparada", "Nenhum lançamento foi publicado. O lote segue para aprovação humana no fluxo real.")}>Preparar publicação →</button></section></aside></div>
    </>
  );
}

function LedgerPage({ company, period, onEvidence }: ContextProps & { onEvidence: (value: string) => void }) {
  if (!demoCovers(company, period)) {
    return <DemoUnavailable company={company} period={period} />;
  }
  return (
    <>
      <PageHeader eyebrow={`Dados e ledger · ${company.name} · ${period}`} title="A trilha não substitui: ela acrescenta versões e contexto." description="Navegue de um evento para sua fonte, regra, decisão e evidência. Lançamentos publicados não são editados silenciosamente." action={<button className="button button--secondary" type="button" onClick={() => onEvidence("Exportação demonstrativa · ledger, documentos e eventos de auditoria")}>Preparar exportação</button>} />
      <section className="panel panel--flush"><div className="table-toolbar"><div className="filter-row"><FilterPill label="01/2025" /><FilterPill label="Todos os eventos" /><FilterPill label="Orbe" /></div><span className="table-count">5 eventos recentes</span></div><div className="ledger-timeline">{ledgerEvents.map((event) => <article className="ledger-event" key={event.id}><div className={`timeline-pin timeline-pin--${event.tone}`} /><div className="ledger-event__time"><strong>{event.timestamp}</strong><span>{event.actor}</span></div><div className="ledger-event__content"><div><span className="eyebrow">{event.type}</span><h2>{event.title}</h2></div><StatusBadge tone={event.tone} label={event.state} /><p>{event.detail}</p><div className="event-footer"><span>{event.source}</span><button className="inline-action" type="button" onClick={() => onEvidence(event.evidence)}>Abrir evidência →</button></div></div></article>)}</div></section>
    </>
  );
}

function AiReviewPage({ company, period, items, onReview, onEvidence }: ContextProps & { items: AiSuggestion[]; onReview: (id: string, state: "aprovado" | "rejeitado" | "revertido", reason?: string) => void; onEvidence: (value: string) => void }) {
  if (!demoCovers(company, period)) {
    return <DemoUnavailable company={company} period={period} />;
  }
  const pending = items.filter((item) => item.state === "sugerido" || item.state === "revisado").length;
  return (
    <>
      <PageHeader eyebrow={`Assistência com aprovação humana · ${company.name} · ${period}`} title="A IA prepara uma decisão; ela não toma uma decisão." description="Reveja evidência, confiança, responsável e impacto antes de aceitar qualquer sugestão. Toda ação do protótipo fica somente em memória." action={<StatusBadge tone="attention" label={`${pending} para revisar`} />} />
      <section className="ai-intro"><div><span className="eyebrow">Linguagem obrigatória</span><p>Use <b>sugerido</b>, <b>revisado</b>, <b>aprovado</b>, <b>aplicado</b>, <b>rejeitado</b> e <b>revertido</b>. Nunca apresente sugestão como ato humano ou lançamento publicado.</p></div><button className="inline-action" type="button" onClick={() => onEvidence("SPEC v0.1.0 · seção 7 · IA e automação")}>Ver guardrails →</button></section>
      <section className="ai-grid">{items.map((item) => <AiSuggestionCard key={item.id} item={item} onReview={onReview} onEvidence={onEvidence} />)}</section>
    </>
  );
}

function AiSuggestionCard({ item, onReview, onEvidence }: { item: AiSuggestion; onReview: (id: string, state: "aprovado" | "rejeitado" | "revertido", reason?: string) => void; onEvidence: (value: string) => void }) {
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const canRevert = item.state === "aprovado";
  return <article className="panel ai-card"><div className="panel-heading"><div><span className="eyebrow">{item.target}</span><h2>{item.title}</h2></div><StatusBadge tone={item.tone} label={item.state} /></div><div className="confidence-meter"><div><span>Confiança explicável</span><b>{item.confidence}%</b></div><div className="progress-track"><span style={{ width: `${item.confidence}%` }} /></div></div><dl className="ai-details"><div><dt>Impacto</dt><dd>{item.impact}</dd></div><div><dt>Responsável</dt><dd>{item.responsible}</dd></div><div><dt>Regra / versão</dt><dd>{item.rule}</dd></div><div><dt>Evidência</dt><dd><button className="inline-action" type="button" onClick={() => onEvidence(item.evidence)}>Abrir fonte →</button></dd></div><div><dt>Como desfazer</dt><dd>{item.reversal}</dd></div></dl>{item.outcome ? <div className="resolved-note"><StatusBadge tone={item.tone} label={item.state} /><span>{item.outcome}{item.decision ? ` · ${item.decision.actor} · ${item.decision.at}` : ""}</span></div> : null}{canRevert ? <div className="ai-actions"><button className="button button--secondary" type="button" onClick={() => onReview(item.id, "revertido", "Reversão solicitada pela responsável")}>Reverter aprovação</button></div> : item.outcome ? null : <div className="ai-actions ai-actions--stacked">{rejecting && <label className="decision-reason">Motivo da rejeição<input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Descreva a divergência encontrada" /></label>}<div><button className="button button--secondary" type="button" onClick={() => { if (rejecting) { onReview(item.id, "rejeitado", reason.trim()); } else { setRejecting(true); } }} disabled={rejecting && !reason.trim()}>{rejecting ? "Confirmar rejeição" : "Rejeitar"}</button><button className="button" type="button" onClick={() => onReview(item.id, "aprovado")}>Aprovar para revisão</button></div></div>}</article>;
}

function ObligationPage({ company, period, state, onAdvance, onEvidence, onNotice }: ContextProps & { state: ObligationState; onAdvance: (value: ObligationState) => void; onEvidence: (value: string) => void; onNotice: (title: string, detail: string) => void }) {
  const states: ObligationState[] = ["preparada", "validada", "transmitida", "protocolo recebido", "aceite confirmado"];
  const index = states.indexOf(state);
  const next = states[index + 1];
  const nextLabel: Record<ObligationState, string> = { preparada: "Registrar pré-validação", validada: "Preparar transmissão (demo)", transmitida: "Registrar protocolo (demo)", "protocolo recebido": "Registrar recibo de aceite (demo)", "aceite confirmado": "Entrega concluída" };
  const [clientNotified, setClientNotified] = useState(false);
  if (!demoCovers(company, period)) {
    return <DemoUnavailable company={company} period={period} />;
  }
  return (
    <>
      <PageHeader eyebrow={`Obrigação e entrega · ${company.name} · ${period}`} title="Transmissão não é aceite; protocolo não é recibo." description="A obrigação mantém versão de regra, arquivos, retorno e evidências em estados separados para não criar falsa segurança." action={<button className="button button--secondary" type="button" onClick={() => onEvidence("Matriz de cobertura · obrigação ECD · SP · regra v2025.1")}>Ver cobertura</button>} />
      <section className="panel obligation-card"><div className="obligation-header"><div><span className="eyebrow">ECD · {company.name}</span><h2>Competência {period}</h2><p>Regra v2025.1 · layout 9.0 · jurisdição configurada para demonstração</p></div><StatusBadge tone={state === "aceite confirmado" ? "success" : state === "protocolo recebido" ? "info" : "attention"} label={state} /></div><div className="obligation-path">{states.map((item, itemIndex) => <div key={item} className={`obligation-step ${itemIndex <= index ? "obligation-step--reached" : ""}`}><span>{itemIndex + 1}</span><b>{item}</b></div>)}</div><div className="obligation-body"><div><span className="eyebrow">Evidências disponíveis</span><ul className="clean-list"><li>Arquivo preparado · ECD-2025-01-ORBE.zip</li><li>Pré-validação · REG-ECF-091</li><li>Versão de regra · v2025.1</li><li>Responsável · Lucas Barros</li></ul><button className="inline-action" type="button" onClick={() => onEvidence("REG-ECF-091 · arquivo, regra, relatório, protocolo e recibo")}>Abrir conjunto de evidências →</button></div><div className="obligation-callout"><span className="eyebrow">Próximo passo</span><h3>{next ? nextLabel[state] : "Entrega documentada"}</h3><p>{next ? "Esta ação demonstra uma mudança de estado local. Nenhum órgão ou conector será acionado." : "O aceite é demonstrativo e não representa uma confirmação externa real."}</p><button className="button" type="button" disabled={!next} onClick={() => { if (next) { onAdvance(next); onNotice("Estado atualizado", `A obrigação agora está em “${next}” apenas na demonstração.`); } }}>{next ? nextLabel[state] : "Concluído"}</button></div></div></section>
      <section className="delivery-subgrid"><article className="panel delivery-card"><span className="eyebrow">Calendário da competência</span><h2>Próximos marcos</h2><div className="delivery-line"><b>Hoje · 16:30</b><span>Revisão interna da pré-validação</span></div><div className="delivery-line"><b>Amanhã · 10:00</b><span>Conferência da responsável contábil</span></div><div className="delivery-line"><b>Após recibo</b><span>Comunicação e pacote ao cliente</span></div></article><article className="panel delivery-card"><div className="panel-heading"><div><span className="eyebrow">Comunicação ao cliente</span><h2>Confirmação de entrega</h2></div><StatusBadge tone={clientNotified ? "success" : "attention"} label={clientNotified ? "cliente notificado" : "não notificado"} /></div><p>Leitura e contestação são eventos próprios; não substituem protocolo nem recibo.</p><button className="button button--secondary" type="button" disabled={clientNotified} onClick={() => { setClientNotified(true); onNotice("Aviso preparado", "A notificação ao cliente foi registrada apenas na demonstração; nenhuma mensagem foi enviada."); }}>{clientNotified ? "Aviso registrado" : "Preparar aviso (demo)"}</button></article></section>
    </>
  );
}

function IntegrationsPage({ company, period, items, onRetry, onEvidence }: ContextProps & { items: Integration[]; onRetry: (id: string) => void; onEvidence: (value: string) => void }) {
  if (!demoCovers(company, period)) {
    return <DemoUnavailable company={company} period={period} />;
  }
  return (
    <>
      <PageHeader eyebrow={`Integrações observáveis · ${company.name} · ${period}`} title="Conector também é um objeto de trabalho." description="Cada integração mostra escopo, frescor, fila, tentativa e alternativa segura. A tela evita prometer cobertura ou sincronismo em tempo real." action={<button className="button button--secondary" type="button" onClick={() => onEvidence("Catálogo de conectores · escopos, consentimentos e estado de homologação")}>Gerenciar conectores</button>} />
      <section className="integration-grid">{items.map((item) => <article className="panel integration-card" key={item.id}><div className="panel-heading"><div><span className="eyebrow">{item.kind}</span><h2>{item.name}</h2></div><StatusBadge tone={item.tone} label={item.health} /></div><dl className="integration-data"><div><dt>Escopo</dt><dd>{item.scope}</dd></div><div><dt>Última atualização</dt><dd>{item.lastSync}</dd></div><div><dt>Fila</dt><dd>{item.queue}</dd></div></dl><div className="integration-note">{item.detail}</div><div className="integration-footer"><span>Fallback: {item.fallback}</span><div><button className="inline-action" type="button" onClick={() => onEvidence(`${item.name} · escopo, sincronização, fila e log de tentativas`)}>Ver log →</button><button className="text-button" type="button" onClick={() => onRetry(item.id)}>Nova tentativa</button></div></div></article>)}</section>
    </>
  );
}

function EvidenceLibraryPage({ company, period, onEvidence, onNotice }: ContextProps & { onEvidence: (value: string) => void; onNotice: (title: string, detail: string) => void }) {
  if (!demoCovers(company, period)) {
    return <DemoUnavailable company={company} period={period} />;
  }
  const documents = [
    ["Pacote de fechamento", "PKG-2025-01-ORBE", "Em preparação", "attention" as Tone, "Checklist, snapshot, ledger, conciliações, obrigação e manifesto"],
    ["Lote de migração", "IMP-2025-01-018", "Requer revisão", "danger" as Tone, "Arquivo original, hash, mapeamento v4 e relatório de diferenças"],
    ["Solicitação ao cliente", "DOC-483", "Aguardando leitura", "attention" as Tone, "Extrato de aplicação, prazo, destinatário e histórico de contato"],
    ["Pré-validação ECD", "REG-ECF-091", "Pronto para aprovação", "info" as Tone, "Regra v2025.1, layout, relatório e arquivo preparado"],
  ];
  return (
    <>
      <PageHeader eyebrow={`Biblioteca de evidências · ${company.name} · ${period}`} title="Evidência é parte do fluxo, não um anexo perdido." description="Documentos, eventos, regras, aprovações e pacotes são navegáveis por objeto, competência e decisão." action={<button className="button" type="button" onClick={() => onNotice("Exportação preparada", "A exportação real deverá obedecer permissões, retenção e um manifesto de integridade.")}>Preparar exportação</button>} />
      <section className="evidence-grid">{documents.map(([title, id, state, tone, description]) => <article className="panel evidence-card" key={String(id)}><div className="evidence-card__icon" aria-hidden="true">{String(title).charAt(0)}</div><div className="evidence-card__content"><span className="eyebrow">{id}</span><h2>{title}</h2><p>{description}</p><StatusBadge tone={tone as Tone} label={String(state)} /><button className="inline-action" type="button" onClick={() => onEvidence(`${id} · ${description}`)}>Abrir evidência →</button></div></article>)}</section>
      <section className="panel library-guidance"><div><span className="eyebrow">Manifesto de integridade</span><h2>Um pacote sempre declara o que contém.</h2><p>O pacote de fechamento deve informar período, regras, dados de origem, evidências, aprovações, exceções e data de corte. O protótipo ilustra o conceito, sem assinatura ou promessa jurídica.</p></div><button className="button button--secondary" type="button" onClick={() => onEvidence("Manifesto PKG-2025-01-ORBE · conteúdo, identificadores, período e data de corte")}>Ver manifesto</button></section>
    </>
  );
}

function PageHeader({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <section className="page-header"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{action && <div className="page-header__action">{action}</div>}</section>;
}

function Metric({ label, value, note, tone }: { label: string; value: string; note: string; tone: Tone }) {
  return <article className={`metric metric--${tone}`}><span>{label}</span><strong>{value}</strong><small>{note}</small></article>;
}

function StatusBadge({ tone, label }: { tone: Tone; label: string }) {
  return <span className={`status-badge status-badge--${tone}`}><i aria-hidden="true" />{label}</span>;
}

function FilterPill({ label }: { label: string }) {
  return <button className="filter-pill" type="button">{label}<span aria-hidden="true">⌄</span></button>;
}

function WorkItemRow({ item, companyName, period, onNavigate, onEvidence }: { item: WorkItem; companyName: string; period: string; onNavigate: () => void; onEvidence: (value: string) => void }) {
  return <article className="work-item"><div className={`work-item__signal work-item__signal--${item.tone}`}><span /></div><div className="work-item__body"><div className="work-item__meta"><span>{item.eyebrow}</span><time>{item.due}</time></div><h3>{item.title}</h3><p>{item.detail}</p><div className="work-item__foot"><span>{companyName} · {period}</span><span>Responsável: {item.responsible}</span></div></div><div className="work-item__actions"><button className="text-button" type="button" onClick={() => onEvidence(item.evidence)}>Evidência</button><button className="button button--compact" type="button" onClick={onNavigate}>{item.action}</button></div></article>;
}

function Deadline({ name, meta, tone }: { name: string; meta: string; tone: Tone }) {
  const severity = tone === "danger" ? "Urgente" : tone === "attention" ? "Atenção" : "Informativo";
  return <div className="deadline"><span className={`deadline-dot deadline-dot--${tone}`} aria-hidden="true" /><div><strong>{name}</strong><span>{meta}</span><em>{severity}</em></div></div>;
}

function CloseTaskRow({ task, onResolve, onEvidence }: { task: CloseTask; onResolve: (id: string, resolution: string) => void; onEvidence: (value: string) => void }) {
  const [resolving, setResolving] = useState(false);
  const [resolution, setResolution] = useState("");
  const label = task.blocker ? "Resolver bloqueio" : "Registrar decisão";
  return <article className="checklist-row"><div className={`check-icon check-icon--${task.tone}`}>{task.state === "concluído" ? "✓" : "!"}</div><div className="checklist-row__main"><div className="checklist-row__title"><span>{task.domain}</span><h3>{task.title}</h3></div><p>{task.detail}</p><div className="checklist-row__meta"><span>{task.responsible}</span><span>{task.updatedAt}</span><button className="inline-action" type="button" onClick={() => onEvidence(task.evidence)}>Ver evidência →</button></div>{task.resolution && <div className="resolution-record"><strong>Decisão: </strong>{task.resolution}<span> · {task.resolvedBy} · {task.updatedAt}</span></div>}{resolving && <div className="resolution-form"><label htmlFor={`resolution-${task.id}`}>Motivo e evidência da decisão<textarea id={`resolution-${task.id}`} value={resolution} onChange={(event) => setResolution(event.target.value)} placeholder="Ex.: extrato conferido no portal do cliente; DOC-483 anexado." /></label><div><button className="text-button" type="button" onClick={() => { setResolving(false); setResolution(""); }}>Cancelar</button><button className="button button--compact" type="button" disabled={!resolution.trim()} onClick={() => { onResolve(task.id, resolution.trim()); setResolving(false); setResolution(""); }}>Confirmar decisão</button></div></div>}</div><div className="checklist-row__state"><StatusBadge tone={task.tone} label={task.state} />{task.state !== "concluído" && <button className="text-button" type="button" onClick={() => setResolving(true)}>{label}</button>}</div></article>;
}

function EvidenceDrawer({ evidence, onClose }: { evidence: string; onClose: () => void }) {
  const panelRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  useEffect(() => {
    previousFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeButtonRef.current?.focus();
    const onEscape = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    document.addEventListener("keydown", onEscape);
    return () => { document.removeEventListener("keydown", onEscape); previousFocus.current?.focus(); };
  }, [onClose]);
  const trapFocus = (event: ReactKeyboardEvent<HTMLElement>) => {
    if (event.key !== "Tab") return;
    const focusable = Array.from(panelRef.current?.querySelectorAll<HTMLElement>("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])") ?? []).filter((item) => !item.hasAttribute("disabled"));
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  };
  return <aside ref={panelRef} className="evidence-drawer" role="dialog" aria-modal="true" aria-labelledby="evidence-drawer-title" onKeyDown={trapFocus}><div className="drawer-heading"><div><span className="eyebrow">Painel de evidências</span><h2 id="evidence-drawer-title">Rastreabilidade do objeto</h2></div><button ref={closeButtonRef} className="icon-button" type="button" onClick={onClose} aria-label="Fechar painel">×</button></div><div className="evidence-object"><span>Objeto selecionado</span><strong>{evidence}</strong></div><div className="evidence-chain"><span className="eyebrow">Cadeia demonstrativa</span><EvidenceStep label="Fonte preservada" meta="Arquivo, integração ou usuário de origem" /><EvidenceStep label="Regra identificada" meta="Versão e critério vinculados à decisão" /><EvidenceStep label="Ação rastreada" meta="Ator, horário e motivo quando aplicável" /><EvidenceStep label="Próximo passo" meta="Abrir detalhe, revisar ou exportar o pacote" /></div><div className="drawer-note"><strong>Ambiente de demonstração</strong><p>Este painel usa dados sintéticos. A integração futura deve expor somente dados autorizados pelo tenant e pelo papel do usuário.</p></div><button className="button button--secondary drawer-close" type="button" onClick={onClose}>Voltar ao trabalho</button></aside>;
}

function EvidenceStep({ label, meta }: { label: string; meta: string }) {
  return <div className="evidence-step"><span>✓</span><div><strong>{label}</strong><small>{meta}</small></div></div>;
}

function ToastMessage({ toast, onDismiss }: { toast: Exclude<Toast, null>; onDismiss: () => void }) {
  return <div className="toast" role="status"><div><strong>{toast.title}</strong><p>{toast.detail}</p></div><button className="icon-button" type="button" onClick={onDismiss} aria-label="Fechar mensagem">×</button></div>;
}
