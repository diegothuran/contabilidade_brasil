export type CompanyMatch = {
  name: string;
  cnpj: string;
};

function fold(value: string): string {
  return value.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
}

function digitsOf(value: string): string {
  return value.replace(/\D/g, "");
}

function isSubsequence(query: string, target: string): boolean {
  let index = 0;
  for (const char of target) {
    if (char === query[index]) {
      index += 1;
      if (index === query.length) {
        return true;
      }
    }
  }
  return false;
}

function editDistance(left: string, right: string): number {
  const rows = left.length + 1;
  const cols = right.length + 1;
  const grid = Array.from({ length: rows }, () => Array<number>(cols).fill(0));
  for (let row = 0; row < rows; row += 1) {
    grid[row][0] = row;
  }
  for (let col = 0; col < cols; col += 1) {
    grid[0][col] = col;
  }
  for (let row = 1; row < rows; row += 1) {
    for (let col = 1; col < cols; col += 1) {
      const cost = left[row - 1] === right[col - 1] ? 0 : 1;
      grid[row][col] = Math.min(grid[row - 1][col] + 1, grid[row][col - 1] + 1, grid[row - 1][col - 1] + cost);
    }
  }
  return grid[left.length][right.length];
}

function tokenScore(token: string, name: string, cnpj: string): number {
  const folded = fold(token);
  const digits = digitsOf(token);
  if (digits.length >= 2 && cnpj.includes(digits)) {
    return 92;
  }
  if (!folded || /^\d+$/.test(folded)) {
    return 0;
  }
  if (name.startsWith(folded)) {
    return 100;
  }
  if (name.includes(folded)) {
    return 84;
  }
  const words = name.split(/[^a-z0-9]+/).filter(Boolean);
  let nearest = 0;
  for (const word of words) {
    if (Math.abs(word.length - folded.length) > 2) {
      continue;
    }
    const distance = editDistance(folded, word);
    const limit = folded.length <= 4 ? 1 : 2;
    if (distance > 0 && distance <= limit) {
      nearest = Math.max(nearest, 62 - distance * 8);
    }
  }
  if (nearest > 0) {
    return nearest;
  }
  if (folded.length >= 2 && isSubsequence(folded, name.replace(/[^a-z0-9]+/g, ""))) {
    return 48;
  }
  return 0;
}

export function rankCompanies<T extends CompanyMatch>(companies: T[], query: string): T[] {
  const tokens = query.trim().split(/\s+/).filter(Boolean);
  if (tokens.length === 0) {
    return [];
  }
  const ranked = companies.flatMap((company) => {
    const name = fold(company.name);
    const cnpj = digitsOf(company.cnpj);
    let score = 0;
    for (const token of tokens) {
      const tokenRank = tokenScore(token, name, cnpj);
      if (tokenRank === 0) {
        return [];
      }
      score += tokenRank;
    }
    return [{ company, score }];
  });
  ranked.sort((left, right) => right.score - left.score || left.company.name.localeCompare(right.company.name, "pt"));
  return ranked.map((item) => item.company);
}
