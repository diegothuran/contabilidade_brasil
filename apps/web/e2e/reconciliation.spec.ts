import { expect, test } from "@playwright/test";
import { chooseCompany } from "./company";

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

test("envia um OFX e o aprovador concilia o caso sugerido", async ({ page }) => {
  const memo = `Recebimento ${Date.now()}`;
  const ofx = [
    "OFXHEADER:100",
    "DATA:OFXSGML",
    "VERSION:102",
    "SECURITY:NONE",
    "ENCODING:USASCII",
    "CHARSET:1252",
    "COMPRESSION:NONE",
    "OLDFILEUID:NONE",
    "NEWFILEUID:NONE",
    "",
    "<OFX>",
    "<STMTTRN>",
    "<TRNTYPE>CREDIT",
    "<DTPOSTED>20260115",
    "<TRNAMT>18.00",
    `<FITID>e2e-${Date.now()}`,
    `<MEMO>${memo}`,
    "</STMTTRN>",
    "</OFX>",
    "",
  ].join("\n");

  await login(page, "preparer");
  await chooseCompany(page, "Empresa Alfa");
  await page.getByRole("link", { name: "Novo lançamento" }).click();
  await page.getByTestId("period-select").selectOption({ label: "le_alfa-2026-01" });
  await page.getByTestId("entry-date").fill("2026-01-15");
  await page.getByTestId("journal-description").fill(memo);
  await page.getByTestId("line-account-0").selectOption({ label: "1.1.01 Caixa" });
  await page.getByTestId("line-side-0").selectOption("debit");
  await page.getByTestId("line-amount-0").fill("18.00");
  await page.getByTestId("line-account-1").selectOption({ label: "4.1.01 Receita de serviços" });
  await page.getByTestId("line-side-1").selectOption("credit");
  await page.getByTestId("line-amount-1").fill("18.00");
  await page.getByTestId("save-journal").click();
  await page.getByTestId("submit-journal").click();
  await expect(page.getByTestId("journal-status")).toHaveText("Pendente");
  await page.getByRole("button", { name: "Sair" }).click();
  await expect(page.getByTestId("login-button")).toBeVisible();

  await login(page, "approver");
  await chooseCompany(page, "Empresa Alfa");
  await page.getByRole("link", { name: memo }).click();
  await page.getByTestId("approve-journal").click();
  await page.getByTestId("publish-journal").click();
  await expect(page.getByTestId("journal-status")).toHaveText("Publicado");
  await page.getByRole("button", { name: "Sair" }).click();
  await expect(page.getByTestId("login-button")).toBeVisible();

  await login(page, "preparer");
  await chooseCompany(page, "Empresa Alfa");
  await page.getByRole("link", { name: "Bancos" }).click();
  if ((await page.getByRole("cell", { name: "Caixa e2e" }).count()) === 0) {
    await page.getByTestId("bank-ledger-account").selectOption({ label: "1.1.01 Caixa" });
    await page.getByTestId("bank-name").fill("Caixa e2e");
    await page.getByTestId("bank-code").fill("001");
    await page.getByTestId("bank-branch").fill("0001");
    await page.getByTestId("bank-last4").fill("4321");
    await page.getByTestId("save-bank-account").click();
    await expect(page.getByRole("cell", { name: "Caixa e2e" })).toBeVisible();
  }
  await page.getByRole("link", { name: "Conciliação" }).click();
  await page.getByTestId("bank-account-select").selectOption({ label: "Caixa e2e · 4321" });
  await page.getByTestId("statement-file").setInputFiles({
    name: "extrato.ofx",
    mimeType: "application/x-ofx",
    buffer: Buffer.from(ofx),
  });
  await page.getByTestId("import-statement").click();
  const card = page.getByTestId("reconciliation-case").filter({ hasText: memo });
  await expect(card.getByTestId("case-status")).toHaveText("Sugerido", { timeout: 30_000 });
  await page.getByRole("button", { name: "Sair" }).click();
  await expect(page.getByTestId("login-button")).toBeVisible();

  await login(page, "approver");
  await chooseCompany(page, "Empresa Alfa");
  await page.getByRole("link", { name: "Conciliação" }).click();
  await page.getByTestId("bank-account-select").selectOption({ label: "Caixa e2e · 4321" });
  const suggested = page.getByTestId("reconciliation-case").filter({ hasText: memo });
  await suggested.getByTestId("approve-case").click();
  await expect(suggested.getByTestId("case-status")).toHaveText("Aprovado");
});
