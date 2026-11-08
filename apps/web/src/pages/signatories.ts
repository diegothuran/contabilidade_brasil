// Signatários das demonstrações (ADR 030): o contador responsável e o representante legal.

export type StatementSignatory = { name: string; caption: string };
export type StatementSignatories = {
  accountant: StatementSignatory | null;
  legal_representative: StatementSignatory | null;
} | null;

export const UFS = [
  "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
  "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
] as const;

export const CRC_CATEGORIES = [
  ["contador", "Contador"],
  ["tecnico", "Técnico em contabilidade"],
] as const;

export const LEGAL_REP_ROLES = [
  ["socio_administrador", "Sócio-administrador"],
  ["administrador", "Administrador"],
  ["diretor", "Diretor"],
  ["titular", "Titular"],
] as const;

export function signaturesPath(entityId: string): string {
  return `/app/rastro/empresas/${entityId}/assinaturas`;
}
