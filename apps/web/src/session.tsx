import { createContext, useContext } from "react";

export type Me = {
  user_id: string;
  display_name: string;
  tenant_name: string;
  roles: string[];
};

export type Entity = {
  legal_entity_id: string;
  name: string;
  cnpj: string;
  currency: string;
};

export type SessionValue = {
  me: Me;
  entities: Entity[];
  entityId: string;
  setEntityId: (entityId: string) => void;
  periodId: string;
  setPeriodId: (periodId: string) => void;
};

const SessionContext = createContext<SessionValue | null>(null);

export const SessionProvider = SessionContext.Provider;

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) {
    throw new Error("sessão ausente");
  }
  return value;
}

export function can(roles: string[], ...needed: string[]): boolean {
  return needed.some((role) => roles.includes(role));
}

export const STATUS_LABEL: Record<string, string> = {
  draft: "Rascunho",
  pending_approval: "Pendente",
  approved: "Aprovado",
  published: "Publicado",
  reversed: "Revertido",
  rejected: "Rejeitado",
  open: "Aberto",
  closed: "Fechado",
  reopened: "Reaberto",
  closing: "Fechando",
  received: "Recebido",
  suggested: "Sugerido",
  ignored: "Ignorado",
  parsed: "Lido",
  validating: "Validando",
  ready: "Pronto",
  partially_published: "Publicado parcial",
  failed: "Falhou",
  rolled_back: "Revertido",
};
