import { useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { rankCompanies } from "./companyMatch";
import { formatCnpj } from "../format";
import type { Entity } from "../session";

const FOCUS_EVENT = "rastro-focus-company-search";

export function focusCompanySearch(): void {
  window.dispatchEvent(new Event(FOCUS_EVENT));
}

function initials(name: string): string {
  const parts = name.split(" ").filter((part) => part && part !== "(teste)").slice(0, 2);
  return parts.map((part) => part[0]?.toUpperCase() ?? "").join("") || "E";
}

export function CompanySearch({
  entities,
  entityId,
  setEntityId,
  isAdmin,
}: {
  entities: Entity[];
  entityId: string;
  setEntityId: (entityId: string) => void;
  isAdmin: boolean;
}) {
  const listId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const selected = entities.find((entity) => entity.legal_entity_id === entityId);
  const results = rankCompanies(entities, query).slice(0, 8);
  const activeIndex = results.length === 0 ? 0 : Math.min(active, results.length - 1);

  useEffect(() => {
    function focus() {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
    function onKey(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        focus();
      }
    }
    window.addEventListener(FOCUS_EVENT, focus);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener(FOCUS_EVENT, focus);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  useEffect(() => {
    function onPointer(event: MouseEvent) {
      if (!boxRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onPointer);
    return () => document.removeEventListener("mousedown", onPointer);
  }, []);

  function choose(nextId: string) {
    setEntityId(nextId);
    setQuery("");
    setOpen(false);
    inputRef.current?.blur();
  }

  return (
    <>
      <div className="company-current" data-testid="current-company">
        <span className="company-mark" aria-hidden="true">{selected ? initials(selected.name) : "—"}</span>
        <span>
          <strong>{selected ? selected.name : "Nenhuma empresa"}</strong>
          <small>{selected ? formatCnpj(selected.cnpj) : "Cadastre uma empresa para começar"}</small>
        </span>
      </div>
      <div className="company-search" ref={boxRef}>
        <label>
          <span className="sr-only">Buscar empresa</span>
          <input
            ref={inputRef}
            data-testid="company-search"
            role="combobox"
            aria-expanded={open && query.trim().length > 0}
            aria-controls={listId}
            aria-autocomplete="list"
            placeholder="Buscar empresa"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setActive(0);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            onKeyDown={(event) => {
              if (event.key === "ArrowDown") {
                event.preventDefault();
                setOpen(true);
                setActive((current) => Math.min(current + 1, Math.max(results.length - 1, 0)));
              } else if (event.key === "ArrowUp") {
                event.preventDefault();
                setActive((current) => Math.max(current - 1, 0));
              } else if (event.key === "Enter" && results[activeIndex]) {
                event.preventDefault();
                choose(results[activeIndex].legal_entity_id);
              } else if (event.key === "Escape") {
                setQuery("");
                setOpen(false);
              }
            }}
          />
        </label>
        {open && query.trim() ? (
          <div className="company-results" id={listId} role="listbox">
            {results.length === 0 ? <p className="muted">Nenhuma empresa com esse termo.</p> : null}
            {results.map((entity, index) => (
              <button
                key={entity.legal_entity_id}
                type="button"
                role="option"
                aria-selected={entity.legal_entity_id === entityId}
                className={index === activeIndex ? "company-result company-result--active" : "company-result"}
                data-testid="company-result"
                onMouseEnter={() => setActive(index)}
                onClick={() => choose(entity.legal_entity_id)}
              >
                <strong>{entity.name}</strong>
                <span>{formatCnpj(entity.cnpj)}{entity.legal_entity_id === entityId ? " · selecionada" : ""}</span>
              </button>
            ))}
            {isAdmin ? (
              <Link className="company-create" to="/app/companies/new" onClick={() => setOpen(false)}>
                Nova empresa
              </Link>
            ) : null}
          </div>
        ) : null}
      </div>
    </>
  );
}
