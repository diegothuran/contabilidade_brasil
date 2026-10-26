import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ApiError, api } from "./api";
import { userManager } from "./auth";
import { RastroShell } from "./rastro/RastroShell";
import "./rastro/rastro.css";
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
    return <LoginScreen pending />;
  }
  if (!signedIn) {
    return <LoginScreen />;
  }
  return <Shell />;
}

function LoginScreen({ pending = false }: { pending?: boolean }) {
  return (
    <main className="rastro login-screen">
      <LoginBrand />
      <section className="login-panel">
        <div className="panel login-card" aria-busy={pending}>
          <span className="eyebrow">Acesso</span>
          <h2>Entre no escritório</h2>
          {pending ? (
            <p>Carregando sessão…</p>
          ) : (
            <>
              <p>Use o usuário do escritório. A sala de fechamento abre em seguida.</p>
              <button type="button" className="button" data-testid="login-button" onClick={() => void userManager.signinRedirect()}>
                Entrar
              </button>
            </>
          )}
        </div>
      </section>
    </main>
  );
}

function LoginBrand() {
  return (
    <section className="login-brand">
      <div className="brand-lockup">
        <div className="brand-mark" aria-hidden="true"><span>R</span><i /></div>
        <div>
          <strong>Rastro</strong>
          <small>fechamento com evidência</small>
        </div>
      </div>
      <div className="login-brand__copy">
        <h1>O fechamento do escritório, com a evidência ao lado.</h1>
        <ul className="login-points">
          <li><span>H</span>Fila do dia e o que bloqueia o mês</li>
          <li><span>C</span>Conciliação com a decisão registrada</li>
          <li><span>E</span>Documento, hash e trilha no mesmo lugar</li>
        </ul>
      </div>
    </section>
  );
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
  const items = entities.data.items;
  const selectedId = items.some((item) => item.legal_entity_id === entityId) ? entityId : "";
  if (items.length > 0 && !selectedId) {
    return <p className="muted">Carregando escritório…</p>;
  }

  return (
    <SessionProvider value={{ me: me.data, entities: items, entityId: selectedId, setEntityId }}>
      <RastroShell />
    </SessionProvider>
  );
}
