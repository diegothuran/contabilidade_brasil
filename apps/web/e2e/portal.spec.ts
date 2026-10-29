import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
import { chooseCompany, choosePeriod } from "./company";

// Cada usuário entra num contexto novo, sem os cookies do Keycloak do usuário anterior.
async function login(browser: Browser, username: string): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto("/");
  await page.getByTestId("login-button").click();
  await page.locator("#username").fill(username);
  await page.locator("#password").fill("dev-only-password");
  await page.locator("#kc-login").click();
  await page.waitForURL("**/app/rastro");
  return { context, page };
}

async function openOfficeRequests(browser: Browser, username: string, period: string | null) {
  const session = await login(browser, username);
  const { page } = session;
  await chooseCompany(page, "Empresa Alfa");
  if (period) {
    await choosePeriod(page, period);
  }
  await page.locator(".sidebar").getByRole("link", { name: "Pendências", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Pendências", exact: true })).toBeVisible();
  return session;
}

async function openPortal(browser: Browser) {
  const session = await login(browser, "cliente");
  await expect(session.page.getByRole("heading", { name: "Empresa Alfa" })).toBeVisible();
  return session;
}

function inSevenDays(): string {
  const due = new Date();
  due.setDate(due.getDate() + 7);
  const month = String(due.getMonth() + 1).padStart(2, "0");
  const day = String(due.getDate()).padStart(2, "0");
  return `${due.getFullYear()}-${month}-${day}`;
}

function pdf(label: string) {
  // O conteúdo muda a cada execução: o armazenamento reaproveita documento com o mesmo hash.
  return { name: "e2e.pdf", mimeType: "application/pdf", buffer: Buffer.from(`%PDF-1.4 e2e ${label}`) };
}

test("cliente envia, escritório devolve e confirma o pedido", async ({ browser }) => {
  const stamp = Date.now();
  const title = `E2E portal ${stamp}`;
  const reason = "Arquivo ilegível, envie de novo.";

  // 1. O preparador pede o documento na competência que a barra escolher.
  const preparer = await openOfficeRequests(browser, "preparer", null);
  const periodSelect = preparer.page.getByTestId("context-period");
  await expect(periodSelect).not.toHaveValue("");
  const period = (await periodSelect.locator("option:checked").textContent())?.trim() ?? "";
  expect(period).toMatch(/^\d{2}\/\d{4}$/);
  await preparer.page.getByLabel("Título", { exact: true }).fill(title);
  await preparer.page.getByLabel("Prazo", { exact: true }).fill(inSevenDays());
  await preparer.page.getByRole("button", { name: "Pedir documento" }).click();
  const preparerRow = preparer.page.getByRole("row").filter({ hasText: title });
  await expect(preparerRow).toContainText("Pedido aberto");
  await preparer.context.close();

  // 2. O cliente envia o arquivo e escreve na conversa.
  let client = await openPortal(browser);
  let clientRow = client.page.getByRole("row").filter({ hasText: title });
  await expect(clientRow).toContainText("Pedido aberto");
  await clientRow.getByLabel(`Arquivo de ${title}`, { exact: true }).setInputFiles(pdf(`${stamp} primeiro`));
  await clientRow.getByRole("button", { name: "Enviar arquivo" }).click();
  await expect(clientRow).toContainText("Arquivo recebido");
  await clientRow.getByRole("button", { name: "Abrir pedido" }).click();
  await client.page.getByLabel("Mensagem do pedido").fill("Segue o arquivo.");
  await client.page.getByRole("button", { name: "Enviar mensagem" }).click();
  await expect(client.page.getByRole("listitem").filter({ hasText: "Segue o arquivo." })).toContainText("Cliente");
  await client.context.close();

  // 3. O aprovador lê a mensagem e devolve o arquivo ao cliente.
  let approver = await openOfficeRequests(browser, "approver", period);
  let approverRow = approver.page.getByRole("row").filter({ hasText: title });
  await expect(approverRow).toContainText("Arquivo recebido");
  await approverRow.getByRole("button", { name: "Ver arquivos" }).click();
  await expect(approver.page.getByRole("listitem").filter({ hasText: "Segue o arquivo." })).toContainText("Cliente");
  await approver.page.getByLabel("Motivo da devolução").fill(reason);
  await approver.page.getByRole("button", { name: "Devolver ao cliente" }).click();
  await expect(approver.page.getByRole("listitem").filter({ hasText: "e2e.pdf" })).toContainText(`devolvido. ${reason}`);
  await approver.context.close();

  // 4. O cliente vê a devolução com o motivo e envia outro arquivo.
  client = await openPortal(browser);
  clientRow = client.page.getByRole("row").filter({ hasText: title });
  await expect(clientRow).toContainText("Pedido aberto");
  await clientRow.getByRole("button", { name: "Abrir pedido" }).click();
  await expect(client.page.getByRole("listitem").filter({ hasText: "e2e.pdf" })).toContainText(`devolvido. ${reason}`);
  await clientRow.getByLabel(`Arquivo de ${title}`, { exact: true }).setInputFiles(pdf(`${stamp} segundo`));
  await clientRow.getByRole("button", { name: "Enviar arquivo" }).click();
  await expect(clientRow).toContainText("Arquivo recebido");
  await client.context.close();

  // 5. O aprovador confirma o pedido.
  approver = await openOfficeRequests(browser, "approver", period);
  approverRow = approver.page.getByRole("row").filter({ hasText: title });
  await expect(approverRow).toContainText("Arquivo recebido");
  await approverRow.getByRole("button", { name: "Confirmar" }).click();
  await expect(approverRow).toContainText("Confirmado");
  await approver.context.close();

  // 6. O cliente encontra o pedido no histórico.
  client = await openPortal(browser);
  await client.page.getByRole("button", { name: "Histórico" }).click();
  await expect(client.page.getByRole("heading", { name: "Histórico" })).toBeVisible();
  await expect(client.page.getByRole("row").filter({ hasText: title })).toContainText("Pedido confirmado");
  await client.context.close();
});
