import { expect, test } from "@playwright/test";

function cnpjFromBase(base12: string): string {
  const digit = (numbers: string) => {
    const weights = numbers.length === 12 ? [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2] : [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
    const total = [...numbers].reduce((sum, char, index) => sum + Number(char) * weights[index], 0);
    const remainder = total % 11;
    return remainder < 2 ? "0" : String(11 - remainder);
  };
  const first = digit(base12);
  return base12 + first + digit(base12 + first);
}

async function login(page: import("@playwright/test").Page, username: string) {
  await page.goto("/");
  await page.getByTestId("login-button").click();
  await page.locator("#username").fill(username);
  await page.locator("#password").fill("dev-only-password");
  await page.locator("#kc-login").click();
  await page.waitForURL("**/app/rastro");
  await page.goto("/app/journals");
  await expect(page.getByRole("heading", { name: "Lançamentos" })).toBeVisible();
}

test("cria, aprova e publica um lançamento", async ({ page }) => {
  const description = `E2E ${Date.now()}`;
  await login(page, "preparer");
  await page.getByTestId("entity-select").selectOption({ label: "Empresa Alfa" });
  await page.getByRole("link", { name: "Novo lançamento" }).click();
  await page.getByTestId("journal-description").fill(description);
  await page.getByTestId("line-account-0").selectOption({ label: "5.1.01 Despesas de serviços" });
  await page.getByTestId("line-amount-0").fill("25.00");
  await page.getByTestId("line-account-1").selectOption({ label: "2.1.01 Fornecedores" });
  await page.getByTestId("line-amount-1").fill("25.00");
  await page.getByTestId("save-journal").click();
  await page.getByTestId("submit-journal").click();
  await expect(page.getByTestId("journal-status")).toHaveText("Pendente");
  await page.getByRole("button", { name: "Sair" }).click();
  await expect(page.getByTestId("login-button")).toBeVisible();

  await login(page, "approver");
  await page.getByTestId("entity-select").selectOption({ label: "Empresa Alfa" });
  await page.getByRole("link", { name: description }).click();
  await page.getByTestId("approve-journal").click();
  await page.getByTestId("publish-journal").click();
  await expect(page.getByTestId("journal-status")).toHaveText("Publicado");
});

test("admin cadastra uma empresa", async ({ page }) => {
  const name = `E2E Empresa ${Date.now()}`;
  const base = String(Date.now()).slice(-12).padStart(12, "1");
  await page.goto("/");
  await page.getByTestId("login-button").click();
  await page.locator("#username").fill("admin");
  await page.locator("#password").fill("dev-only-password");
  await page.locator("#kc-login").click();
  await page.waitForURL("**/app/rastro");
  await page.goto("/app/companies/new");
  await page.getByTestId("company-name").fill(name);
  await page.getByTestId("company-cnpj").fill(cnpjFromBase(base));
  await page.getByTestId("company-year").fill("2026");
  await page.getByTestId("save-company").click();
  await expect(page.getByRole("heading", { name: "Plano de contas" })).toBeVisible();
  await expect(page.getByTestId("entity-select")).toContainText(name);
});
