import { expect, test } from "@playwright/test";
import { chooseCompany, choosePeriod } from "./company";

test("a prévia da EFD-Reinf da Empresa Alfa recebe um pagamento fictício e sai marcada como não transmissível", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("login-button").click();
  await page.locator("#username").fill("preparer");
  await page.locator("#password").fill("dev-only-password");
  await page.locator("#kc-login").click();
  await page.waitForURL("**/app/rastro");
  await chooseCompany(page, "Empresa Alfa");
  await choosePeriod(page, "12/2026");

  await page.locator(".sidebar").getByRole("link", { name: "Relatórios" }).click();
  await page.getByTestId("link-reinf").click();
  await expect(page.getByRole("heading", { name: "Prévia da EFD-Reinf" })).toBeVisible();
  await expect(page.getByTestId("reinf-notice")).toHaveText("Prévia para conferência. Não assinar nem transmitir.");

  // Pagamento fictício a pessoa jurídica: CNPJ de teste, natureza da Tabela 01 da prévia.
  const form = page.getByTestId("reinf-form");
  await form.getByTestId("reinf-kind").selectOption("pj");
  await form.getByTestId("reinf-document").fill("11.222.333/0001-81");
  await form.getByTestId("reinf-name").fill("Fornecedor Fictício Ltda");
  await expect(form.getByTestId("reinf-nature").locator("option[value='15015']")).toHaveCount(1);
  await form.getByTestId("reinf-nature").selectOption("15015");
  await form.getByTestId("reinf-date").fill("2026-12-10");
  await form.getByTestId("reinf-gross").fill("1000,00");
  await form.getByTestId("reinf-ir-base").fill("1000,00");
  await form.getByTestId("reinf-ir-amount").fill("15,00");
  await form.getByTestId("reinf-save").click();

  const row = page.getByTestId("reinf-payment-row").filter({ hasText: "Fornecedor Fictício Ltda" }).first();
  await expect(row).toContainText("11.***.***/0001-**");
  await expect(row).not.toContainText("11.222.333");

  await page.getByTestId("reinf-generate-button").click();
  const issues = page.getByTestId("reinf-issues");
  await expect(issues).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("reinf-checks")).toContainText("XSD");
  await expect(page.getByTestId("reinf-result")).toContainText("não transmissível");

  const download = page.waitForEvent("download");
  await page.getByTestId("reinf-download").click();
  expect((await download).suggestedFilename()).toMatch(/^REINF-R4000-PREVIA-[0-9A-Z]{14}-202612\.zip$/);

  await row.getByTestId("reinf-delete").click();
  await row.getByTestId("reinf-delete-confirm").click();
  await expect(page.getByTestId("reinf-payment-row").filter({ hasText: "Fornecedor Fictício Ltda" })).toHaveCount(0);
});
