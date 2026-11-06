import { defineConfig, devices } from "@playwright/test";

// O visual-refresh usa OIDC e API fictícios num Vite dedicado (docs/design-motion/VERIFICACAO.md).
// Contra o compose ele nunca entra; com RASTRO_VISUAL=1 roda sozinho.
const visual = process.env.RASTRO_VISUAL === "1";

export default defineConfig({
  testDir: "./e2e",
  ...(visual ? { testMatch: "visual-refresh.spec.ts" } : { testIgnore: "visual-refresh.spec.ts" }),
  timeout: 120_000,
  expect: { timeout: 15_000 },
  // Os specs dividem a Empresa Alfa e o mesmo compose; na CI rodam um de cada vez.
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    ...devices["Desktop Chrome"],
    ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH ? { launchOptions: { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH } } : {}),
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:5173",
    trace: process.env.CI ? "retain-on-failure" : "on-first-retry",
  },
});
