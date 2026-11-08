import { expect, test } from "@playwright/test";
import { chooseCompany, choosePeriod } from "./company";

test("a prévia da ECD da Empresa Alfa sai marcada e lista o que falta", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("login-button").click();
  await page.locator("#username").fill("preparer");
  await page.locator("#password").fill("dev-only-password");
  await page.locator("#kc-login").click();
  await page.waitForURL("**/app/rastro");
  await chooseCompany(page, "Empresa Alfa");
  await choosePeriod(page, "12/2026");

  await page.locator(".sidebar").getByRole("link", { name: "Relatórios" }).click();
  await page.getByTestId("link-ecd").click();
  await expect(page.getByRole("heading", { name: "Prévia da ECD" })).toBeVisible();
  await expect(page.getByTestId("ecd-notice")).toHaveText("Prévia para conferência no PVA. Não transmitir.");
  // O preparador lê os dados da escrituração, mas só o admin altera.
  await expect(page.getByTestId("ecd-registration").locator("fieldset")).toBeDisabled();

  const generate = page.getByTestId("ecd-generate");
  await expect(generate.getByRole("combobox")).toHaveValue("2026");
  await generate.getByRole("button", { name: "Gerar prévia" }).click();
  const issues = page.getByTestId("ecd-issues");
  await expect(issues).toBeVisible({ timeout: 30_000 });
  await expect(issues).toContainText("Preencha os dados da escrituração");
  await expect(issues).toContainText("Fora da prévia");
  await expect(issues.getByRole("link", { name: "Preencher os dados da escrituração" })).toBeVisible();

  const download = page.waitForEvent("download");
  await page.getByTestId("ecd-download").click();
  expect((await download).suggestedFilename()).toMatch(/^ECD-PREVIA-\d{14}-2026\.txt$/);
});
