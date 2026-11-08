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
  const signatures = page.getByTestId("report-signatures");
  await expect(signatures).toContainText("Aprovador");
  await expect(signatures).toContainText("Contador, CRC-PE 012345/O");
  await expect(signatures).toContainText("Sócio-administrador");
  await expect(page.getByTestId("signatures-missing")).toHaveCount(0);
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
  await expect(page.getByTestId("report-signatures")).toBeVisible();
  await expect(page.getByTestId("report-signatures")).toContainText("CRC-PE 012345/O");

  await page.emulateMedia({ media: "screen" });
  await switcher.getByRole("link", { name: "DRE" }).click();
  await page.emulateMedia({ media: "print" });
  await expect(page.getByTestId("print-dre")).toBeHidden();
  await expect(page.getByTestId("report-signatures")).toBeVisible();
  await expect(page.getByTestId("report-signatures")).toContainText("Sócia Fictícia da Alfa");
});

test("empresa sem signatários avisa na DRE e o admin chega ao cadastro pelo aviso", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("login-button").click();
  await page.locator("#username").fill("admin");
  await page.locator("#password").fill("dev-only-password");
  await page.locator("#kc-login").click();
  await page.waitForURL("**/app/rastro");

  await page.getByTestId("profile-link").click();
  await expect(page.getByRole("heading", { name: "Perfil" })).toBeVisible();
  await expect(page.getByTestId("profile-current")).toContainText("Contador, CRC-PE 023456/O");

  await chooseCompany(page, "Empresa Beta");
  await choosePeriod(page, "12/2026");
  await page.locator(".sidebar").getByRole("link", { name: "Relatórios" }).click();
  await page.getByRole("navigation", { name: "Relatórios" }).getByRole("link", { name: "DRE" }).click();
  const missing = page.getByTestId("signatures-missing");
  await expect(missing).toContainText("Aviso:");
  await expect(page.getByTestId("report-signatures")).toContainText("Responsável técnico não cadastrado");

  await page.emulateMedia({ media: "print" });
  await expect(missing).toBeHidden();
  await expect(page.getByTestId("report-signatures")).toBeVisible();
  await page.emulateMedia({ media: "screen" });

  await missing.getByRole("link", { name: "Definir as assinaturas da empresa" }).click();
  await expect(page.getByRole("heading", { name: "Assinaturas das demonstrações" })).toBeVisible();
  await expect(page.getByTestId("signatories-accountant")).toContainText("Aprovador — CRC-PE 012345/O");
});
