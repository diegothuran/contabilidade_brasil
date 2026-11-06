import { defineConfig, devices } from "@playwright/test";

// Esta suíte testa acabamento com API/sessão fictícias. Não usa compose, Keycloak ou piloto.
export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/visual-refresh.spec.ts",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  workers: 1,
  reporter: process.env.CI ? [["list"], ["html", { open: "never", outputFolder: "playwright-report-visual" }]] : "list",
  use: {
    ...devices["Desktop Chrome"],
    ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH ? { launchOptions: { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH } } : {}),
    baseURL: "http://127.0.0.1:5174",
    trace: process.env.CI ? "retain-on-failure" : "on-first-retry",
  },
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 5174 --strictPort",
    url: "http://127.0.0.1:5174",
    reuseExistingServer: false,
    timeout: 60_000,
    env: {
      VITE_OIDC_AUTHORITY: "http://synthetic.invalid",
      VITE_OIDC_CLIENT_ID: "rastro-visual",
      VITE_OIDC_USE_ID_TOKEN: "0",
      VITE_API_URL: "",
      VITE_RASTRO_DEMO: "true",
    },
  },
});
