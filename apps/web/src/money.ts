const SCALE = 1_000_000n;

export function parseAmount(value: string): bigint | null {
  const match = /^(\d+)(?:\.(\d{1,6}))?$/.exec(value.trim());
  if (!match) {
    return null;
  }
  const scaled = BigInt(match[1]) * SCALE + BigInt((match[2] ?? "").padEnd(6, "0"));
  return scaled > 0n ? scaled : null;
}

export function formatAmount(value: bigint): string {
  const negative = value < 0n;
  const absolute = negative ? -value : value;
  const whole = absolute / SCALE;
  const fraction = (absolute % SCALE).toString().padStart(6, "0").replace(/0+$/, "");
  const text = fraction ? `${whole}.${fraction}` : `${whole}`;
  return negative ? `-${text}` : text;
}

export function addAmounts(values: string[]): string {
  let total = 0n;
  for (const value of values) {
    const parsed = parseAmount(value);
    if (parsed !== null) {
      total += parsed;
    }
  }
  return formatAmount(total);
}
