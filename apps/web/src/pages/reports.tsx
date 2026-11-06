import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";
import { api } from "../api";
import { formatCnpj, formatPeriod } from "../format";
import { useSession } from "../session";

export const DISCLAIMER = "Relatório gerencial gerado pelo sistema. Não é livro contábil oficial.";

export type Period = { period_id: string; fiscal_year: number; month: number; status?: string };

// Soma de strings decimais em micros (6 casas, como a API), sem float.
export function sum(values: string[]): string {
  const micros = values.reduce((total, value) => {
    const negative = value.startsWith("-");
    const [whole, fraction = ""] = value.replace("-", "").split(".");
    const amount = BigInt((whole || "0") + (fraction + "000000").slice(0, 6));
    return total + (negative ? -amount : amount);
  }, 0n);
  const negative = micros < 0n;
  const absolute = negative ? -micros : micros;
  const text = `${absolute / 1000000n}.${(absolute % 1000000n).toString().padStart(6, "0")}`;
  return negative ? `-${text}` : text;
}

export function isZero(value: string): boolean {
  return /^-?0*(\.0*)?$/.test(value);
}

// A classe no body diz ao CSS de impressão qual bloco sai no papel.
export function printOnly(target: string) {
  const className = `print-${target}`;
  document.body.classList.add(className);
  const cleanup = () => {
    document.body.classList.remove(className);
    window.removeEventListener("afterprint", cleanup);
  };
  window.addEventListener("afterprint", cleanup);
  window.print();
}

export function ReportHeading({ title, entity, period, issuedAt }: { title: string; entity: string; period: string; issuedAt: string }) {
  return (
    <div className="report-print-heading">
      <strong>{title}</strong>
      <span>{entity}</span>
      <span>Competência: {period} · Emitido em {issuedAt}</span>
    </div>
  );
}

const REPORTS = [
  { to: "/app/rastro/balancete", label: "Balancete" },
  { to: "/app/rastro/dre", label: "DRE" },
  { to: "/app/rastro/balanco", label: "Balanço" },
] as const;

export function ReportSwitcher() {
  const location = useLocation();
  return (
    <nav className="report-switcher" aria-label="Relatórios">
      {REPORTS.map((report) => {
        const current = location.pathname === report.to || (report.to.endsWith("balancete") && location.pathname === "/app/trial-balance");
        return (
          <Link key={report.to} to={report.to} aria-current={current ? "page" : undefined}>
            {report.label}
          </Link>
        );
      })}
    </nav>
  );
}

export function useReportContext() {
  const { entityId, periodId, entities } = useSession();
  const entity = entities.find((item) => item.legal_entity_id === entityId);
  const periods = useQuery({
    queryKey: ["periods", entityId],
    enabled: Boolean(entityId),
    queryFn: () => api<{ items: Period[] }>(`/v1/legal-entities/${entityId}/periods`),
  });
  const period = periods.data?.items.find((item) => item.period_id === periodId);
  return {
    entityId,
    periodId,
    period,
    entityText: entity ? `${entity.name} · CNPJ ${formatCnpj(entity.cnpj)}` : "Empresa",
    periodText: period ? formatPeriod(period.fiscal_year, period.month) : "competência escolhida",
    issuedAt: new Date().toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }),
  };
}
