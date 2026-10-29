export function formatCnpj(value: string): string {
  const digits = value.replace(/\D/g, "");
  if (digits.length !== 14) {
    return value || "Sem CNPJ";
  }
  return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5, 8)}/${digits.slice(8, 12)}-${digits.slice(12)}`;
}

const MONTHS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];

function groupThousands(digits: string): string {
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

// Os valores chegam da API como string decimal ("-1234.5"); a tela mostra "-1.234,50" sem passar por float.
export function formatMoney(value: string): string {
  const negative = value.startsWith("-");
  const [whole, fraction = ""] = value.replace("-", "").split(".");
  const micros = BigInt((whole || "0") + (fraction + "000000").slice(0, 6));
  const cents = (micros + 5000n) / 10000n;
  const text = `${groupThousands((cents / 100n).toString())},${(cents % 100n).toString().padStart(2, "0")}`;
  return negative && text !== "0,00" ? `-${text}` : text;
}

// Saldo com natureza: positivo é devedor (D), negativo é credor (C).
export function formatBalance(value: string): string {
  const text = formatMoney(value).replace("-", "");
  if (text === "0,00") {
    return "0,00";
  }
  return `${text} ${value.startsWith("-") ? "C" : "D"}`;
}

export function formatDate(iso: string): string {
  const [year, month, day] = iso.slice(0, 10).split("-");
  return `${day}/${month}/${year}`;
}

export function formatPeriod(year: number, month: number): string {
  return `${MONTHS[month - 1]} de ${year}`;
}
