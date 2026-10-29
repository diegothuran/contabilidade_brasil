import { expect, test } from "@playwright/test";
import { chooseCompany, choosePeriod } from "./company";

test("o balancete mostra saldos, abre o razão, baixa CSV e imprime sem o menu", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("login-button").click();
  await page.locator("#username").fill("preparer");
  await page.locator("#password").fill("dev-only-password");
  await page.locator("#kc-login").click();
  await page.waitForURL("**/app/rastro");
  await chooseCompany(page, "Empresa Alfa");
  await choosePeriod(page, "02/2026");

  await page.locator(".sidebar").getByRole("link", { name: "Balancete e razão" }).click();
  await expect(page.getByRole("heading", { name: "Balancete" })).toBeVisible();
  await expect(page.getByTestId("print-balancete")).toBeVisible();
  await expect(page.getByTestId("csv-balancete")).toBeVisible();
  await expect(page.getByTestId("balance-difference")).toContainText("Débitos e créditos fecham");

  const balanceDownload = page.waitForEvent("download");
  await page.getByTestId("csv-balancete").click();
  expect((await balanceDownload).suggestedFilename()).toMatch(/^balancete-\d{14}-2026-02\.csv$/);

  // A base da CI pode não ter movimento: mostrar todas as contas garante uma para abrir.
  await page.getByLabel("Só contas com saldo ou movimento").uncheck();
  await page.locator(".report-link").first().click();
  const ledger = page.getByTestId("ledger-panel");
  await expect(ledger).toContainText("Saldo anterior");
  await expect(ledger).toContainText("Saldo atual");
  const ledgerDownload = page.waitForEvent("download");
  await page.getByTestId("csv-razao").click();
  expect((await ledgerDownload).suggestedFilename()).toMatch(/^razao-.+-2026-02\.csv$/);

  await page.emulateMedia({ media: "print" });
  await expect(page.locator(".sidebar")).toBeHidden();
  await expect(page.getByTestId("print-balancete")).toBeHidden();
  await expect(page.locator(".report-print-heading").first()).toBeVisible();
});
