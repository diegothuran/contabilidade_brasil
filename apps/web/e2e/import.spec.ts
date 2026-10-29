import { expect, test } from "@playwright/test";
import { chooseCompany, choosePeriod } from "./company";

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

test("simula um lote e o aprovador publica o relatório", async ({ page }) => {
  const source = `e2e-${Date.now()}`;
  const csv = [
    "external_journal_id;entry_date;description;account_code;side;amount;line_description;cost_center_code",
    "e2e-1;2026-01-15;Compra e2e;5.1.01;debit;10.00;Despesa;",
    "e2e-1;2026-01-15;Compra e2e;2.1.01;credit;10.00;Fornecedor;",
    "",
  ].join("\n");

  await login(page, "preparer");
  await chooseCompany(page, "Empresa Alfa");
  await page.locator(".sidebar").getByRole("link", { name: "Migrações" }).click();
  await page.getByTestId("import-source").fill(source);
  await choosePeriod(page, "01/2026");
  await page.getByTestId("import-file").setInputFiles({
    name: "lote.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(csv),
  });
  await page.getByTestId("create-batch").click();
  await expect(page.getByTestId("batch-status")).toHaveText("Pronto", { timeout: 30_000 });
  await page.getByRole("button", { name: "Sair" }).click();
  await expect(page.getByTestId("login-button")).toBeVisible();

  await login(page, "approver");
  await chooseCompany(page, "Empresa Alfa");
  await page.locator(".sidebar").getByRole("link", { name: "Migrações" }).click();
  await page.getByRole("link", { name: source }).click();
  await page.getByTestId("publish-batch").click();
  await expect(page.getByTestId("import-report")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("batch-status")).toHaveText("Publicado");
});
