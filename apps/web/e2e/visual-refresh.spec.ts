import { expect, test, type Page } from "@playwright/test";

const PREVIEW = process.env.RASTRO_VISUAL_OUTPUT ?? "test-results/visual-refresh";
const USER_KEY = "oidc.user:http://synthetic.invalid:rastro-visual";
const officeEntity = {
  legal_entity_id: "entity-orbe",
  name: "Orbe Serviços Digitais Ltda.",
  cnpj: "12345678000195",
  currency: "BRL",
};

const officeMe = {
  user_id: "user-preparer",
  display_name: "Marina Rocha",
  tenant_id: "tenant-sintetico",
  tenant_name: "Escritório Horizonte (sintético)",
  roles: ["preparer", "approver", "admin", "viewer"],
};

const portalMe = {
  user_id: "user-client",
  display_name: "Cliente Orbe",
  tenant_id: "tenant-sintetico",
  tenant_name: "Escritório Horizonte (sintético)",
  roles: ["client"],
  legal_entity_id: officeEntity.legal_entity_id,
  legal_entity_name: officeEntity.name,
  legal_entity_cnpj: officeEntity.cnpj,
};

function seedUser(page: Page, me: typeof officeMe | typeof portalMe): Promise<void> {
  return page.addInitScript(({ key, profile }) => {
    sessionStorage.setItem(key, JSON.stringify({
      id_token: "synthetic-id-token",
      session_state: null,
      access_token: "synthetic-access-token",
      refresh_token: null,
      token_type: "Bearer",
      scope: "openid profile email",
      profile,
      expires_at: Math.floor(Date.now() / 1000) + 3600,
    }));
  }, {
    key: USER_KEY,
    profile: { sub: me.user_id, ...me },
  });
}

async function json(route: Parameters<Parameters<Page["route"]>[1]>[0], payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(payload),
  });
}

async function installOfficeApi(page: Page): Promise<void> {
  await page.route("**/*googleapis.com/**", (route) => route.abort());
  await page.route("**/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (path === "/v1/me") return json(route, officeMe);
    if (path === "/v1/legal-entities") return json(route, { items: [officeEntity] });
    if (path === "/v1/legal-entities/entity-orbe/periods") {
      return json(route, { items: [{ period_id: "period-2026-02", fiscal_year: 2026, month: 2, status: "open" }] });
    }
    if (path === "/v1/journals") {
      return json(route, { items: [{ journal_id: "journal-1", description: "Serviços de fevereiro", entry_date: "2026-02-05", status: "published" }] });
    }
    if (path === "/v1/document-requests/queue") return json(route, { items: [] });
    if (path === "/v1/client-submissions") return json(route, { items: [] });
    if (path === "/v1/legal-entities/entity-orbe/trial-balance") {
      return json(route, {
        rows: [
          { account_id: "account-cash", code: "1.1.01", name: "Caixa", opening_balance: "0", debit: "1234.50", credit: "0", balance: "1234.50", closing_balance: "1234.50" },
          { account_id: "account-supplier", code: "2.1.01", name: "Fornecedores", opening_balance: "0", debit: "0", credit: "1234.50", balance: "-1234.50", closing_balance: "-1234.50" },
          { account_id: "account-zero", code: "3.1.01", name: "Conta sem movimento", opening_balance: "0", debit: "0", credit: "0", balance: "0", closing_balance: "0" },
        ],
        debit_total: "1234.50",
        credit_total: "1234.50",
      });
    }
    if (path === "/v1/accounts/account-cash/lines") {
      return json(route, {
        code: "1.1.01",
        name: "Caixa",
        opening_balance: "0",
        lines: [{ journal_id: "journal-1", line_id: "line-1", entry_date: "2026-02-05", side: "debit", amount: "1234.50", description: "Serviços de fevereiro", journal_status: "published" }],
      });
    }
    return json(route, {});
  });
}

async function installPortalApi(page: Page): Promise<void> {
  await page.route("**/*googleapis.com/**", (route) => route.abort());
  await page.route("**/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/v1/me") return json(route, portalMe);
    if (path === "/v1/portal/preferences") return json(route, { notify_client: true });
    if (path === "/v1/portal/document-requests") {
      return json(route, {
        items: [{
          document_request_id: "request-1",
          title: "Extrato bancário sintético",
          due_on: "2026-02-18",
          period: "02/2026",
          status: "open",
          document_id: null,
          file_name: null,
          blocks_close: true,
          cancel_reason: null,
          received_at: null,
          confirmed_at: null,
        }],
        next_cursor: null,
        summary: { open: 1, received: 0, overdue: 0, next_due_on: "2026-02-18" },
      });
    }
    if (path.startsWith("/v1/portal/document-requests/request-1")) {
      return json(route, { document_request_id: "request-1", title: "Extrato bancário sintético", files: [], comments: [] });
    }
    return json(route, {});
  });
}

