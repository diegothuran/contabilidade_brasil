import { expect, type Page } from "@playwright/test";

export async function chooseCompany(page: Page, name: string): Promise<void> {
  const search = page.getByTestId("company-search");
  await search.fill(name);
  await page.getByRole("option", { name: new RegExp(name) }).first().click();
  await expect(page.getByTestId("current-company")).toContainText(name);
}
