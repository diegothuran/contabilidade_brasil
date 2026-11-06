import { expect, test } from "@playwright/test";
import { chooseCompany, choosePeriod } from "./company";

test("relatórios trocam entre balancete, DRE e balanço, e dezembro oferece o encerramento", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("login-button").click();
  await page.locator("#username").fill("preparer");
  await page.locator("#password").fill("dev-only-password");
  await page.locator("#kc-login").click();
  await page.waitForURL("**/app/rastro");
  await chooseCompany(page, "Empresa Alfa");
  await choosePeriod(page, "12/2026");

  await page.locator(".sidebar").getByRole("link", { name: "Relatórios" }).click();
  await expect(page.getByRole("heading", { name: "Balancete" })).toBeVisible();
  const closing = page.getByTestId("year-end-closing");
  await expect(closing).toContainText("Encerramento do exercício 2026");
  await expect(closing.getByRole("combobox")).toContainText("Lucros ou prejuízos acumulados");
  await expect(closing.getByRole("button", { name: "Gerar rascunho do encerramento" })).toBeEnabled();

  const switcher = page.getByRole("navigation", { name: "Relatórios" });
  await switcher.getByRole("link", { name: "DRE" }).click();
  await expect(page.getByRole("heading", { name: "DRE" })).toBeVisible();
  await expect(page.getByTestId("print-dre")).toBeVisible();
  await expect(page.getByTestId("income-result")).toBeVisible();
  const dre = page.waitForEvent("download");
  await page.getByTestId("csv-dre").click();
  expect((await dre).suggestedFilename()).toMatch(/^dre-\d{14}-2026-12\.csv$/);

  await switcher.getByRole("link", { name: "Balanço" }).click();
  await expect(page.getByRole("heading", { name: "Balanço" })).toBeVisible();
  await expect(page.getByTestId("balance-sheet-difference")).toContainText("Ativo igual a passivo + PL");
  const sheet = page.waitForEvent("download");
  await page.getByTestId("csv-balanco").click();
  expect((await sheet).suggestedFilename()).toMatch(/^balanco-\d{14}-2026-12\.csv$/);

  await page.emulateMedia({ media: "print" });
  await expect(page.locator(".sidebar")).toBeHidden();
  await expect(page.getByTestId("print-balanco")).toBeHidden();
  await expect(page.locator(".report-print-heading")).toBeVisible();
});