test.describe("renovação visual Rastro v0.7.0", () => {
  test("desktop e mobile mantêm a casca, tokens e estados legíveis", async ({ page }) => {
    await seedUser(page, officeMe);
    await installOfficeApi(page);
    await page.goto("/app/rastro");
    await expect(page.getByRole("heading", { name: "O que precisa de atenção neste escritório." })).toBeVisible();
    await expect(page.locator(".rastro")).toHaveCSS("background-color", "rgb(245, 248, 251)");
    await expect(page.locator("button").first()).toHaveCSS("font-family", /Inter|system-ui/);
    await expect(page.getByRole("cell", { name: "Carregando pendências…" })).toHaveCount(0);
    await expect(page.locator(".sidebar-close")).toBeHidden();
    const lastSidebarControl = page.locator(".sidebar").locator("button:visible, a:visible, input:visible, select:visible").last();
    await lastSidebarControl.focus();
    await lastSidebarControl.press("Tab");
    expect(await page.evaluate(() => Boolean(document.activeElement?.closest(".sidebar")))).toBe(false);
    await page.screenshot({ path: `${PREVIEW}/office-desktop.png`, fullPage: true });

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/app/rastro");
    await expect(page.locator(".page-container")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false);
    await page.screenshot({ path: `${PREVIEW}/office-mobile.png`, fullPage: true });
  });

  test("sidebar e painel respeitam foco, Escape e reduced-motion", async ({ page }) => {
    await seedUser(page, officeMe);
    await installOfficeApi(page);
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/app/rastro/demonstracao");

    const menu = page.getByRole("button", { name: "Abrir navegação" });
    await menu.focus();
    await menu.press("Enter");
    await expect(page.locator(".sidebar")).toHaveClass(/sidebar--open/);
    await expect(page.locator(".sidebar-close")).toBeFocused();
    await page.keyboard.press("Shift+Tab");
    expect(await page.evaluate(() => Boolean(document.activeElement?.closest(".sidebar")))).toBe(true);
    await page.keyboard.press("Tab");
    await expect(page.locator(".sidebar-close")).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(page.locator(".sidebar")).not.toHaveClass(/sidebar--open/);
    await expect(menu).toBeFocused();

    const evidence = page.getByRole("button", { name: "Evidência" }).first();
    await evidence.focus();
    await evidence.press("Enter");
    const drawer = page.getByRole("dialog", { name: "Rastreabilidade do objeto" });
    await expect(drawer).toBeVisible();
    await expect(page.getByRole("button", { name: "Fechar painel" })).toBeFocused();
    await expect(drawer).toHaveCSS("animation-name", "none");
    await page.keyboard.press("Escape");
    await expect(drawer).toBeHidden();
    await expect(evidence).toBeFocused();
  });

  test("balancete preserva precisão, D/C e scroll estático com movimento reduzido", async ({ page }) => {
    await seedUser(page, officeMe);
    await installOfficeApi(page);
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/app/rastro/balancete");
    await expect(page.getByTestId("balance-difference")).toContainText("Débitos e créditos fecham");
    await expect(page.getByRole("cell", { name: "1.234,50 D" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "1.234,50 C" })).toBeVisible();

    await page.evaluate(() => {
      const original = HTMLElement.prototype.scrollIntoView;
      (window as Window & { __rastroScrollBehavior?: string; __rastroOriginalScroll?: typeof original }).__rastroOriginalScroll = original;
      HTMLElement.prototype.scrollIntoView = function scrollIntoView(options?: ScrollIntoViewOptions) {
        (window as Window & { __rastroScrollBehavior?: string }).__rastroScrollBehavior = options?.behavior ?? "auto";
      };
    });
    await page.getByRole("button", { name: /Ver o razão de 1\.1\.01 Caixa/ }).click();
    await expect(page.getByTestId("ledger-panel")).toBeVisible();
    expect(await page.evaluate(() => (window as Window & { __rastroScrollBehavior?: string }).__rastroScrollBehavior)).toBe("auto");
    await page.screenshot({ path: `${PREVIEW}/trial-balance-desktop.png`, fullPage: true });
  });

  test("portal tem acabamento Rastro sem menu, contexto ou vocabulário de escritório", async ({ page }) => {
    await seedUser(page, portalMe);
    await installPortalApi(page);
    await page.goto("/app/rastro");
    await expect(page.getByRole("heading", { name: "Orbe Serviços Digitais Ltda." })).toBeVisible();
    await expect(page.locator(".sidebar")).toHaveCount(0);
    await expect(page.getByTestId("context-period")).toHaveCount(0);
    await expect(page.getByText("Esta tela não mostra lançamentos.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Sair" })).toBeVisible();
    await expect(page.getByRole("row", { name: /Extrato bancário sintético/ })).toContainText("Pedido aberto");
    await page.screenshot({ path: `${PREVIEW}/portal-desktop.png`, fullPage: true });

    await page.setViewportSize({ width: 390, height: 844 });
    await page.reload();
    await expect(page.locator(".portal-page")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false);
    await page.screenshot({ path: `${PREVIEW}/portal-mobile.png`, fullPage: true });
  });
});
